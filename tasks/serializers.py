from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from attachments.serializers import AttachmentSerializer

from .lifecycle import available_actions, status_for_assignee
from .models import Tag, Task, TaskClaimRequest


class SimpleUserSerializer(serializers.ModelSerializer):
    nickname = serializers.CharField(source="profile.nickname", default="")
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "nickname", "avatar"]

    def get_avatar(self, obj):
        profile = getattr(obj, "profile", None)
        if profile and profile.avatar:
            return profile.avatar.url
        return None


class TagSerializer(serializers.ModelSerializer):
    task_count = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = ["id", "name", "color", "task_count"]

    def get_task_count(self, obj):
        return obj.tasks.count()


class TaskClaimRequestSerializer(serializers.ModelSerializer):
    claimant = SimpleUserSerializer(read_only=True)
    reviewed_by = SimpleUserSerializer(read_only=True)

    class Meta:
        model = TaskClaimRequest
        fields = [
            "id", "task", "claimant", "status",
            "reason", "reviewed_by", "reviewed_at", "created_at",
        ]
        read_only_fields = ["claimant", "status", "reviewed_by", "reviewed_at", "created_at"]


class TaskListSerializer(serializers.ModelSerializer):
    creator = SimpleUserSerializer(read_only=True)
    assignee = SimpleUserSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    attachment_count = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id", "title", "status", "priority",
            "creator", "assignee", "tags",
            "completed_at",
            "reject_reason",
            "attachment_count",
            "created_at", "updated_at",
        ]

    def get_attachment_count(self, obj):
        return obj.attachments.count()


class TaskDetailSerializer(serializers.ModelSerializer):
    creator = SimpleUserSerializer(read_only=True)
    assignee = SimpleUserSerializer(read_only=True)
    collaborators = SimpleUserSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    claim_requests = TaskClaimRequestSerializer(many=True, read_only=True)
    available_actions = serializers.SerializerMethodField()

    assignee_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True, write_only=True,
        source="assignee",
    )
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False, write_only=True,
        source="tags",
    )
    collaborator_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), many=True, required=False, write_only=True,
        source="collaborators",
    )

    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "status", "priority",
            "creator", "assignee", "assignee_id",
            "collaborators", "collaborator_ids",
            "tags", "tag_ids",
            "attachments", "claim_requests", "available_actions",
            "completed_at",
            "reject_reason",
            "created_at", "updated_at",
        ]
        read_only_fields = ["creator", "status", "completed_at", "reject_reason", "created_at", "updated_at"]

    def get_available_actions(self, task):
        """当前查看者可对该任务执行的动作（来自生命周期模块）。列表序列化不带此字段。"""
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return []
        return available_actions(task, user)

    def create(self, validated_data):
        tags = validated_data.pop("tags", [])
        collaborators = validated_data.pop("collaborators", [])
        # 负责人↔状态联动委托生命周期模块（与指派动作共用一处判定）。
        validated_data["status"] = status_for_assignee(validated_data.get("assignee"))
        task = Task.objects.create(**validated_data)
        if tags:
            task.tags.set(tags)
        if collaborators:
            task.collaborators.set(collaborators)
        return task

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        collaborators = validated_data.pop("collaborators", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        if collaborators is not None:
            instance.collaborators.set(collaborators)
        return instance
