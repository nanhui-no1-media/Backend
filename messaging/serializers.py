from rest_framework import serializers

from tasks.serializers import SimpleUserSerializer
from .models import Conversation, Message, MessageReadStatus


class MessageSerializer(serializers.ModelSerializer):
    sender = SimpleUserSerializer(read_only=True)
    mentions = SimpleUserSerializer(many=True, read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id", "conversation", "sender", "content",
            "mentions", "is_read", "created_at", "updated_at",
        ]
        read_only_fields = ["sender", "mentions", "created_at", "updated_at"]

    def get_is_read(self, obj):
        user = self.context["request"].user
        return obj.read_statuses.filter(user=user).exists()


class ConversationSerializer(serializers.ModelSerializer):
    participants = SimpleUserSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id", "conversation_type", "task", "proposal", "title",
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
        user = self.context["request"].user
        return obj.messages.exclude(read_statuses__user=user).count()
