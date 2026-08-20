from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Submission, SubmissionResult, Test, _now
from app.schemas import CallbackIn

TERMINAL = {"done", "failed"}


def apply_callback(db: Session, payload: CallbackIn) -> None:
    submission = db.query(Submission).filter(Submission.id == payload.submission_id).first()
    if submission is None:
        raise HTTPException(status_code=404, detail="Nie ma takiego zgłoszenia")

    if submission.status in TERMINAL:
        return

    if payload.status == "running":
        submission.status = "running"
        db.commit()
        return

    if payload.status == "failed":
        submission.status = "failed"
        submission.message = payload.message
        submission.finished_at = _now()
        db.commit()
        return

    if payload.status != "done":
        raise HTTPException(status_code=422, detail="Nieznany status callbacku")

    for item in payload.tests:
        test = db.get(Test, item.test_id)
        if test is None:
            raise HTTPException(status_code=422, detail=f"Nie ma testu {item.test_id}")

    db.query(SubmissionResult).filter(
        SubmissionResult.submission_id == submission.id
    ).delete()

    submission.status = "done"
    submission.verdict = payload.verdict
    submission.time_ms = payload.time_ms
    submission.memory_kb = payload.memory_kb
    submission.message = payload.message
    submission.score = payload.score
    if payload.max_score is not None:
        submission.max_score = payload.max_score
    submission.finished_at = _now()

    for item in payload.tests:
        db.add(
            SubmissionResult(
                submission_id=submission.id,
                test_id=item.test_id,
                verdict=item.verdict,
                time_ms=item.time_ms,
                memory_kb=item.memory_kb,
                score=item.score,
                message=item.message,
            )
        )
    db.commit()
