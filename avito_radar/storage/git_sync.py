"""Sync of the data/ directory with a private git repository.

Enabled when the DATA_REPO_URL env var is set to an https URL with embedded
credentials, e.g. https://x-access-token:TOKEN@github.com/user/avito-radar-data.git

On startup the data is restored from the remote repository; a background
thread then commits and pushes local changes every SYNC_INTERVAL seconds.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from avito_radar.storage.db import DATA_DIR

logger = logging.getLogger(__name__)

SYNC_INTERVAL = int(os.environ.get("DATA_SYNC_INTERVAL", "300"))


def _repo_url() -> str:
    return os.environ.get("DATA_REPO_URL", "").strip()


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120,
    )


def restore_data() -> bool:
    """Clone or pull the data repository into DATA_DIR. Returns True if sync is enabled."""
    url = _repo_url()
    if not url:
        return False
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if (DATA_DIR / ".git").exists():
            fetch = _git(["fetch", "origin"], DATA_DIR)
            if fetch.returncode == 0:
                _git(["reset", "--hard", "origin/HEAD"], DATA_DIR)
        else:
            with tempfile.TemporaryDirectory() as tmp:
                clone = _git(["clone", "--depth", "1", url, tmp], Path("."))
                if clone.returncode != 0:
                    logger.error("Data sync: clone failed: %s", clone.stderr.strip())
                    return True
                shutil.move(str(Path(tmp) / ".git"), str(DATA_DIR / ".git"))
            _git(["checkout", "--", "."], DATA_DIR)
        _git(["config", "user.name", "avito-radar-bot"], DATA_DIR)
        _git(["config", "user.email", "bot@avito-radar.local"], DATA_DIR)
        ignore = DATA_DIR / ".gitignore"
        if not ignore.exists():
            ignore.write_text("bot.lock\n__pycache__/\n", encoding="utf-8")
        logger.info("Data sync: data restored from remote repository")
    except Exception as exc:
        logger.error("Data sync: restore failed: %s", exc)
    return True


def _sync_once() -> None:
    if not (DATA_DIR / ".git").exists():
        return
    status = _git(["status", "--porcelain"], DATA_DIR)
    if status.returncode != 0 or not status.stdout.strip():
        return
    _git(["add", "-A"], DATA_DIR)
    msg = f"data snapshot {time.strftime('%Y-%m-%d %H:%M:%S')}"
    commit = _git(["commit", "-m", msg], DATA_DIR)
    if commit.returncode != 0:
        logger.error("Data sync: commit failed: %s", commit.stderr.strip())
        return
    push = _git(["push", "origin", "HEAD"], DATA_DIR)
    if push.returncode != 0:
        logger.warning("Data sync: push rejected, rebasing: %s", push.stderr.strip())
        _git(["pull", "--rebase", "origin"], DATA_DIR)
        retry = _git(["push", "origin", "HEAD"], DATA_DIR)
        if retry.returncode != 0:
            logger.error("Data sync: push failed: %s", retry.stderr.strip())


def start_sync_thread(interval: int = SYNC_INTERVAL) -> None:
    """Start the background push loop. No-op unless DATA_REPO_URL is set and restored."""
    if not _repo_url():
        return
    if not (DATA_DIR / ".git").exists():
        logger.warning("Data sync: no git repository in data/, sync disabled")
        return

    def loop() -> None:
        while True:
            time.sleep(interval)
            try:
                _sync_once()
            except Exception as exc:
                logger.error("Data sync: %s", exc)

    threading.Thread(target=loop, daemon=True).start()
    logger.info("Data sync: enabled, pushing every %ds", interval)
