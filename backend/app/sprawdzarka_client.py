from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

SPRAWDZARKA_URL = os.environ.get("SPRAWDZARKA_URL", "http://127.0.0.1:8002")
SERVICE_KEY = os.environ.get("SERVICE_KEY", "dev-service-key")


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Service-Key": SERVICE_KEY,
    }


def post_job(body: dict) -> dict | None:
    url = SPRAWDZARKA_URL.rstrip("/") + "/jobs"
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers=_headers(),
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def fetch_workers() -> int:
    url = SPRAWDZARKA_URL.rstrip("/") + "/stats"
    request = urllib.request.Request(url, method="GET", headers=_headers())
    try:
        with urllib.request.urlopen(request, timeout=1) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            return int(data.get("workers") or 0)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, TypeError, ValueError):
        return 0
