"""活动 HTTP 黑盒测试（主 seam：经 APIClient 打端点，断言状态码 + 响应形状 + DB 副作用）。

T1 范围：创建（已验证成员）+ 列表/详情（成员可读）+ 正文消毒 + 正文图片上传。
投票/投稿/复审在后续切片的测试类里增补。
"""
import json
from datetime import timedelta

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.test_helpers import grant_verification

from .models import Activity


def _json(client, method, path, user, payload=None):
    client.force_authenticate(user)
    fn = getattr(client, method)
    if payload is None:
        return fn(path)
    return fn(path, data=json.dumps(payload), content_type="application/json")


class ActivityCreateReadTest(TestCase):
    """T1：创建 + 读 + 消毒。"""

    def setUp(self):
        self.author = grant_verification(User.objects.create_user(username="author", password="x"))
        self.visitor = User.objects.create_user(username="visitor", password="x")  # 未验证 = 访客
        self.other = grant_verification(User.objects.create_user(username="other", password="x"))
        self.client = APIClient()

    # ---- 创建 ----

    def test_verified_member_creates_deliberation(self):
        resp = _json(self.client, "post", "/activities/activities/", self.author,
                     {"type": "deliberation", "title": "去哪团建", "body": "<p>投票</p>",
                      "max_choices_per_voter": 1, "option_texts": ["去A地", "去B地"]})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["type"], "deliberation")
        self.assertEqual(resp.data["status"], "open")  # 众议创建即投票中
        self.assertEqual(resp.data["creator"]["id"], self.author.pk)
        self.assertEqual(resp.data["body"], "<p>投票</p>")

    def test_verified_member_creates_collection(self):
        resp = _json(self.client, "post", "/activities/activities/", self.author,
                     {"type": "collection", "title": "征社徽", "body": "<p>收件</p>"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["status"], "collecting")  # 征集创建即收件中

    def test_unverified_member_cannot_create(self):
        # 访客（未验证）发起 → IsVerified 门禁拒绝
        resp = _json(self.client, "post", "/activities/activities/", self.visitor,
                     {"type": "deliberation", "title": "x"})
        self.assertEqual(resp.status_code, 403)

    def test_invalid_type_rejected(self):
        resp = _json(self.client, "post", "/activities/activities/", self.author,
                     {"type": "bogus", "title": "x"})
        self.assertEqual(resp.status_code, 400)

    def test_body_is_sanitized_on_write(self):
        # script / 事件处理器须被剥（与新闻同级的消毒契约）
        resp = _json(self.client, "post", "/activities/activities/", self.author,
                     {"type": "collection", "title": "x",
                      "body": "<p>ok</p><script>alert(1)</script><img onload=alert(1) src=x>"})
        self.assertEqual(resp.status_code, 201)
        self.assertNotIn("<script>", resp.data["body"])
        self.assertIn("<p>ok</p>", resp.data["body"])
        self.assertNotIn("onload", resp.data["body"])

    def test_https_iframe_kept_http_iframe_stripped(self):
        body = '<p><iframe src="https://example.com/a"></iframe><iframe src="http://evil.com"></iframe></p>'
        resp = _json(self.client, "post", "/activities/activities/", self.author,
                     {"type": "collection", "title": "x", "body": body})
        self.assertEqual(resp.status_code, 201)
        self.assertIn("https://example.com/a", resp.data["body"])
        self.assertNotIn("evil.com", resp.data["body"])

    # ---- 读 ----

    def test_list_returns_activities(self):
        Activity.objects.create(type="deliberation", status="open", title="a", creator=self.author)
        Activity.objects.create(type="collection", status="collecting", title="b", creator=self.other)
        resp = _json(self.client, "get", "/activities/activities/", self.author)
        self.assertEqual(resp.status_code, 200)
        items = resp.data["results"] if isinstance(resp.data, dict) and "results" in resp.data else resp.data
        self.assertEqual(len(items), 2)
        # 列表序列化不带 body（轻量）
        self.assertNotIn("body", items[0])

    def test_retrieve_returns_body(self):
        a = Activity.objects.create(type="collection", status="collecting", title="b",
                                    body="<p>hi</p>", creator=self.author)
        resp = _json(self.client, "get", f"/activities/activities/{a.pk}/", self.other)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["body"], "<p>hi</p>")
        self.assertEqual(resp.data["creator"]["id"], self.author.pk)

    def test_unauthenticated_list_forbidden(self):
        self.client.force_authenticate(None)
        resp = self.client.get("/activities/activities/")
        # 仅 SessionAuthentication：未带凭据 → 403（无 WWW-Authenticate 挑战）。
        self.assertEqual(resp.status_code, 403)

    # ---- 删除（发起人 / change_activity）----

    def test_creator_can_delete_own(self):
        a = Activity.objects.create(type="deliberation", status="open", title="a", creator=self.author)
        self.client.force_authenticate(self.author)
        resp = self.client.delete(f"/activities/activities/{a.pk}/")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Activity.objects.filter(pk=a.pk).exists())

    def test_other_cannot_delete(self):
        a = Activity.objects.create(type="deliberation", status="open", title="a", creator=self.author)
        self.client.force_authenticate(self.other)
        resp = self.client.delete(f"/activities/activities/{a.pk}/")
        self.assertEqual(resp.status_code, 403)


class ActivityUploadImageTest(TestCase):
    """正文图片上传端点（镜像新闻）。"""

    def setUp(self):
        self.author = grant_verification(User.objects.create_user(username="author", password="x"))
        self.visitor = User.objects.create_user(username="visitor", password="x")
        self.client = APIClient()

    def _img(self, name="a.png", content_type="image/png", data=b"\x89PNG\r\n"):
        return SimpleUploadedFile(name, data, content_type=content_type)

    def test_verified_member_uploads_image(self):
        self.client.force_authenticate(self.author)
        resp = self.client.post("/activities/activities/upload_image/", {"image": self._img()})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("url", resp.data)

    def test_unverified_cannot_upload(self):
        self.client.force_authenticate(self.visitor)
        resp = self.client.post("/activities/activities/upload_image/", {"image": self._img()})
        self.assertEqual(resp.status_code, 403)

    def test_rejects_non_image(self):
        self.client.force_authenticate(self.author)
        resp = self.client.post(
            "/activities/activities/upload_image/",
            {"image": SimpleUploadedFile("a.txt", b"hi", content_type="text/plain")},
        )
        self.assertEqual(resp.status_code, 400)


class DeliberationVotingTest(TestCase):
    """T2：众议投票（自定义选项、K 选、不可改、惰性结算、公开计票）。"""

    def setUp(self):
        self.author = grant_verification(User.objects.create_user(username="author", password="x"))
        self.m1 = grant_verification(User.objects.create_user(username="m1", password="x"))
        self.m2 = grant_verification(User.objects.create_user(username="m2", password="x"))
        self.visitor = User.objects.create_user(username="visitor", password="x")  # 未验证
        self.client = APIClient()

    def _create(self, user, **payload):
        defaults = {"type": "deliberation", "title": "去哪团建", "body": "<p>x</p>",
                    "option_texts": ["A", "B", "C"]}
        defaults.update(payload)
        return _json(self.client, "post", "/activities/activities/", user, defaults)

    def _vote(self, user, activity_id, option_ids):
        return _json(self.client, "post", f"/activities/activities/{activity_id}/vote/", user,
                     {"option_ids": option_ids})

    def _opt(self, resp, idx):
        return resp.data["options"][idx]["id"]

    # ---- 创建（自定义选项 + K）----

    def test_create_with_options_and_default_end(self):
        resp = self._create(self.author, max_choices_per_voter=1)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["status"], "open")
        self.assertEqual([o["text"] for o in resp.data["options"]], ["A", "B", "C"])
        self.assertEqual(resp.data["max_choices_per_voter"], 1)
        self.assertIsNotNone(resp.data["end_at"])  # 默认 +3d

    def test_create_requires_at_least_two_options(self):
        resp = self._create(self.author, option_texts=["仅一个"])
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_k_above_option_count(self):
        resp = self._create(self.author, option_texts=["A", "B"], max_choices_per_voter=3)
        self.assertEqual(resp.status_code, 400)

    # ---- 投票（K=1 / K>1 / 不可改）----

    def test_k1_one_choice_only(self):
        a = self._create(self.author, max_choices_per_voter=1)
        aid, oa, ob = a.data["id"], self._opt(a, 0), self._opt(a, 1)
        # K=1 时选多项被拒
        self.assertEqual(self._vote(self.m1, aid, [oa, ob]).status_code, 400)
        # 选一项成功
        resp = self._vote(self.m1, aid, [oa])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["my_selections"], [oa])

    def test_k2_multi_choice(self):
        a = self._create(self.author, max_choices_per_voter=2)
        aid, oa, ob, oc = a.data["id"], self._opt(a, 0), self._opt(a, 1), self._opt(a, 2)
        resp = self._vote(self.m1, aid, [oa, ob])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.data["my_selections"]), {oa, ob})
        # 超过 K 被拒
        self.assertEqual(self._vote(self.m2, aid, [oa, ob, oc]).status_code, 400)

    def test_ballot_immutable(self):
        a = self._create(self.author)
        aid, oa = a.data["id"], self._opt(a, 0)
        self.assertEqual(self._vote(self.m1, aid, [oa]).status_code, 200)
        self.assertEqual(self._vote(self.m1, aid, [oa]).status_code, 400)  # 已投，不可改

    def test_visitor_cannot_vote(self):
        a = self._create(self.author)
        resp = self._vote(self.visitor, a.data["id"], [self._opt(a, 0)])
        self.assertEqual(resp.status_code, 403)

    def test_invalid_option_rejected(self):
        a = self._create(self.author)
        self.assertEqual(self._vote(self.m1, a.data["id"], [999999]).status_code, 400)

    def test_duplicate_option_rejected(self):
        a = self._create(self.author, max_choices_per_voter=2)
        oa = self._opt(a, 0)
        self.assertEqual(self._vote(self.m1, a.data["id"], [oa, oa]).status_code, 400)

    def test_cannot_vote_on_collection(self):
        c = _json(self.client, "post", "/activities/activities/", self.author,
                  {"type": "collection", "title": "征", "body": "<p>x</p>"})
        self.assertEqual(self._vote(self.m1, c.data["id"], [1]).status_code, 400)

    # ---- 公开计票 ----

    def test_public_tally_and_voters_visible(self):
        a = self._create(self.author, max_choices_per_voter=2)
        aid, oa, ob = a.data["id"], self._opt(a, 0), self._opt(a, 1)
        self._vote(self.m1, aid, [oa])
        self._vote(self.m2, aid, [oa, ob])
        resp = _json(self.client, "get", f"/activities/activities/{aid}/", self.author)
        counts = {o["id"]: o["vote_count"] for o in resp.data["options"]}
        self.assertEqual(counts[oa], 2)
        self.assertEqual(counts[ob], 1)
        self.assertEqual(resp.data["total_ballots"], 2)
        # 公开：可见谁投了什么
        self.assertEqual(len(resp.data["ballots"]), 2)
        self.assertEqual({b["voter"]["id"] for b in resp.data["ballots"]}, {self.m1.pk, self.m2.pk})

    # ---- 惰性结算 ----

    def test_auto_close_on_end_at_blocks_voting(self):
        a = self._create(self.author)
        aid, oa = a.data["id"], self._opt(a, 0)
        Activity.objects.filter(pk=aid).update(end_at=timezone.now() - timedelta(minutes=1))
        _json(self.client, "get", f"/activities/activities/{aid}/", self.author)  # 触发惰性结算
        resp = _json(self.client, "get", f"/activities/activities/{aid}/", self.author)
        self.assertEqual(resp.data["status"], "closed")
        self.assertEqual(self._vote(self.m1, aid, [oa]).status_code, 400)  # closed 后被拒


class SecretBallotAndCloseTest(TestCase):
    """T3：秘密投票（个人明细仅超管可见）+ 提前关闭。"""

    def setUp(self):
        self.author = grant_verification(User.objects.create_user(username="author", password="x"))
        self.m1 = grant_verification(User.objects.create_user(username="m1", password="x"))
        self.super = User.objects.create_superuser(username="super", password="x", email="s@e.com")
        self.client = APIClient()

    def _make(self, user, secret=False):
        return _json(self.client, "post", "/activities/activities/", user, {
            "type": "deliberation", "title": "x", "body": "<p>x</p>",
            "option_texts": ["A", "B"], "max_choices_per_voter": 1,
            "is_secret_ballot": secret,
        })

    def _vote(self, user, aid, oid):
        return _json(self.client, "post", f"/activities/activities/{aid}/vote/", user, {"option_ids": [oid]})

    def test_secret_hides_voters_from_member_but_keeps_aggregate(self):
        a = self._make(self.author, secret=True)
        aid, oa = a.data["id"], a.data["options"][0]["id"]
        self.assertEqual(self._vote(self.m1, aid, oa).status_code, 200)
        resp = _json(self.client, "get", f"/activities/activities/{aid}/", self.m1)
        self.assertIsNone(resp.data["ballots"])          # 个人明细不可见
        self.assertEqual(resp.data["total_ballots"], 1)  # 聚合可见
        self.assertEqual(resp.data["options"][0]["vote_count"], 1)
        self.assertEqual(resp.data["my_selections"], [oa])  # 自己的选择仍可见

    def test_secret_hides_voters_from_creator(self):
        a = self._make(self.author, secret=True)
        aid, oa = a.data["id"], a.data["options"][0]["id"]
        self._vote(self.m1, aid, oa)
        resp = _json(self.client, "get", f"/activities/activities/{aid}/", self.author)
        self.assertIsNone(resp.data["ballots"])  # 发起人也看不到个人明细

    def test_secret_visible_to_superuser(self):
        a = self._make(self.author, secret=True)
        aid, oa = a.data["id"], a.data["options"][0]["id"]
        self._vote(self.m1, aid, oa)
        resp = _json(self.client, "get", f"/activities/activities/{aid}/", self.super)
        self.assertIsNotNone(resp.data["ballots"])
        self.assertEqual(len(resp.data["ballots"]), 1)

    def test_public_shows_voters(self):
        a = self._make(self.author, secret=False)
        aid, oa = a.data["id"], a.data["options"][0]["id"]
        self._vote(self.m1, aid, oa)
        resp = _json(self.client, "get", f"/activities/activities/{aid}/", self.m1)
        self.assertIsNotNone(resp.data["ballots"])
        self.assertEqual(len(resp.data["ballots"]), 1)

    def test_creator_can_early_close(self):
        a = self._make(self.author)
        resp = _json(self.client, "post", f"/activities/activities/{a.data['id']}/close/", self.author)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "closed")

    def test_other_cannot_early_close(self):
        a = self._make(self.author)
        resp = _json(self.client, "post", f"/activities/activities/{a.data['id']}/close/", self.m1)
        self.assertEqual(resp.status_code, 403)

    def test_close_blocks_further_voting(self):
        a = self._make(self.author)
        aid, oa = a.data["id"], a.data["options"][0]["id"]
        _json(self.client, "post", f"/activities/activities/{aid}/close/", self.author)
        self.assertEqual(self._vote(self.m1, aid, oa).status_code, 400)


class CollectionSubmissionTest(TestCase):
    """T4：征集投稿（一人一作品、提交即锁定、上传配置校验、满额自动关闭）。"""

    def setUp(self):
        self.author = grant_verification(User.objects.create_user(username="author", password="x"))
        self.m1 = grant_verification(User.objects.create_user(username="m1", password="x"))
        self.m2 = grant_verification(User.objects.create_user(username="m2", password="x"))
        self.visitor = User.objects.create_user(username="visitor", password="x")  # 未验证
        self.client = APIClient()

    def _collection(self, user, **cfg):
        payload = {"type": "collection", "title": "征logo", "body": "<p>x</p>"}
        payload.update(cfg)
        return _json(self.client, "post", "/activities/activities/", user, payload)

    def _file(self, name="a.png", data=b"x", content_type="image/png"):
        return SimpleUploadedFile(name, data, content_type=content_type)

    def _submit(self, user, cid, files):
        self.client.force_authenticate(user)
        return self.client.post(f"/activities/activities/{cid}/submit/", {"files": files})

    def test_submit_one_work_multiple_files(self):
        c = self._collection(self.author, allowed_extensions=".png,.jpg", max_files_per_submission=3)
        resp = self._submit(self.m1, c.data["id"], [self._file("a.png"), self._file("b.png")])
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["my_submission"]["files"]), 2)
        self.assertEqual(resp.data["my_submission"]["review_status"], "pending")

    def test_one_person_one_submission(self):
        cid = self._collection(self.author).data["id"]
        self.assertEqual(self._submit(self.m1, cid, [self._file()]).status_code, 201)
        self.assertEqual(self._submit(self.m1, cid, [self._file("c.png")]).status_code, 400)

    def test_too_many_files_rejected(self):
        cid = self._collection(self.author, max_files_per_submission=2).data["id"]
        resp = self._submit(self.m1, cid, [self._file("a.png"), self._file("b.png"), self._file("c.png")])
        self.assertEqual(resp.status_code, 400)

    def test_disallowed_extension_rejected(self):
        cid = self._collection(self.author, allowed_extensions=".png").data["id"]
        # 全局禁用后缀
        self.assertEqual(
            self._submit(self.m1, cid, [self._file("a.exe", b"MZ", "application/x-msdownload")]).status_code, 400
        )
        # 非允许后缀（.txt 不在 .png 白名单）
        self.assertEqual(
            self._submit(self.m1, cid, [self._file("a.txt", b"hi", "text/plain")]).status_code, 400
        )

    def test_file_size_limit_enforced(self):
        cid = self._collection(
            self.author, allowed_extensions=".bin", max_file_size=100
        ).data["id"]
        resp = self._submit(self.m1, cid, [self._file("big.bin", b"x" * 200, "application/octet-stream")])
        self.assertEqual(resp.status_code, 400)

    def test_visitor_cannot_submit(self):
        cid = self._collection(self.author).data["id"]
        self.assertEqual(self._submit(self.visitor, cid, [self._file()]).status_code, 403)

    def test_cap_auto_closes_collection(self):
        cid = self._collection(self.author, max_submissions=1).data["id"]
        resp = self._submit(self.m1, cid, [self._file()])
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["status"], "reviewing")  # 满额自动 collecting→reviewing
        # 第二人投稿被拒（已 reviewing）
        self.assertEqual(self._submit(self.m2, cid, [self._file()]).status_code, 400)

    def test_reviewer_sees_all_others_see_only_accepted(self):
        cid = self._collection(self.author).data["id"]
        self._submit(self.m1, cid, [self._file()])  # m1 投了（pending）
        # 非复审者 m2：submissions 只见录用（暂无）→ 空
        self.assertEqual(_json(self.client, "get", f"/activities/activities/{cid}/", self.m2).data["submissions"], [])
        # 提交者 m1：submissions 同样只见录用（空），但 my_submission 有自己的
        resp = _json(self.client, "get", f"/activities/activities/{cid}/", self.m1)
        self.assertEqual(resp.data["submissions"], [])
        self.assertIsNotNone(resp.data["my_submission"])
        # 复审者（发起人）：submissions 见全部（含 m1 的 pending）
        resp = _json(self.client, "get", f"/activities/activities/{cid}/", self.author)
        self.assertEqual(len(resp.data["submissions"]), 1)

    def test_cannot_submit_to_deliberation(self):
        d = _json(self.client, "post", "/activities/activities/", self.author,
                  {"type": "deliberation", "title": "x", "body": "<p>x</p>", "option_texts": ["A", "B"]})
        self.assertEqual(self._submit(self.m1, d.data["id"], [self._file()]).status_code, 400)


class CollectionReviewTest(TestCase):
    """T5：征集复审（录用/退稿、对象级权限、滚动复审、公开展示、提交者见结果）。"""

    def setUp(self):
        self.author = grant_verification(User.objects.create_user(username="author", password="x"))
        self.reviewer = grant_verification(User.objects.create_user(username="reviewer", password="x"))
        perm = Permission.objects.get(content_type__app_label="activities", codename="review_collection")
        self.reviewer.user_permissions.add(perm)
        self.m1 = grant_verification(User.objects.create_user(username="m1", password="x"))
        self.outsider = grant_verification(User.objects.create_user(username="out", password="x"))
        self.client = APIClient()

    def _setup(self):
        """发起人建征集 → m1 投一作品（pending），返回活动 id。"""
        c = _json(self.client, "post", "/activities/activities/", self.author,
                  {"type": "collection", "title": "征", "body": "<p>x</p>"})
        cid = c.data["id"]
        self.client.force_authenticate(self.m1)
        self.client.post(
            f"/activities/activities/{cid}/submit/",
            {"files": [SimpleUploadedFile("a.png", b"x", content_type="image/png")]},
        )
        return cid

    def _sub_id(self, cid):
        resp = _json(self.client, "get", f"/activities/activities/{cid}/", self.author)
        return resp.data["submissions"][0]["id"]

    def _review(self, user, cid, sub_id, decision, comment=""):
        return _json(self.client, "post", f"/activities/activities/{cid}/review_submission/", user,
                     {"submission_id": sub_id, "decision": decision, "comment": comment})

    def test_creator_can_accept(self):
        cid = self._setup()
        r = self._review(self.author, cid, self._sub_id(cid), "accepted", "好")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["submissions"][0]["review_status"], "accepted")
        self.assertEqual(r.data["submissions"][0]["review_comment"], "好")

    def test_perm_holder_can_review(self):
        cid = self._setup()
        r = self._review(self.reviewer, cid, self._sub_id(cid), "rejected", "不合")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["submissions"][0]["review_status"], "rejected")

    def test_outsider_cannot_review(self):
        cid = self._setup()
        self.assertEqual(self._review(self.outsider, cid, self._sub_id(cid), "accepted").status_code, 403)

    def test_rolling_review_during_collecting(self):
        # 未关闭（仍 collecting）即可复审（滚动复审）
        cid = self._setup()
        detail = _json(self.client, "get", f"/activities/activities/{cid}/", self.author).data
        self.assertEqual(detail["status"], "collecting")
        r = self._review(self.author, cid, detail["submissions"][0]["id"], "accepted")
        self.assertEqual(r.status_code, 200)

    def test_accepted_visible_in_public_showcase(self):
        cid = self._setup()
        self._review(self.author, cid, self._sub_id(cid), "accepted")
        resp = _json(self.client, "get", f"/activities/activities/{cid}/", self.outsider)
        self.assertEqual(len(resp.data["submissions"]), 1)  # 录用作品对非复审者可见
        self.assertEqual(resp.data["submissions"][0]["review_status"], "accepted")

    def test_submitter_sees_own_result(self):
        cid = self._setup()
        self._review(self.author, cid, self._sub_id(cid), "rejected", "重做")
        resp = _json(self.client, "get", f"/activities/activities/{cid}/", self.m1)
        self.assertEqual(resp.data["my_submission"]["review_status"], "rejected")
        self.assertEqual(resp.data["my_submission"]["review_comment"], "重做")

    def test_invalid_decision_rejected(self):
        cid = self._setup()
        self.assertEqual(self._review(self.author, cid, self._sub_id(cid), "maybe").status_code, 400)

    def test_cannot_review_deliberation(self):
        d = _json(self.client, "post", "/activities/activities/", self.author,
                  {"type": "deliberation", "title": "x", "body": "<p>x</p>", "option_texts": ["A", "B"]})
        r = _json(self.client, "post", f"/activities/activities/{d.data['id']}/review_submission/",
                  self.author, {"submission_id": 1, "decision": "accepted"})
        self.assertEqual(r.status_code, 400)


class CollectionReviewOptionalTest(TestCase):
    """#51：征集复审改为可选——关闭复审后跳过 reviewing，作品提交即公开、不接受复审。"""

    def setUp(self):
        self.author = grant_verification(User.objects.create_user(username="author", password="x"))
        self.m1 = grant_verification(User.objects.create_user(username="m1", password="x"))
        self.outsider = grant_verification(User.objects.create_user(username="out", password="x"))
        self.client = APIClient()

    def _collection(self, review_enabled, **cfg):
        payload = {"type": "collection", "title": "征", "body": "<p>x</p>",
                   "review_enabled": review_enabled}
        payload.update(cfg)
        return _json(self.client, "post", "/activities/activities/", self.author, payload)

    def _file(self, name="a.png"):
        return SimpleUploadedFile(name, b"x", content_type="image/png")

    def _submit(self, user, cid):
        self.client.force_authenticate(user)
        return self.client.post(f"/activities/activities/{cid}/submit/", {"files": [self._file()]})

    def test_default_review_enabled_true(self):
        c = self._collection(review_enabled=True)
        self.assertEqual(c.status_code, 201)
        self.assertTrue(c.data["review_enabled"])

    def test_submissions_public_without_review(self):
        # 关闭复审：成员一投稿，局外人立即可见（不必录用）
        cid = self._collection(review_enabled=False).data["id"]
        self._submit(self.m1, cid)
        resp = _json(self.client, "get", f"/activities/activities/{cid}/", self.outsider)
        self.assertEqual(len(resp.data["submissions"]), 1)  # pending 也对外可见
        self.assertEqual(resp.data["submissions"][0]["review_status"], "pending")

    def test_close_skips_reviewing_when_disabled(self):
        cid = self._collection(review_enabled=False).data["id"]
        r = _json(self.client, "post", f"/activities/activities/{cid}/close/", self.author)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "archived")  # 直接 collecting→archived

    def test_close_goes_reviewing_when_enabled(self):
        cid = self._collection(review_enabled=True).data["id"]
        r = _json(self.client, "post", f"/activities/activities/{cid}/close/", self.author)
        self.assertEqual(r.data["status"], "reviewing")

    def test_cap_skips_reviewing_when_disabled(self):
        cid = self._collection(review_enabled=False, max_submissions=1).data["id"]
        r = self._submit(self.m1, cid)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["status"], "archived")  # 满额 collecting→archived

    def test_review_rejected_when_disabled(self):
        cid = self._collection(review_enabled=False).data["id"]
        self._submit(self.m1, cid)
        sub_id = _json(self.client, "get", f"/activities/activities/{cid}/", self.author).data["submissions"][0]["id"]
        r = _json(self.client, "post", f"/activities/activities/{cid}/review_submission/", self.author,
                  {"submission_id": sub_id, "decision": "accepted"})
        self.assertEqual(r.status_code, 400)


class SchedulingTest(TestCase):
    """开始时间 + 待开始状态：排期、惰性自动开放、待开始可改/开放后锁、start<end 校验。"""

    def setUp(self):
        self.author = grant_verification(User.objects.create_user(username="author", password="x"))
        self.m1 = grant_verification(User.objects.create_user(username="m1", password="x"))
        self.client = APIClient()

    def _future(self, days=2):
        return (timezone.now() + timedelta(days=days)).isoformat()

    def _past(self, days=1):
        return (timezone.now() - timedelta(days=days)).isoformat()

    def test_future_start_creates_scheduled(self):
        resp = _json(self.client, "post", "/activities/activities/", self.author, {
            "type": "deliberation", "title": "x", "body": "<p>x</p>",
            "option_texts": ["A", "B"], "start_at": self._future(),
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["status"], "scheduled")

    def test_no_start_opens_immediately(self):
        resp = _json(self.client, "post", "/activities/activities/", self.author,
                     {"type": "collection", "title": "x", "body": "<p>x</p>"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["status"], "collecting")  # 创建即开

    def test_past_start_opens_immediately(self):
        resp = _json(self.client, "post", "/activities/activities/", self.author, {
            "type": "deliberation", "title": "x", "body": "<p>x</p>",
            "option_texts": ["A", "B"], "start_at": self._past(),
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["status"], "open")

    def test_auto_open_on_start_at(self):
        resp = _json(self.client, "post", "/activities/activities/", self.author, {
            "type": "deliberation", "title": "x", "body": "<p>x</p>",
            "option_texts": ["A", "B"], "start_at": self._future(),
        })
        aid = resp.data["id"]
        Activity.objects.filter(pk=aid).update(start_at=timezone.now() - timedelta(minutes=1))
        _json(self.client, "get", f"/activities/activities/{aid}/", self.author)  # 触发惰性开放
        self.assertEqual(
            _json(self.client, "get", f"/activities/activities/{aid}/", self.author).data["status"], "open"
        )

    def test_scheduled_blocks_vote_and_submit(self):
        # 众议 scheduled → 投票被拒
        d = _json(self.client, "post", "/activities/activities/", self.author, {
            "type": "deliberation", "title": "x", "body": "<p>x</p>",
            "option_texts": ["A", "B"], "start_at": self._future(),
        })
        opt = d.data["options"][0]["id"]
        self.assertEqual(
            _json(self.client, "post", f"/activities/activities/{d.data['id']}/vote/", self.m1,
                  {"option_ids": [opt]}).status_code,
            400,
        )
        # 征集 scheduled → 投稿被拒
        c = _json(self.client, "post", "/activities/activities/", self.author, {
            "type": "collection", "title": "x", "body": "<p>x</p>", "start_at": self._future(),
        })
        self.client.force_authenticate(self.m1)
        r = self.client.post(
            f"/activities/activities/{c.data['id']}/submit/",
            {"files": [SimpleUploadedFile("a.png", b"x", content_type="image/png")]},
        )
        self.assertEqual(r.status_code, 400)

    def test_edit_allowed_while_scheduled(self):
        d = _json(self.client, "post", "/activities/activities/", self.author, {
            "type": "deliberation", "title": "x", "body": "<p>x</p>",
            "option_texts": ["A", "B"], "start_at": self._future(),
        })
        r = _json(self.client, "patch", f"/activities/activities/{d.data['id']}/", self.author,
                  {"title": "改标题", "option_texts": ["A", "B", "C"]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["title"], "改标题")
        self.assertEqual(len(r.data["options"]), 3)  # 选项替换

    def test_edit_locked_after_open(self):
        # 创建即开 → open；开放后改 → 403
        d = _json(self.client, "post", "/activities/activities/", self.author, {
            "type": "deliberation", "title": "x", "body": "<p>x</p>", "option_texts": ["A", "B"],
        })
        r = _json(self.client, "patch", f"/activities/activities/{d.data['id']}/", self.author, {"title": "改"})
        self.assertEqual(r.status_code, 403)

    def test_start_after_end_rejected(self):
        r = _json(self.client, "post", "/activities/activities/", self.author, {
            "type": "deliberation", "title": "x", "body": "<p>x</p>",
            "option_texts": ["A", "B"],
            "start_at": self._future(days=5), "end_at": self._future(days=1),
        })
        self.assertEqual(r.status_code, 400)


class AutoCloseOnFullVoteTest(TestCase):
    """全员投完即提前结算：众议票数达已验证成员数时自动 closed。"""

    def setUp(self):
        # 本测试下已验证成员恰好 = author + m1 = 2 人（TestCase 隔离，无其他用户）
        self.author = grant_verification(User.objects.create_user(username="author", password="x"))
        self.m1 = grant_verification(User.objects.create_user(username="m1", password="x"))
        self.client = APIClient()

    def _make(self):
        return _json(self.client, "post", "/activities/activities/", self.author, {
            "type": "deliberation", "title": "x", "body": "<p>x</p>",
            "option_texts": ["A", "B"], "max_choices_per_voter": 1,
        })

    def _vote(self, user, aid, oid):
        return _json(self.client, "post", f"/activities/activities/{aid}/vote/", user, {"option_ids": [oid]})

    def test_not_closed_until_all_voted(self):
        a = self._make()
        aid, oa = a.data["id"], a.data["options"][0]["id"]
        r = self._vote(self.m1, aid, oa)  # 1/2 投票
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "open")  # 仍未全员

    def test_closed_when_all_voted(self):
        a = self._make()
        aid, oa = a.data["id"], a.data["options"][0]["id"]
        self._vote(self.m1, aid, oa)
        r = self._vote(self.author, aid, oa)  # 2/2 全员投完
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "closed")  # 自动结算
        # closed 后再投被拒
        self.assertEqual(self._vote(self.m1, aid, a.data["options"][1]["id"]).status_code, 400)


class ExhibitionTest(TestCase):
    """展示：创建时录入并冻结展品（每展品一投票选项）+ 展品投票（1..K）+ 三态赞踩 + 生命周期。"""

    def setUp(self):
        self.curator = grant_verification(User.objects.create_user(username="curator", password="x"))
        self.member = grant_verification(User.objects.create_user(username="member", password="x"))
        self.m2 = grant_verification(User.objects.create_user(username="m2", password="x"))
        self.visitor = User.objects.create_user(username="visitor", password="x")  # 未验证
        self.client = APIClient()

    def _img(self, name="a.png", data=b"x", ct="image/png"):
        return SimpleUploadedFile(name, data, content_type=ct)

    def _create(self, user, exhibits, **scalar):
        """展品在创建时录入。exhibits: [(title, [SimpleUploadedFile...]), ...]

        默认沿用现状（启用投票：每展品一选项）；传 voting_enabled="false" 可创建纯陈列展示。
        """
        data = {"type": "exhibition", "title": "影展", "body": "<p>x</p>", "voting_enabled": "true"}
        data.update(scalar)
        data["exhibit_count"] = str(len(exhibits))
        for i, (title, files) in enumerate(exhibits):
            if title:
                data[f"exhibit_title_{i}"] = title
            data[f"exhibit_files_{i}"] = files
        self.client.force_authenticate(user)
        return self.client.post("/activities/activities/", data=data)

    def _create_empty(self, user, voting_enabled=False, scheduled=False, **kw):
        """直接用 ORM 建一个 0 展品的展示(避开 multipart 创建路径,T5 前创建仍强制展品)。

        scheduled=True → status='scheduled'(可布展);否则 'open'。
        """
        from datetime import datetime, timedelta, timezone as dtz
        from .models import Activity
        a = Activity.objects.create(
            type="exhibition", status="scheduled" if scheduled else "open",
            title=kw.get("title", "影展"), body=kw.get("body", "<p>x</p>"),
            creator=user, voting_enabled=voting_enabled,
            max_choices_per_voter=kw.get("max_choices_per_voter", 1),
            start_at=(datetime.now(dtz.utc) + timedelta(days=1)) if scheduled else None,
        )
        return a

    def _add_exhibit(self, user, aid, title="", files=None):
        files = files if files is not None else [self._img()]
        fd = {}
        if title:
            fd["title"] = title
        for f in files:
            fd.setdefault("files", []).append(f)
        self.client.force_authenticate(user)
        return self.client.post(f"/activities/activities/{aid}/add_exhibit/", data=fd)

    def _vote(self, user, aid, option_ids):
        return _json(self.client, "post", f"/activities/activities/{aid}/vote/", user,
                     {"option_ids": option_ids})

    def _rate(self, user, aid, eid, choice):
        return _json(self.client, "post", f"/activities/activities/{aid}/rate/", user,
                     {"exhibit_id": eid, "choice": choice})

    def _make_collection_with_submissions(self, owner, n=2):
        """建一个征集并提交 n 个作品(含文件),返回 (activity_id, [submission_id])。"""
        self.client.force_authenticate(owner)
        c = self.client.post("/activities/activities/", data={
            "type": "collection", "title": "征", "body": "<p>x</p>",
            "review_enabled": "false",  # 跳过复审,作品直接公开可见
        }, content_type="application/json")
        cid = c.data["id"]
        sub_ids = []
        submitters = [self.member, self.m2]
        for i in range(n):
            fd = {"files": [self._img(f"s{i}.png")]}
            self.client.force_authenticate(submitters[i % len(submitters)])
            r = self.client.post(f"/activities/activities/{cid}/submit/", data=fd)
            sub_ids.append(r.data["my_submission"]["id"])
        return cid, sub_ids

    @staticmethod
    def _ex(resp, idx=0):
        return resp.data["exhibits"][idx]

    # ---- 创建（展品录入即冻结）----

    def test_create_with_exhibits(self):
        r = self._create(self.curator, [("作品A", [self._img(), self._img("b.png")]), ("作品B", [self._img()])])
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["status"], "open")
        self.assertEqual(len(r.data["exhibits"]), 2)
        ex0 = r.data["exhibits"][0]
        self.assertEqual(ex0["title"], "作品A")
        self.assertEqual(len(ex0["files"]), 2)
        self.assertIsNotNone(ex0["vote_option_id"])  # 每展品一个投票选项
        self.assertEqual(ex0["vote_count"], 0)
        self.assertIsNone(r.data["options"])  # 展示的选项即展品，options 不再单独输出

    def test_requires_at_least_one_exhibit(self):
        self.assertEqual(self._create(self.curator, []).status_code, 400)

    def test_exhibit_requires_file(self):
        self.assertEqual(self._create(self.curator, [("作品A", [])]).status_code, 400)

    def test_k_above_exhibit_count_rejected(self):
        r = self._create(self.curator, [("A", [self._img()]), ("B", [self._img()])],
                         max_choices_per_voter=3)
        self.assertEqual(r.status_code, 400)

    def test_visitor_cannot_create(self):
        r = self._create(self.visitor, [("A", [self._img()])])
        self.assertEqual(r.status_code, 403)

    # ---- 纯陈列（voting_enabled=false：不建选项，仅展品+文件）----

    def test_create_voting_disabled_builds_no_options(self):
        r = self._create(
            self.curator,
            [("A", [self._img()]), ("B", [self._img()])],
            voting_enabled="false",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["status"], "open")
        self.assertEqual(r.data["voting_enabled"], False)
        self.assertEqual(len(r.data["exhibits"]), 2)
        # 不启用投票：展品照常创建，但不绑定投票选项
        self.assertIsNone(r.data["exhibits"][0]["vote_option_id"])
        self.assertIsNone(r.data["exhibits"][1]["vote_option_id"])
        self.assertEqual(len(r.data["exhibits"][0]["files"]), 1)

    def test_create_voting_disabled_ignores_k(self):
        # 纯陈列展示：不投票，K 值无意义，不应因 K 超过展品数被拒
        r = self._create(
            self.curator,
            [("A", [self._img()]), ("B", [self._img()])],
            voting_enabled="false", max_choices_per_voter=9,
        )
        self.assertEqual(r.status_code, 201)

    # ---- 详情页布展:add_exhibit(待开始期手动加展品)----

    def test_add_exhibit_creates_exhibit_with_files(self):
        aid = self._create_empty(self.curator, voting_enabled=False, scheduled=True).id
        r = self._add_exhibit(self.curator, aid, title="作品A",
                               files=[self._img(), self._img("b.png")])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["exhibits"]), 1)
        e = r.data["exhibits"][0]
        self.assertEqual(e["title"], "作品A")
        self.assertEqual(len(e["files"]), 2)
        self.assertIsNone(e["vote_option_id"])  # 未启用投票:无选项

    def test_add_exhibit_voting_enabled_builds_option(self):
        aid = self._create_empty(self.curator, voting_enabled=True,
                                 max_choices_per_voter=1, scheduled=True).id
        r = self._add_exhibit(self.curator, aid, title="X")
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.data["exhibits"][0]["vote_option_id"])

    def test_add_exhibit_requires_file(self):
        aid = self._create_empty(self.curator, scheduled=True).id
        r = self._add_exhibit(self.curator, aid, files=[])
        self.assertEqual(r.status_code, 400)

    def test_add_exhibit_blocked_when_open(self):
        # 未排期 → open → 不可布展
        aid = self._create_empty(self.curator, scheduled=False).id
        r = self._add_exhibit(self.curator, aid, title="A")
        self.assertEqual(r.status_code, 400)

    def test_add_exhibit_non_curator_forbidden(self):
        aid = self._create_empty(self.curator, scheduled=True).id
        r = self._add_exhibit(self.member, aid, title="A")
        self.assertEqual(r.status_code, 403)

    def test_add_exhibit_scheduled_allowed(self):
        aid = self._create_empty(self.curator, scheduled=True).id
        r = self._add_exhibit(self.curator, aid, title="A")
        self.assertEqual(r.status_code, 200)

    # ---- 展品删除（delete_exhibit）----

    def _delete_exhibit(self, user, aid, eid):
        self.client.force_authenticate(user)
        return self.client.post(f"/activities/activities/{aid}/delete_exhibit/",
                                data={"exhibit_id": eid})

    def test_delete_exhibit_removes_it_and_option(self):
        aid = self._create_empty(self.curator, voting_enabled=True,
                                 max_choices_per_voter=1, scheduled=True).id
        self._add_exhibit(self.curator, aid, title="A")
        eid = self.client.get(f"/activities/activities/{aid}/").data["exhibits"][0]["id"]
        r = self._delete_exhibit(self.curator, aid, eid)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["exhibits"]), 0)
        from .models import VoteOption
        self.assertEqual(VoteOption.objects.filter(activity_id=aid).count(), 0)

    def test_delete_exhibit_open_blocked(self):
        # open 态(未排期)拒绝——状态门在「展品不存在」之前
        aid = self._create_empty(self.curator, voting_enabled=True, scheduled=False).id
        r = self._delete_exhibit(self.curator, aid, 999)
        self.assertEqual(r.status_code, 400)

    # ---- 展品修改（update_exhibit）----

    def _update_exhibit(self, user, aid, eid, title=None, files=None):
        fd = {"exhibit_id": str(eid)}
        if title is not None:
            fd["title"] = title
        if files:
            for f in files:
                fd.setdefault("files", []).append(f)
        self.client.force_authenticate(user)
        return self.client.post(f"/activities/activities/{aid}/update_exhibit/",
                                data=fd, format="multipart")

    def test_update_exhibit_renames_and_syncs_option(self):
        aid = self._create_empty(self.curator, voting_enabled=True,
                                 max_choices_per_voter=1, scheduled=True).id
        self._add_exhibit(self.curator, aid, title="旧名")
        eid = self.client.get(f"/activities/activities/{aid}/").data["exhibits"][0]["id"]
        r = self._update_exhibit(self.curator, aid, eid, title="新名")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["exhibits"][0]["title"], "新名")
        from .models import VoteOption
        self.assertEqual(VoteOption.objects.get(activity_id=aid).text, "新名")

    def test_update_exhibit_replaces_files(self):
        aid = self._create_empty(self.curator, scheduled=True).id
        self._add_exhibit(self.curator, aid, files=[self._img("a.png"), self._img("b.png")])
        eid = self.client.get(f"/activities/activities/{aid}/").data["exhibits"][0]["id"]
        r = self._update_exhibit(self.curator, aid, eid, files=[self._img("c.png")])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["exhibits"][0]["files"]), 1)
        self.assertEqual(r.data["exhibits"][0]["files"][0]["file_name"], "c.png")

    # ---- 展品投票（每展品一选项）----

    def test_vote_k1_single_exhibit(self):
        ex = self._create(self.curator, [("A", [self._img()]), ("B", [self._img()])],
                          max_choices_per_voter=1)
        aid = ex.data["id"]
        oa, ob = self._ex(ex, 0)["vote_option_id"], self._ex(ex, 1)["vote_option_id"]
        # K=1：选两个展品被拒
        self.assertEqual(self._vote(self.member, aid, [oa, ob]).status_code, 400)
        # 选一个 → 成功
        r = self._vote(self.member, aid, [oa])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["my_selections"], [oa])
        self.assertEqual(self._ex(r, 0)["vote_count"], 1)  # 展品 A 得 1 票

    def test_vote_k2_multi_exhibits(self):
        ex = self._create(self.curator, [("A", [self._img()]), ("B", [self._img()]), ("C", [self._img()])],
                          max_choices_per_voter=2)
        aid = ex.data["id"]
        oa, ob, oc = (self._ex(ex, i)["vote_option_id"] for i in range(3))
        r = self._vote(self.member, aid, [oa, ob])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.data["my_selections"]), {oa, ob})
        # 超过 K 被拒
        self.assertEqual(self._vote(self.m2, aid, [oa, ob, oc]).status_code, 400)

    def test_ballot_immutable(self):
        ex = self._create(self.curator, [("A", [self._img()]), ("B", [self._img()])])
        aid, oa = ex.data["id"], self._ex(ex)["vote_option_id"]
        self.assertEqual(self._vote(self.member, aid, [oa]).status_code, 200)
        self.assertEqual(self._vote(self.member, aid, [oa]).status_code, 400)  # 已投，不可改

    def test_visitor_cannot_vote(self):
        ex = self._create(self.curator, [("A", [self._img()]), ("B", [self._img()])])
        self.assertEqual(self._vote(self.visitor, ex.data["id"], [self._ex(ex)["vote_option_id"]]).status_code, 403)

    def test_public_tally_per_exhibit(self):
        ex = self._create(self.curator, [("A", [self._img()]), ("B", [self._img()])], max_choices_per_voter=2)
        aid = ex.data["id"]
        oa, ob = self._ex(ex, 0)["vote_option_id"], self._ex(ex, 1)["vote_option_id"]
        self._vote(self.member, aid, [oa])
        self._vote(self.m2, aid, [oa, ob])
        resp = _json(self.client, "get", f"/activities/activities/{aid}/", self.curator)
        counts = {e["vote_option_id"]: e["vote_count"] for e in resp.data["exhibits"]}
        self.assertEqual(counts[oa], 2)
        self.assertEqual(counts[ob], 1)
        self.assertEqual(resp.data["total_ballots"], 2)

    def test_secret_exhibition_hides_ballots(self):
        ex = self._create(self.curator, [("A", [self._img()]), ("B", [self._img()])],
                          max_choices_per_voter=1, is_secret_ballot="true")
        aid, oa = ex.data["id"], self._ex(ex)["vote_option_id"]
        self.assertEqual(self._vote(self.member, aid, [oa]).status_code, 200)
        resp = _json(self.client, "get", f"/activities/activities/{aid}/", self.member)
        self.assertIsNone(resp.data["ballots"])  # 秘密：个人明细不可见
        self.assertEqual(resp.data["total_ballots"], 1)  # 聚合可见
        self.assertEqual(self._ex(resp)["vote_count"], 1)

    # ---- 三态赞踩（与投票并存）----

    def test_rate_three_state(self):
        ex = self._create(self.curator, [("A", [self._img()])])
        aid, eid = ex.data["id"], self._ex(ex)["id"]
        r = self._rate(self.member, aid, eid, "like")
        self.assertEqual(self._ex(r)["my_rating"], "like")
        self.assertEqual(self._ex(r)["like_count"], 1)
        # like 再点 → none
        r = self._rate(self.member, aid, eid, "like")
        self.assertIsNone(self._ex(r)["my_rating"])
        self.assertEqual(self._ex(r)["like_count"], 0)
        # dislike
        r = self._rate(self.member, aid, eid, "dislike")
        self.assertEqual(self._ex(r)["my_rating"], "dislike")
        self.assertEqual(self._ex(r)["dislike_count"], 1)

    def test_rate_mutually_exclusive(self):
        ex = self._create(self.curator, [("A", [self._img()])])
        aid, eid = ex.data["id"], self._ex(ex)["id"]
        self._rate(self.member, aid, eid, "like")
        r = self._rate(self.member, aid, eid, "dislike")
        self.assertEqual(self._ex(r)["my_rating"], "dislike")
        self.assertEqual(self._ex(r)["like_count"], 0)
        self.assertEqual(self._ex(r)["dislike_count"], 1)

    def test_visitor_cannot_rate(self):
        ex = self._create(self.curator, [("A", [self._img()])])
        self.assertEqual(self._rate(self.visitor, ex.data["id"], self._ex(ex)["id"], "like").status_code, 403)

    def test_invalid_rating_choice(self):
        ex = self._create(self.curator, [("A", [self._img()])])
        aid, eid = ex.data["id"], self._ex(ex)["id"]
        self.assertEqual(self._rate(self.member, aid, eid, "meh").status_code, 400)

    # ---- 纯陈列：投票被拒、赞踩照常 ----

    def _create_pure(self):
        return self._create(
            self.curator, [("A", [self._img()]), ("B", [self._img()])],
            voting_enabled="false",
        )

    def test_vote_rejected_when_voting_disabled(self):
        ex = self._create_pure()
        aid = ex.data["id"]
        # 纯陈列展示无选项；即便提交任意选项，投票动作本身就被拒（防御性双保险）
        r = self._vote(self.member, aid, [999999])
        self.assertEqual(r.status_code, 400)
        self.assertIn("投票", r.data["detail"])

    def test_rate_works_when_voting_disabled(self):
        ex = self._create_pure()
        aid, eid = ex.data["id"], self._ex(ex)["id"]
        r = self._rate(self.member, aid, eid, "like")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._ex(r)["my_rating"], "like")
        self.assertEqual(self._ex(r)["like_count"], 1)
        self.assertIsNone(self._ex(r)["vote_option_id"])  # 仍未绑定选项

    def test_detail_omits_vote_data_when_voting_disabled(self):
        ex = self._create_pure()
        aid = ex.data["id"]
        # 给展品点赞，确认赞踩数据存在、但投票相关数据全部缺席
        self._rate(self.member, aid, self._ex(ex)["id"], "like")
        resp = _json(self.client, "get", f"/activities/activities/{aid}/", self.member)
        self.assertEqual(resp.data["voting_enabled"], False)
        self.assertIsNone(resp.data["ballots"])
        self.assertIsNone(resp.data["my_selections"])
        self.assertIsNone(resp.data["total_ballots"])
        self.assertIsNone(resp.data["options"])
        # 展品画廊照常：含赞踩计数与我的评分
        self.assertEqual(len(resp.data["exhibits"]), 2)
        self.assertEqual(self._ex(resp)["like_count"], 1)
        self.assertEqual(self._ex(resp)["my_rating"], "like")

    # ---- 生命周期 ----

    def test_closed_blocks_vote_and_rate(self):
        ex = self._create(self.curator, [("A", [self._img()])])
        aid, eid = ex.data["id"], self._ex(ex)["id"]
        oa = self._ex(ex)["vote_option_id"]
        Activity.objects.filter(pk=aid).update(end_at=timezone.now() - timedelta(minutes=1))
        _json(self.client, "get", f"/activities/activities/{aid}/", self.curator)  # 触发惰性结算
        self.assertEqual(self._vote(self.member, aid, [oa]).status_code, 400)
        self.assertEqual(self._rate(self.member, aid, eid, "like").status_code, 400)

    def test_early_close_exhibition(self):
        ex = self._create(self.curator, [("A", [self._img()])])
        r = _json(self.client, "post", f"/activities/activities/{ex.data['id']}/close/", self.curator)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "closed")

    # ---- 征集导入（从征集勾选任意作品，复制独立副本）----

    def test_import_from_collection_copies_selected(self):
        cid, sub_ids = self._make_collection_with_submissions(self.curator, n=2)
        aid = self._create_empty(self.curator, voting_enabled=False, scheduled=True).id
        self.client.force_authenticate(self.curator)
        r = self.client.post(f"/activities/activities/{aid}/import_from_collection/",
                             data={"collection_id": cid, "submission_ids": sub_ids},
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["exhibits"]), 2)
        files = [f for e in r.data["exhibits"] for f in e["files"]]
        self.assertEqual(len(files), 2)

    def test_import_invalid_collection(self):
        aid = self._create_empty(self.curator, scheduled=True).id
        self.client.force_authenticate(self.curator)
        r = self.client.post(f"/activities/activities/{aid}/import_from_collection/",
                             data={"collection_id": 999999, "submission_ids": []},
                             content_type="application/json")
        self.assertEqual(r.status_code, 404)

    def test_import_is_independent_snapshot(self):
        # 复制成独立副本:原作品附件删了,展品文件仍在
        cid, sub_ids = self._make_collection_with_submissions(self.curator, n=1)
        aid = self._create_empty(self.curator, scheduled=True).id
        self.client.force_authenticate(self.curator)
        self.client.post(f"/activities/activities/{aid}/import_from_collection/",
                         data={"collection_id": cid, "submission_ids": sub_ids},
                         content_type="application/json")
        from .models import Submission
        Submission.objects.get(pk=sub_ids[0]).attachments.all().delete()
        detail = self.client.get(f"/activities/activities/{aid}/").data
        self.assertEqual(len(detail["exhibits"][0]["files"]), 1)
