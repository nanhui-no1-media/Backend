from django.contrib.auth.models import Group, User
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
            proposal_type="activity", status="pending_approval",
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
