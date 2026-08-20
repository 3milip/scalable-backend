VERDICT_RANK = {"OK": 0, "WA": 1, "MLE": 2, "TLE": 3, "RE": 4, "CE": 5, "SI": 6}


def _sum_groups(points_by_group: list[tuple[str, int]]) -> int:
    """Grupa = min (OI), zadanie = suma grup. Pusta grupa = 0."""
    by_group: dict[str, list[int]] = {}
    for group, points in points_by_group:
        by_group.setdefault(group, []).append(points)
    return sum(min(pts) for pts in by_group.values())


def problem_max_score(tests: list) -> int:
    return _sum_groups(
        [(test.group, test.max_score) for test in tests if test.max_score > 0]
    )


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
