from rest_framework import serializers

from tasks.serializers import SimpleUserSerializer  # 复用现有用户序列化器

from .models import Attachment


class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = SimpleUserSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = [
            "id", "file_url", "file_type", "file_name",
            "file_size", "uploaded_by", "uploaded_at",
        ]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and hasattr(obj.file, "url"):
            url = obj.file.url
            return request.build_absolute_uri(url) if request else url
        return None
