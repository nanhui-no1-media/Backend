"""Updater window/cutoff logic and unpack/rollback helpers (no GitHub)."""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import sqlite3
import tarfile
import tempfile
import urllib.error
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from common.models import SiteSettings
from common.policy import SitePolicy, get_policy
from common.updater import (
    ApplyError,
    CommandError,
    RemoteRelease,
    SPAWNED_ENV,
    SIGHUP,
    SYNC_EXCLUDES,
    UpdaterPaths,
    WindowClosed,
    apply_release,
    archive_sha,
    before_apply_cutoff,
    can_start_apply,
    in_apply_window,
    is_complete_archive,
    load_policy,
    parse_release_assets,
    parse_sha256_sidecar,
    pending_archive,
    poll_tick,
    prune_keep_newest,
    release_tag,
    retry_delay,
    restore_sqlite,
    sync_tree,
    unpack_archive,
    verify_archive_checksum,
    _format_bytes,
    _format_progress,
    _is_retryable,
)


def _shanghai():
    try:
        return ZoneInfo("Asia/Shanghai")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=8))


def _policy(**kwargs) -> SitePolicy:
    return replace(SitePolicy.defaults(), **kwargs)


def _at(hour, minute=0, *, tz=None):
    tz = tz or _shanghai()
    return datetime(2026, 6, 15, hour, minute, tzinfo=tz)


class WindowLogicTest(SimpleTestCase):
    def test_default_window_bounds(self):
        p = _policy()
        self.assertFalse(in_apply_window(_at(0, 59), p))
        self.assertTrue(in_apply_window(_at(1, 0), p))
        self.assertTrue(in_apply_window(_at(2, 59), p))
        self.assertFalse(in_apply_window(_at(3, 0), p))

    def test_cutoff_blocks_start_but_window_still_open(self):
        p = _policy()
        self.assertTrue(in_apply_window(_at(2, 30), p))
        self.assertFalse(before_apply_cutoff(_at(2, 30), p))
        self.assertTrue(before_apply_cutoff(_at(2, 29), p))
        self.assertTrue(can_start_apply(_at(1, 0), p))
        self.assertFalse(can_start_apply(_at(2, 30), p))

    def test_disabled_blocks_start_even_inside_window(self):
        p = _policy(auto_update_enabled=False)
        self.assertTrue(in_apply_window(_at(1, 30), p))
        self.assertFalse(can_start_apply(_at(1, 30), p))

    def test_uses_policy_timezone_not_naive_clock(self):
        p = _policy(update_timezone="Asia/Shanghai")
        # 2026-06-14 17:00 UTC == 2026-06-15 01:00 CST
        utc = datetime(2026, 6, 14, 17, 0, tzinfo=timezone.utc)
        self.assertTrue(in_apply_window(utc, p))
        self.assertTrue(can_start_apply(utc, p))
        utc_before = datetime(2026, 6, 14, 16, 59, tzinfo=timezone.utc)
        self.assertFalse(in_apply_window(utc_before, p))

    def test_overnight_window_and_cutoff(self):
        p = _policy(
            update_window_start_hour=22,
            update_window_end_hour=2,
            update_apply_cutoff_minutes_before_end=30,
        )
        self.assertFalse(in_apply_window(_at(21, 59), p))
        self.assertTrue(in_apply_window(_at(22, 0), p))
        self.assertTrue(in_apply_window(_at(1, 0), p))
        self.assertFalse(in_apply_window(_at(2, 0), p))
        self.assertTrue(before_apply_cutoff(_at(1, 29), p))
        self.assertFalse(before_apply_cutoff(_at(1, 30), p))

    def test_empty_window_when_start_equals_end(self):
        p = _policy(update_window_start_hour=3, update_window_end_hour=3)
        self.assertFalse(in_apply_window(_at(3, 0), p))
        self.assertFalse(can_start_apply(_at(1, 0), p))

    def test_cutoff_longer_than_window_never_starts(self):
        p = _policy(update_apply_cutoff_minutes_before_end=180)
        self.assertTrue(in_apply_window(_at(1, 0), p))
        self.assertFalse(before_apply_cutoff(_at(1, 0), p))


class ArchiveNameTest(SimpleTestCase):
    def test_sha_from_filename(self):
        sha = "abc123def456"
        self.assertEqual(archive_sha(Path(f"club-{sha}.tar.gz")), sha)

    def test_part_is_never_complete(self):
        part = Path("club-abc123def456.tar.gz.part")
        self.assertIsNone(archive_sha(part))
        self.assertFalse(is_complete_archive(part))

    def test_sidecar_parse_and_verify(self):
        payload = b"hello-release"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = root / "club-deadbeef.tar.gz"
            archive.write_bytes(payload)
            sidecar = Path(str(archive) + ".sha256")
            sidecar.write_text(f"{digest}  club-deadbeef.tar.gz\n", encoding="utf-8")
            self.assertEqual(parse_sha256_sidecar(sidecar.read_text(encoding="utf-8")), digest)
            verify_archive_checksum(archive, sidecar)
            sidecar.write_text("0" * 64 + "  club-deadbeef.tar.gz\n", encoding="utf-8")
            with self.assertRaises(ApplyError):
                verify_archive_checksum(archive, sidecar)


class UnpackExcludeRollbackTest(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.paths = UpdaterPaths.from_root(self.root)
        self.paths.ensure_dirs()

    def _tarball(self, sha: str, files: dict[str, bytes]) -> Path:
        archive = self.paths.releases_dir / f"club-{sha}.tar.gz"
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            for name, data in files.items():
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        archive.write_bytes(buf.getvalue())
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        Path(str(archive) + ".sha256").write_text(
            f"{digest}  {archive.name}\n", encoding="utf-8"
        )
        return archive

    def _seed_live(self):
        (self.root / ".env").write_text("SECRET=keep-me\n", encoding="utf-8")
        (self.root / "app.py").write_text("old\n", encoding="utf-8")
        (self.root / "media").mkdir()
        (self.root / "media" / "photo.jpg").write_text("pic", encoding="utf-8")
        (self.root / "private_media").mkdir()
        (self.root / "private_media" / "id.png").write_text("id", encoding="utf-8")
        (self.root / "run").mkdir(exist_ok=True)
        (self.root / "run" / "gunicorn.sock").write_text("sock", encoding="utf-8")
        (self.root / "backups").mkdir(exist_ok=True)
        (self.root / "backups" / "keep.txt").write_text("bak", encoding="utf-8")
        (self.root / ".venv").mkdir()
        (self.root / ".venv" / "pyvenv.cfg").write_text("venv", encoding="utf-8")
        conn = sqlite3.connect(self.root / "db.sqlite3")
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.execute("INSERT INTO t VALUES ('before')")
        conn.commit()
        conn.close()

    def test_unpack_rejects_part(self):
        part = self.paths.releases_dir / "club-aaaaaaa.tar.gz.part"
        part.write_bytes(b"nope")
        with self.assertRaises(ApplyError):
            unpack_archive(part, self.paths.staging_dir)

    def test_sync_preserves_excludes_and_replaces_code(self):
        self._seed_live()
        src = self.root / "staging-src"
        src.mkdir()
        (src / "app.py").write_text("new\n", encoding="utf-8")
        (src / "added.py").write_text("added\n", encoding="utf-8")
        (src / ".env").write_text("SECRET=from-tarball\n", encoding="utf-8")
        sync_tree(src, self.root)
        self.assertEqual((self.root / "app.py").read_text(encoding="utf-8"), "new\n")
        self.assertEqual((self.root / "added.py").read_text(encoding="utf-8"), "added\n")
        self.assertEqual((self.root / ".env").read_text(encoding="utf-8"), "SECRET=keep-me\n")
        self.assertEqual((self.root / "media" / "photo.jpg").read_text(encoding="utf-8"), "pic")
        self.assertEqual(
            (self.root / "private_media" / "id.png").read_text(encoding="utf-8"), "id"
        )
        self.assertTrue((self.root / "run" / "gunicorn.sock").exists())
        self.assertTrue((self.root / "backups" / "keep.txt").exists())
        self.assertTrue((self.root / ".venv" / "pyvenv.cfg").exists())
        self.assertTrue((self.root / "db.sqlite3").exists())

    def test_sync_excludes_constant_covers_live_data(self):
        for name in (
            ".env",
            "db.sqlite3",
            "media",
            "private_media",
            "run",
            "backups",
            ".venv",
        ):
            self.assertIn(name, SYNC_EXCLUDES)

    def test_unpack_then_sync_then_rollback_restores_previous_tree_and_db(self):
        self._seed_live()
        v1 = self._tarball("111111111111", {"app.py": b"v1\n", "only_v1.py": b"keep\n"})
        v2 = self._tarball("222222222222", {"app.py": b"v2\n", "only_v2.py": b"new\n"})

        unpack_archive(v1, self.paths.staging_dir)
        sync_tree(self.paths.staging_dir, self.root)
        self.assertEqual((self.root / "app.py").read_text(encoding="utf-8"), "v1\n")

        conn = sqlite3.connect(self.root / "db.sqlite3")
        conn.execute("UPDATE t SET v='after-v1'")
        conn.commit()
        conn.close()
        snapshot = self.paths.backups_dir / "db-test.sqlite3"
        shutil.copy2(self.root / "db.sqlite3", snapshot)

        unpack_archive(v2, self.paths.staging_dir)
        sync_tree(self.paths.staging_dir, self.root)
        self.assertEqual((self.root / "app.py").read_text(encoding="utf-8"), "v2\n")
        self.assertTrue((self.root / "only_v2.py").exists())
        self.assertFalse((self.root / "only_v1.py").exists())

        unpack_archive(v1, self.paths.staging_dir)
        sync_tree(self.paths.staging_dir, self.root)
        restore_sqlite(snapshot, self.root / "db.sqlite3")
        self.assertEqual((self.root / "app.py").read_text(encoding="utf-8"), "v1\n")
        self.assertTrue((self.root / "only_v1.py").exists())
        self.assertFalse((self.root / "only_v2.py").exists())
        self.assertEqual((self.root / ".env").read_text(encoding="utf-8"), "SECRET=keep-me\n")
        conn = sqlite3.connect(self.root / "db.sqlite3")
        self.assertEqual(conn.execute("SELECT v FROM t").fetchone()[0], "after-v1")
        conn.close()

    def test_apply_failure_rolls_back_files_and_db(self):
        self._seed_live()
        v1 = self._tarball("aaaaaaaaaaaa", {"app.py": b"good\n"})
        v2 = self._tarball("bbbbbbbbbbbb", {"app.py": b"bad\n"})
        unpack_archive(v1, self.paths.staging_dir)
        sync_tree(self.paths.staging_dir, self.root)
        self.paths.applied_file.write_text("aaaaaaaaaaaa\n", encoding="utf-8")

        calls: list[list[str]] = []

        def run(argv, *, check=True):
            argv = [str(a) for a in argv]
            calls.append(argv)
            if "migrate" in argv:
                if check:
                    raise CommandError(argv, 1)
                return 1
            return 0

        with self.assertRaises(CommandError):
            apply_release(
                self.paths,
                v2,
                _policy(),
                run=run,
                sleep=lambda _s: None,
                now_fn=lambda: _at(1, 15),
                respect_window=True,
                drain_seconds=0,
            )

        self.assertEqual((self.root / "app.py").read_text(encoding="utf-8"), "good\n")
        self.assertEqual((self.root / ".env").read_text(encoding="utf-8"), "SECRET=keep-me\n")
        conn = sqlite3.connect(self.root / "db.sqlite3")
        self.assertEqual(conn.execute("SELECT v FROM t").fetchone()[0], "before")
        conn.close()
        self.assertEqual(self.paths.applied_file.read_text(encoding="utf-8").strip(), "aaaaaaaaaaaa")
        self.assertFalse(self.paths.maintenance_flag.exists())
        self.assertTrue(any("migrate" in c for c in calls))
        self.assertTrue(any(c[:4] == ["sudo", "systemctl", "restart", "club"] for c in calls))

    def test_apply_now_ignores_window_and_writes_applied(self):
        self._seed_live()
        v1 = self._tarball("cccccccccccc", {"app.py": b"ok\n"})
        # 14:00 is well outside the 01:00-03:00 window
        apply_release(
            self.paths,
            v1,
            _policy(),
            run=lambda argv, *, check=True: 0,
            sleep=lambda _s: None,
            now_fn=lambda: _at(14, 0),
            respect_window=False,
            drain_seconds=0,
        )
        self.assertEqual((self.root / "app.py").read_text(encoding="utf-8"), "ok\n")
        self.assertEqual(self.paths.applied_file.read_text(encoding="utf-8").strip(), "cccccccccccc")
        self.assertFalse(self.paths.maintenance_flag.exists())

    def test_spawned_apply_sighups_parent_instead_of_restart(self):
        self._seed_live()
        v1 = self._tarball("cccccccccccc", {"app.py": b"ok\n"})
        calls: list[list[str]] = []

        def run(argv, *, check=True):
            calls.append([str(a) for a in argv])
            return 0

        with (
            mock.patch.dict(os.environ, {SPAWNED_ENV: "1"}),
            mock.patch("common.updater.os.getppid", return_value=4242),
            mock.patch("common.updater.os.kill") as kill,
        ):
            apply_release(
                self.paths,
                v1,
                _policy(),
                run=run,
                sleep=lambda _s: None,
                now_fn=lambda: _at(1, 15),
                drain_seconds=0,
            )
        kill.assert_called_with(4242, SIGHUP)
        self.assertFalse(
            any(c[:4] == ["sudo", "systemctl", "restart", "club"] for c in calls)
        )

    def test_pending_ignores_part_and_applied_sha(self):
        self._tarball("dddddddddddd", {"app.py": b"x\n"})
        part = self.paths.releases_dir / "club-eeeeeeeeeeee.tar.gz.part"
        part.write_bytes(b"partial")
        self.paths.applied_file.write_text("dddddddddddd\n", encoding="utf-8")
        self.assertIsNone(pending_archive(self.paths, remote_sha="dddddddddddd"))
        self.assertIsNone(pending_archive(self.paths))
        other = self._tarball("ffffffffffff", {"app.py": b"y\n"})
        self.assertEqual(pending_archive(self.paths, remote_sha="ffffffffffff"), other)
        self.assertEqual(pending_archive(self.paths), other)

    def test_prune_keeps_newest_n(self):
        files = []
        for i, name in enumerate(("a", "b", "c", "d")):
            path = self.paths.releases_dir / f"{name}.tar.gz"
            path.write_text(name, encoding="utf-8")
            stamp = path.stat().st_mtime + i
            os.utime(path, (stamp, stamp))
            files.append(path)
        removed = prune_keep_newest(files, keep=2)
        self.assertEqual(len(removed), 2)
        remaining = {p.name for p in self.paths.releases_dir.glob("*.tar.gz")}
        self.assertEqual(remaining, {"c.tar.gz", "d.tar.gz"})

    def test_poll_tick_does_not_apply_outside_window(self):
        self._seed_live()
        self._tarball("ffffffffffff", {"app.py": b"new\n"})
        with mock.patch("common.updater.github_token", return_value=""):
            poll_tick(
                self.paths,
                _policy(),
                run=mock.Mock(side_effect=AssertionError("must not apply")),
                sleep=lambda _s: None,
                now_fn=lambda: _at(14, 0),
            )
        self.assertEqual((self.root / "app.py").read_text(encoding="utf-8"), "old\n")

    def test_window_close_mid_apply_rolls_back(self):
        self._seed_live()
        v1 = self._tarball("111111111111", {"app.py": b"good\n"})
        v2 = self._tarball("222222222222", {"app.py": b"late\n"})
        unpack_archive(v1, self.paths.staging_dir)
        sync_tree(self.paths.staging_dir, self.root)
        self.paths.applied_file.write_text("111111111111\n", encoding="utf-8")
        ticks = {"n": 0}

        def now():
            ticks["n"] += 1
            # First backup stamp + first window check inside window; then past 03:00.
            if ticks["n"] <= 2:
                return _at(2, 50)
            return _at(3, 1)

        with self.assertRaises(WindowClosed):
            apply_release(
                self.paths,
                v2,
                _policy(),
                run=lambda argv, *, check=True: 0,
                sleep=lambda _s: None,
                now_fn=now,
                respect_window=True,
                drain_seconds=0,
            )
        self.assertEqual((self.root / "app.py").read_text(encoding="utf-8"), "good\n")


class GithubParseAndRetryTest(SimpleTestCase):
    def test_release_tag_is_not_bare_hex(self):
        sha = "0123456789abcdef0123456789abcdef01234567"
        self.assertEqual(release_tag(sha), f"club-{sha}")
        self.assertEqual(release_tag(f"club-{sha}"), f"club-{sha}")

    def test_parse_release_assets(self):
        sha = "0123456789abcdef0123456789abcdef01234567"
        payload = {
            "tag_name": f"club-{sha}",
            "assets": [
                {
                    "name": f"club-{sha}.tar.gz",
                    "url": "https://api.github.com/repos/x/y/releases/assets/1",
                },
                {
                    "name": f"club-{sha}.tar.gz.sha256",
                    "url": "https://api.github.com/repos/x/y/releases/assets/2",
                },
            ],
        }
        remote = parse_release_assets(payload)
        self.assertIsInstance(remote, RemoteRelease)
        self.assertEqual(remote.sha, sha)
        self.assertTrue(remote.tarball_api_url.endswith("/1"))
        self.assertTrue(remote.checksum_api_url.endswith("/2"))

    def test_parse_skips_nameless_payload(self):
        self.assertIsNone(parse_release_assets({"assets": []}))

    def test_retry_delay_jitter_bounds(self):
        self.assertEqual(retry_delay(0, base=5, cap=300, jitter=lambda: 0.0), 2.5)
        self.assertEqual(retry_delay(0, base=5, cap=300, jitter=lambda: 1.0), 5.0)
        self.assertEqual(retry_delay(10, base=5, cap=300, jitter=lambda: 1.0), 300.0)

    def test_format_progress_includes_percent_and_rate(self):
        self.assertEqual(_format_bytes(512), "512 B")
        self.assertIn("KiB", _format_bytes(2048))
        line = _format_progress("club.tgz.part", 10 * 1024 * 1024, 40 * 1024 * 1024, 1024 * 1024)
        self.assertIn("25%", line)
        self.assertIn("/s", line)

    def test_http_503_is_retryable_404_is_not(self):
        err_503 = urllib.error.HTTPError("http://x", 503, "unavailable", hdrs=None, fp=None)
        err_404 = urllib.error.HTTPError("http://x", 404, "missing", hdrs=None, fp=None)
        self.assertTrue(_is_retryable(err_503))
        self.assertFalse(_is_retryable(err_404))
        self.assertTrue(_is_retryable(urllib.error.URLError("timeout")))

    def test_poll_tick_skips_download_when_disabled(self):
        with tempfile.TemporaryDirectory() as raw:
            paths = UpdaterPaths.from_root(Path(raw))
            paths.ensure_dirs()
            get_json = mock.Mock(side_effect=AssertionError("must not hit GitHub"))
            remote = poll_tick(
                paths,
                _policy(auto_update_enabled=False),
                get_json=get_json,
                download=mock.Mock(),
                sleep=lambda _s: None,
                apply=False,
            )
            self.assertIsNone(remote)
            get_json.assert_not_called()


class LoadPolicyCacheTest(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_load_policy_invalidates_then_rereads(self):
        obj, _ = SiteSettings.objects.get_or_create(pk=1)
        obj.auto_update_enabled = True
        obj.save()
        self.assertTrue(get_policy().auto_update_enabled)
        SiteSettings.objects.filter(pk=1).update(auto_update_enabled=False)
        self.assertTrue(get_policy().auto_update_enabled)
        self.assertFalse(load_policy().auto_update_enabled)
