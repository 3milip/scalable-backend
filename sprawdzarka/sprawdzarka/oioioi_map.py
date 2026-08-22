"""Mapowanie statusu OIOIOI → nasz callback. Per-test nadal puste; czas/RAM z submission_report."""

from __future__ import annotations

from sprawdzarka.oioioi_job import OioioiJobResult

OIOIOI_MAX_SCORE = 100

_STATUS = {
    "OK": "OK",
    "INI_OK": "OK",
    "WA": "WA",
    "TLE": "TLE",
    "MLE": "MLE",
    "RE": "RE",
    "RTE": "RE",
    "CE": "CE",
    "SE": "SI",
    "INI_ERR": "WA",
    "ERR": "SI",
    "RV": "RE",
}


def map_verdict(status: str | None) -> str:
    if not status:
        return "SI"
    return _STATUS.get(status, status if status in _STATUS.values() else "SI")


def to_callback(submission_id: int, result: OioioiJobResult) -> dict:
    if not result.ok:
        return {
            "submission_id": submission_id,
            "status": "failed",
            "message": result.message,
        }
    score = 0 if result.score is None else result.score
    max_score = OIOIOI_MAX_SCORE if result.max_score is None else result.max_score
    return {
        "submission_id": submission_id,
        "status": "done",
        "verdict": map_verdict(result.status),
        "score": score,
        "max_score": max_score,
        "time_ms": result.time_ms,
        "memory_kb": result.memory_kb,
        "tests": [],
        "message": result.message,
    }
