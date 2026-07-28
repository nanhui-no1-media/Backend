import json

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from .factories import make_president
from .models import Task, TaskClaimRequest


class TaskActionSmokeTest(TestCase):
    """八个流转动作的薄冒烟：每动作一条，断言状态码 + 响应形状 + 详情 available_actions。

    重规则矩阵（状态 × 角色 × 动作）由 ``tasks.tests_lifecycle`` 在模块接口层承担，
    此处只验「HTTP 委托是否接对」——成功路径、行为变更，以及 ``kind``→状态码映射。
    """

    def setUp(self):
        self.creator = User.objects.create_user(username="creator", password="x")
        self.member = User.objects.create_user(username="member", password="x")
        self.president = make_president(User.objects.create_user(username="pres", password="x"))
        self.client = APIClient()

    def _post(self, path, user, payload=None):
        self.client.force_authenticate(user)
        if payload is None:
            return self.client.post(path)
        return self.client.post(path, data=json.dumps(payload), content_type="application/json")

    def test_claim_creates_request_and_returns_201(self):
        task = Task.objects.create(title="t", creator=self.creator, status="pending")
        resp = self._post(f"/tasks/tasks/{task.pk}/claim/", self.member, {"reason": "我能做"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["claimant"]["id"], self.member.pk)
        task.refresh_from_db()
        self.assertEqual(task.status, "review")  # 首个认领 → 认领审核

    def test_approve_claim_assigns_claimant(self):
        task = Task.objects.create(title="t", creator=self.creator, status="review")
        claim = TaskClaimRequest.objects.create(task=task, claimant=self.member)
        resp = self._post(f"/tasks/tasks/{task.pk}/approve_claim/", self.creator, {"claim_id": claim.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["assignee"]["id"], self.member.pk)
        self.assertIn("available_actions", resp.data)

    def test_reject_claim_reverts_to_pending(self):
        task = Task.objects.create(title="t", creator=self.creator, status="review")
        claim = TaskClaimRequest.objects.create(task=task, claimant=self.member)
        resp = self._post(f"/tasks/tasks/{task.pk}/reject_claim/", self.creator, {"claim_id": claim.pk})
        self.assertEqual(resp.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, "pending")

    def test_complete_by_assignee_moves_to_reviewing(self):
        task = Task.objects.create(title="t", creator=self.creator, status="in_progress", assignee=self.member)
        resp = self._post(f"/tasks/tasks/{task.pk}/complete/", self.member)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("available_actions", resp.data)
        task.refresh_from_db()
        self.assertEqual(task.status, "reviewing")

    def test_complete_by_collaborator(self):
        # 行为变更（已签字）：协作者（活跃参与者）也能提交验收，此前被静默排除。
        task = Task.objects.create(title="t", creator=self.creator, status="in_progress")
        task.collaborators.add(self.member)
        resp = self._post(f"/tasks/tasks/{task.pk}/complete/", self.member)
        self.assertEqual(resp.status_code, 200)

    def test_approve_completion_completes_task(self):
        task = Task.objects.create(title="t", creator=self.creator, status="reviewing")
        resp = self._post(f"/tasks/tasks/{task.pk}/approve_completion/", self.creator)
        self.assertEqual(resp.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, "completed")
        self.assertIsNotNone(task.completed_at)

    def test_reject_completion_returns_to_in_progress_with_reason(self):
        task = Task.objects.create(title="t", creator=self.creator, status="reviewing", assignee=self.member)
        resp = self._post(f"/tasks/tasks/{task.pk}/reject_completion/", self.creator, {"reason": "返工"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["reject_reason"], "返工")
        task.refresh_from_db()
        self.assertEqual(task.status, "in_progress")
        self.assertEqual(task.assignee_id, self.member.pk)  # 负责人不变

    def test_reject_completion_without_reason_is_bad_request(self):
        # 载荷校验失败 → bad_request → 400（kind→状态码映射的冒烟）。
        task = Task.objects.create(title="t", creator=self.creator, status="reviewing")
        resp = self._post(f"/tasks/tasks/{task.pk}/reject_completion/", self.creator, {"reason": "   "})
        self.assertEqual(resp.status_code, 400)

    def test_cancel_cancels_task(self):
        task = Task.objects.create(title="t", creator=self.creator, status="in_progress")
        resp = self._post(f"/tasks/tasks/{task.pk}/cancel/", self.creator)
        self.assertEqual(resp.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, "cancelled")

    def test_assign_sets_assignee_and_in_progress(self):
        task = Task.objects.create(title="t", creator=self.creator, status="pending")
        resp = self._post(f"/tasks/tasks/{task.pk}/assign/", self.president, {"assignee_id": self.member.pk})
        self.assertEqual(resp.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.assignee_id, self.member.pk)
        self.assertEqual(task.status, "in_progress")

    def test_non_creator_approval_is_forbidden(self):
        # 权限不足 → forbidden → 403（kind→状态码映射的冒烟）。
        task = Task.objects.create(title="t", creator=self.creator, status="reviewing")
        resp = self._post(f"/tasks/tasks/{task.pk}/approve_completion/", self.member)
        self.assertEqual(resp.status_code, 403)


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


class TaskAvailableActionsTest(TestCase):
    """详情序列化带 available_actions（来自生命周期模块）；列表不带。"""

    def setUp(self):
        self.creator = User.objects.create_user(username="creator", password="x")
        self.assignee = User.objects.create_user(username="assignee", password="x")
        self.client = APIClient()

    def test_detail_includes_available_actions(self):
        task = Task.objects.create(title="t", creator=self.creator, status="in_progress", assignee=self.assignee)
        self.client.force_authenticate(self.creator)
        resp = self.client.get(f"/tasks/tasks/{task.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("available_actions", resp.data)
        # 创建者看进行中任务：可取消（非终态 + 创建者）；不可完成（非活跃参与者）。
        self.assertIn("cancel", resp.data["available_actions"])
        self.assertNotIn("complete", resp.data["available_actions"])

    def test_detail_available_actions_for_active_participant(self):
        # 负责人是活跃参与者 → complete 出现在可用动作里。
        task = Task.objects.create(title="t", creator=self.creator, status="in_progress", assignee=self.assignee)
        self.client.force_authenticate(self.assignee)
        resp = self.client.get(f"/tasks/tasks/{task.pk}/")
        self.assertIn("complete", resp.data["available_actions"])

    def test_list_excludes_available_actions(self):
        Task.objects.create(title="t", creator=self.creator, status="pending")
        self.client.force_authenticate(self.creator)
        resp = self.client.get("/tasks/tasks/")
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        items = data["results"] if isinstance(data, dict) and "results" in data else data
        self.assertNotIn("available_actions", items[0])
