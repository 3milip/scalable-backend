from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    status: str


class ProblemOut(BaseModel):
    id: int
    title: str
    difficulty: int | None = None
    tags: list[str] = []
    source: str


class ProblemDetailOut(ProblemOut):
    statement: str
    time_limit_ms: int
    memory_limit_mb: int
    solution: str


class ProblemListOut(BaseModel):
    total: int
    items: list[ProblemOut]


class SubmissionIn(BaseModel):
    problem_id: int
    language: str
    code: str = Field(min_length=1)


class SubmissionCreatedOut(BaseModel):
    id: int
    status: str


class SubmissionOut(BaseModel):
    id: int
    problem_id: int
    language: str
    status: str
    verdict: str | None = None
    time_ms: int | None = None
    memory_kb: int | None = None
    message: str | None = None
    code: str


class SubmissionListItemOut(SubmissionOut):
    problem_title: str


class SubmissionListOut(BaseModel):
    total: int
    items: list[SubmissionListItemOut]


class StatsOut(BaseModel):
    queued: int
    running: int
    finished_last_minute: int
    workers: int
