"""活动视图集（ADR 0007）。

T1：创建（已验证成员）+ 列表/详情（成员可读）+ 正文图片上传。
T2：众议投票（自定义选项、K 选、一人一张不可改、到点惰性结算、公开计票）。
征集投稿/复审在 T4–T5 增补。
"""
import os
import uuid
from datetime import timedelta

from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsVerified

from attachments.models import Attachment
from attachments.validation import classify_file_type, upload_error
from reviews.lifecycle import open_review
from reviews.visibility import public_activity_q

from .debt import annotate_activity_debt
from .lifecycle import (
    CLOSED,
    COLLECTING,
    OPEN,
    REVIEWING,
    SCHEDULED,
    can_curate,
    can_edit,
    can_edit_exhibit,
    can_rate,
    can_submit,
    can_vote,
    collection_close_target,
    maybe_close_collection_on_cap,
    maybe_close_deliberation_on_full_vote,
    transition_due_starts,
    transition_overdue,
)
from .models import (
    Activity, Ballot, BallotSelection, Exhibit, ExhibitRating, Submission, VoteOption,
)
from .permissions import (
    CanCreateActivity,
    CanModifyActivity,
    CanReviewSubmission,
    CanViewActivity,
)
from .serializers import ActivityDetailSerializer, ActivityListSerializer

# 正文内嵌图片上限（与新闻一致）
_CONTENT_IMAGE_MAX_SIZE = 5 * 1024 * 1024
_CONTENT_IMAGE_TYPES = ("image/jpeg", "image/png", "image/gif", "image/webp")


def _content_image_path(filename):
    ext = os.path.splitext(filename)[1]
    return f"activity_content_images/{uuid.uuid4().hex}{ext}"


def _parse_extensions(raw):
    """允许后缀配置串 → 集合：".jpg, .png" → {".jpg", ".png"}；空串 → 空集（=不限）。"""
    if not raw:
        return set()
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


class ActivityViewSet(viewsets.ModelViewSet):
    """活动（众议/征集）：已验证成员可发起与投票；成员可读。"""

    filterset_fields = ["type", "status", "creator"]
    search_fields = ["title", "body"]
    ordering_fields = ["created_at", "updated_at", "end_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # 惰性流转：到 start_at 的待开始活动自动开放；到 end_at 的众议/展示自动结算。
        # 审核轴只门控可见性，不阻断上述状态机。
        transition_due_starts()
        transition_overdue()
        qs = Activity.objects.select_related(
            "creator", "creator__profile", "publication_review",
        ).prefetch_related(
            "options", "options__selections",
            "ballots", "ballots__selections", "ballots__voter__profile",
            "submissions", "submissions__attachments", "submissions__submitter__profile",
            "submissions__reviewed_by",
            "exhibits", "exhibits__attachments",
            "exhibits__vote_option", "exhibits__vote_option__selections",
            "exhibits__ratings",
        )
        public = qs.filter(public_activity_q())
        user = self.request.user
        if self.action == "list":
            return annotate_activity_debt(public, user)
        if self.action == "mine" and user.is_authenticated:
            return qs.filter(creator=user)
        if user.is_authenticated:
            if user.has_perm("reviews.moderate"):
                return qs
            return (public | qs.filter(creator=user)).distinct()
        return public

    def get_serializer_class(self):
        if self.action == "list":
            return ActivityListSerializer
        if self.action == "mine":
            return ActivityListSerializer
        return ActivityDetailSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), CanCreateActivity(), IsVerified()]
        if self.action == "mine":
            return [IsAuthenticated()]
        if self.action == "vote":
            return [IsAuthenticated(), IsVerified()]
        if self.action == "submit":
            return [IsAuthenticated(), IsVerified()]
        if self.action == "rate":
            return [IsAuthenticated(), IsVerified()]
        if self.action == "review_submission":
            # 复审：发起人 OR 持 review_collection 权限（对象级）
            return [IsAuthenticated(), CanReviewSubmission()]
        if self.action == "close":
            # 提前关闭：发起人，或持 change_activity 权限者（对象级）
            return [IsAuthenticated(), CanModifyActivity()]
        if self.action in ("add_exhibit", "update_exhibit", "delete_exhibit", "import_from_collection"):
            return [IsAuthenticated(), CanModifyActivity()]
        if self.action == "upload_image":
            # 正文插图：能发起活动的已验证成员即可（与创建同门禁）
            return [IsAuthenticated(), IsVerified()]
        if self.action in ("update", "partial_update", "destroy"):
            return [IsAuthenticated(), CanModifyActivity()]
        return [IsAuthenticated(), CanViewActivity()]  # list / retrieve

    def perform_create(self, serializer):
        activity = serializer.save(creator=self.request.user)
        open_review(activity=activity, actor=self.request.user)

    @action(detail=False, methods=["get"])
    def mine(self, request):
        """作者预览：当前用户发起的全部活动（含待审/驳回/下架）。"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = ActivityListSerializer(page or queryset, many=True, context={"request": request})
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        # 展示:展品在详情页布展(待开始期),创建只收标量——0 展品可建,走 JSON 通用路径。
        return super().create(request, *args, **kwargs)

    def _build_exhibit(self, activity, title, files, voting_enabled):
        """建一个展品 + 一束附件;启用投票时另建一个 VoteOption 并绑定。

        供 add_exhibit / import_from_collection 复用。
        files 已经过 upload_error 校验(调用方负责)。
        """
        option = None
        if voting_enabled:
            order = activity.options.count()
            option = VoteOption.objects.create(activity=activity, text=title or "", order=order)
        exhibit = Exhibit.objects.create(activity=activity, title=title, vote_option=option)
        for f in files:
            Attachment.objects.create(
                uploaded_by=self.request.user, exhibit=exhibit, file=f,
                file_type=classify_file_type(f.content_type),
                file_name=f.name, file_size=f.size,
            )
        return exhibit

    def perform_update(self, serializer):
        # 仅待开始（scheduled）期间可改；开放后锁定（要改只能删重建）。
        # get_object 已先跑 transition_due_starts，故到点自动开放后此处即拦下。
        if not can_edit(serializer.instance):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("活动开放后不可修改，仅待开始期间可改")
        super().perform_update(serializer)

    # ── 众议投票 ──
    @action(detail=True, methods=["post"])
    def vote(self, request, pk=None):
        activity = self.get_object()  # 触发惰性结算（若已到点则已 closed）
        # 守卫（类型∈{众议,展示}、展示须 voting_enabled、状态=open、已认证）统一走
        # lifecycle.can_vote，与 rate/submit 同模式——单一事实源。
        if not can_vote(activity, request.user):
            # can_vote 已排除未认证（IsVerified 另把关）与非众议/展示类型；此处仅可能是
            # 展示未启用投票（纯陈列）或状态非 open。
            if activity.type == "exhibition" and not activity.voting_enabled:
                return Response({"detail": "该展示未启用投票"}, status=status.HTTP_400_BAD_REQUEST)
            if activity.status != OPEN:
                return Response({"detail": "投票已结束"}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": "仅众议/展示可以投票"}, status=status.HTTP_400_BAD_REQUEST)
        if Ballot.objects.filter(activity=activity, voter=request.user).exists():
            return Response({"detail": "你已经投过票了，不能修改"}, status=status.HTTP_400_BAD_REQUEST)

        option_ids = request.data.get("option_ids") or []
        if not isinstance(option_ids, list) or len(option_ids) < 1:
            return Response({"detail": "请至少选择一个选项"}, status=status.HTTP_400_BAD_REQUEST)
        if len(set(option_ids)) != len(option_ids):
            return Response({"detail": "不能重复选择同一选项"}, status=status.HTTP_400_BAD_REQUEST)
        if len(option_ids) > activity.max_choices_per_voter:
            return Response(
                {"detail": f"最多选择 {activity.max_choices_per_voter} 项"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        valid_ids = set(activity.options.values_list("id", flat=True))
        try:
            ids = [int(x) for x in option_ids]
        except (TypeError, ValueError):
            return Response({"detail": "无效的选项"}, status=status.HTTP_400_BAD_REQUEST)
        if not set(ids).issubset(valid_ids):
            return Response({"detail": "存在不属于本活动的选项"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            ballot = Ballot.objects.create(activity=activity, voter=request.user)
            BallotSelection.objects.bulk_create(
                [BallotSelection(ballot=ballot, option_id=oid) for oid in ids]
            )
            maybe_close_deliberation_on_full_vote(activity)  # 全员投完即提前结算

        activity = self.get_queryset().get(pk=activity.pk)  # 刷新聚合计数
        return Response(ActivityDetailSerializer(activity, context={"request": request}).data)

    # ── 征集投稿（一次性多文件、提交即锁定、一人一作品）──
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        activity = self.get_object()
        if activity.type != "collection":
            return Response({"detail": "仅征集可以投稿"}, status=status.HTTP_400_BAD_REQUEST)
        if activity.status != COLLECTING:
            return Response({"detail": "征集已结束收件"}, status=status.HTTP_400_BAD_REQUEST)
        if Submission.objects.filter(activity=activity, submitter=request.user).exists():
            return Response({"detail": "你已经提交过作品了（一人一作品）"}, status=status.HTTP_400_BAD_REQUEST)

        files = request.FILES.getlist("files")
        if not files:
            return Response({"detail": "请至少上传一个文件"}, status=status.HTTP_400_BAD_REQUEST)
        if len(files) > activity.max_files_per_submission:
            return Response(
                {"detail": f"单个作品最多 {activity.max_files_per_submission} 个文件"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed = _parse_extensions(activity.allowed_extensions)
        for f in files:
            err = upload_error(f)  # 全局禁用扩展名 + 同步上传上限
            if err:
                return Response({"detail": err}, status=status.HTTP_400_BAD_REQUEST)
            if activity.max_file_size and f.size > activity.max_file_size:
                return Response(
                    {"detail": f"文件「{f.name}」超过征集规定的单文件大小上限"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if allowed:
                ext = os.path.splitext(f.name)[1].lower()
                if ext not in allowed:
                    return Response(
                        {"detail": f"文件「{f.name}」的后缀不在允许范围"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        with transaction.atomic():
            submission = Submission.objects.create(activity=activity, submitter=request.user)
            for f in files:
                Attachment.objects.create(
                    uploaded_by=request.user,
                    submission=submission,
                    file=f,
                    file_type=classify_file_type(f.content_type),
                    file_name=f.name,
                    file_size=f.size,
                )
            maybe_close_collection_on_cap(activity)  # 满额自动 collecting→reviewing

        activity = self.get_queryset().get(pk=activity.pk)
        return Response(
            ActivityDetailSerializer(activity, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    # ── 征集复审（录用/退稿；collecting 与 reviewing 阶段均可滚动复审）──
    @action(detail=True, methods=["post"], url_path="review_submission")
    def review_submission(self, request, pk=None):
        activity = self.get_object()
        if activity.type != "collection":
            return Response({"detail": "仅征集作品可复审"}, status=status.HTTP_400_BAD_REQUEST)
        if not activity.review_enabled:
            return Response({"detail": "本征集未启用复审"}, status=status.HTTP_400_BAD_REQUEST)
        if activity.status not in (COLLECTING, REVIEWING):
            return Response({"detail": "当前不可复审"}, status=status.HTTP_400_BAD_REQUEST)
        decision = request.data.get("decision")
        if decision not in ("accepted", "rejected"):
            return Response(
                {"detail": "decision 须为 accepted 或 rejected"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        comment = (request.data.get("comment") or "").strip()
        try:
            submission = activity.submissions.get(pk=request.data.get("submission_id"))
        except (Submission.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "作品不存在"}, status=status.HTTP_404_NOT_FOUND)
        submission.review_status = decision
        submission.review_comment = comment
        submission.reviewed_by = request.user
        submission.reviewed_at = timezone.now()
        submission.save(update_fields=[
            "review_status", "review_comment", "reviewed_by", "reviewed_at",
        ])
        activity = self.get_queryset().get(pk=activity.pk)
        return Response(ActivityDetailSerializer(activity, context={"request": request}).data)

    # ── 提前关闭（众议立即结算 / 征集结束收件进入复审）──
    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        activity = self.get_object()
        now = timezone.now()
        if activity.type == "deliberation":
            if activity.status != OPEN:
                return Response({"detail": "当前不可关闭"}, status=status.HTTP_400_BAD_REQUEST)
            Activity.objects.filter(pk=activity.pk, status=OPEN).update(
                status=CLOSED, updated_at=now,
            )
        elif activity.type == "collection":
            if activity.status != COLLECTING:
                return Response({"detail": "当前不可关闭"}, status=status.HTTP_400_BAD_REQUEST)
            Activity.objects.filter(pk=activity.pk, status=COLLECTING).update(
                status=collection_close_target(activity), updated_at=now,
            )
        elif activity.type == "exhibition":
            if activity.status != OPEN:
                return Response({"detail": "当前不可关闭"}, status=status.HTTP_400_BAD_REQUEST)
            Activity.objects.filter(pk=activity.pk, status=OPEN).update(
                status=CLOSED, updated_at=now,
            )
        else:
            return Response({"detail": "不支持"}, status=status.HTTP_400_BAD_REQUEST)
        activity = self.get_queryset().get(pk=activity.pk)
        return Response(ActivityDetailSerializer(activity, context={"request": request}).data)

    # ── 展示:详情页布展(待开始/展示中加/删/导入;改标题限待开始)──
    @action(detail=True, methods=["post"], url_path="add_exhibit")
    def add_exhibit(self, request, pk=None):
        activity = self.get_object()
        if not can_curate(activity, request.user):
            return Response({"detail": "仅展示可在待开始/展示中加展品"}, status=status.HTTP_400_BAD_REQUEST)
        files = request.FILES.getlist("files")
        if not files:
            return Response({"detail": "展品至少需要 1 个文件"}, status=status.HTTP_400_BAD_REQUEST)
        for f in files:
            err = upload_error(f)
            if err:
                return Response({"detail": err}, status=status.HTTP_400_BAD_REQUEST)
        title = (request.data.get("title") or "").strip()
        with transaction.atomic():
            self._build_exhibit(activity, title, files, activity.voting_enabled)
        activity = self.get_queryset().get(pk=activity.pk)
        return Response(ActivityDetailSerializer(activity, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="delete_exhibit")
    def delete_exhibit(self, request, pk=None):
        activity = self.get_object()
        if not can_curate(activity, request.user):
            return Response({"detail": "仅展示可在待开始/展示中删展品"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            exhibit = activity.exhibits.get(pk=request.data.get("exhibit_id"))
        except (Exhibit.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "展品不存在"}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            if exhibit.vote_option_id:
                VoteOption.objects.filter(pk=exhibit.vote_option_id).delete()
            exhibit.delete()  # 连带删附件(CASCADE)+ 回收文件(post_delete 信号)
        activity = self.get_queryset().get(pk=activity.pk)
        return Response(ActivityDetailSerializer(activity, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="update_exhibit")
    def update_exhibit(self, request, pk=None):
        activity = self.get_object()
        if not can_edit_exhibit(activity, request.user):
            return Response({"detail": "仅展示可在待开始期改展品"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            exhibit = activity.exhibits.get(pk=request.data.get("exhibit_id"))
        except (Exhibit.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "展品不存在"}, status=status.HTTP_404_NOT_FOUND)
        files = request.FILES.getlist("files")
        for f in files:
            err = upload_error(f)
            if err:
                return Response({"detail": err}, status=status.HTTP_400_BAD_REQUEST)
        title = request.data.get("title")
        with transaction.atomic():
            if title is not None:
                exhibit.title = title.strip()
                if exhibit.vote_option_id:
                    VoteOption.objects.filter(pk=exhibit.vote_option_id).update(text=exhibit.title)
            if files:
                exhibit.attachments.all().delete()  # 旧文件回收(CASCADE + post_delete 信号)
                for f in files:
                    Attachment.objects.create(
                        uploaded_by=request.user, exhibit=exhibit, file=f,
                        file_type=classify_file_type(f.content_type),
                        file_name=f.name, file_size=f.size,
                    )
            if title is not None:
                exhibit.save(update_fields=["title"])
        activity = self.get_queryset().get(pk=activity.pk)
        return Response(ActivityDetailSerializer(activity, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="import_from_collection")
    def import_from_collection(self, request, pk=None):
        from django.core.files.base import ContentFile

        activity = self.get_object()
        if not can_curate(activity, request.user):
            return Response({"detail": "仅展示可在待开始/展示中导入展品"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            source = Activity.objects.get(pk=request.data.get("collection_id"), type="collection")
        except (Activity.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "征集不存在"}, status=status.HTTP_404_NOT_FOUND)
        submission_ids = request.data.get("submission_ids") or []
        subs = source.submissions.filter(pk__in=submission_ids)
        if not subs:
            return Response({"detail": "未选择任何作品"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            for sub in subs:
                exhibit = self._build_exhibit(activity, "", [], activity.voting_enabled)
                for a in sub.attachments.all():
                    new_att = Attachment(
                        uploaded_by=request.user, exhibit=exhibit,
                        file_type=a.file_type, file_name=a.file_name, file_size=a.file_size,
                    )
                    new_att.file.save(a.file.name, ContentFile(a.file.read()))
                    # file.save(save=True) 已持久化 Attachment 行,无需再 save()
        activity = self.get_queryset().get(pk=activity.pk)
        return Response(ActivityDetailSerializer(activity, context={"request": request}).data)

    # ── 展示：点赞 / 点踩（三态切换：none/like/dislike）──
    @action(detail=True, methods=["post"], url_path="rate")
    def rate(self, request, pk=None):
        activity = self.get_object()
        # 守卫（类型=展示、状态=open）统一走 lifecycle.can_rate，与 vote/submit 同模式
        if not can_rate(activity, request.user):
            return Response({"detail": "当前不可评分（展示未开放或已结束）"}, status=status.HTTP_400_BAD_REQUEST)
        choice = request.data.get("choice")
        if choice not in ("like", "dislike"):
            return Response({"detail": "choice 须为 like 或 dislike"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            exhibit = activity.exhibits.get(pk=request.data.get("exhibit_id"))
        except (Exhibit.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "展品不存在"}, status=status.HTTP_404_NOT_FOUND)
        existing = ExhibitRating.objects.filter(exhibit=exhibit, user=request.user).first()
        if existing and existing.choice == choice:
            existing.delete()  # 再点当前态 → none
        elif existing:
            existing.choice = choice
            existing.save(update_fields=["choice"])
        else:
            ExhibitRating.objects.create(exhibit=exhibit, user=request.user, choice=choice)
        activity = self.get_queryset().get(pk=activity.pk)
        return Response(ActivityDetailSerializer(activity, context={"request": request}).data)

    @action(detail=False, methods=["post"], url_path="upload_image")
    def upload_image(self, request):
        """正文内嵌图片上传（已验证成员）：返回 {url}。供编辑器「插入图片」与 Word 导入共用。"""
        file = request.FILES.get("image")
        if not file:
            return Response({"detail": "请选择图片。"}, status=status.HTTP_400_BAD_REQUEST)
        if file.size > _CONTENT_IMAGE_MAX_SIZE:
            return Response({"detail": "图片不能超过 5MB。"}, status=status.HTTP_400_BAD_REQUEST)
        if file.content_type not in _CONTENT_IMAGE_TYPES:
            return Response(
                {"detail": "仅支持 JPG、PNG、GIF、WebP 格式。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        path = default_storage.save(_content_image_path(file.name), file)
        return Response({"url": request.build_absolute_uri(default_storage.url(path))})
