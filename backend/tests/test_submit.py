import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError

from app.models import Base, Problem, Submission, Test
from app.schemas import SubmissionIn


class SubmitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        path = Path(self.tmp.name) / "s.db"
        self.engine = create_engine("sqlite:///" + path.resolve().as_posix())
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.session = SessionLocal()
        problem = Problem(
            external_id="s1",
            title="t",
            statement="s",
            source="test",
            time_limit_ms=1000,
            memory_limit_mb=64,
            checker="exact",
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
        self.session.commit()
        self.problem_id = problem.id

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()
        self.tmp.cleanup()

    def test_unreachable_sprawdzarka_marks_failed(self) -> None:
        from app.main import create_submission

        with patch("app.main.post_job", return_value=None):
            out = create_submission(
                SubmissionIn(problem_id=self.problem_id, language="cpp", code="int main(){}"),
                db=self.session,
            )
        self.assertEqual(out.status, "failed")
        sub = self.session.get(Submission, out.id)
        self.assertEqual(sub.status, "failed")
        self.assertEqual(sub.message, "sprawdzarka nieosiągalna")

    def test_successful_post_stays_queued(self) -> None:
        from app.main import create_submission

        with patch("app.main.post_job", return_value={"id": 7, "submission_id": 1, "status": "queued"}):
            out = create_submission(
                SubmissionIn(problem_id=self.problem_id, language="cpp", code="int main(){}"),
                db=self.session,
            )
        self.assertEqual(out.status, "queued")

    def test_rejects_non_cpp_language(self) -> None:
        with self.assertRaises(ValidationError):
            SubmissionIn(problem_id=self.problem_id, language="python", code="print(1)")


if __name__ == "__main__":
    unittest.main()
