"""SQLite-backed request cache to memoize expensive external API calls."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".cache" / "trustworthy_science" / "api_cache.db"
_DEFAULT_TTL = 60 * 60 * 24 * 7  # 7 days in seconds


class SQLiteCache:
    """Simple key-value cache backed by SQLite.

    Keys are SHA-256 hashes of (namespace, args). Values are JSON-serialised.
    Entries expire after ``ttl`` seconds.
    """

    def __init__(self, db_path: Path | str = _DEFAULT_DB, ttl: int = _DEFAULT_TTL) -> None:
        self.db_path = Path(db_path)
        self.ttl = ttl
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_schema()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS cache (
                key      TEXT PRIMARY KEY,
                value    TEXT NOT NULL,
                stored   REAL NOT NULL
            )"""
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS cache_stored ON cache(stored)"
        )
        self._conn.commit()

    @staticmethod
    def _make_key(namespace: str, *args: Any, **kwargs: Any) -> str:
        payload = json.dumps({"ns": namespace, "a": args, "k": kwargs}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, namespace: str, *args: Any, **kwargs: Any) -> Any | None:
        key = self._make_key(namespace, *args, **kwargs)
        row = self._conn.execute(
            "SELECT value, stored FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value, stored = row
        if time.time() - stored > self.ttl:
            self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            self._conn.commit()
            return None
        return json.loads(value)

    def set(self, namespace: str, value: Any, *args: Any, **kwargs: Any) -> None:
        key = self._make_key(namespace, *args, **kwargs)
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, stored) VALUES (?, ?, ?)",
            (key, json.dumps(value), time.time()),
        )
        self._conn.commit()

    def clear_expired(self) -> int:
        cursor = self._conn.execute(
            "DELETE FROM cache WHERE stored < ?", (time.time() - self.ttl,)
        )
        self._conn.commit()
        return cursor.rowcount

    def clear_all(self) -> None:
        self._conn.execute("DELETE FROM cache")
        self._conn.commit()

    def __len__(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]


# Module-level singleton; callers can import `cache` directly
_cache: SQLiteCache | None = None


def get_cache(db_path: Path | str = _DEFAULT_DB, ttl: int = _DEFAULT_TTL) -> SQLiteCache:
    global _cache
    if _cache is None:
        _cache = SQLiteCache(db_path=db_path, ttl=ttl)
    return _cache
