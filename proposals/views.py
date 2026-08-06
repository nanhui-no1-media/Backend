from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .notifications import notify_proposal_event
from .models import Proposal
from .permissions import (
    CanApproveProposal,
    CanCreateProposal,
    CanModifyProposal,
    CanViewProposal,
    CanWithdrawProposal,
)
from .serializers import (
    ProposalDetailSerializer,
    ProposalListSerializer,
)
from .throttles import FeedbackAnonThrottle
from accounts.permissions import IsVerified


class ProposalViewSet(viewsets.ModelViewSet):
    """意见反馈 / 举报 CRUD + 审批工作流（活动已分离至 activities app，ADR 0007）。"""

    queryset = Proposal.objects.select_related(
        "creator", "creator__profile",
        "reviewed_by", "reviewed_by__profile",
    ).prefetch_related(
        "attachments", "attachments__uploaded_by",
    )

    filterset_fields = ["proposal_type", "status", "creator"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return ProposalListSerializer
        return ProposalDetailSerializer

    # 身份门槛：建申报 / 撤回需身份已验证。submit_feedback 故意保留 AllowAny
    #（匿名意见反馈 / 举报通道，需保护举报人）。
    _VERIFIED_GATED = {"create", "withdraw"}

    def get_permissions(self):
        if self.action == "submit_feedback":
            return [AllowAny()]  # 反馈/举报：公开提交，无需登录
        perms = (
            [IsAuthenticated(), CanCreateProposal()] if self.action == "create"
            else [IsAuthenticated(), CanModifyProposal()] if self.action in ("update", "partial_update", "destroy")
            else [IsAuthenticated(), CanApproveProposal()] if self.action in ("approve", "reject")
            else [IsAuthenticated(), CanWithdrawProposal()] if self.action == "withdraw"
            else [IsAuthenticated(), CanViewProposal()]
        )
        if self.action in self._VERIFIED_GATED:
            perms.append(IsVerified())
        return perms

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        # 反馈可见性：持 view_feedback 者(社长)见全部；普通成员只见自己提交的反馈。
        if user.has_perm("proposals.view_feedback"):
            return qs
        return qs.filter(creator=user)

    def perform_create(self, serializer):
        proposal = serializer.save(creator=self.request.user)
        notify_proposal_event(proposal, "created_feedback", actor=self.request.user)

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
        return Response(
            ProposalDetailSerializer(proposal, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

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
    def withdraw(self, request, pk=None):
        """创建人撤回（待审批阶段）"""
        proposal = self.get_object()
        proposal.status = "withdrawn"
        proposal.save(update_fields=["status", "updated_at"])
        if proposal.creator_id is not None:
            notify_proposal_event(proposal, "withdrawn", actor=request.user)
        return Response(ProposalDetailSerializer(proposal, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def my_proposals(self, request):
        """当前用户创建的反馈（匿名反馈无归属，不在此列）"""
        user = request.user
        qs = Proposal.objects.filter(creator=user).select_related("creator").prefetch_related("attachments")
        qs = self.filter_queryset(qs)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ProposalListSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = ProposalListSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)


# 旧的按申报内嵌的上传/删除动作已移除：上传/删除统一走独立 /attachments/ 端点
# （见 attachments app），附件列表随申报详情返回。
