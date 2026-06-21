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

    def test_approve_completion_by_creator(self):
        self.task.status = "reviewing"
        self.task.save()
        self.client.force_authenticate(self.creator)
        resp = self.client.post(f"/tasks/tasks/{self.task.pk}/approve_completion/")
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "completed")
        self.assertIsNotNone(self.task.completed_at)

    def test_approve_completion_forbidden_for_assignee(self):
        self.task.status = "reviewing"
        self.task.save()
        self.client.force_authenticate(self.assignee)
        resp = self.client.post(f"/tasks/tasks/{self.task.pk}/approve_completion/")
        self.assertEqual(resp.status_code, 403)

    def test_approve_completion_requires_reviewing(self):
        # setUp 中 task 为 in_progress
        self.client.force_authenticate(self.creator)
        resp = self.client.post(f"/tasks/tasks/{self.task.pk}/approve_completion/")
        self.assertEqual(resp.status_code, 400)

    def test_reject_completion_returns_to_in_progress(self):
        self.task.status = "reviewing"
        self.task.save()
        self.client.force_authenticate(self.creator)
        resp = self.client.post(f"/tasks/tasks/{self.task.pk}/reject_completion/")
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "in_progress")
        self.assertEqual(self.task.assignee_id, self.assignee.pk)

    def test_reject_completion_forbidden_for_assignee(self):
        self.task.status = "reviewing"
        self.task.save()
        self.client.force_authenticate(self.assignee)
        resp = self.client.post(f"/tasks/tasks/{self.task.pk}/reject_completion/")
        self.assertEqual(resp.status_code, 403)

    def test_reject_completion_requires_reviewing(self):
        self.client.force_authenticate(self.creator)
        resp = self.client.post(f"/tasks/tasks/{self.task.pk}/reject_completion/")
        self.assertEqual(resp.status_code, 400)


class TaskEditLockTest(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username="creator", password="x")
        self.president = make_president(User.objects.create_user(username="pres", password="x"))
        self.client = APIClient()
        self.task = Task.objects.create(
            title="t", creator=self.creator, status="in_progress",
        )

    def _patch(self):
        return self.client.patch(
            f"/tasks/tasks/{self.task.pk}/",
            data=json.dumps({"title": "changed"}),
            content_type="application/json",
        )

    def test_creator_cannot_edit_in_progress(self):
        self.client.force_authenticate(self.creator)
        self.assertEqual(self._patch().status_code, 403)

    def test_president_cannot_edit_in_progress(self):
        self.client.force_authenticate(self.president)
        self.assertEqual(self._patch().status_code, 403)

    def test_creator_cannot_delete_in_progress(self):
        self.client.force_authenticate(self.creator)
        resp = self.client.delete(f"/tasks/tasks/{self.task.pk}/")
        self.assertEqual(resp.status_code, 403)

    def test_creator_can_edit_pending(self):
        self.task.status = "pending"
        self.task.save()
        self.client.force_authenticate(self.creator)
        self.assertEqual(self._patch().status_code, 200)
