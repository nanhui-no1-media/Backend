from rest_framework import permissions


class IsConversationParticipant(permissions.BasePermission):
    """只有对话参与者可以查看/发送消息"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        if hasattr(obj, "participants"):
            return obj.participants.filter(pk=user.pk).exists()
        if hasattr(obj, "conversation"):
            return obj.conversation.participants.filter(pk=user.pk).exists()
        return False
