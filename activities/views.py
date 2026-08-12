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
from attachments.validation import MAX_FILE_SIZE, classify_file_type, upload_error

from .lifecycle import (
    CLOSED,
    COLLECTING,
    OPEN,
    REVIEWING,
    SCHEDULED,
    can_edit,
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
        transition_due_starts()
        transition_overdue()
        return Activity.objects.select_related(
            "creator", "creator__profile",
        ).prefetch_related(
            "options", "options__selections",
            "ballots", "ballots__selections", "ballots__voter__profile",
            "submissions", "submissions__attachments", "submissions__submitter__profile",
            "submissions__reviewed_by",
            "exhibits", "exhibits__attachments",
            "exhibits__vote_option", "exhibits__vote_option__selections",
            "exhibits__ratings",
        )

    def get_serializer_class(self):
        if self.action == "list":
            return ActivityListSerializer
        return ActivityDetailSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), CanCreateActivity(), IsVerified()]
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
        serializer.save(creator=self.request.user)

    def create(self, request, *args, **kwargs):
        # 展示：展品在创建时录入（multipart：每展品一束文件），与 JSON 创建路径分流。
        if request.data.get("type") == "exhibition":
            return self._create_exhibition(request)
        return super().create(request, *args, **kwargs)

    def _build_exhibit(self, activity, title, files, voting_enabled):
        """建一个展品 + 一束附件;启用投票时另建一个 VoteOption 并绑定。

        供 _create_exhibition / add_exhibit / import_from_collection 复用。
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

    def _create_exhibition(self, request):
        data = request.data

        def _parse_int(v, default=0):
            try:
                return int(v)
            except (TypeError, ValueError):
                return default

        def _parse_bool(v):
            return str(v).strip().lower() in ("true", "1", "on", "yes")

        # 1) 先解析并校验展品——避免先建了活动又因展品不合规留下半成品。
        count = _parse_int(data.get("exhibit_count"), default=0)
        exhibits = []  # [(title, [files])]
        for i in range(count):
            title = (data.get(f"exhibit_title_{i}") or "").strip()
            files = request.FILES.getlist(f"exhibit_files_{i}")
            exhibits.append((title, files))
        if not exhibits:
            return Response({"detail": "展示至少需要 1 个展品"}, status=status.HTTP_400_BAD_REQUEST)
        for i, (title, files) in enumerate(exhibits):
            if not files:
                return Response(
                    {"detail": f"展品「{title or i + 1}」至少需要 1 个文件"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for f in files:
                err = upload_error(f)  # 全局禁用后缀 + 50MB
                if err:
                    return Response({"detail": err}, status=status.HTTP_400_BAD_REQUEST)

        # 2) K 值校验（每人最多投几个展品）——仅启用投票时校验；纯陈列不投票，K 无意义。
        voting_enabled = _parse_bool(data.get("voting_enabled"))
        k = _parse_int(data.get("max_choices_per_voter"), default=1)
        if voting_enabled and (k < 1 or k > len(exhibits)):
            return Response(
                {"detail": f"每人最多选几项须在 1..{len(exhibits)} 之间"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3) 标量字段过序列化器校验（正文消毒 / 开始<截止 / 默认截止）。
        scalar = {
            "type": "exhibition",
            "title": (data.get("title") or "").strip(),
            "body": data.get("body") or "",
            "start_at": data.get("start_at") or None,
            "end_at": data.get("end_at") or None,
            "max_choices_per_voter": k,
            "is_secret_ballot": _parse_bool(data.get("is_secret_ballot")),
            "voting_enabled": voting_enabled,
        }
        serializer = ActivityDetailSerializer(data=scalar, context={"request": request})
        serializer.is_valid(raise_exception=True)

        # 4) 原子建活动 + 每展品（启用投票时）一个投票选项 + 一束文件。
        with transaction.atomic():
            activity = serializer.save(creator=request.user)
            for title, files in exhibits:
                self._build_exhibit(activity, title, files, voting_enabled)
        activity = self.get_queryset().get(pk=activity.pk)  # 刷新预取
        headers = self.get_success_headers(serializer.data)
        return Response(
            ActivityDetailSerializer(activity, context={"request": request}).data,
            status=status.HTTP_201_CREATED, headers=headers,
        )

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
            err = upload_error(f)  # 全局禁用扩展名 + 50MB 同步上限
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

    # ── 展示:详情页布展(待开始期加/改/删/导入展品)──
    @action(detail=True, methods=["post"], url_path="add_exhibit")
    def add_exhibit(self, request, pk=None):
        activity = self.get_object()
        if activity.type != "exhibition":
            return Response({"detail": "仅展示可加展品"}, status=status.HTTP_400_BAD_REQUEST)
        if not can_edit(activity):
            return Response({"detail": "展示开放后不可改展品"}, status=status.HTTP_400_BAD_REQUEST)
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
