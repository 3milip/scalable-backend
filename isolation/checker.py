from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from isolation.isolate import RawRun, program_stderr, run_raw
from app.models import Problem, Test

FLOAT_EPS = 1e-6
CHECKER_TIMEOUT_MS = 5000
CHECKER_MEMORY_MB = 128


@dataclass
class CheckResult:
    verdict: str
    message: str | None


def normalize(text: str) -> str:
    lines = text.replace("\r\n", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip()


def exact(got: str, expected: str) -> CheckResult:
    if normalize(got) == normalize(expected):
        return CheckResult("OK", None)
    return CheckResult("WA", "zły wynik")


def tokens(got: str, expected: str) -> CheckResult:
    if got.split() == expected.split():
        return CheckResult("OK", None)
    return CheckResult("WA", "zła sekwencja tokenów")


def _same_token(left: str, right: str) -> bool:
    try:
        return abs(float(left) - float(right)) <= FLOAT_EPS
    except ValueError:
        return left == right


def floats(got: str, expected: str) -> CheckResult:
    left = got.split()
    right = expected.split()
    if len(left) != len(right):
        return CheckResult("WA", "zła liczba tokenów")
    if all(_same_token(a, b) for a, b in zip(left, right)):
        return CheckResult("OK", None)
    return CheckResult("WA", "wartość poza eps")


def _map_custom(raw: RawRun) -> CheckResult:
    if raw.isolate_error and raw.returncode < 0:
        return CheckResult("SI", raw.isolate_error)
    if raw.returncode == 75:
        return CheckResult("SI", raw.isolate_error or "brak wolnego slotu (checker)")
    if raw.returncode == 124 or raw.oom:
        return CheckResult("SI", "checker przekroczył limit")
    if raw.returncode == 0:
        return CheckResult("OK", program_stderr(raw.stderr) or None)
    if raw.returncode in (1, 2):
        return CheckResult("WA", raw.stderr or "checker: WA")
    return CheckResult("SI", raw.stderr or f"checker exit {raw.returncode}")


def custom(problem: Problem, inp: str, got: str, expected: str) -> CheckResult:
    if not (problem.checker_code or "").strip():
        return CheckResult("SI", "brak checker_code")
    work = tempfile.TemporaryDirectory()
    data = tempfile.TemporaryDirectory()
    try:
        checker = Path(work.name) / "checker.py"
        checker.write_text(problem.checker_code, encoding="utf-8")
        checker.chmod(0o644)
        Path(work.name).chmod(0o755)
        for name, text in (("in", inp), ("out", got), ("ans", expected)):
            file = Path(data.name) / name
            file.write_text(text, encoding="utf-8")
            file.chmod(0o644)
        Path(data.name).chmod(0o755)
        raw = run_raw(
            Path(work.name),
            "",
            CHECKER_TIMEOUT_MS,
            CHECKER_MEMORY_MB,
            ["python3", "/work/checker.py", "/data/in", "/data/out", "/data/ans"],
            extra_mounts=[(Path(data.name), "/data")],
        )
        return _map_custom(raw)
    finally:
        work.cleanup()
        data.cleanup()


def check(problem: Problem, test: Test, program_verdict: str, stdout: str) -> CheckResult:
    """Checker tylko gdy program skończył się exit 0."""
    if program_verdict != "OK":
        return CheckResult(program_verdict, None)
    kind = (problem.checker or "exact").lower()
    if kind == "tokens":
        return tokens(stdout, test.output_text)
    if kind in ("float", "floats"):
        return floats(stdout, test.output_text)
    if kind == "custom":
        return custom(problem, test.input_text, stdout, test.output_text)
    return exact(stdout, test.output_text)
