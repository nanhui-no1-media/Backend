from rest_framework import serializers

from tasks.serializers import SimpleUserSerializer  # 复用

from .models import Proposal, ProposalAttachment, Vote


def _creator_repr(obj):
    """反馈/举报无创建人（公开匿名提交）→ 返回 None；活动申报返回创建人。"""
    if obj.creator_id is None:
        return None
    return SimpleUserSerializer(obj.creator).data


class ProposalAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = SimpleUserSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ProposalAttachment
        fields = [
            "id", "file_url", "file_type", "file_name",
            "file_size", "uploaded_by", "uploaded_at",
        ]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and hasattr(obj.file, "url"):
            url = obj.file.url
            if request:
                return request.build_absolute_uri(url)
            return url
        return None


class VoteSerializer(serializers.ModelSerializer):
    voter = SimpleUserSerializer(read_only=True)

    class Meta:
        model = Vote
        fields = ["id", "voter", "vote_choice", "created_at"]
        read_only_fields = ["voter", "created_at"]


class ProposalListSerializer(serializers.ModelSerializer):
    creator = serializers.SerializerMethodField()
    attachment_count = serializers.SerializerMethodField()
    vote_summary = serializers.SerializerMethodField()

    class Meta:
        model = Proposal
        fields = [
            "id", "proposal_type", "status", "title",
            "creator", "contact",
            "activity_type", "feedback_category",
            "voting_end_at", "reject_reason",
            "attachment_count", "vote_summary",
            "created_at", "updated_at",
        ]

    def get_creator(self, obj):
        return _creator_repr(obj)

    def get_attachment_count(self, obj):
        return obj.attachments.count()

    def get_vote_summary(self, obj):
        if obj.proposal_type != "activity":
            return None
        # 优先用视图集中 annotate 的聚合值，避免 N+1
        return {
            "approve": getattr(obj, "approve_count", None) or 0,
            "oppose": getattr(obj, "oppose_count", None) or 0,
            "abstain": getattr(obj, "abstain_count", None) or 0,
            "total": getattr(obj, "total_votes", None) or 0,
        }


class ProposalDetailSerializer(serializers.ModelSerializer):
    creator = serializers.SerializerMethodField()
    reviewed_by = SimpleUserSerializer(read_only=True)
    votes = VoteSerializer(many=True, read_only=True)
    attachments = ProposalAttachmentSerializer(many=True, read_only=True)
    my_vote = serializers.SerializerMethodField()

    class Meta:
        model = Proposal
        fields = [
            "id", "proposal_type", "status", "title", "description",
            "activity_type", "planned_date", "location",
            "expected_participants", "budget",
            "feedback_category", "contact",
            "creator", "reviewed_by", "reviewed_at", "approved_at",
            "votes", "my_vote", "attachments",
            "voting_end_at", "reject_reason",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "creator", "status", "reviewed_by", "reviewed_at", "approved_at",
            "voting_end_at", "reject_reason", "created_at", "updated_at",
        ]

    def get_creator(self, obj):
        return _creator_repr(obj)

    def get_my_vote(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        try:
            vote = obj.votes.get(voter=user)
        except Vote.DoesNotExist:
            return None
        return vote.vote_choice

    def create(self, validated_data):
        # 创建时按类型设置初始状态与投票截止时间
        from datetime import timedelta
        from django.utils import timezone

        if validated_data.get("proposal_type") == "activity":
            validated_data["status"] = "voting"
            validated_data["voting_end_at"] = timezone.now() + timedelta(days=3)
        else:
            validated_data["status"] = "pending_approval"
        return super().create(validated_data)
