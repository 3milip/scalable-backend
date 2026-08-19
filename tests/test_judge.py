import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from isolation.isolate import RunResult
from isolation.judge import judge
from app.models import Base, Problem, Submission, SubmissionResult, Test


def _ok() -> RunResult:
    return RunResult("OK", "3\n", "", 10, 1000)


def _ce() -> RunResult:
    return RunResult("CE", "", "SyntaxError: bad", 5, 800)


class JudgeRecipeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        path = Path(self.tmp.name) / "j.db"
        self.engine = create_engine("sqlite:///" + path.resolve().as_posix())
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        problem = Problem(
            external_id="j1",
            title="t",
            statement="s",
            source="test",
            time_limit_ms=1000,
            memory_limit_mb=64,
        )
        self.session.add(problem)
        self.session.flush()
        self.session.add(
            Test(
                problem_id=problem.id,
                input_text="1 2\n",
                output_text="3\n",
                hidden=False,
                position=0,
                group="0",
                max_score=0,
            )
        )
        self.session.add(
            Test(
                problem_id=problem.id,
                input_text="0 0\n",
                output_text="0\n",
                hidden=True,
                position=1,
                group="1",
                max_score=1,
            )
        )
        self.session.add(
            Test(
                problem_id=problem.id,
                input_text="2 2\n",
                output_text="4\n",
                hidden=True,
                position=2,
                group="1",
                max_score=1,
            )
        )
        sub = Submission(
            problem_id=problem.id,
            language="python",
            code="print(1)",
            status="running",
            max_score=2,
        )
        self.session.add(sub)
        self.session.commit()
        self.sub_id = sub.id

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()
        self.tmp.cleanup()

    def test_compile_failure_skips_tests(self) -> None:
        with patch("isolation.judge.run_in", return_value=_ce()) as mocked:
            with patch("isolation.judge.heartbeat"):
                judge(self.session, self.session.get(Submission, self.sub_id), job_id=1)
        sub = self.session.get(Submission, self.sub_id)
        self.assertEqual(sub.verdict, "CE")
        self.assertEqual(sub.score, 0)
        self.assertEqual(mocked.call_count, 1)
        count = self.session.query(SubmissionResult).count()
        self.assertEqual(count, 0)

    def test_runs_all_tests_after_wa(self) -> None:
        calls = {"n": 0}

        def fake_run(_folder, stdin, *_args, **_kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return _ok()
            if stdin == "0 0\n":
                return RunResult("OK", "9\n", "", 10, 1000)
            return _ok()

        with patch("isolation.judge.run_in", side_effect=fake_run):
            with patch("isolation.judge.heartbeat"):
                judge(self.session, self.session.get(Submission, self.sub_id), job_id=1)

        sub = self.session.get(Submission, self.sub_id)
        results = self.session.query(SubmissionResult).all()
        self.assertEqual(len(results), 3)
        self.assertEqual(sub.verdict, "WA")
        self.assertEqual(sub.score, 0)
        self.assertEqual(calls["n"], 4)


if __name__ == "__main__":
    unittest.main()
