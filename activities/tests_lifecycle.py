"""活动生命周期模块的接口测试（次 seam：直接调用纯领域逻辑，不经 HTTP）。

与 activities/tests.py 的 HTTP 黑盒相对——本文件只测 lifecycle 对外契约。
T2：initial_status / can_vote / transition_overdue。
"""

from datetime import timedelta

from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase
from django.utils import timezone

from accounts.test_helpers import grant_verification

from .lifecycle import (
    CLOSED,
    COLLECTING,
    OPEN,
    can_vote,
    initial_status,
    transition_overdue,
)
from .models import Activity


class InitialStatusTest(TestCase):
    def test_deliberation_opens_open(self):
        self.assertEqual(initial_status("deliberation"), OPEN)

    def test_collection_opens_collecting(self):
        self.assertEqual(initial_status("collection"), COLLECTING)

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            initial_status("bogus")


class CanVoteTest(TestCase):
    def setUp(self):
        self.user = grant_verification(User.objects.create_user(username="u", password="x"))
        self.deliberation = Activity.objects.create(
            type="deliberation", status=OPEN, title="d", max_choices_per_voter=1,
        )
        self.collection = Activity.objects.create(type="collection", status=COLLECTING, title="c")
        self.closed = Activity.objects.create(
            type="deliberation", status=CLOSED, title="x", max_choices_per_voter=1,
        )
        # 展示：默认不启用投票（纯陈列）；启用投票时才可投。
        self.exhibit_pure = Activity.objects.create(
            type="exhibition", status=OPEN, title="e_pure", voting_enabled=False,
        )
        self.exhibit_voting = Activity.objects.create(
            type="exhibition", status=OPEN, title="e_voting", voting_enabled=True,
        )

    def test_open_deliberation_allows_vote(self):
        self.assertTrue(can_vote(self.deliberation, self.user))

    def test_closed_deliberation_blocks_vote(self):
        self.assertFalse(can_vote(self.closed, self.user))

    def test_collection_not_votable(self):
        self.assertFalse(can_vote(self.collection, self.user))

    def test_anonymous_cannot_vote(self):
        self.assertFalse(can_vote(self.deliberation, AnonymousUser()))

    def test_exhibition_voting_disabled_blocks_vote(self):
        # 展示纯陈列（未启用投票）不可投票
        self.assertFalse(can_vote(self.exhibit_pure, self.user))

    def test_exhibition_voting_enabled_allows_vote(self):
        # 展示启用投票时方可投
        self.assertTrue(can_vote(self.exhibit_voting, self.user))


class TransitionOverdueTest(TestCase):
    def test_overdue_open_flips_to_closed(self):
        a = Activity.objects.create(
            type="deliberation", status=OPEN, title="d", max_choices_per_voter=1,
            end_at=timezone.now() - timedelta(minutes=1),
        )
        closed = transition_overdue()
        self.assertIn(a.pk, closed)
        self.assertEqual(Activity.objects.get(pk=a.pk).status, CLOSED)

    def test_not_yet_due_stays_open(self):
        a = Activity.objects.create(
            type="deliberation", status=OPEN, title="d", max_choices_per_voter=1,
            end_at=timezone.now() + timedelta(days=1),
        )
        transition_overdue()
        self.assertEqual(Activity.objects.get(pk=a.pk).status, OPEN)

    def test_collection_not_affected(self):
        # 征集即便 end_at 过去也不被众议结算触碰
        c = Activity.objects.create(
            type="collection", status=COLLECTING, title="c",
            end_at=timezone.now() - timedelta(minutes=1),
        )
        transition_overdue()
        self.assertEqual(Activity.objects.get(pk=c.pk).status, COLLECTING)
