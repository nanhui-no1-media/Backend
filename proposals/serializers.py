from rest_framework import serializers

from attachments.serializers import AttachmentSerializer
from tasks.serializers import SimpleUserSerializer  # 复用

from .models import Proposal


def _creator_repr(obj):
    """反馈/举报无创建人（公开匿名提交）→ 返回 None；署名反馈返回创建人。"""
    if obj.creator_id is None:
        return None
    return SimpleUserSerializer(obj.creator).data


class ProposalListSerializer(serializers.ModelSerializer):
    creator = serializers.SerializerMethodField()
    attachment_count = serializers.SerializerMethodField()

    class Meta:
        model = Proposal
        fields = [
            "id", "proposal_type", "status", "title",
            "creator", "contact", "feedback_category",
            "reject_reason",
            "attachment_count",
            "created_at", "updated_at",
        ]

    def get_creator(self, obj):
        return _creator_repr(obj)

    def get_attachment_count(self, obj):
        return obj.attachments.count()


class ProposalDetailSerializer(serializers.ModelSerializer):
    creator = serializers.SerializerMethodField()
    reviewed_by = SimpleUserSerializer(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Proposal
        fields = [
            "id", "proposal_type", "status", "title", "description",
            "feedback_category", "contact",
            "creator", "reviewed_by", "reviewed_at", "approved_at",
            "attachments",
            "reject_reason",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "creator", "status", "reviewed_by", "reviewed_at", "approved_at",
            "reject_reason", "created_at", "updated_at",
        ]

    def validate_description(self, value):
        # 反馈为纯文本（与旧实现一致）；如需富文本，走活动(activities)正文。
        return value or ""

    def get_creator(self, obj):
        return _creator_repr(obj)

    def create(self, validated_data):
        validated_data["status"] = "pending_approval"
        return super().create(validated_data)
