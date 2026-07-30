from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers as drf_serializers

from .models import Proposal, Vote
from .notifications import notify_proposal_event
from .permissions import (
    CanApproveProposal,
    CanCreateProposal,
    CanModifyProposal,
    CanViewProposal,
    CanVoteProposal,
    CanWithdrawProposal,
)
from .serializers import (
    ProposalDetailSerializer,
    ProposalListSerializer,
)
from .throttles import FeedbackAnonThrottle


def transition_overdue_proposals():
    """自愈式自动结束投票：把已到截止时间的活动申报流转到待审批。

    在 list/get/vote 等入口调用。用「逐行条件更新」保证每条申报只被一个请求流转，
    从而不会重复通知（并发安全；Django 无内置调度，此惰性方式无需 cron）。
    """
    now = timezone.now()
    overdue = (
        Proposal.objects.filter(
            proposal_type="activity", status="voting", voting_end_at__lte=now
        ).select_related("creator")
    )
    transitioned = []
    for proposal in overdue:
        # 仅当仍为 voting 时才翻转；并发请求里只有一个能成功（行级原子）
        changed = Proposal.objects.filter(pk=proposal.pk, status="voting").update(
            status="pending_approval", updated_at=now
        )
        if changed:
            transitioned.append(proposal)
    # 通知社长：投票结束（仅活动有创建人时才通知）
    for proposal in transitioned:
        if proposal.creator_id is not None:
            notify_proposal_event(proposal, "voting_ended", actor=proposal.creator)


class ProposalViewSet(viewsets.ModelViewSet):
    """活动申报 / 意见反馈 CRUD + 投票 + 审批工作流"""

    queryset = Proposal.objects.select_related(
        "creator", "creator__profile",
        "reviewed_by", "reviewed_by__profile",
    ).prefetch_related(
        "votes", "votes__voter", "votes__voter__profile",
        "attachments", "attachments__uploaded_by",
    ).annotate(
        approve_count=Count("votes", filter=Q(votes__vote_choice="approve")),
        oppose_count=Count("votes", filter=Q(votes__vote_choice="oppose")),
        abstain_count=Count("votes", filter=Q(votes__vote_choice="abstain")),
        total_votes=Count("votes"),
    )

    filterset_fields = ["proposal_type", "status", "creator"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "updated_at", "voting_end_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return ProposalListSerializer
        return ProposalDetailSerializer

    def get_permissions(self):
        if self.action == "submit_feedback":
            return [AllowAny()]  # 反馈/举报：公开提交，无需登录
        if self.action == "create":
            return [IsAuthenticated(), CanCreateProposal()]  # 活动申报需登录
        if self.action in ("update", "partial_update", "destroy", "resubmit"):
            return [IsAuthenticated(), CanModifyProposal()]
        if self.action in ("approve", "return_proposal", "reject"):
            return [IsAuthenticated(), CanApproveProposal()]
        if self.action == "vote":
            return [IsAuthenticated(), CanVoteProposal()]
        if self.action == "withdraw":
            return [IsAuthenticated(), CanWithdrawProposal()]
        return [IsAuthenticated(), CanViewProposal()]

    def get_queryset(self):
        # 惰性流转逾期投票
        transition_overdue_proposals()
        qs = super().get_queryset()
        user = self.request.user
        # 反馈/举报仅有 view_feedback 权限者可见；其余成员只看得到活动申报
        if not user.is_authenticated or not user.has_perm("proposals.view_feedback"):
            qs = qs.filter(proposal_type="activity")
        return qs

    def perform_create(self, serializer):
        # 主创建接口仅用于活动申报（需登录）；反馈走公开 submit_feedback
        if serializer.validated_data.get("proposal_type") != "activity":
            raise drf_serializers.ValidationError({"proposal_type": "请使用反馈专用入口提交意见反馈"})
        proposal = serializer.save(creator=self.request.user)
        notify_proposal_event(proposal, "created_activity", actor=self.request.user)

    # ── 公开反馈提交（无需登录）──
    @action(detail=False, methods=["post"], url_path="submit_feedback",
            throttle_classes=[FeedbackAnonThrottle])
    def submit_feedback(self, request):
        """意见反馈/举报：可匿名（默认）或署名（登录后显式选择）提交。

        - 匿名：``creator=None``（未登录只能走这条；登录用户选「匿名」也走这条），仅纯文字。
        - 署名：登录用户传 ``disclose_identity=True``，记录 ``creator``、对社长可见，方可附媒体。
          媒体天然携带上传者身份，与匿名互斥。
        """
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        data["proposal_type"] = "feedback"
        disclose_identity = bool(data.pop("disclose_identity", False))
        if disclose_identity and not request.user.is_authenticated:
            return Response(
                {"detail": "署名提交需要登录"}, status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ProposalDetailSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        creator = request.user if (disclose_identity and request.user.is_authenticated) else None
        proposal = serializer.save(creator=creator)  # create() 设 status=pending_approval
        # 反馈无站内通信通知（社长在列表中查看新反馈）
        return Response(
            ProposalDetailSerializer(proposal, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    # ── 投票（仅活动申报）──
    @action(detail=True, methods=["post"])
    def vote(self, request, pk=None):
        proposal = self.get_object()
        if proposal.proposal_type != "activity":
            return Response({"detail": "仅活动申报可以投票"}, status=status.HTTP_400_BAD_REQUEST)
        if proposal.status != "voting":
            return Response({"detail": "投票已结束"}, status=status.HTTP_400_BAD_REQUEST)
        vote_choice = request.data.get("vote_choice")
        if vote_choice not in ("approve", "oppose", "abstain"):
            return Response({"detail": "无效的投票选项"}, status=status.HTTP_400_BAD_REQUEST)
        vote, created = Vote.objects.get_or_create(
            proposal=proposal, voter=request.user, defaults={"vote_choice": vote_choice}
        )
        if not created:
            return Response({"detail": "你已经投过票了，不能修改"}, status=status.HTTP_400_BAD_REQUEST)
        proposal = self.get_queryset().get(pk=proposal.pk)
        return Response(ProposalDetailSerializer(proposal, context={"request": request}).data)

    # ── 社长审批 ──
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        proposal = self.get_object()
        if proposal.status != "pending_approval":
            return Response({"detail": "当前状态不可通过"}, status=status.HTTP_400_BAD_REQUEST)
        proposal.status = "approved"
        proposal.reject_reason = ""
        proposal.reviewed_by = request.user
        proposal.reviewed_at = timezone.now()
        proposal.approved_at = timezone.now()
        proposal.save(update_fields=["status", "reject_reason", "reviewed_by", "reviewed_at", "approved_at", "updated_at"])
        if proposal.creator_id is not None:
            notify_proposal_event(proposal, "approved", actor=request.user)
        return Response(ProposalDetailSerializer(proposal, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="return_proposal")
    def return_proposal(self, request, pk=None):
        """打回（可编辑后重新提交）"""
        proposal = self.get_object()
        # 反馈是单向投递箱（跟进走线下）：不可打回，社长仅通过/拒绝。
        if proposal.proposal_type == "feedback":
            return Response({"detail": "反馈不可打回，请使用通过或拒绝"}, status=status.HTTP_400_BAD_REQUEST)
        if proposal.status != "pending_approval":
            return Response({"detail": "当前状态不可打回"}, status=status.HTTP_400_BAD_REQUEST)
        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response({"detail": "请填写打回理由"}, status=status.HTTP_400_BAD_REQUEST)
        proposal.status = "returned"
        proposal.reject_reason = reason
        proposal.reviewed_by = request.user
        proposal.reviewed_at = timezone.now()
        proposal.save(update_fields=["status", "reject_reason", "reviewed_by", "reviewed_at", "updated_at"])
        if proposal.creator_id is not None:
            notify_proposal_event(proposal, "returned", actor=request.user, reason=reason)
        return Response(ProposalDetailSerializer(proposal, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        proposal = self.get_object()
        if proposal.status != "pending_approval":
            return Response({"detail": "当前状态不可拒绝"}, status=status.HTTP_400_BAD_REQUEST)
        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response({"detail": "请填写拒绝理由"}, status=status.HTTP_400_BAD_REQUEST)
        proposal.status = "rejected"
        proposal.reject_reason = reason
        proposal.reviewed_by = request.user
        proposal.reviewed_at = timezone.now()
        proposal.save(update_fields=["status", "reject_reason", "reviewed_by", "reviewed_at", "updated_at"])
        if proposal.creator_id is not None:
            notify_proposal_event(proposal, "rejected", actor=request.user, reason=reason)
        return Response(ProposalDetailSerializer(proposal, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def resubmit(self, request, pk=None):
        """打回后重新提交：活动重开 3 天投票并清空旧票；反馈回到待审批"""
        proposal = self.get_object()
        # CanModifyProposal 已校验 status=returned 且 creator/社长
        if proposal.proposal_type == "activity":
            proposal.voting_end_at = timezone.now() + timedelta(days=3)
            proposal.status = "voting"
            proposal.votes.all().delete()
        else:
            proposal.status = "pending_approval"
        proposal.reject_reason = ""
        proposal.save(update_fields=["voting_end_at", "status", "reject_reason", "updated_at"])
        if proposal.creator_id is not None:
            notify_proposal_event(proposal, "resubmitted", actor=request.user)
        proposal = self.get_queryset().get(pk=proposal.pk)
        return Response(ProposalDetailSerializer(proposal, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        """创建人撤回（投票中/待审批）"""
        proposal = self.get_object()
        proposal.status = "withdrawn"
        proposal.save(update_fields=["status", "updated_at"])
        if proposal.creator_id is not None:
            notify_proposal_event(proposal, "withdrawn", actor=request.user)
        return Response(ProposalDetailSerializer(proposal, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def my_proposals(self, request):
        """当前用户创建的申报（活动申报；反馈为匿名，无归属）"""
        user = request.user
        qs = Proposal.objects.filter(creator=user).select_related("creator").prefetch_related("votes", "attachments")
        qs = self.filter_queryset(qs)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ProposalListSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = ProposalListSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)


# 旧的按申报内嵌的上传/删除动作已移除：上传/删除统一走独立 /attachments/ 端点
# （见 attachments app），附件列表随申报详情返回。

