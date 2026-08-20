from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
DB = DATA / "jobs.db"
_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with _lock:
        conn = _connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backend_submission_id INTEGER NOT NULL,
                callback_url TEXT NOT NULL,
                problem_short_name TEXT NOT NULL,
                language TEXT NOT NULL,
                code TEXT NOT NULL,
                oioioi_id INTEGER,
                status TEXT NOT NULL DEFAULT 'queued',
                verdict TEXT,
                score INTEGER,
                max_score INTEGER,
                time_ms INTEGER,
                memory_kb INTEGER,
                message TEXT,
                tests_json TEXT,
                callback_sent INTEGER NOT NULL DEFAULT 0,
                poll_fails INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()


def create_job(
    *,
    backend_submission_id: int,
    callback_url: str,
    problem_short_name: str,
    language: str,
    code: str,
    oioioi_id: int | None,
    status: str,
) -> int:
    with _lock:
        conn = _connect()
        cur = conn.execute(
            """
            INSERT INTO jobs (
                backend_submission_id, callback_url, problem_short_name, language, code,
                oioioi_id, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                backend_submission_id,
                callback_url,
                problem_short_name,
                language,
                code,
                oioioi_id,
                status,
                time.time(),
            ),
        )
        conn.commit()
        job_id = int(cur.lastrowid)
        conn.close()
        return job_id


def get_job(job_id: int) -> dict | None:
    with _lock:
        conn = _connect()
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        conn.close()
    return dict(row) if row else None


def open_jobs() -> list[dict]:
    with _lock:
        conn = _connect()
        rows = conn.execute(
            "SELECT * FROM jobs WHERE callback_sent = 0 AND status IN ('queued', 'running')"
        ).fetchall()
        conn.close()
    return [dict(r) for r in rows]


def update_job(job_id: int, **fields: object) -> None:
    if not fields:
        return
    keys = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [job_id]
    with _lock:
        conn = _connect()
        conn.execute(f"UPDATE jobs SET {keys} WHERE id = ?", values)
        conn.commit()
        conn.close()


def tests_of(job: dict) -> list:
    raw = job.get("tests_json")
    if not raw:
        return []
    return json.loads(raw)
