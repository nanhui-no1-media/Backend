from rest_framework import serializers

from .models import ExamData


class ExamDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamData
        fields = ["id", "exam_date", "exam_title", "exam_list", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_exam_title(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("请填写考试标题")
        if len(value) > 50:
            raise serializers.ValidationError("标题不能超过 50 字")
        return value

    def validate_exam_list(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("请填写科目列表")
        if len(value) > 255:
            raise serializers.ValidationError("科目列表过长")
        return value

    def validate_exam_date(self, value):
        if value is None:
            raise serializers.ValidationError("请填写考试日期")
        return value
