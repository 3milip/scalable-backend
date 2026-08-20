from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
SERVICE_KEY = os.environ.get("SERVICE_KEY", "dev-service-key")


def post_results(body: dict, retries: int = 1) -> bool:
    url = BACKEND_URL.rstrip("/") + "/internal/results"
    payload = json.dumps(body).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        request = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Service-Key": SERVICE_KEY,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                if 200 <= response.status < 300:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
        if attempt + 1 < retries:
            time.sleep(0.5)
    if last_error is not None:
        print(f"callback: {last_error}")
    return False
