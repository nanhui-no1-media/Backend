"""GitHub-release prefetch + night-window apply.

``start.sh`` spawns ``scripts/updater.py`` next to Gunicorn (same systemd
cgroup). Tests import the helpers below and never hit GitHub.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator, Sequence
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from common.maintenance import (
    enter_update,
    leave_update,
    update_progress,
)
from common.policy import SitePolicy, get_policy, invalidate_policy_cache

log = logging.getLogger("updater")

DEFAULT_GITHUB_REPO = "nanhui-no1-media/Backend"
DRAIN_SECONDS = 10
HEALTH_WAIT_SECONDS = 3
RETRY_BASE_SECONDS = 5
RETRY_MAX_SECONDS = 300
MAX_DOWNLOAD_ATTEMPTS = 8
# POSIX hangup; production is Linux. Windows tests have no signal.SIGHUP.
SIGHUP = getattr(signal, "SIGHUP", 1)
# Set by start.sh so apply can SIGHUP Gunicorn (the parent) instead of
# ``systemctl restart club``, which would kill this process with the cgroup.
SPAWNED_ENV = "CLUB_UPDATER_SPAWNED"
GITHUB_API = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"

ARCHIVE_RE = re.compile(r"^club-([0-9a-f]{7,40})\.tar\.gz$", re.IGNORECASE)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
# GitHub forbids tags that are exactly 40/64 hex; assets stay club-{sha}.tar.gz.
RELEASE_TAG_PREFIX = "club-"

# Live-tree names that must never be replaced or deleted by a release unpack.
# ``.git`` is extra to the plan's list: deploy.sh still clones once.
SYNC_EXCLUDES = frozenset(
    {
        ".env",
        "db.sqlite3",
        "db.sqlite3-journal",
        "db.sqlite3-wal",
        "db.sqlite3-shm",
        "media",
        "private_media",
        "run",
        "backups",
        ".venv",
        ".git",
    }
)

Runner = Callable[..., int]
SleepFn = Callable[[float], None]
NowFn = Callable[[], datetime]


class UpdaterError(Exception):
    """Any apply / download failure the daemon should log and continue from."""


class ApplyError(UpdaterError):
    pass


class WindowClosed(ApplyError):
    """Clock hit the policy window end mid-apply."""


class CommandError(ApplyError):
    def __init__(self, argv: Sequence[str], returncode: int):
        self.argv = list(argv)
        self.returncode = returncode
        super().__init__(f"exit {returncode}: {' '.join(self.argv)}")


@dataclass(frozen=True)
class UpdaterPaths:
    root: Path
    run_dir: Path
    backups_dir: Path
    releases_dir: Path
    staging_dir: Path
    lock_file: Path
    applied_file: Path
    maintenance_flag: Path
    db: Path

    @classmethod
    def from_root(cls, root: Path) -> UpdaterPaths:
        root = Path(root).resolve()
        run_dir = root / "run"
        backups = root / "backups"
        return cls(
            root=root,
            run_dir=run_dir,
            backups_dir=backups,
            releases_dir=backups / "releases",
            staging_dir=backups / "staging",
            lock_file=run_dir / "update.lock",
            applied_file=run_dir / "applied-release",
            maintenance_flag=run_dir / "MAINTENANCE",
            db=root / "db.sqlite3",
        )

    def ensure_dirs(self) -> None:
        for p in (self.run_dir, self.releases_dir, self.staging_dir):
            p.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class RemoteRelease:
    sha: str
    tarball_name: str
    tarball_api_url: str
    checksum_api_url: str | None


# ---------------------------------------------------------------------------
# Policy clock
# ---------------------------------------------------------------------------


def policy_tz(policy: SitePolicy):
    name = (policy.update_timezone or "Asia/Shanghai").strip()
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        log.warning("unknown timezone %s; using UTC+8", name)
        return timezone(timedelta(hours=8))


def _window_bounds(local: datetime, policy: SitePolicy):
    """Return (start, end) for the window that *could* contain ``local``.

    ``start == end`` hour means an empty window. Overnight (start > end) wraps
    midnight. Bounds are half-open ``[start, end)``.
    """
    start_h = int(policy.update_window_start_hour)
    end_h = int(policy.update_window_end_hour)
    if start_h == end_h:
        return None
    today_start = local.replace(hour=start_h, minute=0, second=0, microsecond=0)
    today_end = local.replace(hour=end_h, minute=0, second=0, microsecond=0)
    if start_h < end_h:
        return today_start, today_end
    if local < today_end:
        return today_start - timedelta(days=1), today_end
    return today_start, today_end + timedelta(days=1)


def in_apply_window(now: datetime, policy: SitePolicy) -> bool:
    local = now.astimezone(policy_tz(policy))
    bounds = _window_bounds(local, policy)
    if bounds is None:
        return False
    start, end = bounds
    return start <= local < end


def before_apply_cutoff(now: datetime, policy: SitePolicy) -> bool:
    """True when ``now`` is inside the window and before the start-apply cutoff."""
    if not in_apply_window(now, policy):
        return False
    local = now.astimezone(policy_tz(policy))
    bounds = _window_bounds(local, policy)
    if bounds is None:
        return False
    _start, end = bounds
    cutoff = end - timedelta(minutes=int(policy.update_apply_cutoff_minutes_before_end))
    return local < cutoff


def can_start_apply(now: datetime, policy: SitePolicy) -> bool:
    """Kill switch + window + cutoff. Manual ``--apply-now`` skips this."""
    if not policy.auto_update_enabled:
        return False
    return before_apply_cutoff(now, policy)


def past_window_end(now: datetime, policy: SitePolicy) -> bool:
    return not in_apply_window(now, policy)


def load_policy() -> SitePolicy:
    """Re-read SiteSettings. locmem is not shared with Gunicorn workers."""
    invalidate_policy_cache()
    return get_policy()


# ---------------------------------------------------------------------------
# Archives on disk
# ---------------------------------------------------------------------------


def archive_sha(path: Path) -> str | None:
    """SHA encoded in ``club-{sha}.tar.gz``. ``None`` for ``.part`` / junk names."""
    name = path.name
    if name.endswith(".part"):
        return None
    match = ARCHIVE_RE.match(name)
    return match.group(1) if match else None


def is_complete_archive(path: Path) -> bool:
    return path.is_file() and archive_sha(path) is not None


def parse_sha256_sidecar(text: str) -> str:
    first = text.strip().split()[0].lower() if text.strip() else ""
    if not SHA256_RE.fullmatch(first):
        raise ValueError("invalid sha256 sidecar")
    return first


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive_checksum(archive: Path, sidecar: Path | None = None) -> None:
    sidecar = sidecar or Path(str(archive) + ".sha256")
    if not sidecar.is_file():
        raise ApplyError(f"missing checksum sidecar {sidecar}")
    expected = parse_sha256_sidecar(sidecar.read_text(encoding="utf-8"))
    actual = file_sha256(archive)
    if expected != actual:
        raise ApplyError(f"sha256 mismatch for {archive.name}: {actual} != {expected}")


def read_applied_sha(paths: UpdaterPaths) -> str | None:
    if not paths.applied_file.is_file():
        return None
    text = paths.applied_file.read_text(encoding="utf-8").strip()
    return text or None


def write_applied_sha(paths: UpdaterPaths, sha: str) -> None:
    paths.run_dir.mkdir(parents=True, exist_ok=True)
    paths.applied_file.write_text(sha.strip() + "\n", encoding="utf-8")


def release_tag(sha: str) -> str:
    """GitHub Release tag for a commit SHA (must not be bare 40-hex)."""
    text = sha.strip()
    if text.startswith(RELEASE_TAG_PREFIX):
        return text
    return f"{RELEASE_TAG_PREFIX}{text}"


def complete_archives(releases_dir: Path) -> list[Path]:
    if not releases_dir.is_dir():
        return []
    found = []
    for path in releases_dir.iterdir():
        if is_complete_archive(path):
            found.append(path)
    return found


def archive_for_sha(releases_dir: Path, sha: str) -> Path | None:
    candidate = releases_dir / f"club-{sha}.tar.gz"
    return candidate if is_complete_archive(candidate) else None


def pending_archive(paths: UpdaterPaths, remote_sha: str | None = None) -> Path | None:
    applied = read_applied_sha(paths)
    if remote_sha and remote_sha != applied:
        match = archive_for_sha(paths.releases_dir, remote_sha)
        if match is not None:
            return match
    newest = None
    newest_mtime = -1.0
    for path in complete_archives(paths.releases_dir):
        sha = archive_sha(path)
        if sha is None or sha == applied:
            continue
        mtime = path.stat().st_mtime
        if mtime > newest_mtime:
            newest = path
            newest_mtime = mtime
    return newest


def prune_keep_newest(files: Sequence[Path], keep: int) -> list[Path]:
    keep = max(0, int(keep))
    ordered = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    removed = ordered[keep:]
    for path in removed:
        path.unlink(missing_ok=True)
        sidecar = Path(str(path) + ".sha256")
        sidecar.unlink(missing_ok=True)
    return list(removed)


def prune_releases(paths: UpdaterPaths, keep: int) -> list[Path]:
    return prune_keep_newest(complete_archives(paths.releases_dir), keep)


def prune_db_backups(paths: UpdaterPaths, keep: int) -> list[Path]:
    if not paths.backups_dir.is_dir():
        return []
    snaps = [
        p
        for p in paths.backups_dir.glob("db-*.sqlite3")
        if p.is_file()
    ]
    return prune_keep_newest(snaps, keep)


# ---------------------------------------------------------------------------
# Unpack / rsync-equivalent / sqlite
# ---------------------------------------------------------------------------


def unpack_archive(archive: Path, staging: Path) -> None:
    """Extract a complete tarball into ``staging`` (replaced). Never unpack ``.part``."""
    if archive_sha(archive) is None:
        raise ApplyError(f"refusing to unpack incomplete or unnamed archive: {archive.name}")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(staging, filter="data")


def _rel_top(rel: Path) -> str | None:
    return rel.parts[0] if rel.parts else None


def sync_tree(
    src: Path,
    dest: Path,
    *,
    excludes: frozenset[str] = SYNC_EXCLUDES,
) -> None:
    """Mirror ``src`` onto ``dest``, never touching excluded live-tree names.

    Equivalent to ``rsync -a --delete`` with those ``--exclude`` entries.
    """
    src = src.resolve()
    dest = dest.resolve()
    if not src.is_dir():
        raise FileNotFoundError(src)
    dest.mkdir(parents=True, exist_ok=True)

    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        rel_dir = Path(dirpath).relative_to(src)
        top = _rel_top(rel_dir)
        if top in excludes:
            dirnames.clear()
            continue
        dest_dir = dest / rel_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            rel = Path(name) if rel_dir == Path(".") else rel_dir / name
            if _rel_top(rel) in excludes:
                continue
            shutil.copy2(Path(dirpath) / name, dest_dir / name)

    for dirpath, dirnames, filenames in os.walk(dest, topdown=True, followlinks=False):
        rel_dir = Path(dirpath).relative_to(dest)
        if _rel_top(rel_dir) in excludes:
            dirnames.clear()
            continue
        if rel_dir == Path("."):
            dirnames[:] = [d for d in dirnames if d not in excludes]
        for name in filenames:
            rel = Path(name) if rel_dir == Path(".") else rel_dir / name
            if _rel_top(rel) in excludes:
                continue
            if not (src / rel).is_file():
                (Path(dirpath) / name).unlink(missing_ok=True)
        for name in list(dirnames):
            rel = Path(name) if rel_dir == Path(".") else rel_dir / name
            if _rel_top(rel) in excludes:
                continue
            if not (src / rel).is_dir():
                shutil.rmtree(Path(dirpath) / name, ignore_errors=True)
                dirnames.remove(name)


def backup_sqlite(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not src.is_file():
        return
    src_conn = sqlite3.connect(str(src))
    try:
        dst_conn = sqlite3.connect(str(dest))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def restore_sqlite(snapshot: Path, db: Path) -> None:
    if not snapshot.is_file():
        return
    for suffix in ("-journal", "-wal", "-shm"):
        Path(str(db) + suffix).unlink(missing_ok=True)
    shutil.copy2(snapshot, db)


def set_maintenance(paths: UpdaterPaths, on: bool, *, sha: str = "") -> None:
    """Back-compat wrapper: enter/leave update intercept (not ops)."""
    if on:
        enter_update(paths.maintenance_flag, sha=sha)
    else:
        leave_update(paths.maintenance_flag)


# ---------------------------------------------------------------------------
# flock
# ---------------------------------------------------------------------------


def _lock_exclusive(fh, *, blocking: bool) -> None:
    try:
        import fcntl
    except ImportError:
        fcntl = None
    if fcntl is not None:
        flags = fcntl.LOCK_EX
        if not blocking:
            flags |= fcntl.LOCK_NB
        try:
            fcntl.flock(fh.fileno(), flags)
        except BlockingIOError:
            raise
        except OSError as exc:
            raise BlockingIOError("update lock held") from exc
        return
    import msvcrt

    mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
    try:
        msvcrt.locking(fh.fileno(), mode, 1)
    except OSError as exc:
        raise BlockingIOError("update lock held") from exc


def _lock_release(fh) -> None:
    try:
        import fcntl
    except ImportError:
        fcntl = None
    if fcntl is not None:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        return
    try:
        import msvcrt

        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


@contextmanager
def update_lock(lock_path: Path, *, blocking: bool = True) -> Iterator[None]:
    """Exclusive lock on ``run/update.lock`` (fcntl flock on Unix)."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "a+b")
    try:
        fh.seek(0, os.SEEK_END)
        if fh.tell() == 0:
            fh.write(b"0")
            fh.flush()
        fh.seek(0)
        _lock_exclusive(fh, blocking=blocking)
        yield
    finally:
        try:
            _lock_release(fh)
        finally:
            fh.close()


# ---------------------------------------------------------------------------
# GitHub HTTP
# ---------------------------------------------------------------------------


class _StripAuthOnRedirect(urllib.request.HTTPRedirectHandler):
    """Drop Authorization when GitHub 302s the asset to S3."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is None:
            return None
        if urlparse(new.full_url).netloc != urlparse(req.full_url).netloc:
            for header in ("Authorization", "authorization"):
                try:
                    new.remove_header(header)
                except KeyError:
                    pass
        return new


def _github_headers(token: str, *, accept: str) -> dict[str, str]:
    headers = {
        "Accept": accept,
        "User-Agent": "club-updater",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_StripAuthOnRedirect)


def github_json(url: str, token: str, *, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        url,
        headers=_github_headers(token, accept="application/vnd.github+json"),
    )
    try:
        with _opener().open(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raise UpdaterError(f"GitHub HTTP {exc.code} for {url}") from exc


def github_download(url: str, dest: Path, token: str, *, timeout: int = 300) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers=_github_headers(token, accept="application/octet-stream"),
    )
    try:
        with _opener().open(req, timeout=timeout) as resp, open(dest, "wb") as out:
            shutil.copyfileobj(resp, out, length=1024 * 1024)
    except urllib.error.HTTPError as exc:
        dest.unlink(missing_ok=True)
        raise UpdaterError(f"GitHub HTTP {exc.code} downloading {url}") from exc


def parse_release_assets(payload: dict) -> RemoteRelease | None:
    assets = payload.get("assets") or []
    tarball = None
    checksum = None
    for asset in assets:
        name = asset.get("name") or ""
        if name.endswith(".tar.gz.sha256"):
            checksum = asset
        elif ARCHIVE_RE.match(name):
            tarball = asset
    if tarball is None:
        return None
    sha = archive_sha(Path(tarball["name"]))
    if sha is None:
        return None
    api_url = tarball.get("url") or ""
    if not api_url:
        return None
    checksum_url = None
    if checksum and checksum.get("url"):
        checksum_url = checksum["url"]
    return RemoteRelease(
        sha=sha,
        tarball_name=tarball["name"],
        tarball_api_url=api_url,
        checksum_api_url=checksum_url,
    )


def retry_delay(
    attempt: int,
    *,
    base: float = RETRY_BASE_SECONDS,
    cap: float = RETRY_MAX_SECONDS,
    jitter: Callable[[], float] | None = None,
) -> float:
    """Exponential backoff with jitter. ``attempt`` is 0-based."""
    raw = min(cap, float(base) * (2 ** attempt))
    roll = random.random() if jitter is None else jitter()
    return raw * (0.5 + 0.5 * roll)


def github_token() -> str:
    from django.conf import settings

    return (getattr(settings, "UPDATE_GITHUB_TOKEN", None) or os.environ.get("UPDATE_GITHUB_TOKEN") or "").strip()


def github_repo() -> str:
    from django.conf import settings

    raw = (
        getattr(settings, "UPDATE_GITHUB_REPO", None)
        or os.environ.get("UPDATE_GITHUB_REPO")
        or DEFAULT_GITHUB_REPO
    )
    return raw.strip() or DEFAULT_GITHUB_REPO


def fetch_release(
    repo: str,
    token: str,
    *,
    tag: str | None = None,
    get_json: Callable[[str, str], dict] | None = None,
) -> RemoteRelease | None:
    fetch = get_json or github_json
    if tag:
        url = f"{GITHUB_API}/repos/{repo}/releases/tags/{release_tag(tag)}"
    else:
        url = f"{GITHUB_API}/repos/{repo}/releases/latest"
    try:
        payload = fetch(url, token)
    except UpdaterError as exc:
        log.warning("release lookup failed: %s", exc)
        return None
    return parse_release_assets(payload)


def download_release(
    remote: RemoteRelease,
    paths: UpdaterPaths,
    token: str,
    *,
    download: Callable[..., None] | None = None,
    sleep: SleepFn = time.sleep,
) -> Path:
    """Download tarball + sidecar to ``.part``, verify, then rename. Never leaves a usable ``.part``."""
    dest = paths.releases_dir / remote.tarball_name
    if is_complete_archive(dest):
        sidecar = Path(str(dest) + ".sha256")
        try:
            if sidecar.is_file():
                verify_archive_checksum(dest, sidecar)
                return dest
        except ApplyError:
            log.warning("existing %s failed checksum; re-downloading", dest.name)
            dest.unlink(missing_ok=True)
            sidecar.unlink(missing_ok=True)

    if remote.checksum_api_url is None:
        raise UpdaterError(f"release {remote.sha} has no sha256 sidecar")

    save = download or github_download
    paths.releases_dir.mkdir(parents=True, exist_ok=True)
    part = Path(str(dest) + ".part")
    sidecar_dest = Path(str(dest) + ".sha256")
    sidecar_part = Path(str(sidecar_dest) + ".part")
    last_error: Exception | None = None
    for attempt in range(MAX_DOWNLOAD_ATTEMPTS):
        part.unlink(missing_ok=True)
        sidecar_part.unlink(missing_ok=True)
        try:
            save(remote.checksum_api_url, sidecar_part, token)
            save(remote.tarball_api_url, part, token)
            expected = parse_sha256_sidecar(sidecar_part.read_text(encoding="utf-8"))
            actual = file_sha256(part)
            if expected != actual:
                raise ApplyError(f"downloaded sha256 mismatch: {actual} != {expected}")
            sidecar_part.replace(sidecar_dest)
            part.replace(dest)
            return dest
        except (UpdaterError, ApplyError, OSError, urllib.error.URLError) as exc:
            last_error = exc
            log.warning(
                "download attempt %s/%s failed: %s",
                attempt + 1,
                MAX_DOWNLOAD_ATTEMPTS,
                exc,
            )
            part.unlink(missing_ok=True)
            sidecar_part.unlink(missing_ok=True)
            if attempt + 1 < MAX_DOWNLOAD_ATTEMPTS:
                sleep(retry_delay(attempt))
    raise UpdaterError(f"download failed after {MAX_DOWNLOAD_ATTEMPTS} attempts: {last_error}")


def poll_and_download(
    paths: UpdaterPaths,
    token: str,
    repo: str,
    *,
    get_json: Callable[[str, str], dict] | None = None,
    download: Callable[..., None] | None = None,
    sleep: SleepFn = time.sleep,
) -> RemoteRelease | None:
    """Fetch latest (and applied SHA, for rollback insurance). Return latest remote."""
    latest = fetch_release(repo, token, get_json=get_json)
    if latest is None:
        return None
    download_release(latest, paths, token, download=download, sleep=sleep)

    applied = read_applied_sha(paths)
    if applied and applied != latest.sha and archive_for_sha(paths.releases_dir, applied) is None:
        previous = fetch_release(repo, token, tag=applied, get_json=get_json)
        if previous is not None:
            try:
                download_release(previous, paths, token, download=download, sleep=sleep)
            except UpdaterError:
                log.warning("could not prefetch applied-release %s for rollback", applied)
    return latest


# ---------------------------------------------------------------------------
# Apply / rollback
# ---------------------------------------------------------------------------


def find_uv() -> str:
    found = shutil.which("uv")
    if found:
        return found
    home = Path.home()
    candidates = [home / ".local" / "bin" / "uv", home / ".cargo" / "bin" / "uv"]
    if os.name == "nt":
        candidates = [c.with_suffix(".exe") for c in candidates] + candidates
    for path in candidates:
        if path.is_file():
            return str(path)
    return "uv"


def make_runner(cwd: Path) -> Runner:
    def run(argv: Sequence[str], *, check: bool = True) -> int:
        log.info("+ %s", " ".join(str(a) for a in argv))
        completed = subprocess.run([str(a) for a in argv], cwd=cwd)
        if check and completed.returncode != 0:
            raise CommandError(argv, completed.returncode)
        return completed.returncode

    return run


def _service_active(run: Runner, service: str) -> bool:
    return run(["sudo", "systemctl", "is-active", "--quiet", service], check=False) == 0


def spawned_from_web() -> bool:
    return os.environ.get(SPAWNED_ENV) == "1"


def reload_web(run: Runner, service: str) -> None:
    """Reload Gunicorn workers without stopping the systemd unit (or this updater).

    When spawned by start.sh, Gunicorn is our parent (same PID after ``exec``).
    ``systemctl restart club`` would kill the whole cgroup, including us.
    Manual ``--apply-now`` still uses ``systemctl restart``.
    """
    if spawned_from_web():
        ppid = os.getppid()
        if ppid > 1:
            log.info("SIGHUP gunicorn master pid=%s", ppid)
            os.kill(ppid, SIGHUP)
            return
        log.warning("%s set but ppid=%s; falling back to systemctl restart", SPAWNED_ENV, ppid)
    run(["sudo", "systemctl", "restart", service])


def reexec_updater(paths: UpdaterPaths) -> None:
    """Replace this process with the on-disk updater (new code after unpack)."""
    python = paths.root / ".venv" / "bin" / "python"
    script = paths.root / "scripts" / "updater.py"
    if not python.is_file() or not script.is_file():
        log.warning("skip re-exec: missing %s or %s", python, script)
        return
    log.info("re-exec %s %s", python, script)
    os.execv(str(python), [str(python), str(script)])


def _check_window(now: datetime, policy: SitePolicy, *, respect_window: bool) -> None:
    if respect_window and past_window_end(now, policy):
        raise WindowClosed("apply window closed")


def rollback_release(
    paths: UpdaterPaths,
    *,
    previous_archive: Path | None,
    db_snapshot: Path | None,
    previous_sha: str | None,
    restore_files: bool,
    run: Runner,
    sleep: SleepFn,
    service: str,
) -> None:
    log.error("rolling back to %s", previous_sha or "current files + db snapshot")
    try:
        update_progress(paths.maintenance_flag, "rollback")
        if restore_files and previous_archive is not None and is_complete_archive(previous_archive):
            unpack_archive(previous_archive, paths.staging_dir)
            sync_tree(paths.staging_dir, paths.root)
        elif restore_files:
            log.error("no previous tarball; leaving files as they are")
        if db_snapshot is not None and db_snapshot.is_file():
            restore_sqlite(db_snapshot, paths.db)
            log.info("restored DB snapshot %s", db_snapshot)
        uv = find_uv()
        run([uv, "sync", "--frozen"])
        run([uv, "run", "python", "manage.py", "collectstatic", "--noinput"])
        reload_web(run, service)
        sleep(HEALTH_WAIT_SECONDS)
        healthy = _service_active(run, service)
        if previous_sha:
            write_applied_sha(paths, previous_sha)
        if healthy:
            leave_update(paths.maintenance_flag)
        else:
            log.error("rollback service unhealthy; leaving MAINTENANCE on")
    except Exception:
        log.exception("rollback failed; leaving MAINTENANCE on")


def apply_release(
    paths: UpdaterPaths,
    archive: Path,
    policy: SitePolicy,
    *,
    run: Runner | None = None,
    sleep: SleepFn = time.sleep,
    now_fn: NowFn | None = None,
    respect_window: bool = True,
    service: str = "club",
    drain_seconds: float = DRAIN_SECONDS,
    reexec: bool = False,
) -> str:
    """Apply a complete local tarball. On failure or window end, roll back."""
    sha = archive_sha(archive)
    if sha is None:
        raise ApplyError(f"refusing to apply incomplete archive {archive.name}")
    sidecar = Path(str(archive) + ".sha256")
    if sidecar.is_file():
        verify_archive_checksum(archive, sidecar)

    now_fn = now_fn or (lambda: datetime.now(timezone.utc))
    run = run or make_runner(paths.root)
    previous_sha = read_applied_sha(paths)
    previous = archive_for_sha(paths.releases_dir, previous_sha) if previous_sha else None
    if previous_sha and previous is None:
        log.warning(
            "applied-release %s has no local tarball; file rollback may be impossible",
            previous_sha,
        )

    stamp = now_fn().strftime("%Y%m%d-%H%M%S")
    db_bak = paths.backups_dir / f"db-{stamp}.sqlite3"
    files_changed = False
    uv = find_uv()

    enter_update(paths.maintenance_flag, sha=sha)
    sleep(drain_seconds)
    update_progress(paths.maintenance_flag, "backup", sha=sha)
    backup_sqlite(paths.db, db_bak)
    try:
        prune_db_backups(paths, policy.update_db_backup_keep)
    except OSError:
        log.warning("prune of old DB snapshots failed", exc_info=True)

    try:
        _check_window(now_fn(), policy, respect_window=respect_window)
        update_progress(paths.maintenance_flag, "unpack", sha=sha)
        unpack_archive(archive, paths.staging_dir)
        _check_window(now_fn(), policy, respect_window=respect_window)
        update_progress(paths.maintenance_flag, "sync", sha=sha)
        sync_tree(paths.staging_dir, paths.root)
        files_changed = True
        _check_window(now_fn(), policy, respect_window=respect_window)
        update_progress(paths.maintenance_flag, "deps", sha=sha)
        run([uv, "sync", "--frozen"])
        _check_window(now_fn(), policy, respect_window=respect_window)
        update_progress(paths.maintenance_flag, "migrate", sha=sha)
        run([uv, "run", "python", "manage.py", "migrate"])
        _check_window(now_fn(), policy, respect_window=respect_window)
        update_progress(paths.maintenance_flag, "collectstatic", sha=sha)
        run([uv, "run", "python", "manage.py", "collectstatic", "--noinput"])
        _check_window(now_fn(), policy, respect_window=respect_window)
        update_progress(paths.maintenance_flag, "reload", sha=sha)
        reload_web(run, service)
        sleep(HEALTH_WAIT_SECONDS)
        if not _service_active(run, service):
            raise ApplyError(f"{service} is not active after reload")
        write_applied_sha(paths, sha)
        try:
            os.utime(archive, None)
        except OSError:
            pass
        try:
            prune_releases(paths, policy.update_release_keep)
        except OSError:
            log.warning("prune of old release tarballs failed", exc_info=True)
    except Exception as exc:
        log.exception("apply of %s failed: %s", sha, exc)
        rollback_release(
            paths,
            previous_archive=previous,
            db_snapshot=db_bak if db_bak.is_file() else None,
            previous_sha=previous_sha,
            restore_files=files_changed,
            run=run,
            sleep=sleep,
            service=service,
        )
        raise

    leave_update(paths.maintenance_flag)
    log.info("applied %s", sha)
    if reexec:
        reexec_updater(paths)
    return sha


def _ensure_uv_on_path() -> None:
    home = Path.home()
    extra = [str(home / ".local" / "bin"), str(home / ".cargo" / "bin")]
    parts = os.environ.get("PATH", "").split(os.pathsep)
    for item in reversed(extra):
        if item and item not in parts:
            parts.insert(0, item)
    os.environ["PATH"] = os.pathsep.join(parts)


def _configure_logging() -> None:
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def _apply_pending(
    paths: UpdaterPaths,
    policy: SitePolicy,
    *,
    remote_sha: str | None,
    respect_window: bool,
    service: str,
    blocking_lock: bool,
    run: Runner | None = None,
    sleep: SleepFn = time.sleep,
    now_fn: NowFn | None = None,
    reexec: bool = False,
) -> str | None:
    archive = pending_archive(paths, remote_sha=remote_sha)
    if archive is None:
        return None
    try:
        with update_lock(paths.lock_file, blocking=blocking_lock):
            if respect_window and not can_start_apply(
                (now_fn or (lambda: datetime.now(timezone.utc)))(),
                policy,
            ):
                return None
            return apply_release(
                paths,
                archive,
                policy,
                run=run,
                sleep=sleep,
                now_fn=now_fn,
                respect_window=respect_window,
                service=service,
                reexec=reexec,
            )
    except BlockingIOError:
        log.info("skip apply: %s held", paths.lock_file)
        return None


def poll_tick(
    paths: UpdaterPaths,
    policy: SitePolicy,
    *,
    service: str = "club",
    run: Runner | None = None,
    sleep: SleepFn = time.sleep,
    now_fn: NowFn | None = None,
    get_json=None,
    download=None,
    apply: bool = True,
    reexec: bool = False,
) -> RemoteRelease | None:
    """One loop iteration: maybe download, maybe apply. Used by the daemon and tests."""
    if not policy.auto_update_enabled:
        log.info("auto_update_enabled=false; skip download and apply")
        return None
    token = github_token()
    repo = github_repo()
    remote = None
    if token:
        try:
            remote = poll_and_download(
                paths,
                token,
                repo,
                get_json=get_json,
                download=download,
                sleep=sleep,
            )
        except UpdaterError:
            log.exception("poll/download failed")
    else:
        log.warning("UPDATE_GITHUB_TOKEN empty; skip download")

    if not apply:
        return remote
    now = (now_fn or (lambda: datetime.now(timezone.utc)))()
    if not can_start_apply(now, policy):
        return remote
    _apply_pending(
        paths,
        policy,
        remote_sha=remote.sha if remote else None,
        respect_window=True,
        service=service,
        blocking_lock=False,
        run=run,
        sleep=sleep,
        now_fn=now_fn,
        reexec=reexec,
    )
    return remote


def apply_now(
    paths: UpdaterPaths | None = None,
    *,
    service: str | None = None,
    run: Runner | None = None,
    sleep: SleepFn = time.sleep,
    get_json=None,
    download=None,
) -> int:
    """Manual path: download latest if needed, apply regardless of window."""
    from django.conf import settings as dj_settings

    paths = paths or UpdaterPaths.from_root(Path(dj_settings.BASE_DIR))
    paths.ensure_dirs()
    service = service or os.environ.get("SERVICE_NAME", "club")
    policy = load_policy()
    token = github_token()
    remote = None
    if token:
        try:
            remote = poll_and_download(
                paths,
                token,
                github_repo(),
                get_json=get_json,
                download=download,
                sleep=sleep,
            )
        except UpdaterError:
            log.exception("download before --apply-now failed")
    archive = pending_archive(paths, remote_sha=remote.sha if remote else None)
    if archive is None:
        applied = read_applied_sha(paths)
        if remote is not None and remote.sha == applied:
            log.info("already on %s", applied)
            return 0
        log.error("nothing to apply (no complete pending package on disk)")
        return 1
    try:
        with update_lock(paths.lock_file, blocking=True):
            apply_release(
                paths,
                archive,
                policy,
                run=run,
                sleep=sleep,
                respect_window=False,
                service=service,
            )
    except Exception:
        log.exception("--apply-now failed")
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    _configure_logging()
    _ensure_uv_on_path()
    parser = argparse.ArgumentParser(description="Club GitHub-release updater")
    parser.add_argument(
        "--apply-now",
        action="store_true",
        help="download latest if needed and apply immediately (ignore window)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    from django.conf import settings as dj_settings

    paths = UpdaterPaths.from_root(Path(dj_settings.BASE_DIR))
    paths.ensure_dirs()
    service = os.environ.get("SERVICE_NAME", "club")

    if args.apply_now:
        return apply_now(paths, service=service)

    log.info("updater loop starting (root=%s)", paths.root)
    while True:
        policy = load_policy()
        interval = max(1, int(policy.update_poll_interval_seconds or 900))
        try:
            poll_tick(paths, policy, service=service, reexec=True)
        except Exception:
            log.exception("updater tick failed")
        time.sleep(interval)
