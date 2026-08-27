from rest_framework import serializers

from tasks.serializers import SimpleUserSerializer
from .models import (
    Banner,
    Comment,
    CommentThread,
    Conversation,
    Message,
    Notification,
    UserMute,
    unread_message_count,
)
from .services import can_manage_thread


class MessageSerializer(serializers.ModelSerializer):
    sender = SimpleUserSerializer(read_only=True)
    mentions = SimpleUserSerializer(many=True, read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id", "conversation", "sender", "content",
            "mentions", "is_read", "retracted_at", "created_at", "updated_at",
        ]
        read_only_fields = ["sender", "mentions", "retracted_at", "created_at", "updated_at"]

    def get_is_read(self, obj):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        return obj.read_statuses.filter(user=request.user).exists()


class ConversationSerializer(serializers.ModelSerializer):
    participants = SimpleUserSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id", "title",
            "participants", "last_message", "unread_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_last_message(self, obj):
        msg = obj.messages.order_by("-created_at").first()
        if msg:
            return MessageSerializer(msg, context=self.context).data
        return None

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return 0
        return unread_message_count(request.user, obj)


class CommentThreadSerializer(serializers.ModelSerializer):
    can_manage = serializers.SerializerMethodField()

    class Meta:
        model = CommentThread
        fields = ["id", "status", "news", "activity", "task", "can_manage"]
        read_only_fields = ["news", "activity", "task"]

    def get_can_manage(self, obj):
        request = self.context.get("request")
        if request is None:
            return False
        return can_manage_thread(request.user, obj)


class CommentSerializer(serializers.ModelSerializer):
    author = SimpleUserSerializer(read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id", "thread", "author", "parent", "content",
            "retracted_at", "deleted_at", "created_at", "updated_at", "replies",
        ]
        read_only_fields = [
            "author", "retracted_at", "deleted_at", "created_at", "updated_at",
        ]

    def get_replies(self, obj):
        children_map = self.context.get("children_map")
        if children_map is None:
            return []
        children = children_map.get(obj.pk, [])
        return CommentSerializer(children, many=True, context=self.context).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.deleted_at:
            data["content"] = "该评论已删除"
        return data


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "category", "event", "payload", "read_at", "created_at"]
        read_only_fields = fields


class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = ["id", "body", "link", "starts_at", "ends_at", "priority"]
        read_only_fields = fields


class UserMuteSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserMute
        fields = ["id", "user", "muted_by", "reason", "starts_at", "ends_at", "lifted_at"]
        read_only_fields = fields
