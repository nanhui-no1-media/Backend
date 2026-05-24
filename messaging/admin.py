from django.contrib import admin

from .models import Conversation, Message, MessageReadStatus


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ["sender", "content", "created_at"]


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "conversation_type", "task", "title", "created_at", "updated_at"]
    list_filter = ["conversation_type"]
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "conversation", "sender", "content_preview", "created_at"]
    search_fields = ["content"]

    def content_preview(self, obj):
        return obj.content[:50]


@admin.register(MessageReadStatus)
class MessageReadStatusAdmin(admin.ModelAdmin):
    list_display = ["message", "user", "read_at"]
