from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from messaging.models import Conversation, Message, MessageReadStatus


class UnreadCountTest(TestCase):
    """GET /messaging/conversations/unread_count/ —— 驱动顶栏铃铛红点。

    红点应当只在「确实有别人发来、且自己未读的消息」时出现；自己发出的消息
    不计（发送者不会为自己生成 MessageReadStatus）。
    """

    URL = "/messaging/conversations/unread_count/"

    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="secret123")
        self.bob = User.objects.create_user(username="bob", password="secret123")
        self.conv = Conversation.objects.create(conversation_type="private")
        self.conv.participants.set([self.alice, self.bob])
        self.client.login(username="alice", password="secret123")

    def _total(self):
        return self.client.get(self.URL).json()["total"]

    def test_requires_auth(self):
        resp = Client().get(self.URL)
        self.assertIn(resp.status_code, (401, 403))

    def test_zero_when_no_messages(self):
        self.assertEqual(self._total(), 0)

    def test_counts_messages_from_others(self):
        Message.objects.create(conversation=self.conv, sender=self.bob, content="在吗")
        Message.objects.create(conversation=self.conv, sender=self.bob, content="还有个事")
        self.assertEqual(self._total(), 2)

    def test_ignores_own_messages(self):
        # alice 给自己发的不算未读，否则发过消息的人红点永远亮着
        Message.objects.create(conversation=self.conv, sender=self.alice, content="我自己说的")
        Message.objects.create(conversation=self.conv, sender=self.bob, content="回你")
        self.assertEqual(self._total(), 1)

    def test_clears_once_read(self):
        msg = Message.objects.create(conversation=self.conv, sender=self.bob, content="看一下")
        MessageReadStatus.objects.create(message=msg, user=self.alice)
        self.assertEqual(self._total(), 0)

    def test_only_counts_conversations_user_joined(self):
        # alice 不参与的会话里的消息，不计入 alice 的未读
        carol = User.objects.create_user(username="carol", password="secret123")
        other = Conversation.objects.create(conversation_type="private")
        other.participants.set([self.bob, carol])
        Message.objects.create(conversation=other, sender=carol, content="与 alice 无关")
        self.assertEqual(self._total(), 0)


class MessageThreadPaginationTest(TestCase):
    """GET /messaging/conversations/messages/ —— 消息线程倒序分页。

    前端「最新优先 + 向上加载更早」消费信封：page=1 为最新一页（20/页），
    next 非空即还有更早；结果按 created_at 倒序。
    """

    URL = "/messaging/conversations/messages/"
    PAGE_SIZE = 20

    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="secret123")
        self.bob = User.objects.create_user(username="bob", password="secret123")
        self.carol = User.objects.create_user(username="carol", password="secret123")
        self.conv = Conversation.objects.create(conversation_type="private")
        self.conv.participants.set([self.alice, self.bob])
        self.client.login(username="alice", password="secret123")

    def _get(self, conversation_id, page=None):
        url = f"{self.URL}?conversation_id={conversation_id}"
        if page is not None:
            url += f"&page={page}"
        return self.client.get(url)

    def test_requires_auth(self):
        resp = Client().get(f"{self.URL}?conversation_id={self.conv.pk}")
        self.assertIn(resp.status_code, (401, 403))

    def test_missing_conversation_id(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 400)

    def test_non_participant_not_found(self):
        resp = self._get(self.conv.pk + 9999)  # 不存在
        self.assertEqual(resp.status_code, 404)
        # carol 不是参与者，也应 404（视图用 participants=request.user 过滤）
        self.client.logout()
        self.client.login(username="carol", password="secret123")
        resp = self._get(self.conv.pk)
        self.assertEqual(resp.status_code, 404)

    def test_paginated_envelope(self):
        Message.objects.create(conversation=self.conv, sender=self.bob, content="你好")
        resp = self._get(self.conv.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.json().keys()), {"count", "next", "previous", "results"})

    def test_newest_first_and_two_pages(self):
        # 25 条消息：page1 = 最新 20 条，page2 = 最早 5 条
        for i in range(1, 26):
            Message.objects.create(conversation=self.conv, sender=self.bob, content=f"消息{i}")

        page1 = self._get(self.conv.pk, 1).json()
        self.assertEqual(page1["count"], 25)
        self.assertEqual(len(page1["results"]), self.PAGE_SIZE)
        self.assertIsNotNone(page1["next"])
        self.assertIsNone(page1["previous"])
        # 最新在前：首条是最后发的「消息25」，末条是「消息6」
        self.assertEqual(page1["results"][0]["content"], "消息25")
        self.assertEqual(page1["results"][-1]["content"], "消息6")

        page2 = self._get(self.conv.pk, 2).json()
        self.assertEqual(len(page2["results"]), 5)
        self.assertIsNone(page2["next"])
        self.assertIsNotNone(page2["previous"])
        self.assertEqual(page2["results"][0]["content"], "消息5")
        self.assertEqual(page2["results"][-1]["content"], "消息1")

    def test_out_of_range_page_404(self):
        Message.objects.create(conversation=self.conv, sender=self.bob, content="只有一条")
        resp = self._get(self.conv.pk, 99)
        self.assertEqual(resp.status_code, 404)


class ConversationSidebarTest(TestCase):
    """会话侧栏：-updated_at 排序 + 分页信封（数字页码器消费）。"""

    URL = "/messaging/conversations/"

    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="secret123")
        self.bob = User.objects.create_user(username="bob", password="secret123")
        self.client.login(username="alice", password="secret123")

    def _mk(self, n=1):
        convs = []
        for _ in range(n):
            c = Conversation.objects.create(conversation_type="private")
            c.participants.set([self.alice, self.bob])
            convs.append(c)
        return convs

    def test_list_returns_paginated_envelope(self):
        self._mk()
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.json().keys()), {"count", "next", "previous", "results"})

    def test_ordered_by_updated_at_desc(self):
        c1, c2 = self._mk(2)
        # 让 c1 最近活跃（updated_at 最新）
        Conversation.objects.filter(pk=c1.pk).update(updated_at=timezone.now() + timedelta(hours=1))
        ids = [r["id"] for r in self.client.get(self.URL).json()["results"]]
        self.assertEqual(ids[0], c1.pk)
        self.assertEqual(ids[1], c2.pk)

    def test_paginated_two_pages(self):
        self._mk(25)
        page1 = self.client.get(self.URL).json()
        self.assertEqual(page1["count"], 25)
        self.assertEqual(len(page1["results"]), 20)
        self.assertIsNotNone(page1["next"])
        page2 = self.client.get(f"{self.URL}?page=2").json()
        self.assertEqual(len(page2["results"]), 5)
        self.assertIsNone(page2["next"])
