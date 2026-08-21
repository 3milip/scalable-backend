from typing import Literal

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
    language: Literal["cpp"]
    code: str = Field(min_length=1)


class SubmissionCreatedOut(BaseModel):
    id: int
    status: str


class TestResultOut(BaseModel):
    test_id: int
    position: int
    group: str
    hidden: bool
    verdict: str
    time_ms: int | None = None
    memory_kb: int | None = None
    score: int = 0
    max_score: int = 0
    message: str | None = None
    input: str | None = None
    output: str | None = None


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
    score: int | None = None
    max_score: int = 0


class SubmissionDetailOut(SubmissionOut):
    tests: list[TestResultOut] = []


class SubmissionListItemOut(SubmissionOut):
    problem_title: str


class SubmissionListOut(BaseModel):
    total: int
    items: list[SubmissionListItemOut]


class StatsOut(BaseModel):
    queued: int
    running: int
    failed: int = 0
    finished_last_minute: int
    workers: int


class CallbackTestIn(BaseModel):
    test_id: int
    verdict: str
    time_ms: int | None = None
    memory_kb: int | None = None
    score: int = 0
    max_score: int = 0
    message: str | None = None


class CallbackIn(BaseModel):
    submission_id: int
    status: str
    verdict: str | None = None
    time_ms: int | None = None
    memory_kb: int | None = None
    message: str | None = None
    score: int | None = None
    max_score: int | None = None
    tests: list[CallbackTestIn] = []
