from django.contrib.auth.models import User
from django.test import Client, TestCase

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
