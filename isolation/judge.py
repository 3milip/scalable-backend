from pathlib import Path

from sqlalchemy.orm import Session

from isolation.checker import check
from isolation.isolate import COMPILE_PROGRAM, RUN_PROGRAM, RunResult, prepare_work, run_in
from app.models import Problem, Submission, Test, _now
from isolation.queue import heartbeat
from app.results import (
    problem_max_score,
    save_result,
    score_groups,
    worst_verdict,
)


def _finish(
    db: Session,
    submission: Submission,
    *,
    verdict: str,
    message: str | None,
    time_ms: int | None = None,
    memory_kb: int | None = None,
    score: int = 0,
    max_score: int = 0,
) -> None:
    submission.status = "done"
    submission.verdict = verdict
    submission.message = message
    submission.time_ms = time_ms
    submission.memory_kb = memory_kb
    submission.score = score
    submission.max_score = max_score
    submission.finished_at = _now()
    db.commit()


def _apply_output(problem: Problem, test: Test, result: RunResult) -> tuple[str, str | None]:
    if result.verdict != "OK":
        return result.verdict, result.message or None
    checked = check(problem, test, result.verdict, result.stdout)
    return checked.verdict, checked.message or result.message or None


def judge(db: Session, submission: Submission, job_id: int) -> None:
    problem = db.query(Problem).filter(Problem.id == submission.problem_id).first()
    if problem is None:
        _finish(db, submission, verdict="RE", message="Nie ma takiego zadania")
        return

    tests = (
        db.query(Test)
        .filter(Test.problem_id == submission.problem_id)
        .order_by(Test.position, Test.id)
        .all()
    )
    max_score = problem_max_score(tests)

    if submission.language != "python":
        _finish(db, submission, verdict="CE", message="Na razie tylko python", max_score=max_score)
        return

    if not tests:
        _finish(db, submission, verdict="RE", message="Brak testów do tego zadania", max_score=max_score)
        return

    work = prepare_work(submission.code)
    folder = Path(work.name)
    try:
        heartbeat(job_id)
        compiled = run_in(
            folder,
            "",
            problem.time_limit_ms,
            problem.memory_limit_mb,
            COMPILE_PROGRAM,
        )
        if compiled.verdict != "OK":
            if compiled.verdict == "RE" and (
                compiled.message.startswith("brak izolacji")
                or "izolacja nie odpowiedziała" in compiled.message
            ):
                _finish(
                    db,
                    submission,
                    verdict="RE",
                    message=compiled.message,
                    time_ms=compiled.time_ms,
                    memory_kb=compiled.memory_kb,
                    max_score=max_score,
                )
                return
            _finish(
                db,
                submission,
                verdict="CE",
                message=compiled.message or "błąd kompilacji",
                time_ms=compiled.time_ms,
                memory_kb=compiled.memory_kb,
                max_score=max_score,
            )
            return

        examples = [test for test in tests if not test.hidden]
        hidden = [test for test in tests if test.hidden]
        scored_rows: list[tuple[str, str, int]] = []
        verdicts: list[str] = []
        total_ms = compiled.time_ms or 0
        peak_kb = compiled.memory_kb
        overall_message: str | None = None

        for batch in (examples, hidden):
            for test in batch:
                heartbeat(job_id)
                ran = run_in(
                    folder,
                    test.input_text,
                    problem.time_limit_ms,
                    problem.memory_limit_mb,
                    RUN_PROGRAM,
                )
                verdict, message = _apply_output(problem, test, ran)
                if ran.time_ms is not None:
                    total_ms += ran.time_ms
                if ran.memory_kb is not None:
                    peak_kb = ran.memory_kb if peak_kb is None else max(peak_kb, ran.memory_kb)
                save_result(db, submission, test, verdict, message, ran.time_ms, ran.memory_kb)
                scored_rows.append((test.group, verdict, test.max_score))
                verdicts.append(verdict)
                if verdict != "OK" and overall_message is None:
                    overall_message = message or verdict

        _finish(
            db,
            submission,
            verdict=worst_verdict(verdicts),
            message=overall_message,
            time_ms=total_ms,
            memory_kb=peak_kb,
            score=score_groups(scored_rows),
            max_score=max_score,
        )
    finally:
        work.cleanup()
