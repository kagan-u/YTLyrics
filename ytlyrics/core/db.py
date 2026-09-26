from __future__ import annotations

import re
import sqlite3
import threading
import time
from pathlib import Path

from .models import TERMINAL, TRANSITIONS, Status

_SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL DEFAULT '',
    comment_id TEXT NOT NULL DEFAULT '',
    commenter TEXT NOT NULL DEFAULT '',
    artist TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    query TEXT NOT NULL DEFAULT '',
    pitch REAL NOT NULL DEFAULT 0,
    bg_preset TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'queued',
    progress REAL NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    output_path TEXT NOT NULL DEFAULT '',
    yt_video_id TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_requests_dedupe
    ON requests(lower(artist), lower(title))
    WHERE status NOT IN ('done', 'cancelled', 'failed');
CREATE TABLE IF NOT EXISTS seen_comments (
    comment_id TEXT PRIMARY KEY,
    seen_at INTEGER NOT NULL
);
"""


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        self._lock = threading.Lock()
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @staticmethod
    def _row_to_request(row: sqlite3.Row) -> dict:
        return dict(row)

    def add_request(
        self,
        artist: str,
        title: str,
        *,
        video_id: str = "",
        comment_id: str = "",
        commenter: str = "",
        pitch: float = 0.0,
        bg_preset: str = "",
        query: str = "",
    ) -> int | None:
        now = int(time.time())
        with self._lock, self._conn() as conn:
            try:
                cur = conn.execute(
                    "INSERT INTO requests (video_id, comment_id, commenter, artist,"
                    " title, query, pitch, bg_preset, status, created_at, updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        video_id,
                        comment_id,
                        commenter,
                        artist.strip(),
                        title.strip(),
                        query or f"{artist} {title}".strip(),
                        pitch,
                        bg_preset,
                        Status.QUEUED.value,
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError:
                return None
            return int(cur.lastrowid)

    def list_requests(self, limit: int = 300) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM requests ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_request(self, req_id: int) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM requests WHERE id=?", (req_id,)
            ).fetchone()
        return dict(row) if row else None

    def recover_stale(self) -> int:
        """Requeue rows stuck in active states (app killed mid-job)."""
        active = [
            s.value
            for s in Status
            if s not in TERMINAL and s != Status.QUEUED
        ]
        with self._lock, self._conn() as conn:
            marks = ",".join("?" * len(active))
            cur = conn.execute(
                f"UPDATE requests SET status=?, progress=0, error='',"
                f" updated_at=? WHERE status IN ({marks})",
                (Status.QUEUED.value, int(time.time()), *active),
            )
            return cur.rowcount

    def claim_next(self) -> dict | None:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM requests WHERE status=? ORDER BY id LIMIT 1",
                (Status.QUEUED.value,),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE requests SET status=?, progress=0, updated_at=? WHERE id=?",
                (Status.DOWNLOADING.value, int(time.time()), row["id"]),
            )
            return dict(row) | {"status": Status.DOWNLOADING.value}

    def set_status(
        self, req_id: int, status: Status, error: str = ""
    ) -> bool:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT status FROM requests WHERE id=?", (req_id,)
            ).fetchone()
            if not row:
                return False
            current = Status(row["status"])
            if status == current:
                return True
            if status not in TRANSITIONS[current]:
                return False
            conn.execute(
                "UPDATE requests SET status=?, error=?, progress=?, updated_at=?"
                " WHERE id=?",
                (status.value, error, 0.0 if status != Status.DONE else 1.0,
                 int(time.time()), req_id),
            )
            return True

    def set_progress(self, req_id: int, progress: float, stage: str = "") -> None:
        progress = max(0.0, min(1.0, progress))
        with self._lock, self._conn() as conn:
            conn.execute(
                "UPDATE requests SET progress=?, updated_at=? WHERE id=?",
                (progress, int(time.time()), req_id),
            )

    def set_result(
        self,
        req_id: int,
        *,
        output_path: str = "",
        yt_video_id: str = "",
        status: Status = Status.DONE,
        error: str = "",
    ) -> bool:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT status FROM requests WHERE id=?", (req_id,)
            ).fetchone()
            if not row:
                return False
            current = Status(row["status"])
            if status not in TRANSITIONS[current] and status != current:
                return False
            conn.execute(
                "UPDATE requests SET status=?, error=?, progress=?, output_path=?,"
                " yt_video_id=?, updated_at=? WHERE id=?",
                (
                    status.value,
                    error,
                    1.0 if status == Status.DONE else 0.0,
                    output_path,
                    yt_video_id,
                    int(time.time()),
                    req_id,
                ),
            )
            return True

    def cancel(self, req_id: int) -> bool:
        return self.set_status(req_id, Status.CANCELLED)

    def retry(self, req_id: int) -> bool:
        return self.set_status(req_id, Status.QUEUED)

    def is_cancelled(self, req_id: int) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT status FROM requests WHERE id=?", (req_id,)
            ).fetchone()
        return bool(row) and row["status"] == Status.CANCELLED.value

    def mark_comment_seen(self, comment_id: str) -> bool:
        if not comment_id:
            return False
        with self._lock, self._conn() as conn:
            try:
                conn.execute(
                    "INSERT INTO seen_comments (comment_id, seen_at) VALUES (?,?)",
                    (comment_id, int(time.time())),
                )
            except sqlite3.IntegrityError:
                return False
            return True

    def has_comment_seen(self, comment_id: str) -> bool:
        if not comment_id:
            return True
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_comments WHERE comment_id=?", (comment_id,)
            ).fetchone()
        return row is not None

    def stats(self) -> dict[str, int]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM requests GROUP BY status"
            ).fetchall()
        out = {s.value: 0 for s in Status}
        for r in rows:
            out[r["status"]] = r["n"]
        return out


def normalize_key(artist: str, title: str) -> str:
    return re.sub(r"\s+", " ", f"{artist} {title}".strip().lower())
