from rest_framework import serializers

from tasks.serializers import SimpleUserSerializer

from .models import Review


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
