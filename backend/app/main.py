from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import require_service_key
from app.callback import apply_callback
from app.db import get_db, init_db
from app.models import Problem, Submission, Test
from app.results import problem_max_score, results_for_api
from app.schemas import (
    CallbackIn,
    HealthOut,
    ProblemDetailOut,
    ProblemListOut,
    ProblemOut,
    StatsOut,
    SubmissionCreatedOut,
    SubmissionDetailOut,
    SubmissionIn,
    SubmissionListItemOut,
    SubmissionListOut,
    TestResultOut,
)
from app.sprawdzarka_client import fetch_workers, post_job


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root():
    return HTMLResponse(
        """<!DOCTYPE html>
<html lang="pl"><head><meta charset="utf-8"><title>Backend</title></head>
<body>
<p>To jest API (port 8000), nie strona.</p>
<p>Frontend: <a href="http://127.0.0.1:3000/">http://127.0.0.1:3000/</a></p>
<p>Odpal w katalogu <code>frontend/</code>:</p>
<pre>python -m http.server 3000 --bind 127.0.0.1</pre>
<p>Docs: <a href="/docs">/docs</a></p>
</body></html>"""
    )


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
        solution=problem.solution or "",
    )


@app.post("/submissions", response_model=SubmissionCreatedOut)
def create_submission(payload: SubmissionIn, db: Session = Depends(get_db)):
    problem = db.query(Problem).filter(Problem.id == payload.problem_id).first()
    if problem is None:
        raise HTTPException(status_code=404, detail="Nie ma takiego zadania")

    tests = (
        db.query(Test)
        .filter(Test.problem_id == problem.id)
        .order_by(Test.position, Test.id)
        .all()
    )
    submission = Submission(
        problem_id=payload.problem_id,
        language=payload.language,
        code=payload.code,
        status="queued",
        max_score=problem_max_score(tests),
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    job = post_job(
        {
            "submission_id": submission.id,
            "language": submission.language,
            "code": submission.code,
            "time_limit_ms": problem.time_limit_ms,
            "memory_limit_mb": problem.memory_limit_mb,
            "checker": problem.checker or "exact",
            "checker_code": problem.checker_code or "",
            "tests": [
                {
                    "id": test.id,
                    "input": test.input_text,
                    "output": test.output_text,
                    "position": test.position,
                    "group": test.group,
                    "max_score": test.max_score,
                }
                for test in tests
            ],
        }
    )
    if job is None:
        submission.status = "failed"
        submission.message = "sprawdzarka nieosiągalna"
        db.commit()
    return SubmissionCreatedOut(id=submission.id, status=submission.status)


@app.get("/submissions", response_model=SubmissionListOut)
def list_submissions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Submission, Problem.title).join(
        Problem, Problem.id == Submission.problem_id
    )
    total = query.count()
    rows = (
        query.order_by(Submission.id.desc()).offset(offset).limit(limit).all()
    )
    return SubmissionListOut(
        total=total,
        items=[
            SubmissionListItemOut(
                id=sub.id,
                problem_id=sub.problem_id,
                problem_title=title,
                language=sub.language,
                status=sub.status,
                verdict=sub.verdict,
                time_ms=sub.time_ms,
                memory_kb=sub.memory_kb,
                message=sub.message,
                code=sub.code,
                score=sub.score,
                max_score=sub.max_score,
            )
            for sub, title in rows
        ],
    )


@app.get("/submissions/{submission_id}", response_model=SubmissionDetailOut)
def get_submission(submission_id: int, db: Session = Depends(get_db)):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if submission is None:
        raise HTTPException(status_code=404, detail="Nie ma takiego zgłoszenia")
    return SubmissionDetailOut(
        id=submission.id,
        problem_id=submission.problem_id,
        language=submission.language,
        status=submission.status,
        verdict=submission.verdict,
        time_ms=submission.time_ms,
        memory_kb=submission.memory_kb,
        message=submission.message,
        code=submission.code,
        score=submission.score,
        max_score=submission.max_score,
        tests=[TestResultOut(**item) for item in results_for_api(db, submission)],
    )


@app.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
    return StatsOut(
        queued=db.query(Submission).filter(Submission.status == "queued").count(),
        running=db.query(Submission).filter(Submission.status == "running").count(),
        failed=db.query(Submission).filter(Submission.status == "failed").count(),
        finished_last_minute=db.query(Submission)
        .filter(Submission.status == "done", Submission.finished_at >= one_minute_ago)
        .count(),
        workers=fetch_workers(),
    )


@app.post("/internal/results", dependencies=[Depends(require_service_key)])
def internal_results(payload: CallbackIn, db: Session = Depends(get_db)):
    apply_callback(db, payload)
    return {"ok": True}
