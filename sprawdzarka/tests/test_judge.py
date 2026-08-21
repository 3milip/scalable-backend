import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sprawdzarka.isolate import RunResult
from sprawdzarka.judge import JobPayload, JobTest, judge


def _ok() -> RunResult:
    return RunResult("OK", "3\n", "", 10, 1000)


def _ce() -> RunResult:
    return RunResult("CE", "", "błąd kompilacji", 5, 800)


def _payload(**overrides) -> JobPayload:
    data = dict(
        submission_id=9,
        language="cpp",
        code="int main() { return 0; }",
        time_limit_ms=1000,
        memory_limit_mb=64,
        tests=[
            JobTest(id=1, input="1 2\n", output="3\n", position=0, group="0", max_score=0),
            JobTest(id=2, input="0 0\n", output="0\n", position=1, group="1", max_score=1),
            JobTest(id=3, input="2 2\n", output="4\n", position=2, group="1", max_score=1),
        ],
    )
    data.update(overrides)
    return JobPayload(**data)


class JudgeRecipeTests(unittest.TestCase):
    def test_compile_failure_skips_tests(self) -> None:
        with patch("sprawdzarka.judge.run_in", return_value=_ce()) as mocked:
            with patch("sprawdzarka.judge.heartbeat"):
                outcome = judge(_payload(), job_id=1)
        self.assertEqual(outcome.verdict, "CE")
        self.assertEqual(outcome.score, 0)
        self.assertEqual(outcome.status, "done")
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(outcome.tests, [])

    def test_runs_all_tests_after_wa(self) -> None:
        calls = {"n": 0}

        def fake_run(_folder, stdin, *_args, **_kwargs):
            calls["n"] += 1
            if stdin == "0 0\n":
                return RunResult("OK", "9\n", "", 10, 1000)
            return _ok()

        with patch("sprawdzarka.judge.run_in", side_effect=fake_run):
            with patch("sprawdzarka.judge.heartbeat"):
                outcome = judge(_payload(), job_id=1)

        self.assertEqual(len(outcome.tests), 3)
        self.assertEqual(outcome.verdict, "WA")
        self.assertEqual(outcome.score, 0)
        self.assertEqual(calls["n"], 3)
        self.assertEqual(outcome.tests[1].test_id, 2)
        self.assertEqual(outcome.tests[1].verdict, "WA")

    def test_rejects_python_without_isolate(self) -> None:
        with patch("sprawdzarka.judge.run_in") as mocked:
            with patch("sprawdzarka.judge.heartbeat"):
                outcome = judge(_payload(language="python", code="print(1)"), job_id=1)
        self.assertEqual(outcome.verdict, "CE")
        self.assertIn("C++", outcome.message or "")
        mocked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
