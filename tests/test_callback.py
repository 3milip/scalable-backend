import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import hash_password, new_session_token
from app.db import Base, get_db
from app.judge_client import SERVICE_KEY
from app.main import app
from app.models import Problem, Test, User


class CallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        path = Path(self.tmp.name) / "t.db"
        engine = create_engine("sqlite:///" + path.resolve().as_posix())
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        db = self.Session()
        user = User(
            username="ala",
            password_hash=hash_password("sekret1"),
            session_token=new_session_token(),
        )
        db.add(user)
        problem = Problem(
            external_id="local-01",
            title="Suma",
            statement="s",
            source="local",
            time_limit_ms=1000,
            memory_limit_mb=64,
        )
        db.add(problem)
        db.flush()
        db.add(Test(problem_id=problem.id, input_text="1 2\n", output_text="3\n", hidden=False, position=0, group="0", max_score=0))
        db.add(Test(problem_id=problem.id, input_text="0 0\n", output_text="0\n", hidden=True, position=1, group="1", max_score=1))
        db.commit()
        self.token = user.session_token
        db.close()

        def override():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.tmp.cleanup()

    def test_register_does_not_need_oioioi(self) -> None:
        response = self.client.post("/auth/register", json={"username": "bob", "password": "abcdef"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())

    def test_callback_updates_submission(self) -> None:
        with patch("app.main.enqueue_job", return_value="j-9"):
            created = self.client.post(
                "/submissions",
                json={"problem_id": 1, "language": "cpp", "code": "int main(){}"},
                headers={"Authorization": f"Bearer {self.token}"},
            )
        self.assertEqual(created.status_code, 200)
        sub_id = created.json()["id"]
        cb = self.client.post(
            f"/internal/submissions/{sub_id}/result",
            json={
                "job_id": "j-9",
                "status": "done",
                "verdict": "OK",
                "score": 1,
                "max_score": 1,
                "tests": [],
            },
            headers={"X-Service-Key": SERVICE_KEY},
        )
        self.assertEqual(cb.status_code, 200)
        detail = self.client.get(
            f"/submissions/{sub_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(detail.json()["status"], "done")
        self.assertEqual(detail.json()["verdict"], "OK")
        self.assertEqual(detail.json()["score"], 1)

    def test_callback_rejects_bad_key(self) -> None:
        response = self.client.post(
            "/internal/submissions/1/result",
            json={"job_id": "j-1", "status": "done"},
            headers={"X-Service-Key": "nope"},
        )
        self.assertEqual(response.status_code, 401)
