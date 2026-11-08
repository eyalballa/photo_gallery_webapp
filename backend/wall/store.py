"""SQLite persistence. Rows go in and come out as pydantic models."""

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from wall.schemas import Status

SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  url TEXT NOT NULL,
  created_at TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  removed_at TEXT,
  processed_at TEXT,
  status TEXT NOT NULL CHECK (status IN ('pending','ready','failed','removed')),
  width INT NOT NULL,
  height INT NOT NULL,
  faces INT,
  effect TEXT,
  variant TEXT,
  aged_paper INT NOT NULL DEFAULT 0,
  reroll_salt INT NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 1,
  error TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def ts(at: datetime) -> str:
    """Timestamps are compared as text in SQL, so every one is stored and queried as UTC isoformat."""
    return (at if at.tzinfo else at.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()


class PhotoRow(BaseModel):
    id: str
    source: str
    url: str
    created_at: datetime
    first_seen_at: datetime
    removed_at: datetime | None = None
    processed_at: datetime | None = None
    status: Status
    width: int
    height: int
    faces: int | None = None
    effect: str | None = None
    variant: str | None = None
    aged_paper: bool = False
    reroll_salt: int = 0
    version: int = 1
    error: str | None = None


class ProcessedFields(BaseModel):
    status: Status
    width: int
    height: int
    faces: int | None
    effect: str | None
    variant: str | None
    aged_paper: bool
    error: str | None = None


class PhotoStore:
    """Thread-safe (one connection, one lock): the API, the sync task and the process pool share it."""

    def __init__(self, path: Path | str):
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)

    def _rows(self, sql: str, *args) -> list[PhotoRow]:
        with self._lock:
            return [PhotoRow.model_validate(dict(r)) for r in self._db.execute(sql, args)]

    def _exec(self, sql: str, *args) -> None:
        with self._lock, self._db:
            self._db.execute(sql, args)

    def get(self, photo_id: str) -> PhotoRow | None:
        rows = self._rows("SELECT * FROM photos WHERE id = ?", photo_id)
        return rows[0] if rows else None

    def known_ids(self) -> set[str]:
        """Ids of every photo not marked removed."""
        with self._lock:
            return {r[0] for r in self._db.execute("SELECT id FROM photos WHERE status != 'removed'")}

    def insert_pending(self, row: PhotoRow) -> None:
        """Adds a new photo, or brings back one that was removed and re-added to the album."""
        self._exec(
            """INSERT INTO photos (id, source, url, created_at, first_seen_at, status, width, height)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
               ON CONFLICT(id) DO UPDATE SET status='pending', removed_at=NULL, url=excluded.url""",
            row.id, row.source, row.url, ts(row.created_at), ts(row.first_seen_at), row.width, row.height,
        )

    def mark_removed(self, photo_id: str, at: datetime) -> None:
        self._exec("UPDATE photos SET status='removed', removed_at=? WHERE id=?", ts(at), photo_id)

    def pending(self, limit: int | None = None) -> list[PhotoRow]:
        return self._rows("SELECT * FROM photos WHERE status='pending' ORDER BY created_at LIMIT ?", limit or -1)

    def ready_since(self, since: datetime | None) -> list[PhotoRow]:
        """Ready photos that are new or were re-processed after `since`; all ready photos when `since` is None."""
        if since is None:
            return self._rows("SELECT * FROM photos WHERE status='ready' ORDER BY first_seen_at")
        return self._rows(
            "SELECT * FROM photos WHERE status='ready' AND processed_at > ? ORDER BY first_seen_at", ts(since)
        )

    def removed_since(self, since: datetime | None) -> list[str]:
        if since is None:
            return []
        with self._lock:
            return [r[0] for r in self._db.execute("SELECT id FROM photos WHERE status='removed' AND removed_at > ?", (ts(since),))]

    def save_processed(self, photo_id: str, f: ProcessedFields, at: datetime) -> None:
        self._exec(
            """UPDATE photos SET status=?, width=?, height=?, faces=?, effect=?, variant=?, aged_paper=?, error=?,
               processed_at=? WHERE id=? AND status != 'removed'""",
            f.status, f.width, f.height, f.faces, f.effect, f.variant, int(f.aged_paper), f.error, ts(at), photo_id,
        )

    def queue_reroll(self, photo_id: str | None) -> int:
        """Sends ready photos back to processing with a new salt and a bumped version (busts browser caches)."""
        where, args = ("AND id=?", (photo_id,)) if photo_id else ("", ())
        with self._lock, self._db:
            cur = self._db.execute(
                f"UPDATE photos SET status='pending', reroll_salt=reroll_salt+1, version=version+1 WHERE status IN ('ready','failed') {where}",
                args,
            )
            return cur.rowcount

    def counts(self) -> dict[str, int]:
        with self._lock:
            return {r[0]: r[1] for r in self._db.execute("SELECT status, COUNT(*) FROM photos GROUP BY status")}

    def get_meta(self, key: str) -> str | None:
        with self._lock:
            r = self._db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
            return r[0] if r else None

    def set_meta(self, key: str, value: str | None) -> None:
        self._exec("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", key, value)

    def wipe(self) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM photos")
            self._db.execute("DELETE FROM meta")
