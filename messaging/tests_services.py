"""Focused unit tests for messaging.services write rules (not the full HTTP suite)."""
from datetime import timedelta

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from accounts.models import Profile
from accounts.test_helpers import grant_verification
from common.models import SiteSettings
from common.policy import invalidate_policy_cache
from news.models import News
from reviews.test_helpers import approve_news
from tasks.models import Task

from messaging.models import Banner, Comment, CommentThread, Notification, UserMute
from messaging.services import (
    MessagingError,
    MessagingForbidden,
    can_manage_thread,
    can_see_host,
    can_see_thread,
    current_banner,
    delete_comment,
    is_muted,
    lift_mute,
    mute_user,
    notify,
    post_comment,
    push_user,
    retract_comment,
    send_dm,
    set_thread_status,
    start_private,
    thread_for,
)


class ThreadAndCommentRulesTest(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="author", password="x")
        self.news = News.objects.create(title="n", author=self.author, is_published=True)
        self.thread = thread_for(self.news)

    def tearDown(self):
        invalidate_policy_cache()
        cache.clear()
        super().tearDown()

    def test_thread_for_is_get_or_create(self):
        again = thread_for(self.news)
        self.assertEqual(self.thread.pk, again.pk)
        self.assertEqual(self.thread.status, CommentThread.STATUS_OPEN)

    def test_depth_cap_rejects_and_does_not_reparent(self):
        SiteSettings(comment_max_depth=1).save()
        invalidate_policy_cache()
        root = post_comment(self.thread, self.author, "root")
        with self.assertRaises(MessagingError) as ctx:
            post_comment(self.thread, self.author, "too deep", parent=root)
        self.assertIn("嵌套", ctx.exception.detail)
        self.assertEqual(Comment.objects.filter(thread=self.thread).count(), 1)

    def test_depth_cap_follows_get_policy(self):
        SiteSettings(comment_max_depth=2).save()
        invalidate_policy_cache()
        root = post_comment(self.thread, self.author, "root")
        child = post_comment(self.thread, self.author, "child", parent=root)
        with self.assertRaises(MessagingError):
            post_comment(self.thread, self.author, "grandchild", parent=child)
        self.assertEqual(Comment.objects.filter(thread=self.thread).count(), 2)

    def test_unpublished_news_comments_not_public(self):
        news = approve_news(
            News.objects.create(title="draft", author=self.author, is_published=False),
        )
        thread = thread_for(news)
        post_comment(thread, self.author, "内部讨论")
        stranger = User.objects.create_user(username="stranger", password="x")
        guest = AnonymousUser()
        self.assertFalse(can_see_host(guest, news))
        self.assertFalse(can_see_thread(guest, thread))
        self.assertFalse(can_see_host(stranger, news))
        self.assertFalse(can_see_thread(stranger, thread))
        self.assertTrue(can_see_host(self.author, news))
        self.assertTrue(can_see_thread(self.author, thread))

    def test_published_approved_news_comments_are_readable(self):
        news = approve_news(
            News.objects.create(title="public", author=self.author, is_published=True),
        )
        thread = thread_for(news)
        stranger = User.objects.create_user(username="reader", password="x")
        self.assertTrue(can_see_thread(AnonymousUser(), thread))
        self.assertTrue(can_see_thread(stranger, thread))

    def test_closed_thread_hidden_from_readers_not_managers(self):
        news = approve_news(
            News.objects.create(title="closable", author=self.author, is_published=True),
        )
        thread = thread_for(news)
        set_thread_status(thread, self.author, CommentThread.STATUS_CLOSED)
        stranger = User.objects.create_user(username="closed-reader", password="x")
        self.assertFalse(can_see_thread(AnonymousUser(), thread))
        self.assertFalse(can_see_thread(stranger, thread))
        self.assertTrue(can_see_thread(self.author, thread))

    def test_muted_thread_rejects_new_comments_but_stays_readable(self):
        news = approve_news(
            News.objects.create(title="muted-host", author=self.author, is_published=True),
        )
        thread = thread_for(news)
        set_thread_status(thread, self.author, CommentThread.STATUS_MUTED)
        stranger = User.objects.create_user(username="muted-reader", password="x")
        self.assertTrue(can_see_thread(stranger, thread))
        with self.assertRaises(MessagingError) as ctx:
            post_comment(thread, self.author, "禁言后不能发")
        self.assertIn("禁言", ctx.exception.detail)

    def test_retract_blocked_when_replies_exist(self):
        root = post_comment(self.thread, self.author, "root")
        post_comment(self.thread, self.author, "child", parent=root)
        with self.assertRaises(MessagingError):
            retract_comment(root, self.author)
        root.refresh_from_db()
        self.assertIsNone(root.retracted_at)

    def test_retract_window(self):
        root = post_comment(self.thread, self.author, "root")
        Comment.objects.filter(pk=root.pk).update(created_at=timezone.now() - timedelta(minutes=4))
        root.refresh_from_db()
        with self.assertRaises(MessagingError):
            retract_comment(root, self.author)

    def test_retract_within_window_when_leaf(self):
        root = post_comment(self.thread, self.author, "leaf")
        retract_comment(root, self.author)
        root.refresh_from_db()
        self.assertIsNotNone(root.retracted_at)

    def test_manager_delete_tombstones_and_keeps_children(self):
        root = post_comment(self.thread, self.author, "root")
        child = post_comment(self.thread, self.author, "child", parent=root)
        delete_comment(root, self.author)
        root.refresh_from_db()
        child.refresh_from_db()
        self.assertIsNotNone(root.deleted_at)
        self.assertEqual(root.deleted_by_id, self.author.pk)
        self.assertIsNone(child.deleted_at)
        self.assertEqual(child.content, "child")

    def test_task_assignee_cannot_manage_thread(self):
        creator = User.objects.create_user(username="creator", password="x")
        assignee = User.objects.create_user(username="assignee", password="x")
        task = Task.objects.create(title="t", creator=creator, assignee=assignee)
        thread = thread_for(task)
        self.assertTrue(can_manage_thread(creator, thread))
        self.assertFalse(can_manage_thread(assignee, thread))


class MuteAndNotifyTest(TestCase):
    def setUp(self):
        self.mod = User.objects.create_user(username="mod", password="x")
        perm = Permission.objects.get(
            content_type__app_label="messaging", codename="mute_user",
        )
        self.mod.user_permissions.add(perm)
        self.target = User.objects.create_user(username="target", password="x", email="t@example.com")
        Profile.objects.get_or_create(user=self.target)

    def test_lazy_expiry_lifts_and_notifies(self):
        UserMute.objects.create(
            user=self.target,
            muted_by=self.mod,
            starts_at=timezone.now() - timedelta(days=2),
            ends_at=timezone.now() - timedelta(hours=1),
        )
        self.assertFalse(is_muted(self.target))
        mute = UserMute.objects.get(user=self.target)
        self.assertIsNotNone(mute.lifted_at)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.target, category=Notification.CATEGORY_DISCIPLINE, event="mute_expired",
            ).exists()
        )

    def test_mute_blocks_comment(self):
        author = User.objects.create_user(username="author2", password="x")
        news = News.objects.create(title="n2", author=author, is_published=True)
        thread = thread_for(news)
        mute_user(self.mod, author, reason="spam")
        with self.assertRaises(MessagingForbidden):
            post_comment(thread, author, "nope")
        self.assertTrue(can_see_thread(author, thread))

    def test_mute_blocks_dm_not_receive(self):
        alice = grant_verification(User.objects.create_user(username="alice", password="x"))
        bob = grant_verification(User.objects.create_user(username="bob", password="x"))
        conv, created = start_private(alice, bob)
        self.assertTrue(created)
        mute_user(self.mod, alice, reason="spam")
        with self.assertRaises(MessagingForbidden):
            send_dm(conv, alice, "blocked")
        incoming = send_dm(conv, bob, "you can still receive")
        self.assertEqual(incoming.content, "you can still receive")
        self.assertTrue(is_muted(alice))

    def test_email_only_when_pref_and_bound_email(self):
        profile = self.target.profile
        profile.email_notify_comment = True
        profile.save()
        notify(self.target, Notification.CATEGORY_COMMENT, "comment_posted", actor=self.mod, payload={})
        self.assertEqual(len(mail.outbox), 1)

        mail.outbox.clear()
        profile.email_notify_comment = False
        profile.save()
        notify(self.target, Notification.CATEGORY_COMMENT, "comment_posted", actor=self.mod, payload={})
        self.assertEqual(len(mail.outbox), 0)

        mail.outbox.clear()
        profile.email_notify_comment = True
        profile.save()
        self.target.email = ""
        self.target.save()
        notify(self.target, Notification.CATEGORY_COMMENT, "comment_posted", actor=self.mod, payload={})
        self.assertEqual(len(mail.outbox), 0)

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.target, category=Notification.CATEGORY_COMMENT,
            ).count(),
            3,
        )

    def test_lift_requires_perm(self):
        other = User.objects.create_user(username="other", password="x")
        mute_user(self.mod, self.target)
        with self.assertRaises(MessagingForbidden):
            lift_mute(other, self.target)


class BannerPickerTest(TestCase):
    def test_highest_priority_then_newer(self):
        now = timezone.now()
        Banner.objects.create(
            body="low", starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=1),
            priority=1,
        )
        winner = Banner.objects.create(
            body="high", starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=1),
            priority=5,
        )
        Banner.objects.create(
            body="expired", starts_at=now - timedelta(days=2), ends_at=now - timedelta(hours=1),
            priority=9,
        )
        Banner.objects.create(
            body="future", starts_at=now + timedelta(hours=1), ends_at=now + timedelta(days=1),
            priority=9,
        )
        self.assertEqual(current_banner(now).pk, winner.pk)

    def test_tie_breaks_to_newer(self):
        now = timezone.now()
        Banner.objects.create(
            body="old", starts_at=now - timedelta(hours=2), ends_at=now + timedelta(hours=1),
            priority=3,
        )
        newer = Banner.objects.create(
            body="new", starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=1),
            priority=3,
        )
        self.assertEqual(current_banner(now).pk, newer.pk)


class PushNoOpTest(TestCase):
    def test_push_user_does_not_raise_without_channels(self):
        push_user(1, "notification", {"notification_id": 1})
