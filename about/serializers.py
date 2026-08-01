from rest_framework import serializers

from common.rich_text import sanitize_html

from .models import AboutPage


class AboutPageSerializer(serializers.ModelSerializer):
    """关于页序列化：updated_at 只读；content 写入时经 sanitize_html 清洗。"""

    class Meta:
        model = AboutPage
        fields = ["title", "content", "updated_at"]
        read_only_fields = ["updated_at"]

    def validate_content(self, value):
        return sanitize_html(value or "")
