from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from attachments.serializers import AttachmentSerializer
from common.rich_text import sanitize_html
from tasks.serializers import SimpleUserSerializer  # 复用（与申报/新闻一致）

from .lifecycle import initial_status
from .models import Activity, Ballot, VoteOption, Submission


class VoteOptionSerializer(serializers.ModelSerializer):
    """投票选项读侧：附各选项票数（聚合计数）。"""

    vote_count = serializers.SerializerMethodField()

    class Meta:
        model = VoteOption
        fields = ["id", "text", "order", "vote_count"]

    def get_vote_count(self, obj):
        return obj.selections.count()


class BallotSerializer(serializers.ModelSerializer):
    """公开选票：投票人 + 勾选的 option_ids。秘密投票下不输出（get_ballots 裁剪）。"""

    voter = SimpleUserSerializer(read_only=True)
    option_ids = serializers.SerializerMethodField()

    class Meta:
        model = Ballot
        fields = ["id", "voter", "option_ids", "created_at"]

    def get_option_ids(self, obj):
        return list(obj.selections.values_list("option_id", flat=True))


class SubmissionSerializer(serializers.ModelSerializer):
    """征集作品：提交者 + 一束文件 + 复审状态。"""

    submitter = SimpleUserSerializer(read_only=True)
    files = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            "id", "submitter", "files",
            "review_status", "review_comment", "reviewed_at", "created_at",
        ]

    def get_files(self, obj):
        return AttachmentSerializer(obj.attachments.all(), many=True, context=self.context).data


class ActivityListSerializer(serializers.ModelSerializer):
    creator = SimpleUserSerializer(read_only=True)

    class Meta:
        model = Activity
        fields = ["id", "type", "status", "title", "creator", "end_at", "created_at", "updated_at"]


def _is_reviewer(activity, user):
    """征集复审者：活动发起人，或持 change_activity / review_collection 权限者。

    review_collection 权限由 T5 落地；在此之前 has_perm 返回 False，复审者仅含发起人。
    """
    return user.is_authenticated and (
        activity.creator_id == user.pk
        or user.has_perm("activities.change_activity")
        or user.has_perm("activities.review_collection")
    )


class ActivityDetailSerializer(serializers.ModelSerializer):
    creator = SimpleUserSerializer(read_only=True)
    # 众议读侧
    options = VoteOptionSerializer(many=True, read_only=True)
    ballots = serializers.SerializerMethodField()
    my_selections = serializers.SerializerMethodField()
    total_ballots = serializers.SerializerMethodField()
    # 征集读侧
    my_submission = serializers.SerializerMethodField()
    submissions = serializers.SerializerMethodField()
    # 众议写侧：创建时给选项文本（开放即锁定，无后续编辑）
    option_texts = serializers.ListField(
        child=serializers.CharField(max_length=200), write_only=True, required=False,
    )

    class Meta:
        model = Activity
        fields = [
            "id", "type", "status", "title", "body", "creator",
            "end_at",
            "max_choices_per_voter", "is_secret_ballot",
            "allowed_extensions", "max_file_size", "max_files_per_submission", "max_submissions",
            "options", "ballots", "my_selections", "total_ballots",
            "my_submission", "submissions",
            "option_texts",
            "created_at", "updated_at",
        ]
        read_only_fields = ["creator", "status", "created_at", "updated_at"]

    def validate_body(self, value):
        # 与新闻同级：写时消毒，存消毒后 HTML，读时原样返回。
        return sanitize_html(value or "")

    def validate(self, attrs):
        # 仅创建时校验众议选项与 K 值（选项开放即锁定，无更新路径）
        if attrs.get("type") == "deliberation" and self.instance is None:
            texts = attrs.get("option_texts") or []
            if len(texts) < 2:
                raise serializers.ValidationError({"option_texts": "众议至少需要 2 个选项"})
            if len(texts) > 50:
                raise serializers.ValidationError({"option_texts": "众议选项不超过 50 个"})
            k = attrs.get("max_choices_per_voter", 1)
            if k < 1 or k > len(texts):
                raise serializers.ValidationError(
                    {"max_choices_per_voter": "每人最多选几项须在 1..选项数 之间"}
                )
        return attrs

    def create(self, validated_data):
        texts = validated_data.pop("option_texts", [])
        activity_type = validated_data["type"]
        # 截止时间默认：众议 +3 天、征集 +7 天（发起人可显式传 end_at 覆盖）
        if not validated_data.get("end_at"):
            days = 3 if activity_type == "deliberation" else 7
            validated_data["end_at"] = timezone.now() + timedelta(days=days)
        validated_data["status"] = initial_status(activity_type)
        activity = Activity.objects.create(**validated_data)
        for i, text in enumerate(texts):
            VoteOption.objects.create(activity=activity, text=text, order=i)
        return activity

    # ---- 众议读侧聚合 ----

    def get_ballots(self, obj):
        # 秘密投票：个人明细仅 is_superuser 可见；其余（含发起人）只见聚合计数。
        if obj.type != "deliberation":
            return None
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if obj.is_secret_ballot and not (
            user and user.is_authenticated and user.is_superuser
        ):
            return None
        return BallotSerializer(obj.ballots.all(), many=True, context=self.context).data

    def get_my_selections(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or obj.type != "deliberation":
            return None
        ballot = obj.ballots.filter(voter=user).first()
        if ballot is None:
            return None
        return list(ballot.selections.values_list("option_id", flat=True))

    def get_total_ballots(self, obj):
        if obj.type != "deliberation":
            return None
        return obj.ballots.count()

    # ---- 征集读侧 ----

    def get_my_submission(self, obj):
        if obj.type != "collection":
            return None
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        sub = obj.submissions.filter(submitter=user).first()
        return SubmissionSerializer(sub, context=self.context).data if sub else None

    def get_submissions(self, obj):
        # 复审者见全部作品；其余只见录用作品（公开展示）。自己的作品另走 my_submission。
        if obj.type != "collection":
            return None
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return []
        qs = obj.submissions.all()
        if not _is_reviewer(obj, user):
            qs = qs.filter(review_status="accepted")
        return SubmissionSerializer(qs, many=True, context=self.context).data
