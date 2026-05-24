import re

from django.contrib.auth.models import User
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tasks.models import Task
from tasks.permissions import is_president

from .models import Conversation, Message, MessageReadStatus
from .permissions import IsConversationParticipant
from .serializers import ConversationSerializer, MessageSerializer


class ConversationViewSet(viewsets.ModelViewSet):
    """会话管理"""
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated, IsConversationParticipant]
    filterset_fields = ["conversation_type", "task"]

    def get_queryset(self):
        return (
            Conversation.objects
            .filter(participants=self.request.user)
            .select_related("task")
            .prefetch_related("participants", "messages", "messages__sender")
        )

    @action(detail=True, methods=["post"])
    def send_message(self, request, pk=None):
        """发送消息"""
        conversation = self.get_object()
        content = request.data.get("content", "").strip()
        if not content:
            return Response({"detail": "消息内容不能为空"}, status=status.HTTP_400_BAD_REQUEST)

        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=content,
        )

        mentioned_usernames = re.findall(r"@(\w+)", content)
        if mentioned_usernames:
            mentioned_users = User.objects.filter(username__in=mentioned_usernames)
            message.mentions.set(mentioned_users)

        return Response(
            MessageSerializer(message, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        """标记会话中所有消息为已读"""
        conversation = self.get_object()
        unread = conversation.messages.exclude(read_statuses__user=request.user)
        for msg in unread:
            MessageReadStatus.objects.get_or_create(message=msg, user=request.user)
        return Response({"detail": "已标记为已读"})

    @action(detail=False, methods=["get"])
    def messages(self, request):
        """获取会话的消息列表（通过 conversation id 参数）"""
        conversation_id = request.query_params.get("conversation_id")
        if not conversation_id:
            return Response({"detail": "缺少 conversation_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            conversation = Conversation.objects.get(pk=conversation_id, participants=request.user)
        except Conversation.DoesNotExist:
            return Response({"detail": "会话不存在"}, status=status.HTTP_404_NOT_FOUND)

        messages = conversation.messages.select_related("sender").prefetch_related("mentions").order_by("created_at")
        return Response(MessageSerializer(messages, many=True, context={"request": request}).data)

    @action(detail=False, methods=["post"])
    def start_private(self, request):
        """发起私人对话"""
        target_id = request.data.get("user_id")
        if not target_id:
            return Response({"detail": "缺少 user_id"}, status=status.HTTP_400_BAD_REQUEST)
        if int(target_id) == request.user.pk:
            return Response({"detail": "不能和自己对话"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            target = User.objects.get(pk=target_id)
        except User.DoesNotExist:
            return Response({"detail": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)

        # 查找已有的私人对话
        existing = (
            Conversation.objects
            .filter(conversation_type="private", participants=request.user)
            .filter(participants=target)
            .first()
        )
        if existing:
            return Response(ConversationSerializer(existing, context={"request": request}).data)

        conversation = Conversation.objects.create(conversation_type="private")
        conversation.participants.set([request.user, target])
        return Response(
            ConversationSerializer(conversation, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"])
    def get_task_conversation(self, request):
        """获取或创建任务讨论会话"""
        task_id = request.data.get("task_id")
        if not task_id:
            return Response({"detail": "缺少 task_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            task = Task.objects.get(pk=task_id)
        except Task.DoesNotExist:
            return Response({"detail": "任务不存在"}, status=status.HTTP_404_NOT_FOUND)

        # 检查用户是否有权限查看此任务
        user = request.user
        if not is_president(user):
            if task.creator != user and task.assignee != user and not task.collaborators.filter(pk=user.pk).exists():
                return Response({"detail": "无权访问此任务"}, status=status.HTTP_403_FORBIDDEN)

        conversation, _ = Conversation.objects.get_or_create(
            conversation_type="task",
            task=task,
        )

        # 确保所有任务相关者都是参与者
        participant_ids = {task.creator_id}
        if task.assignee_id:
            participant_ids.add(task.assignee_id)
        for cid in task.collaborators.values_list("id", flat=True):
            participant_ids.add(cid)
        if is_president(user):
            participant_ids.add(user.pk)
        # 请求者也需要加入
        participant_ids.add(user.pk)

        conversation.participants.set(participant_ids)
        return Response(ConversationSerializer(conversation, context={"request": request}).data)
