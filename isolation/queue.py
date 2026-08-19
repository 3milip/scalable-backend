"""Port kolejki: job != zgłoszenie. Silnik: SQLite (SqliteQueue)."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from app.db import init_db, sqlite_path

LEASE_SECONDS = 60
MAX_ATTEMPTS = 3
HEARTBEAT_EVERY = 10
KIND_JUDGE = "judge"


@dataclass(frozen=True)
class Job:
    id: int
    submission_id: int
    kind: str
    attempts: int


def now_ts() -> int:
    return int(time.time())


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=5)
    conn.isolation_level = None
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def enqueue(
    submission_id: int,
    kind: str = KIND_JUDGE,
    priority: int = 0,
    path: Path | None = None,
) -> int | None:
    """Dodaj job jeśli nie ma już otwartego (queued/leased) tego rodzaju."""
    db_file = path or sqlite_path()
    conn = _connect(db_file)
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            """
            SELECT id FROM jobs
            WHERE submission_id = ? AND kind = ? AND status IN ('queued', 'leased')
            """,
            (submission_id, kind),
        ).fetchone()
        if existing:
            conn.execute("COMMIT")
            return int(existing[0])
        cur = conn.execute(
            """
            INSERT INTO jobs (submission_id, kind, status, priority, attempts)
            VALUES (?, ?, 'queued', ?, 0)
            """,
            (submission_id, kind, priority),
        )
        conn.execute("COMMIT")
        return int(cur.lastrowid)
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def claim(worker_id: str, path: Path | None = None) -> Job | None:
    db_file = path or sqlite_path()
    cutoff = now_ts() - LEASE_SECONDS
    stamp = now_ts()
    conn = _connect(db_file)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE jobs
            SET status = 'queued', leased_by = NULL, last_error = 'lease wygasl'
            WHERE status = 'leased'
              AND attempts < ?
              AND (heartbeat_at IS NULL OR heartbeat_at < ?)
              AND submission_id IN (
                  SELECT id FROM submissions WHERE status IN ('queued', 'running')
              )
            """,
            (MAX_ATTEMPTS, cutoff),
        )
        stale = conn.execute(
            """
            SELECT id, submission_id FROM jobs
            WHERE status = 'leased'
              AND attempts >= ?
              AND (heartbeat_at IS NULL OR heartbeat_at < ?)
              AND submission_id IN (
                  SELECT id FROM submissions WHERE status IN ('queued', 'running')
              )
            """,
            (MAX_ATTEMPTS, cutoff),
        ).fetchall()
        for job_id, submission_id in stale:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'failed', leased_by = NULL,
                    last_error = 'lease wygasl, limit prob'
                WHERE id = ?
                """,
                (job_id,),
            )
            conn.execute(
                """
                UPDATE submissions
                SET status = 'failed',
                    verdict = 'RE',
                    message = 'worker zmarl',
                    last_error = 'lease wygasl, limit prob',
                    finished_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status IN ('queued', 'running')
                """,
                (submission_id,),
            )
        row = conn.execute(
            """
            SELECT id, submission_id, kind, attempts FROM jobs
            WHERE status = 'queued'
            ORDER BY priority ASC, id ASC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            conn.execute("COMMIT")
            return None
        job_id, submission_id, kind, attempts = row
        conn.execute(
            """
            UPDATE jobs
            SET status = 'leased',
                leased_by = ?,
                attempts = attempts + 1,
                heartbeat_at = ?,
                last_error = NULL
            WHERE id = ?
            """,
            (worker_id, stamp, job_id),
        )
        conn.execute(
            """
            UPDATE submissions
            SET status = 'running'
            WHERE id = ? AND status = 'queued'
            """,
            (submission_id,),
        )
        conn.execute(
            "DELETE FROM submission_results WHERE submission_id = ?",
            (submission_id,),
        )
        conn.execute("COMMIT")
        return Job(
            id=int(job_id),
            submission_id=int(submission_id),
            kind=str(kind),
            attempts=int(attempts) + 1,
        )
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def heartbeat(job_id: int, path: Path | None = None) -> None:
    db_file = path or sqlite_path()
    conn = _connect(db_file)
    try:
        conn.execute(
            """
            UPDATE jobs SET heartbeat_at = ?
            WHERE id = ? AND status = 'leased'
            """,
            (now_ts(), job_id),
        )
    finally:
        conn.close()


def ack(job_id: int, path: Path | None = None) -> None:
    db_file = path or sqlite_path()
    conn = _connect(db_file)
    try:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'done', leased_by = NULL
            WHERE id = ? AND status = 'leased'
            """,
            (job_id,),
        )
    finally:
        conn.close()


def nack(job_id: int, path: Path | None = None) -> None:
    """Oddaj job bez spalania próby (Ctrl+C)."""
    db_file = path or sqlite_path()
    conn = _connect(db_file)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT submission_id FROM jobs WHERE id = ? AND status = 'leased'",
            (job_id,),
        ).fetchone()
        conn.execute(
            """
            UPDATE jobs
            SET status = 'queued',
                leased_by = NULL,
                heartbeat_at = NULL,
                attempts = CASE WHEN attempts > 0 THEN attempts - 1 ELSE 0 END,
                last_error = 'worker zatrzymany'
            WHERE id = ? AND status = 'leased'
            """,
            (job_id,),
        )
        if row:
            conn.execute(
                """
                UPDATE submissions
                SET status = 'queued'
                WHERE id = ? AND status = 'running'
                """,
                (row[0],),
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def fail(job_id: int, reason: str, path: Path | None = None) -> None:
    db_file = path or sqlite_path()
    conn = _connect(db_file)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT submission_id FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        conn.execute(
            """
            UPDATE jobs
            SET status = 'failed', leased_by = NULL, last_error = ?
            WHERE id = ?
            """,
            (reason, job_id),
        )
        if row:
            conn.execute(
                """
                UPDATE submissions
                SET status = 'failed',
                    verdict = 'RE',
                    message = ?,
                    last_error = ?,
                    finished_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status IN ('queued', 'running')
                """,
                (reason, reason, row[0]),
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def touch_worker(worker_id: str, path: Path | None = None) -> None:
    db_file = path or sqlite_path()
    conn = _connect(db_file)
    try:
        conn.execute(
            """
            INSERT INTO workers (id, seen_at) VALUES (?, ?)
            ON CONFLICT(id) DO UPDATE SET seen_at = excluded.seen_at
            """,
            (worker_id, now_ts()),
        )
    finally:
        conn.close()


def remove_worker(worker_id: str, path: Path | None = None) -> None:
    db_file = path or sqlite_path()
    conn = _connect(db_file)
    try:
        conn.execute("DELETE FROM workers WHERE id = ?", (worker_id,))
    finally:
        conn.close()


def live_worker_count(path: Path | None = None) -> int:
    db_file = path or sqlite_path()
    cutoff = now_ts() - LEASE_SECONDS
    conn = _connect(db_file)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM workers WHERE seen_at >= ?",
            (cutoff,),
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def ensure_db() -> None:
    init_db()
