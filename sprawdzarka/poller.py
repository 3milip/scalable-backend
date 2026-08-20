from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sprawdzarka.map_status import map_status
from sprawdzarka.oioioi_api import fetch_status, service_token
from sprawdzarka.jobs import get_job, open_jobs, tests_of, update_job
from sprawdzarka.security import SERVICE_KEY

_stop = threading.Event()
_thread: threading.Thread | None = None


def start() -> None:
    global _thread
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="judge-poller", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()


def _loop() -> None:
    token = ""
    while not _stop.is_set():
        try:
            if not token:
                token = service_token()
            _tick(token)
        except Exception:
            token = ""
        _stop.wait(1.5)


def _tick(token: str) -> None:
    for job in open_jobs():
        oioioi_id = job.get("oioioi_id")
        if not oioioi_id:
            fails = int(job.get("poll_fails") or 0) + 1
            if fails >= 3:
                _finish(job, "failed", None, None, "brak oioioi_id")
            else:
                update_job(job["id"], poll_fails=fails, status="running")
            continue
        try:
            row = fetch_status(token, job["problem_short_name"], int(oioioi_id))
        except RuntimeError:
            fails = int(job.get("poll_fails") or 0) + 1
            update_job(job["id"], poll_fails=fails, status="running")
            if fails >= 8:
                _finish(job, "failed", None, None, "poll OIOIOI nie działa")
            continue
        if row is None:
            update_job(job["id"], status="running")
            continue
        raw_score = row.get("score")
        score = int(raw_score) if raw_score is not None else None
        status, verdict = map_status(row.get("status"), score, job.get("max_score"))
        if status == "running":
            update_job(job["id"], status="running", score=score)
            continue
        _finish(job, status, verdict, score, None)


def _finish(job: dict, status: str, verdict: str | None, score: int | None, message: str | None) -> None:
    update_job(
        job["id"],
        status=status,
        verdict=verdict,
        score=score,
        message=message,
    )
    fresh = get_job(int(job["id"])) or job
    payload = {
        "job_id": f"j-{fresh['id']}",
        "status": status,
        "verdict": verdict,
        "score": score,
        "max_score": fresh.get("max_score"),
        "time_ms": fresh.get("time_ms"),
        "memory_kb": fresh.get("memory_kb"),
        "message": message,
        "tests": tests_of(fresh),
    }
    ok = _callback(fresh["callback_url"], payload)
    if ok:
        update_job(fresh["id"], callback_sent=1)
    else:
        fails = int(fresh.get("poll_fails") or 0) + 1
        update_job(fresh["id"], poll_fails=fails)
        if fails >= 8:
            update_job(fresh["id"], callback_sent=1, message=(message or "") + " (callback padł)")


def _callback(url: str, payload: dict) -> bool:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "X-Service-Key": SERVICE_KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as error:
        return 200 <= error.code < 300
    except Exception:
        return False
