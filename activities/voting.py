"""众议/展示投票：选票、选项锁定、秘密票可见性、全员提前结算。

视图 ``vote`` 动作是 HTTP 适配器；本模块是领域接缝。
"""
from django.db import transaction
from django.utils import timezone

from .lifecycle import CLOSED, OPEN, SCHEDULED, can_vote
from .models import Activity, Ballot, BallotSelection


class BallotError(Exception):
    """cast_ballot 拒绝写入；``detail`` 给适配器当 400 文案。"""

    def __init__(self, detail):
        super().__init__(detail)
        self.detail = detail


def voting_active(activity):
    """该活动是否走投票读侧：众议始终；展示仅 ``voting_enabled`` 时。纯陈列无投票数据。"""
    if activity.type == "deliberation":
        return True
    return activity.type == "exhibition" and activity.voting_enabled


def options_locked(activity):
    """众议选项在投票开放后锁定，不可增删改。待开始期间可改。

    展示的选项随展品走 exhibition 模块（展示中仍可加展品/选项）。
    """
    return activity.type == "deliberation" and activity.status != SCHEDULED


def ballots_visible_to(activity, user):
    """选票明细是否对该用户可见。无投票轴则否；秘密投票仅超级管理员。"""
    if not voting_active(activity):
        return False
    if not activity.is_secret_ballot:
        return True
    return bool(
        user and getattr(user, "is_authenticated", False) and user.is_superuser
    )


def maybe_close_deliberation_on_full_vote(activity):
    """全员投完即提前结算：众议 open 状态下，若已投票数 ≥ 已验证成员数，翻 closed。

    分母 = 已验证成员数（``accounts.verified_member_count``）。
    在 ``cast_ballot`` 里调用（只有投票会改变票数）。逐行条件更新保证并发安全。
    """
    if activity.type != "deliberation" or activity.status != OPEN:
        return False
    from accounts.models import verified_member_count

    total = verified_member_count()
    if total <= 0:
        return False
    # 绕开预取缓存：用 Ballot 模型直接计票。
    if Ballot.objects.filter(activity_id=activity.pk).count() >= total:
        changed = Activity.objects.filter(
            pk=activity.pk, status=OPEN,
        ).update(status=CLOSED, updated_at=timezone.now())
        return bool(changed)
    return False


def cast_ballot(*, activity, user, option_ids):
    """投一张选票。失败抛 ``BallotError``。成功后众议可能提前结算。"""
    if not can_vote(activity, user):
        if activity.type not in ("deliberation", "exhibition"):
            raise BallotError("仅众议/展示可以投票")
        if activity.type == "exhibition" and not activity.voting_enabled:
            raise BallotError("该展示未启用投票")
        raise BallotError("投票已结束")
    if Ballot.objects.filter(activity=activity, voter=user).exists():
        raise BallotError("你已经投过票了，不能修改")

    if not isinstance(option_ids, list) or len(option_ids) < 1:
        raise BallotError("请至少选择一个选项")
    if len(set(option_ids)) != len(option_ids):
        raise BallotError("不能重复选择同一选项")
    if len(option_ids) > activity.max_choices_per_voter:
        raise BallotError(f"最多选择 {activity.max_choices_per_voter} 项")
    valid_ids = set(activity.options.values_list("id", flat=True))
    try:
        ids = [int(x) for x in option_ids]
    except (TypeError, ValueError):
        raise BallotError("无效的选项")
    if not set(ids).issubset(valid_ids):
        raise BallotError("存在不属于本活动的选项")

    with transaction.atomic():
        ballot = Ballot.objects.create(activity=activity, voter=user)
        BallotSelection.objects.bulk_create(
            [BallotSelection(ballot=ballot, option_id=oid) for oid in ids]
        )
        maybe_close_deliberation_on_full_vote(activity)
    return ballot
