"""Keep the rotating Threads token encrypted in a public repository."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet

from threads_api import ThreadsAPI

TOKEN_FILE = Path(__file__).resolve().parent / "private" / "threads_token.enc"


def _cipher() -> Fernet:
    key = os.environ.get("CATNOTE_TOKEN_ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError("Missing token encryption key")
    return Fernet(key.encode("ascii"))


def load() -> tuple[str, datetime]:
    if TOKEN_FILE.exists():
        data = json.loads(_cipher().decrypt(TOKEN_FILE.read_bytes()))
        return data["access_token"], datetime.fromisoformat(data["refreshed_at"])
    bootstrap = os.environ.get("CATNOTE_THREADS_BOOTSTRAP_TOKEN", "")
    if not bootstrap:
        raise RuntimeError("No encrypted Threads token or bootstrap secret")
    # Initial token must be a long-lived token obtained through the official
    # Threads developer flow. It is never printed or written in plaintext.
    return bootstrap, datetime.now(timezone.utc)


def save(token: str, refreshed_at: datetime) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps({"access_token": token, "refreshed_at": refreshed_at.isoformat()})
    TOKEN_FILE.write_bytes(_cipher().encrypt(data.encode("utf-8")))


def maybe_refresh(api: ThreadsAPI, refreshed_at: datetime) -> bool:
    now = datetime.now(timezone.utc)
    if now - refreshed_at < timedelta(days=30):
        return False
    new_token = api.refresh()
    save(new_token, now)
    api.token = new_token
    return True
