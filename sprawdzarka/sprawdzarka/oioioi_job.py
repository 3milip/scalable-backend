"""Submit-once + poll w tym samym lease. Worker woła to zamiast isolate."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sprawdzarka.oioioi_client import (
    OioioiClient,
    OioioiError,
    OioioiHttpError,
    OioioiSubmitUncertain,
    is_terminal,
    parse_score,
)
from sprawdzarka.queue import Job, heartbeat, merge_payload, oioioi_id_from_payload

POLL_INTERVAL_SEC = 2.0
POLL_TIMEOUT_SEC = 600.0


@dataclass(frozen=True)
class OioioiJobResult:
    ok: bool
    oioioi_id: int | None
    status: str | None
    score: int | None
    message: str | None
    item: dict | None = None


def short_name_from_payload(payload: dict) -> str | None:
    for key in ("short_name", "oioioi_short_name", "external_id"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def run_oioioi_job(
    job: Job,
    client: OioioiClient,
    *,
    path: Path | None = None,
    heartbeat_fn: Callable[[int], None] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
    poll_interval: float = POLL_INTERVAL_SEC,
    poll_timeout: float = POLL_TIMEOUT_SEC,
) -> OioioiJobResult:
    beat = heartbeat_fn or (lambda job_id: heartbeat(job_id, path=path))
    short_name = short_name_from_payload(job.payload)
    code = str(job.payload.get("code") or "")
    if not short_name:
        return OioioiJobResult(False, None, None, None, "brak short_name zadania w jobie")
    if not code.strip():
        return OioioiJobResult(False, None, None, None, "pusty kod")

    oioioi_id = oioioi_id_from_payload(job.payload)
    if oioioi_id is None:
        try:
            oioioi_id = client.submit(short_name, code)
        except OioioiSubmitUncertain as error:
            return OioioiJobResult(False, None, None, None, str(error))
        except OioioiHttpError as error:
            return OioioiJobResult(False, None, None, None, f"OIOIOI HTTP {error.status}: {error.message}")
        except OioioiError as error:
            return OioioiJobResult(False, None, None, None, str(error))
        merge_payload(job.id, {"oioioi_submission_id": oioioi_id}, path=path)

    deadline = monotonic_fn() + poll_timeout
    while monotonic_fn() < deadline:
        beat(job.id)
        try:
            item, truncated = client.find_submission(short_name, oioioi_id)
        except OioioiHttpError as error:
            if error.status == 429:
                sleep_fn(poll_interval * 2)
                continue
            return OioioiJobResult(False, oioioi_id, None, None, f"OIOIOI HTTP {error.status}: {error.message}")
        except OioioiError as error:
            return OioioiJobResult(False, oioioi_id, None, None, str(error))
        if item is None:
            if truncated:
                return OioioiJobResult(
                    False,
                    oioioi_id,
                    None,
                    None,
                    "oioioi_submission_id wypadł z okna ostatnich 20",
                )
            sleep_fn(poll_interval)
            continue
        status = item.get("status")
        status_text = None if status is None else str(status)
        score = parse_score(item.get("score"))
        if is_terminal(status_text, score):
            return OioioiJobResult(True, oioioi_id, status_text, score, None, item)
        sleep_fn(poll_interval)
    return OioioiJobResult(False, oioioi_id, None, None, "timeout polla OIOIOI")
