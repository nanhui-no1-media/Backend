"""统一附件端点：POST /attachments/（上传）、DELETE /attachments/{id}/（删除）。"""
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from proposals.models import Proposal
from tasks.models import Task

from .models import Attachment
from .permissions import can_manage_parent_attachments, can_upload_to_parent
from .serializers import AttachmentSerializer
from .validation import classify_file_type, feedback_quota_error, upload_error


class AttachmentViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """统一附件：仅提供创建（上传）与删除；列表随父级详情返回。"""

    queryset = Attachment.objects.select_related("uploaded_by", "task", "proposal")
    serializer_class = AttachmentSerializer
    permission_classes = [IsAuthenticated]

    # ── 上传：POST /attachments/ ──
    def create(self, request, *args, **kwargs):
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"detail": "请选择文件"}, status=status.HTTP_400_BAD_REQUEST,
            )

        err = upload_error(file)
        if err:
            return Response({"detail": err}, status=status.HTTP_400_BAD_REQUEST)
        file_type = classify_file_type(file.content_type)

        task_id = request.data.get("task_id")
        proposal_id = request.data.get("proposal_id")
        has_task = task_id not in (None, "")
        has_proposal = proposal_id not in (None, "")
        if has_task == has_proposal:  # 同时传或都不传
            return Response(
                {"detail": "必须且只能指定一个父级（task_id 或 proposal_id）"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            parent = Task.objects.get(pk=task_id) if has_task else Proposal.objects.get(pk=proposal_id)
        except (Task.DoesNotExist, Proposal.DoesNotExist, ValueError, TypeError):
            return Response(
                {"detail": "指定的父级不存在"}, status=status.HTTP_404_NOT_FOUND,
            )

        if not can_upload_to_parent(request.user, parent):
            return Response(
                {"detail": "无权操作此父级的附件"}, status=status.HTTP_403_FORBIDDEN,
            )

        # 反馈附件配额（仅反馈父级；同步 / tus 共用的校验收在 validation）
        quota_err = feedback_quota_error(parent, file.size)
        if quota_err:
            return Response({"detail": quota_err}, status=status.HTTP_400_BAD_REQUEST)

        attachment = Attachment.objects.create(
            uploaded_by=request.user,
            task=parent if isinstance(parent, Task) else None,
            proposal=parent if isinstance(parent, Proposal) else None,
            file=file,
            file_type=file_type,
            file_name=file.name,
            file_size=file.size,
        )
        return Response(
            AttachmentSerializer(attachment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    # ── 删除：DELETE /attachments/{id}/ ──
    def destroy(self, request, *args, **kwargs):
        attachment = self.get_object()
        parent = attachment.task or attachment.proposal
        # 统一规则；此外附件上传者始终可删自己上传的（用户故事 #12）。
        allowed = (
            can_manage_parent_attachments(request.user, parent)
            or attachment.uploaded_by_id == request.user.pk
        )
        if not allowed:
            return Response(
                {"detail": "无权删除此附件"}, status=status.HTTP_403_FORBIDDEN,
            )
        attachment.delete()  # post_delete 信号回收磁盘文件
        return Response(status=status.HTTP_204_NO_CONTENT)
