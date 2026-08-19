from sqlalchemy.orm import Session

from app.models import Submission, SubmissionResult, Test


def meta_from_sample(
    hidden: bool,
    group: str | None = None,
    max_score: int | None = None,
    position: int = 0,
) -> tuple[str, int]:
    """Przykłady: grupa 0 / 0 pkt. Ukryty bez group w JSON: własna grupa (pozycja), 1 pkt."""
    if hidden:
        default_group = str(position) if position > 0 else "1"
        return (
            group if group is not None else default_group,
            1 if max_score is None else max_score,
        )
    return group if group is not None else "0", 0 if max_score is None else max_score


def _sum_groups(points_by_group: list[tuple[str, int]]) -> int:
    """Grupa = min (OI), zadanie = suma grup. Pusta grupa = 0."""
    by_group: dict[str, list[int]] = {}
    for group, points in points_by_group:
        by_group.setdefault(group, []).append(points)
    return sum(min(pts) for pts in by_group.values())


def problem_max_score(tests: list[Test]) -> int:
    return _sum_groups(
        [(test.group, test.max_score) for test in tests if test.max_score > 0]
    )


def public_result_payload(result: SubmissionResult, test: Test) -> dict:
    payload = {
        "test_id": test.id,
        "position": test.position,
        "group": test.group,
        "hidden": test.hidden,
        "verdict": result.verdict,
        "time_ms": result.time_ms,
        "memory_kb": result.memory_kb,
        "score": result.score,
        "max_score": test.max_score,
        "message": result.message,
        "input": None,
        "output": None,
    }
    if not test.hidden:
        payload["input"] = test.input_text
        payload["output"] = test.output_text
    return payload


from isolation.checker import exact as checker_exact

VERDICT_RANK = {"OK": 0, "WA": 1, "MLE": 2, "TLE": 3, "RE": 4, "CE": 5, "SI": 6}


def exact_match(got: str, expected: str) -> bool:
    return checker_exact(got, expected).verdict == "OK"


def test_points(verdict: str, max_score: int) -> int:
    if verdict == "OK" and max_score > 0:
        return max_score
    return 0


def score_groups(rows: list[tuple[str, str, int]]) -> int:
    """rows: (group, verdict, max_score). Przykłady (max 0) skip. WA w grupie = min 0."""
    return _sum_groups(
        [
            (group, test_points(verdict, max_score))
            for group, verdict, max_score in rows
            if max_score > 0
        ]
    )


def worst_verdict(verdicts: list[str]) -> str:
    if not verdicts:
        return "OK"
    return max(verdicts, key=lambda item: VERDICT_RANK.get(item, 0))


def save_result(
    db: Session,
    submission: Submission,
    test: Test,
    verdict: str,
    message: str | None,
    time_ms: int | None,
    memory_kb: int | None,
) -> SubmissionResult:
    row = SubmissionResult(
        submission_id=submission.id,
        test_id=test.id,
        verdict=verdict,
        time_ms=time_ms,
        memory_kb=memory_kb,
        score=test_points(verdict, test.max_score),
        message=message,
    )
    db.add(row)
    db.commit()
    return row


def results_for_api(db: Session, submission: Submission) -> list[dict]:
    rows = (
        db.query(SubmissionResult, Test)
        .join(Test, Test.id == SubmissionResult.test_id)
        .filter(SubmissionResult.submission_id == submission.id)
        .order_by(Test.position, Test.id)
        .all()
    )
    return [public_result_payload(result, test) for result, test in rows]
