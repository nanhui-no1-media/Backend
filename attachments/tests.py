"""统一附件端点测试。

单一接缝：HTTP API（``POST /attachments/``、``DELETE /attachments/{id}/``）。
只测外部行为（状态码、响应体、``refresh_from_db`` 后的模型状态、磁盘文件存在性），
不测信号/校验函数的内部实现。风格仿 ``tasks/tests.py`` / ``proposals/tests.py``。

所有用例经 ``_AttachmentTestCase`` 把 ``MEDIA_ROOT`` 重定向到临时目录，并在结束时兜底
清理真实 ``media/attachments/``（Django 可能缓存 FileField 存储、使 override 不生效）。
"""
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from proposals.models import Proposal
from tasks.models import Task

from .models import Attachment


def make_president(user):
    """加入「社长」组：已含 manage_tasks / change_proposal 等管理权限。"""
    group, _ = Group.objects.get_or_create(name="社长")
    user.groups.add(group)
    return user


def upload(name="a.png", content=b"data", content_type="image/png"):
    return SimpleUploadedFile(name, content, content_type=content_type)


class _AttachmentTestCase(TestCase):
    """临时 MEDIA_ROOT + 兜底清理，确保测试不污染真实 media/。"""

    def setUp(self):
        self._real_media_root = Path(settings.MEDIA_ROOT)
        self.tmp_media = tempfile.mkdtemp()
        self._override = override_settings(MEDIA_ROOT=self.tmp_media)
        self._override.enable()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self._override.disable()
        # 兜底：若 FileField 存储未随 override 重定向，文件会落到真实 media/attachments/
        att_dir = self._real_media_root / "attachments"
        if att_dir.exists():
            for path in att_dir.glob("*"):
                path.unlink(missing_ok=True)
        shutil.rmtree(self.tmp_media, ignore_errors=True)


# ── 上传权限（任务父级）──
class UploadTaskPermissionTest(_AttachmentTestCase):
    def setUp(self):
        super().setUp()
        self.creator = User.objects.create_user(username="creator", password="x")
        self.assignee = User.objects.create_user(username="assignee", password="x")
        self.collab = User.objects.create_user(username="collab", password="x")
        self.outsider = User.objects.create_user(username="outsider", password="x")
        self.president = make_president(User.objects.create_user(username="pres", password="x"))
        self.client = APIClient()
        # 进行中任务：creator + assignee + collaborator
        self.task = Task.objects.create(
            title="t", creator=self.creator, assignee=self.assignee, status="in_progress",
        )
        self.task.collaborators.add(self.collab)
        # 待处理任务：仅 creator 可上传
        self.pending = Task.objects.create(title="p", creator=self.creator, status="pending")

    def _post(self, user, task):
        self.client.force_authenticate(user)
        return self.client.post(
            "/attachments/", {"file": upload(), "task_id": task.pk}, format="multipart",
        )

    def test_creator_can_upload_to_in_progress_task(self):
        self.assertEqual(self._post(self.creator, self.task).status_code, 201)

    def test_creator_can_upload_to_own_pending_task(self):  # 故事 #6
        self.assertEqual(self._post(self.creator, self.pending).status_code, 201)

    def test_assignee_can_upload_to_in_progress_task(self):
        self.assertEqual(self._post(self.assignee, self.task).status_code, 201)

    def test_collaborator_can_upload_to_in_progress_task(self):
        self.assertEqual(self._post(self.collab, self.task).status_code, 201)

    def test_president_can_upload_to_any_task(self):  # 故事 #9
        self.assertEqual(self._post(self.president, self.task).status_code, 201)

    def test_outsider_cannot_upload_to_others_task(self):  # 故事 #7
        self.assertEqual(self._post(self.outsider, self.task).status_code, 403)

    def test_collaborator_cannot_upload_when_task_not_in_progress(self):
        # 协作者仅在进行中才是活跃参与者
        other = Task.objects.create(title="c", creator=self.creator, status="pending")
        other.collaborators.add(self.collab)
        self.assertEqual(self._post(self.collab, other).status_code, 403)

    def test_anonymous_cannot_upload(self):  # 故事 #11
        self.client.force_authenticate(None)
        resp = self.client.post(
            "/attachments/", {"file": upload(), "task_id": self.task.pk}, format="multipart",
        )
        self.assertEqual(resp.status_code, 403)


# ── 上传权限（申报父级）──
class UploadProposalPermissionTest(_AttachmentTestCase):
    def setUp(self):
        super().setUp()
        self.creator = User.objects.create_user(username="creator", password="x")
        self.outsider = User.objects.create_user(username="outsider", password="x")
        self.president = make_president(User.objects.create_user(username="pres", password="x"))
        self.client = APIClient()
        self.prop = Proposal.objects.create(
            proposal_type="activity", status="pending_approval",
            title="p", creator=self.creator,
        )

    def _post(self, user):
        self.client.force_authenticate(user)
        return self.client.post(
            "/attachments/", {"file": upload(), "proposal_id": self.prop.pk}, format="multipart",
        )

    def test_creator_can_upload_to_own_proposal(self):
        self.assertEqual(self._post(self.creator).status_code, 201)

    def test_president_can_upload_to_any_proposal(self):  # 故事 #10
        self.assertEqual(self._post(self.president).status_code, 201)

    def test_outsider_cannot_upload_to_others_proposal(self):  # 故事 #8
        self.assertEqual(self._post(self.outsider).status_code, 403)


# ── 恰一父级 ──
class ParentValidationTest(_AttachmentTestCase):
    def setUp(self):
        super().setUp()
        self.creator = User.objects.create_user(username="creator", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.creator)
        self.task = Task.objects.create(title="t", creator=self.creator, status="pending")
        self.prop = Proposal.objects.create(
            proposal_type="activity", status="pending_approval", title="p", creator=self.creator,
        )

    def test_both_parents_rejected(self):  # 故事 #20
        resp = self.client.post(
            "/attachments/",
            {"file": upload(), "task_id": self.task.pk, "proposal_id": self.prop.pk},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 400)

    def test_neither_parent_rejected(self):  # 故事 #20
        resp = self.client.post("/attachments/", {"file": upload()}, format="multipart")
        self.assertEqual(resp.status_code, 400)


# ── 文件校验 ──
class FileValidationTest(_AttachmentTestCase):
    def setUp(self):
        super().setUp()
        self.creator = User.objects.create_user(username="creator", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.creator)
        self.task = Task.objects.create(title="t", creator=self.creator, status="pending")

    def _post(self, f):
        return self.client.post(
            "/attachments/", {"file": f, "task_id": self.task.pk}, format="multipart",
        )

    def test_oversize_rejected(self):  # 故事 #17：把上限降到 1B，4B 文件即超限
        with mock.patch("attachments.validation.MAX_FILE_SIZE", 1):
            resp = self._post(upload())
        self.assertEqual(resp.status_code, 400)

    def test_banned_extension_rejected(self):  # 故事 #18
        resp = self._post(upload("evil.py", b"x", "text/x-python"))
        self.assertEqual(resp.status_code, 400)

    def test_classifies_image(self):  # 故事 #19
        resp = self._post(upload("a.png", b"x", "image/png"))
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["file_type"], "image")

    def test_classifies_document(self):
        resp = self._post(upload("a.pdf", b"x", "application/pdf"))
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["file_type"], "document")

    def test_classifies_archive(self):
        resp = self._post(upload("a.zip", b"x", "application/zip"))
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["file_type"], "archive")

    def test_classifies_other(self):
        resp = self._post(upload("a.bin", b"x", "application/octet-stream"))
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["file_type"], "other")


# ── 删除权限 ──
class DeletePermissionTest(_AttachmentTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(username="owner", password="x")
        self.uploader = User.objects.create_user(username="uploader", password="x")
        self.collab = User.objects.create_user(username="collab", password="x")
        self.outsider = User.objects.create_user(username="outsider", password="x")
        self.president = make_president(User.objects.create_user(username="pres", password="x"))
        self.client = APIClient()
        # 进行中任务：owner 创建；uploader=assignee（活跃参与者）；collab=协作者
        self.task = Task.objects.create(
            title="t", creator=self.owner, assignee=self.uploader, status="in_progress",
        )
        self.task.collaborators.add(self.collab)
        # uploader（=负责人）上传一个附件
        self.client.force_authenticate(self.uploader)
        resp = self.client.post(
            "/attachments/", {"file": upload(), "task_id": self.task.pk}, format="multipart",
        )
        self.assertEqual(resp.status_code, 201)
        self.attachment_id = resp.data["id"]

    def _delete(self, user):
        self.client.force_authenticate(user)
        return self.client.delete(f"/attachments/{self.attachment_id}/")

    def test_uploader_can_delete_own(self):  # 故事 #12
        self.assertEqual(self._delete(self.uploader).status_code, 204)

    def test_parent_creator_can_delete(self):  # 故事 #13
        self.assertEqual(self._delete(self.owner).status_code, 204)

    def test_president_can_delete(self):  # 故事 #9 / #10
        self.assertEqual(self._delete(self.president).status_code, 204)

    def test_active_participant_can_delete(self):  # ADR：增、删同一套规则
        self.assertEqual(self._delete(self.collab).status_code, 204)

    def test_outsider_cannot_delete(self):  # 故事 #14
        self.assertEqual(self._delete(self.outsider).status_code, 403)


class DeleteOwnAfterTaskNotInProgressTest(_AttachmentTestCase):
    """故事 #12 健壮性：任务离开进行中后，上传者仍可删自己上传的附件。"""

    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(username="owner", password="x")
        self.uploader = User.objects.create_user(username="uploader", password="x")
        self.client = APIClient()
        self.task = Task.objects.create(
            title="t", creator=self.owner, assignee=self.uploader, status="in_progress",
        )
        # uploader 在进行中上传（活跃参与者）
        self.client.force_authenticate(self.uploader)
        resp = self.client.post(
            "/attachments/", {"file": upload(), "task_id": self.task.pk}, format="multipart",
        )
        self.attachment_id = resp.data["id"]
        # 任务流转出进行中：uploader 不再是活跃参与者
        self.task.status = "completed"
        self.task.save()

    def test_uploader_can_delete_after_task_left_in_progress(self):
        self.client.force_authenticate(self.uploader)
        resp = self.client.delete(f"/attachments/{self.attachment_id}/")
        self.assertEqual(resp.status_code, 204)


# ── 级联回收（删父级 → 行 + 磁盘文件同步消失）──
class CascadeReclaimTest(_AttachmentTestCase):
    def setUp(self):
        super().setUp()
        self.creator = User.objects.create_user(username="creator", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.creator)
        self.task = Task.objects.create(title="t", creator=self.creator, status="pending")
        self.prop = Proposal.objects.create(
            proposal_type="activity", status="returned", title="p", creator=self.creator,
        )

    def _upload_and_capture(self, parent_key, parent_pk):
        resp = self.client.post(
            "/attachments/",
            {"file": upload(), parent_key: parent_pk},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201)
        att = Attachment.objects.get(pk=resp.data["id"])
        return att.id, att.file.storage, att.file.name

    def test_deleting_task_removes_attachment_and_file(self):  # 故事 #15
        att_id, storage, name = self._upload_and_capture("task_id", self.task.pk)
        self.assertTrue(storage.exists(name))

        resp = self.client.delete(f"/tasks/tasks/{self.task.pk}/")  # creator 删 pending 任务
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Attachment.objects.filter(pk=att_id).exists())
        self.assertFalse(storage.exists(name))

    def test_deleting_proposal_removes_attachment_and_file(self):  # 故事 #16
        att_id, storage, name = self._upload_and_capture("proposal_id", self.prop.pk)
        self.assertTrue(storage.exists(name))

        resp = self.client.delete(f"/proposals/proposals/{self.prop.pk}/")  # creator 删 returned 申报
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Attachment.objects.filter(pk=att_id).exists())
        self.assertFalse(storage.exists(name))
