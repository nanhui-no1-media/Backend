from rest_framework import serializers

from attachments.serializers import AttachmentSerializer
from tasks.serializers import SimpleUserSerializer

from .models import Feedback, ReportCase, ReportFiling, Review
from .report_lifecycle import target_id_of, target_type_of


class ReviewSerializer(serializers.ModelSerializer):
    """审核队列条目：带目标类型/标题，供统一队列展示。"""

    reviewer = SimpleUserSerializer(read_only=True)
    target_type = serializers.SerializerMethodField()
    target_id = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id", "status", "comment", "reviewer", "reviewed_at",
            "target_type", "target_id", "title", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_target_type(self, obj):
        if obj.news_id:
            return "news"
        if obj.activity_id:
            return "activity"
        if obj.tutorial_id:
            return "tutorial"
        return None

    def get_target_id(self, obj):
        return obj.news_id or obj.activity_id or obj.tutorial_id

    def get_title(self, obj):
        if obj.news_id:
            return obj.news.title
        if obj.activity_id:
            return obj.activity.title
        if obj.tutorial_id:
            return obj.tutorial.title
        return ""


def _creator_repr(obj):
    if obj.creator_id is None:
        return None
    return SimpleUserSerializer(obj.creator).data


class FeedbackListSerializer(serializers.ModelSerializer):
    creator = serializers.SerializerMethodField()
    attachment_count = serializers.SerializerMethodField()

    class Meta:
        model = Feedback
        fields = [
            "id", "status", "title", "category", "contact",
            "creator", "close_note", "attachment_count",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_creator(self, obj):
        return _creator_repr(obj)

    def get_attachment_count(self, obj):
        return obj.attachments.count()


class FeedbackDetailSerializer(serializers.ModelSerializer):
    creator = serializers.SerializerMethodField()
    closed_by = SimpleUserSerializer(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Feedback
        fields = [
            "id", "status", "title", "description", "category", "contact",
            "creator", "closed_by", "closed_at", "close_note",
            "attachments", "created_at", "updated_at",
        ]
        read_only_fields = [
            "creator", "status", "closed_by", "closed_at", "close_note",
            "created_at", "updated_at",
        ]

    def get_creator(self, obj):
        return _creator_repr(obj)

    def validate_category(self, value):
        allowed = {c[0] for c in Feedback.CATEGORY_CHOICES}
        if value not in allowed:
            raise serializers.ValidationError("类别须为建议、投诉或其他")
        return value

    def validate_description(self, value):
        return value or ""


class ReportFilingSerializer(serializers.ModelSerializer):
    reporter = SimpleUserSerializer(read_only=True)

    class Meta:
        model = ReportFiling
        fields = ["id", "reporter", "reason", "created_at"]
        read_only_fields = fields


class ReportCaseSerializer(serializers.ModelSerializer):
    resolved_by = SimpleUserSerializer(read_only=True)
    filings = ReportFilingSerializer(many=True, read_only=True)
    target_type = serializers.SerializerMethodField()
    target_id = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()

    class Meta:
        model = ReportCase
        fields = [
            "id", "status", "target_type", "target_id", "title",
            "resolved_by", "resolved_at", "resolution_comment",
            "filings", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_target_type(self, obj):
        return target_type_of(obj)

    def get_target_id(self, obj):
        return target_id_of(obj)

    def get_title(self, obj):
        if obj.news_id:
            return obj.news.title
        if obj.activity_id:
            return obj.activity.title
        if obj.tutorial_id:
            return obj.tutorial.title
        if obj.comment_id:
            text = (obj.comment.content or "").strip()
            return text[:80] + ("…" if len(text) > 80 else "")
        if obj.reported_user_id:
            return obj.reported_user.username
        return ""


class ReportCreateSerializer(serializers.Serializer):
    target_type = serializers.CharField()
    target_id = serializers.IntegerField()
    reason = serializers.CharField()
