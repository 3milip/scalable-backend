from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

SPRAWDZARKA_URL = os.environ.get("SPRAWDZARKA_URL", "http://127.0.0.1:8002").rstrip("/")
SERVICE_KEY = os.environ.get("SERVICE_KEY", "dev-service-key")
PUBLIC_CALLBACK_BASE = os.environ.get("PUBLIC_CALLBACK_BASE", "http://127.0.0.1:8000").rstrip("/")


def enqueue_job(*, backend_submission_id: int, problem_short_name: str, language: str, code: str) -> str:
    payload = {
        "backend_submission_id": backend_submission_id,
        "callback_url": f"{PUBLIC_CALLBACK_BASE}/internal/submissions/{backend_submission_id}/result",
        "problem_short_name": problem_short_name,
        "language": language,
        "code": code,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{SPRAWDZARKA_URL}/jobs",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "X-Service-Key": SERVICE_KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"sprawdzarka {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"sprawdzarka niedostępna: {error}") from error
    job_id = data.get("job_id")
    if not job_id:
        raise RuntimeError("sprawdzarka nie zwróciła job_id")
    return str(job_id)
