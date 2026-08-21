import sys
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.callback import apply_callback
from app.models import Base, Problem, Submission, SubmissionResult, Test
from app.schemas import CallbackIn, CallbackTestIn


class CallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        path = Path(self.tmp.name) / "cb.db"
        self.engine = create_engine("sqlite:///" + path.resolve().as_posix())
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        problem = Problem(
            external_id="c1",
            title="t",
            statement="s",
            source="test",
            time_limit_ms=1000,
            memory_limit_mb=64,
        )
        self.session.add(problem)
        self.session.flush()
        test = Test(
            problem_id=problem.id,
            input_text="1 2\n",
            output_text="3\n",
            hidden=False,
            position=0,
            group="0",
            max_score=0,
        )
        self.session.add(test)
        sub = Submission(
            problem_id=problem.id,
            language="cpp",
            code="int main(){}",
            status="queued",
            max_score=0,
        )
        self.session.add(sub)
        self.session.commit()
        self.sub_id = sub.id
        self.test_id = test.id

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()
        self.tmp.cleanup()

    def test_unknown_submission_is_404(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            apply_callback(
                self.session,
                CallbackIn(submission_id=999, status="running"),
            )
        self.assertEqual(caught.exception.status_code, 404)

    def test_running_then_done(self) -> None:
        apply_callback(self.session, CallbackIn(submission_id=self.sub_id, status="running"))
        sub = self.session.get(Submission, self.sub_id)
        self.assertEqual(sub.status, "running")

        apply_callback(
            self.session,
            CallbackIn(
                submission_id=self.sub_id,
                status="done",
                verdict="OK",
                score=0,
                max_score=0,
                tests=[
                    CallbackTestIn(
                        test_id=self.test_id,
                        verdict="OK",
                        score=0,
                        max_score=0,
                    )
                ],
            ),
        )
        sub = self.session.get(Submission, self.sub_id)
        self.assertEqual(sub.status, "done")
        self.assertEqual(sub.verdict, "OK")
        count = self.session.query(SubmissionResult).count()
        self.assertEqual(count, 1)

    def test_terminal_ignores_running_and_second_done(self) -> None:
        apply_callback(
            self.session,
            CallbackIn(
                submission_id=self.sub_id,
                status="done",
                verdict="WA",
                score=0,
            ),
        )
        apply_callback(self.session, CallbackIn(submission_id=self.sub_id, status="running"))
        apply_callback(
            self.session,
            CallbackIn(
                submission_id=self.sub_id,
                status="done",
                verdict="OK",
                score=99,
            ),
        )
        sub = self.session.get(Submission, self.sub_id)
        self.assertEqual(sub.status, "done")
        self.assertEqual(sub.verdict, "WA")
        self.assertEqual(sub.score, 0)

    def test_failed(self) -> None:
        apply_callback(
            self.session,
            CallbackIn(submission_id=self.sub_id, status="failed", message="worker zmarl"),
        )
        sub = self.session.get(Submission, self.sub_id)
        self.assertEqual(sub.status, "failed")
        self.assertEqual(sub.message, "worker zmarl")
        self.assertIsNotNone(sub.finished_at)

    def test_unknown_test_id_is_422(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            apply_callback(
                self.session,
                CallbackIn(
                    submission_id=self.sub_id,
                    status="done",
                    verdict="OK",
                    tests=[CallbackTestIn(test_id=999, verdict="OK")],
                ),
            )
        self.assertEqual(caught.exception.status_code, 422)
        sub = self.session.get(Submission, self.sub_id)
        self.assertEqual(sub.status, "queued")


if __name__ == "__main__":
    unittest.main()
