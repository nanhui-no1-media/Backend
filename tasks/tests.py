import json

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Task


def make_president(user):
    """把用户加入「社长」组，使其通过 is_president()。"""
    group, _ = Group.objects.get_or_create(name="社长")
    user.groups.add(group)
    return user


class TaskCompletionReviewTest(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username="creator", password="x")
        self.assignee = User.objects.create_user(username="assignee", password="x")
        self.other = User.objects.create_user(username="other", password="x")
        self.president = make_president(User.objects.create_user(username="pres", password="x"))
        self.client = APIClient()
        self.task = Task.objects.create(
            title="t", creator=self.creator, assignee=self.assignee, status="in_progress",
        )

    def test_complete_moves_to_reviewing(self):
        self.client.force_authenticate(self.assignee)
        resp = self.client.post(f"/tasks/tasks/{self.task.pk}/complete/")
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "reviewing")
        self.assertIsNone(self.task.completed_at)
