"""SQLite cache for text responses (HTML/JSON) and tile blobs."""
import sqlite3
import threading
import time
import pathlib
from typing import Optional, Tuple

import desktop.config as cfg


class Cache:
    def __init__(self, db_path: pathlib.Path):
        self._path = str(db_path)
        self._lock = threading.Lock()
        self._local = threading.local()
        self._init_schema()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        """Return a per-thread SQLite connection."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self._path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_schema(self):
        with self._lock:
            self._conn().executescript("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key          TEXT PRIMARY KEY,
                    body         TEXT NOT NULL,
                    content_type TEXT NOT NULL DEFAULT 'application/json',
                    fetched_at   REAL NOT NULL,
                    ttl_s        INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tile_cache (
                    z          INTEGER NOT NULL,
                    x          INTEGER NOT NULL,
                    y          INTEGER NOT NULL,
                    data       BLOB NOT NULL,
                    fetched_at REAL NOT NULL,
                    PRIMARY KEY (z, x, y)
                );
            """)
            self._conn().commit()

    # ------------------------------------------------------------------
    # Text cache (HTML, JSON, JS, CSS)
    # ------------------------------------------------------------------

    def get_text(self, key: str) -> Optional[Tuple[str, str, float, bool]]:
        """Return (body, content_type, fetched_at, is_stale) or None."""
        row = self._conn().execute(
            "SELECT body, content_type, fetched_at, ttl_s FROM cache_entries WHERE key=?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        is_stale = (time.time() - row["fetched_at"]) > row["ttl_s"]
        return row["body"], row["content_type"], row["fetched_at"], is_stale

    def set_text(self, key: str, body: str, content_type: str, ttl_s: int):
        with self._lock:
            self._conn().execute(
                """
                INSERT INTO cache_entries (key, body, content_type, fetched_at, ttl_s)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    body         = excluded.body,
                    content_type = excluded.content_type,
                    fetched_at   = excluded.fetched_at,
                    ttl_s        = excluded.ttl_s
                """,
                (key, body, content_type, time.time(), ttl_s),
            )
            self._conn().commit()

    # ------------------------------------------------------------------
    # Tile cache (PNG blobs)
    # ------------------------------------------------------------------

    def get_tile(self, z: int, x: int, y: int) -> Optional[bytes]:
        """Return PNG bytes or None if missing/expired."""
        row = self._conn().execute(
            "SELECT data, fetched_at FROM tile_cache WHERE z=? AND x=? AND y=?",
            (z, x, y),
        ).fetchone()
        if row is None:
            return None
        if (time.time() - row["fetched_at"]) > cfg.TTL_TILES:
            return None  # expired — re-fetch
        return bytes(row["data"])

    def set_tile(self, z: int, x: int, y: int, data: bytes):
        with self._lock:
            self._conn().execute(
                """
                INSERT INTO tile_cache (z, x, y, data, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(z, x, y) DO UPDATE SET
                    data       = excluded.data,
                    fetched_at = excluded.fetched_at
                """,
                (z, x, y, data, time.time()),
            )
            self._conn().commit()

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def clear(self, key: Optional[str] = None):
        """Delete one cache entry (or all if key is None)."""
        with self._lock:
            if key:
                self._conn().execute("DELETE FROM cache_entries WHERE key=?", (key,))
            else:
                self._conn().execute("DELETE FROM cache_entries")
            self._conn().commit()

    def close(self):
        if hasattr(self._local, "conn"):
            self._local.conn.close()
