from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Problem, Submission
from app.schemas import (
    HealthOut,
    ProblemDetailOut,
    ProblemListOut,
    ProblemOut,
    StatsOut,
    SubmissionCreatedOut,
    SubmissionIn,
    SubmissionOut,
)

WORKERS = 4

app = FastAPI(title="scalable-backend")


@app.get("/health", response_model=HealthOut)
def health():
    return {"status": "ok"}


@app.get("/problems", response_model=ProblemListOut)
def list_problems(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    tag: str | None = None,
    difficulty: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Problem)
    if difficulty is not None:
        query = query.filter(Problem.difficulty == difficulty)

    items = query.all()
    if tag:
        items = [p for p in items if tag in (p.tags or [])]

    total = len(items)
    page = items[offset : offset + limit]
    return ProblemListOut(
        total=total,
        items=[
            ProblemOut(
                id=p.id,
                title=p.title,
                difficulty=p.difficulty,
                tags=p.tags or [],
                source=p.source,
            )
            for p in page
        ],
    )


@app.get("/problems/{problem_id}", response_model=ProblemDetailOut)
def get_problem(problem_id: int, db: Session = Depends(get_db)):
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if problem is None:
        raise HTTPException(status_code=404, detail="Nie ma takiego zadania")
    return ProblemDetailOut(
        id=problem.id,
        title=problem.title,
        difficulty=problem.difficulty,
        tags=problem.tags or [],
        source=problem.source,
        statement=problem.statement,
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
    )


@app.post("/submissions", response_model=SubmissionCreatedOut)
def create_submission(payload: SubmissionIn, db: Session = Depends(get_db)):
    problem = db.query(Problem).filter(Problem.id == payload.problem_id).first()
    if problem is None:
        raise HTTPException(status_code=404, detail="Nie ma takiego zadania")

    submission = Submission(
        problem_id=payload.problem_id,
        language=payload.language,
        code=payload.code,
        status="queued",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return SubmissionCreatedOut(id=submission.id, status=submission.status)


@app.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: int, db: Session = Depends(get_db)):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if submission is None:
        raise HTTPException(status_code=404, detail="Nie ma takiego zgłoszenia")
    return SubmissionOut(
        id=submission.id,
        problem_id=submission.problem_id,
        language=submission.language,
        status=submission.status,
        verdict=submission.verdict,
        time_ms=submission.time_ms,
        memory_kb=submission.memory_kb,
        message=submission.message,
    )


@app.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
    return StatsOut(
        queued=db.query(Submission).filter(Submission.status == "queued").count(),
        running=db.query(Submission).filter(Submission.status == "running").count(),
        finished_last_minute=db.query(Submission)
        .filter(Submission.status == "done", Submission.finished_at >= one_minute_ago)
        .count(),
        workers=WORKERS,
    )
