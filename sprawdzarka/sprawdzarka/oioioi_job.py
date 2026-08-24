"""Submit-once + poll. Lista tylko do kolejki; karty z submission_report."""

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
    list_early_fail,
    parse_score,
    report_is_complete,
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
    time_ms: int | None = None
    memory_kb: int | None = None
    max_score: int | None = None


def short_name_from_payload(payload: dict) -> str | None:
    for key in ("short_name", "oioioi_short_name", "external_id"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def _str_or_none(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _result_from_report(
    oioioi_id: int,
    item: dict | None,
    report: dict,
    fallback_status: str | None,
) -> OioioiJobResult:
    verdict = _str_or_none(report.get("verdict")) or fallback_status
    score = parse_score(report.get("score"))
    if score is None:
        score = parse_score((item or {}).get("score"))
    return OioioiJobResult(
        True,
        oioioi_id,
        verdict,
        score,
        None,
        item,
        time_ms=parse_score(report.get("time_ms")),
        memory_kb=parse_score(report.get("memory_kb")),
        max_score=parse_score(report.get("max_score")),
    )


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
            report = client.get_submission_report(oioioi_id)
        except OioioiHttpError as error:
            if error.status == 429:
                sleep_fn(poll_interval * 2)
                continue
            sleep_fn(poll_interval)
            continue
        except OioioiError:
            sleep_fn(poll_interval)
            continue
        if not isinstance(report, dict):
            sleep_fn(poll_interval)
            continue
        status_text = _str_or_none(report.get("verdict") or report.get("status"))
        if report_is_complete(report) or list_early_fail(status_text):
            return _result_from_report(oioioi_id, None, report, status_text)
        sleep_fn(poll_interval)
    return OioioiJobResult(False, oioioi_id, None, None, "timeout polla OIOIOI")
