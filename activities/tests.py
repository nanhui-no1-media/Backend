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
