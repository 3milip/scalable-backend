from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from sprawdzarka.auth import require_service_key
from sprawdzarka.db import init_db
from sprawdzarka.queue import enqueue, live_worker_count
from sprawdzarka.schemas import HealthOut, JobCreatedOut, JobIn, StatsOut


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="sprawdzarka", lifespan=lifespan)


@app.get("/health", response_model=HealthOut)
def health():
    return {"status": "ok"}


@app.get("/stats", response_model=StatsOut, dependencies=[Depends(require_service_key)])
def stats():
    return StatsOut(workers=live_worker_count())


@app.post(
    "/jobs",
    response_model=JobCreatedOut,
    status_code=201,
    dependencies=[Depends(require_service_key)],
)
def create_job(payload: JobIn):
    job_id = enqueue(payload.submission_id, payload.model_dump())
    return JobCreatedOut(id=job_id, submission_id=payload.submission_id, status="queued")
