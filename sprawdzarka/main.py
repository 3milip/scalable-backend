from __future__ import annotations

import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# `uvicorn main:app` z folderu sprawdzarka/ — korzeń repo musi być na path,
# zanim cokolwiek robi `from sprawdzarka...`.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from sprawdzarka.jobs import create_job, get_job, init as init_jobs, tests_of
from sprawdzarka.oioioi_api import health_oioioi, submit as oioioi_submit, service_token
from sprawdzarka.poller import start as start_poller, stop as stop_poller
from sprawdzarka.security import require_service_key

REPO = Path(__file__).resolve().parents[1]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_jobs()
    start_poller()
    yield
    stop_poller()


app = FastAPI(title="sprawdzarka", lifespan=lifespan)


class JobIn(BaseModel):
    backend_submission_id: int
    callback_url: str
    problem_short_name: str
    language: str
    code: str = Field(min_length=1)


class JobOut(BaseModel):
    job_id: str
    status: str


class SyncOut(BaseModel):
    upserted: list[str]
    errors: list[str]


@app.get("/health")
def health():
    return {"status": "ok", "oioioi": health_oioioi()}


@app.post("/jobs", response_model=JobOut, dependencies=[Depends(require_service_key)])
def create(payload: JobIn):
    if payload.language.lower() not in {"cpp", "c++"}:
        raise HTTPException(status_code=400, detail="Na razie tylko cpp")
    try:
        token = service_token()
        oioioi_id = oioioi_submit(token, payload.problem_short_name, payload.code, "cpp")
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    job_id = create_job(
        backend_submission_id=payload.backend_submission_id,
        callback_url=payload.callback_url,
        problem_short_name=payload.problem_short_name,
        language="cpp",
        code=payload.code,
        oioioi_id=oioioi_id,
        status="queued",
    )
    return JobOut(job_id=f"j-{job_id}", status="queued")


@app.get("/jobs/{job_id}", dependencies=[Depends(require_service_key)])
def read_job(job_id: str):
    raw = job_id.removeprefix("j-")
    try:
        num = int(raw)
    except ValueError as error:
        raise HTTPException(status_code=404, detail="Nie ma takiego joba") from error
    job = get_job(num)
    if job is None:
        raise HTTPException(status_code=404, detail="Nie ma takiego joba")
    return {
        "job_id": f"j-{job['id']}",
        "backend_submission_id": job["backend_submission_id"],
        "status": job["status"],
        "verdict": job["verdict"],
        "score": job["score"],
        "max_score": job["max_score"],
        "time_ms": job["time_ms"],
        "memory_kb": job["memory_kb"],
        "message": job["message"],
        "tests": tests_of(job),
    }


@app.post("/problems/sync", response_model=SyncOut, dependencies=[Depends(require_service_key)])
def sync_problems():
    script = REPO / "scripts" / "push_to_oioioi.py"
    ran = subprocess.run([sys.executable, str(script)], cwd=REPO, capture_output=True, text=True)
    if ran.returncode != 0:
        err = (ran.stderr or ran.stdout or "sync failed")[-400:]
        return SyncOut(upserted=[], errors=[err])
    return SyncOut(upserted=["ok"], errors=[])
