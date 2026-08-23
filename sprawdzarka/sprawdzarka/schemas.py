from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    status: str


class StatsOut(BaseModel):
    workers: int


class JobTestIn(BaseModel):
    id: int
    input: str
    output: str
    position: int = 0
    group: str = "0"
    max_score: int = 0


class JobIn(BaseModel):
    submission_id: int
    language: str
    code: str = Field(min_length=1)
    short_name: str = ""
    # Zostają pod isolate w testach; live (OIOIOI) ich nie wysyła i nie czyta.
    time_limit_ms: int = 0
    memory_limit_mb: int = 0
    checker: str = "exact"
    checker_code: str = ""
    tests: list[JobTestIn] = []


class JobCreatedOut(BaseModel):
    id: int
    submission_id: int
    status: str
