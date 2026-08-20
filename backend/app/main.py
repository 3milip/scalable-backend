import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import (
    get_current_user,
    hash_password,
    new_session_token,
    validate_password,
    validate_username,
    verify_password,
)
from app.db import get_db, init_db
from app.judge_client import SERVICE_KEY, enqueue_job
from app.models import Problem, Submission, SubmissionResult, Test, User
from app.results import problem_max_score, results_for_api, test_points
from app.schemas import (
    AuthIn,
    AuthOut,
    CallbackIn,
    HealthOut,
    MeOut,
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
from app.sinolpack import short_name_for


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_service_key(x_service_key: str | None = Header(default=None, alias="X-Service-Key")) -> None:
    if not x_service_key or x_service_key != SERVICE_KEY:
        raise HTTPException(status_code=401, detail="Zły X-Service-Key")


def _issue_session(db: Session, user: User) -> str:
    token = new_session_token()
    user.session_token = token
    db.commit()
    return token


FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:3000").rstrip("/")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(FRONTEND_URL + "/", status_code=307)


@app.get("/health", response_model=HealthOut)
def health():
    return {"status": "ok"}


@app.post("/auth/register", response_model=AuthOut)
def register(payload: AuthIn, db: Session = Depends(get_db)):
    username = validate_username(payload.username)
    password = validate_password(payload.password)
    if db.query(User).filter(User.username == username).first() is not None:
        raise HTTPException(status_code=409, detail="Taki login już jest")
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthOut(token=_issue_session(db, user), username=user.username)


@app.post("/auth/login", response_model=AuthOut)
def login(payload: AuthIn, db: Session = Depends(get_db)):
    username = validate_username(payload.username)
    user = db.query(User).filter(User.username == username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Zły login lub hasło")
    return AuthOut(token=_issue_session(db, user), username=user.username)


@app.get("/auth/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return MeOut(username=user.username)


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
def create_submission(
    payload: SubmissionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.language.lower() not in {"cpp", "c++"}:
        raise HTTPException(status_code=400, detail="Na razie tylko cpp")
    problem = db.query(Problem).filter(Problem.id == payload.problem_id).first()
    if problem is None:
        raise HTTPException(status_code=404, detail="Nie ma takiego zadania")
    tests = db.query(Test).filter(Test.problem_id == problem.id).all()
    submission = Submission(
        user_id=user.id,
        problem_id=payload.problem_id,
        language="cpp",
        code=payload.code,
        status="queued",
        max_score=problem_max_score(tests),
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    try:
        job_id = enqueue_job(
            backend_submission_id=submission.id,
            problem_short_name=short_name_for(problem.external_id),
            language="cpp",
            code=payload.code,
        )
    except RuntimeError as error:
        submission.status = "failed"
        submission.message = str(error)
        submission.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=502, detail=str(error)) from error
    submission.judge_job_id = job_id
    db.commit()
    return SubmissionCreatedOut(id=submission.id, status=submission.status)


@app.get("/submissions", response_model=SubmissionListOut)
def list_submissions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Submission, Problem).join(
        Problem, Problem.id == Submission.problem_id
    ).filter(Submission.user_id == user.id)
    total = query.count()
    rows = query.order_by(Submission.id.desc()).offset(offset).limit(limit).all()
    return SubmissionListOut(
        total=total,
        items=[
            SubmissionListItemOut(
                id=sub.id,
                problem_id=sub.problem_id,
                problem_title=problem.title,
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
            for sub, problem in rows
        ],
    )


@app.get("/submissions/{submission_id}", response_model=SubmissionDetailOut)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    submission = (
        db.query(Submission)
        .filter(Submission.id == submission_id, Submission.user_id == user.id)
        .first()
    )
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


@app.post("/internal/submissions/{submission_id}/result")
def internal_result(
    submission_id: int,
    payload: CallbackIn,
    db: Session = Depends(get_db),
    _: None = Depends(require_service_key),
):
    if payload.status not in {"done", "failed"}:
        raise HTTPException(status_code=400, detail="status: done albo failed")
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if submission is None:
        raise HTTPException(status_code=404, detail="Nie ma takiego zgłoszenia")
    if submission.status in {"done", "failed"} and submission.judge_job_id == payload.job_id:
        return {"ok": True}
    submission.status = payload.status
    submission.verdict = payload.verdict
    submission.score = payload.score
    if payload.max_score is not None:
        submission.max_score = payload.max_score
    submission.time_ms = payload.time_ms
    submission.memory_kb = payload.memory_kb
    submission.message = payload.message
    submission.judge_job_id = payload.job_id
    if submission.finished_at is None:
        submission.finished_at = datetime.now(timezone.utc)
    if payload.tests:
        tests = db.query(Test).filter(Test.problem_id == submission.problem_id).all()
        by_pos = {t.position: t for t in tests}
        db.query(SubmissionResult).filter(SubmissionResult.submission_id == submission.id).delete()
        for item in payload.tests:
            test = by_pos.get(item.position)
            if test is None:
                continue
            db.add(
                SubmissionResult(
                    submission_id=submission.id,
                    test_id=test.id,
                    verdict=item.verdict,
                    time_ms=item.time_ms,
                    memory_kb=item.memory_kb,
                    score=test_points(item.verdict, test.max_score),
                    message=item.message,
                )
            )
    db.commit()
    return {"ok": True}


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
        workers=0,
    )
