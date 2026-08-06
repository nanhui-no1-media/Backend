from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Proposal


def _president(user):
    g, _ = Group.objects.get_or_create(name="社长")
    user.groups.add(g)
    return user


class ProposalApprovePermissionTest(TestCase):
    def setUp(self):
        self.normal = User.objects.create_user(username="normal", password="x")
        self.president = _president(User.objects.create_user(username="pres", password="x"))
        self.client = APIClient()
        self.prop = Proposal.objects.create(
            proposal_type="feedback", status="pending_approval",
            title="p", creator=self.normal,
        )

    def test_non_approver_cannot_approve(self):
        self.client.force_authenticate(self.normal)
        resp = self.client.post(f"/proposals/proposals/{self.prop.pk}/approve/")
        self.assertEqual(resp.status_code, 403)

    def test_approver_can_approve(self):
        self.client.force_authenticate(self.president)
        resp = self.client.post(f"/proposals/proposals/{self.prop.pk}/approve/")
        self.assertEqual(resp.status_code, 200)


class FeedbackAttributionTest(TestCase):
    """意见反馈的「署名 / 匿名」归属：署名才记录 creator，复用 is_parent_creator 授权附件。

    单一接缝：HTTP（``POST /proposals/proposals/submit_feedback/``）。setUp 清缓存以
    隔离 FeedbackAnonThrottle 的跨用例计数。
    """

    def setUp(self):
        cache.clear()
        self.member = User.objects.create_user(username="member", password="x")
        self.client = APIClient()

    def test_attributed_feedback_records_creator(self):
        self.client.force_authenticate(self.member)
        resp = self.client.post(
            "/proposals/proposals/submit_feedback/",
            {
                "title": "举报",
                "description": "证据……",
                "feedback_category": "report",
                "disclose_identity": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["creator"]["username"], "member")
        proposal = Proposal.objects.get(pk=resp.data["id"])
        self.assertEqual(proposal.creator, self.member)
        self.assertEqual(proposal.proposal_type, "feedback")
        self.assertEqual(proposal.status, "pending_approval")

    def test_anonymous_feedback_has_no_creator(self):
        resp = self.client.post(
            "/proposals/proposals/submit_feedback/",
            {"title": "匿名举报", "description": "……", "feedback_category": "report"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIsNone(resp.data["creator"])
        self.assertIsNone(Proposal.objects.get(pk=resp.data["id"]).creator)

    def test_logged_in_choosing_anonymous_has_no_creator(self):
        # 登录用户选「匿名」：不传 disclose_identity → 仍 creator=None
        self.client.force_authenticate(self.member)
        resp = self.client.post(
            "/proposals/proposals/submit_feedback/",
            {"title": "匿名举报", "description": "……", "feedback_category": "report"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIsNone(resp.data["creator"])

    def test_disclose_without_login_rejected(self):
        resp = self.client.post(
            "/proposals/proposals/submit_feedback/",
            {
                "title": "举报", "description": "……", "feedback_category": "report",
                "disclose_identity": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
