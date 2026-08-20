from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sprawdzarka.checker import check
from sprawdzarka.isolate import COMPILE_PROGRAM, RUN_PROGRAM, RunResult, prepare_work, run_in
from sprawdzarka.queue import heartbeat
from sprawdzarka.scoring import problem_max_score, score_groups, test_points, worst_verdict


@dataclass
class JobTest:
    id: int
    input: str
    output: str
    position: int = 0
    group: str = "0"
    max_score: int = 0


@dataclass
class JobPayload:
    submission_id: int
    language: str
    code: str
    time_limit_ms: int
    memory_limit_mb: int
    checker: str = "exact"
    checker_code: str = ""
    tests: list[JobTest] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> JobPayload:
        tests = [
            JobTest(
                id=int(item["id"]),
                input=item.get("input") or "",
                output=item.get("output") or "",
                position=int(item.get("position") or 0),
                group=str(item.get("group") or "0"),
                max_score=int(item.get("max_score") or 0),
            )
            for item in data.get("tests") or []
        ]
        tests.sort(key=lambda item: (item.position, item.id))
        return cls(
            submission_id=int(data["submission_id"]),
            language=str(data.get("language") or ""),
            code=str(data.get("code") or ""),
            time_limit_ms=int(data.get("time_limit_ms") or 1000),
            memory_limit_mb=int(data.get("memory_limit_mb") or 256),
            checker=str(data.get("checker") or "exact"),
            checker_code=str(data.get("checker_code") or ""),
            tests=tests,
        )


@dataclass
class TestOutcome:
    test_id: int
    verdict: str
    time_ms: int | None
    memory_kb: int | None
    score: int
    max_score: int
    message: str | None


@dataclass
class JudgeOutcome:
    submission_id: int
    status: str
    verdict: str
    time_ms: int | None
    memory_kb: int | None
    message: str | None
    score: int
    max_score: int
    tests: list[TestOutcome] = field(default_factory=list)

    def to_callback(self) -> dict:
        body: dict = {
            "submission_id": self.submission_id,
            "status": self.status,
            "verdict": self.verdict,
            "time_ms": self.time_ms,
            "memory_kb": self.memory_kb,
            "message": self.message,
            "score": self.score,
            "max_score": self.max_score,
            "tests": [
                {
                    "test_id": item.test_id,
                    "verdict": item.verdict,
                    "time_ms": item.time_ms,
                    "memory_kb": item.memory_kb,
                    "score": item.score,
                    "max_score": item.max_score,
                    "message": item.message,
                }
                for item in self.tests
            ],
        }
        return body


def _done(
    payload: JobPayload,
    *,
    verdict: str,
    message: str | None,
    time_ms: int | None = None,
    memory_kb: int | None = None,
    score: int = 0,
    tests: list[TestOutcome] | None = None,
) -> JudgeOutcome:
    return JudgeOutcome(
        submission_id=payload.submission_id,
        status="done",
        verdict=verdict,
        time_ms=time_ms,
        memory_kb=memory_kb,
        message=message,
        score=score,
        max_score=problem_max_score(payload.tests),
        tests=tests or [],
    )


def _apply_output(payload: JobPayload, test: JobTest, result: RunResult) -> tuple[str, str | None]:
    if result.verdict != "OK":
        return result.verdict, result.message or None
    checked = check(
        payload.checker,
        payload.checker_code,
        test.input,
        test.output,
        result.verdict,
        result.stdout,
    )
    return checked.verdict, checked.message or result.message or None


def judge(payload: JobPayload, job_id: int) -> JudgeOutcome:
    max_score = problem_max_score(payload.tests)

    if payload.language != "python":
        return _done(payload, verdict="CE", message="Na razie tylko python", score=0)

    if not payload.tests:
        return _done(payload, verdict="RE", message="Brak testów do tego zadania", score=0)

    work = prepare_work(payload.code)
    folder = Path(work.name)
    try:
        heartbeat(job_id)
        compiled = run_in(
            folder,
            "",
            payload.time_limit_ms,
            payload.memory_limit_mb,
            COMPILE_PROGRAM,
        )
        if compiled.verdict != "OK":
            if compiled.verdict == "RE" and (
                compiled.message.startswith("brak izolacji")
                or "izolacja nie odpowiedziała" in compiled.message
            ):
                return _done(
                    payload,
                    verdict="RE",
                    message=compiled.message,
                    time_ms=compiled.time_ms,
                    memory_kb=compiled.memory_kb,
                )
            return _done(
                payload,
                verdict="CE",
                message=compiled.message or "błąd kompilacji",
                time_ms=compiled.time_ms,
                memory_kb=compiled.memory_kb,
            )

        scored_rows: list[tuple[str, str, int]] = []
        verdicts: list[str] = []
        outcomes: list[TestOutcome] = []
        total_ms = compiled.time_ms or 0
        peak_kb = compiled.memory_kb
        overall_message: str | None = None

        for test in payload.tests:
            heartbeat(job_id)
            ran = run_in(
                folder,
                test.input,
                payload.time_limit_ms,
                payload.memory_limit_mb,
                RUN_PROGRAM,
            )
            verdict, message = _apply_output(payload, test, ran)
            if ran.time_ms is not None:
                total_ms += ran.time_ms
            if ran.memory_kb is not None:
                peak_kb = ran.memory_kb if peak_kb is None else max(peak_kb, ran.memory_kb)
            points = test_points(verdict, test.max_score)
            outcomes.append(
                TestOutcome(
                    test_id=test.id,
                    verdict=verdict,
                    time_ms=ran.time_ms,
                    memory_kb=ran.memory_kb,
                    score=points,
                    max_score=test.max_score,
                    message=message,
                )
            )
            scored_rows.append((test.group, verdict, test.max_score))
            verdicts.append(verdict)
            if verdict != "OK" and overall_message is None:
                overall_message = message or verdict

        return JudgeOutcome(
            submission_id=payload.submission_id,
            status="done",
            verdict=worst_verdict(verdicts),
            time_ms=total_ms,
            memory_kb=peak_kb,
            message=overall_message,
            score=score_groups(scored_rows),
            max_score=max_score,
            tests=outcomes,
        )
    finally:
        work.cleanup()
