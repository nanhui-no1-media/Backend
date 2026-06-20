import os
import re

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Attachment, Tag, Task, TaskClaimRequest
from .permissions import (
    CanAssignTask,
    CanCreateTask,
    CanManageTag,
    CanModifyTask,
    CanUploadAttachment,
    CanViewTask,
    is_president,
)
from .serializers import (
    AttachmentSerializer,
    SimpleUserSerializer,
    TagSerializer,
    TaskClaimRequestSerializer,
    TaskDetailSerializer,
    TaskListSerializer,
)


class TagViewSet(viewsets.ModelViewSet):
    """标签管理"""
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated, CanManageTag]
    search_fields = ["name"]


class TaskViewSet(viewsets.ModelViewSet):
    """任务 CRUD"""
    queryset = Task.objects.select_related(
        "creator", "assignee",
    ).prefetch_related("tags", "collaborators", "attachments", "claim_requests", "claim_requests__claimant")

    filterset_fields = ["status", "priority", "assignee", "creator"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "completed_at", "priority", "status"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return TaskListSerializer
        return TaskDetailSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), CanCreateTask()]
        if self.action in ("update", "partial_update", "destroy"):
            return [IsAuthenticated(), CanModifyTask()]
        if self.action == "assign":
            return [IsAuthenticated(), CanAssignTask()]
        if self.action in ("add_attachment", "delete_attachment"):
            return [IsAuthenticated(), CanUploadAttachment()]
        return [IsAuthenticated(), CanViewTask()]

    def get_queryset(self):
        return super().get_queryset()

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def perform_update(self, serializer):
        serializer.save()

    @action(detail=True, methods=["post"])
    def claim(self, request, pk=None):
        """申请认领任务"""
        task = self.get_object()
        if task.assignee:
            return Response({"detail": "任务已有负责人"}, status=status.HTTP_400_BAD_REQUEST)
        if task.status not in ("pending", "review"):
            return Response({"detail": "当前状态不可申请认领"}, status=status.HTTP_400_BAD_REQUEST)
        reason = request.data.get("reason", "").strip()
        claim, created = TaskClaimRequest.objects.get_or_create(
            task=task, claimant=request.user,
            defaults={"reason": reason},
        )
        if not created:
            return Response({"detail": "你已经申请过认领此任务"}, status=status.HTTP_400_BAD_REQUEST)
        # 第一个认领申请时自动流转到待审核
        if task.status == "pending":
            task.status = "review"
            task.save(update_fields=["status", "updated_at"])
        return Response(TaskClaimRequestSerializer(claim).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def approve_claim(self, request, pk=None):
        """批准认领请求"""
        task = self.get_object()
        if task.creator != request.user and not is_president(request.user):
            return Response({"detail": "只有创建者或社长可以审批"}, status=status.HTTP_403_FORBIDDEN)
        claim_id = request.data.get("claim_id")
        if not claim_id:
            return Response({"detail": "缺少 claim_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            claim = TaskClaimRequest.objects.get(pk=claim_id, task=task, status="pending")
        except TaskClaimRequest.DoesNotExist:
            return Response({"detail": "认领请求不存在或已处理"}, status=status.HTTP_404_NOT_FOUND)
        claim.status = "approved"
        claim.reviewed_by = request.user
        claim.reviewed_at = timezone.now()
        claim.save()
        task.assignee = claim.claimant
        task.status = "in_progress"
        task.save(update_fields=["assignee", "status", "updated_at"])
        # 刷新 prefetch 缓存
        task = self.get_queryset().get(pk=task.pk)
        return Response(TaskDetailSerializer(task, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def reject_claim(self, request, pk=None):
        """拒绝认领请求"""
        task = self.get_object()
        if task.creator != request.user and not is_president(request.user):
            return Response({"detail": "只有创建者或社长可以审批"}, status=status.HTTP_403_FORBIDDEN)
        claim_id = request.data.get("claim_id")
        if not claim_id:
            return Response({"detail": "缺少 claim_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            claim = TaskClaimRequest.objects.get(pk=claim_id, task=task, status="pending")
        except TaskClaimRequest.DoesNotExist:
            return Response({"detail": "认领请求不存在或已处理"}, status=status.HTTP_404_NOT_FOUND)
        claim.status = "rejected"
        claim.reviewed_by = request.user
        claim.reviewed_at = timezone.now()
        claim.save()
        if not TaskClaimRequest.objects.filter(task=task, status="pending").exists():
            if task.status == "review":
                task.status = "pending"
                task.save(update_fields=["status", "updated_at"])
        task = self.get_queryset().get(pk=task.pk)
        return Response(TaskDetailSerializer(task, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """提交验收：负责人/社长完成工作，任务进入待验收"""
        task = self.get_object()
        if task.status != "in_progress":
            return Response({"detail": "只有进行中的任务可以提交验收"}, status=status.HTTP_400_BAD_REQUEST)
        if task.assignee != request.user and not is_president(request.user):
            return Response({"detail": "只有负责人或社长可以提交验收"}, status=status.HTTP_403_FORBIDDEN)
        task.status = "reviewing"
        task.save(update_fields=["status", "updated_at"])
        return Response(TaskDetailSerializer(task, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def approve_completion(self, request, pk=None):
        """通过验收：发起人/社长确认，任务完成"""
        task = self.get_object()
        if task.creator != request.user and not is_president(request.user):
            return Response({"detail": "只有创建者或社长可以审批"}, status=status.HTTP_403_FORBIDDEN)
        if task.status != "reviewing":
            return Response({"detail": "只有待验收的任务可以审批"}, status=status.HTTP_400_BAD_REQUEST)
        task.status = "completed"
        task.completed_at = timezone.now()
        task.save(update_fields=["status", "completed_at", "updated_at"])
        return Response(TaskDetailSerializer(task, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """取消任务"""
        task = self.get_object()
        if task.status == "completed":
            return Response({"detail": "已完成的任务不能取消"}, status=status.HTTP_400_BAD_REQUEST)
        if task.creator != request.user and not is_president(request.user):
            return Response({"detail": "只有创建者或社长可以取消"}, status=status.HTTP_403_FORBIDDEN)
        task.status = "cancelled"
        task.save(update_fields=["status", "updated_at"])
        return Response(TaskDetailSerializer(task, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def add_attachment(self, request, pk=None):
        task = self.get_object()
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "请选择文件"}, status=status.HTTP_400_BAD_REQUEST)

        if file.size > 50 * 1024 * 1024:
            return Response({"detail": "文件大小不能超过 50MB"}, status=status.HTTP_400_BAD_REQUEST)

        ext = os.path.splitext(file.name)[1].lower()
        forbidden = {".exe", ".bat", ".cmd", ".sh", ".php", ".asp", ".jsp", ".py", ".rb", ".pl", ".cgi", ".com", ".scr", ".pif", ".msi"}
        if ext in forbidden:
            return Response({"detail": "禁止上传此类型的文件"}, status=status.HTTP_400_BAD_REQUEST)

        content_type = file.content_type or ""
        if content_type.startswith("image/"):
            file_type = "image"
        elif content_type.startswith("video/"):
            file_type = "video"
        elif content_type in (
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "text/plain",
        ):
            file_type = "document"
        elif content_type in (
            "application/zip",
            "application/x-rar-compressed",
            "application/x-7z-compressed",
            "application/gzip",
        ):
            file_type = "archive"
        else:
            file_type = "other"

        attachment = Attachment.objects.create(
            task=task,
            uploaded_by=request.user,
            file=file,
            file_type=file_type,
            file_name=file.name,
            file_size=file.size,
        )
        return Response(
            AttachmentSerializer(attachment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def delete_attachment(self, request, pk=None):
        task = self.get_object()
        attachment_id = request.data.get("attachment_id")
        if not attachment_id:
            return Response({"detail": "缺少 attachment_id"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            attachment = Attachment.objects.get(id=attachment_id, task=task)
        except Attachment.DoesNotExist:
            return Response({"detail": "附件不存在"}, status=status.HTTP_404_NOT_FOUND)

        can_delete = (
            attachment.uploaded_by == request.user
            or is_president(request.user)
            or task.creator == request.user
        )
        if not can_delete:
            return Response({"detail": "无权删除此附件"}, status=status.HTTP_403_FORBIDDEN)

        attachment.file.delete(save=False)
        attachment.delete()
        return Response({"detail": "附件已删除"})

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        """社长直接指派"""
        task = self.get_object()
        assignee_id = request.data.get("assignee_id")
        if assignee_id:
            try:
                assignee = User.objects.get(pk=assignee_id)
            except User.DoesNotExist:
                return Response({"detail": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)
            task.assignee = assignee
            task.status = "in_progress"
        else:
            task.assignee = None
            task.status = "pending"
        task.save(update_fields=["assignee", "status", "updated_at"])
        return Response(TaskDetailSerializer(task, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def my_tasks(self, request):
        """当前用户的任务"""
        user = request.user
        qs = Task.objects.filter(
            Q(creator=user) | Q(assignee=user) | Q(collaborators=user)
        ).select_related(
            "creator", "assignee",
        ).prefetch_related("tags").distinct()
        qs = self.filter_queryset(qs)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = TaskListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = TaskListSerializer(qs, many=True)
        return Response(serializer.data)


class AttachmentViewSet(viewsets.ReadOnlyModelViewSet):
    """附件列表"""
    queryset = Attachment.objects.select_related("uploaded_by", "task").all()
    serializer_class = AttachmentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["task", "file_type"]

    def get_queryset(self):
        return super().get_queryset()
