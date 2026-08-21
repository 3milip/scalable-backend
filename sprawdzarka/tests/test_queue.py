import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sprawdzarka.models import Base, Job
from sprawdzarka.queue import MAX_ATTEMPTS, ack, claim, enqueue, nack, reap


def _engine(path: Path):
    return create_engine("sqlite:///" + path.resolve().as_posix())


def _payload(submission_id: int) -> dict:
    return {
        "submission_id": submission_id,
        "language": "cpp",
        "code": "int main(){}",
        "time_limit_ms": 1000,
        "memory_limit_mb": 64,
        "checker": "exact",
        "checker_code": "",
        "tests": [],
    }


def _seed(path: Path):
    engine = _engine(path)
    Base.metadata.create_all(engine)
    submission_id = 42
    job_id = enqueue(submission_id, _payload(submission_id), path=path)
    return engine, submission_id, job_id


def _job_row(path: Path, job_id: int) -> tuple[str, int]:
    conn = sqlite3.connect(str(path))
    row = conn.execute(
        "SELECT status, attempts FROM jobs WHERE id = ?",
        (job_id,),
    ).fetchone()
    conn.close()
    assert row is not None
    return str(row[0]), int(row[1])


class QueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.path = Path(self.tmp.name) / "queue.db"
        self.engine, self.submission_id, self.job_id = _seed(self.path)

    def tearDown(self) -> None:
        self.engine.dispose()
        self.tmp.cleanup()

    def test_two_processes_one_job(self) -> None:
        helper = (
            "import sys\n"
            f"sys.path.insert(0, {str(ROOT)!r})\n"
            "from pathlib import Path\n"
            "from sprawdzarka.queue import claim\n"
            "job = claim(sys.argv[1], path=Path(sys.argv[2]))\n"
            "print('' if job is None else job.id)\n"
        )
        script = Path(self.tmp.name) / "claim_once.py"
        script.write_text(helper, encoding="utf-8")

        def spawn(name: str) -> subprocess.Popen:
            return subprocess.Popen(
                [sys.executable, str(script), name, str(self.path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        first = spawn("w-a")
        second = spawn("w-b")
        out_a, err_a = first.communicate(timeout=15)
        out_b, err_b = second.communicate(timeout=15)
        self.assertEqual(first.returncode, 0, err_a)
        self.assertEqual(second.returncode, 0, err_b)

        got = {part.strip() for part in (out_a.strip(), out_b.strip())}
        self.assertIn(str(self.job_id), got)
        self.assertIn("", got)
        status, attempts = _job_row(self.path, self.job_id)
        self.assertEqual(status, "leased")
        self.assertEqual(attempts, 1)

    def test_stale_lease_returns_then_reclaim(self) -> None:
        job = claim("w1", path=self.path)
        self.assertIsNotNone(job)
        self.assertEqual(job.id, self.job_id)
        conn = sqlite3.connect(str(self.path))
        conn.execute(
            "UPDATE jobs SET heartbeat_at = ? WHERE id = ?",
            (int(time.time()) - 120, self.job_id),
        )
        conn.commit()
        conn.close()

        job2 = claim("w2", path=self.path)
        self.assertIsNotNone(job2)
        self.assertEqual(job2.id, self.job_id)
        status, attempts = _job_row(self.path, self.job_id)
        self.assertEqual(status, "leased")
        self.assertEqual(attempts, 2)

    def test_three_expired_leases_fail_job(self) -> None:
        conn = sqlite3.connect(str(self.path))
        conn.execute(
            """
            UPDATE jobs
            SET status = 'leased', attempts = ?, heartbeat_at = ?
            WHERE id = ?
            """,
            (MAX_ATTEMPTS, int(time.time()) - 120, self.job_id),
        )
        conn.commit()
        conn.close()

        failed = reap(path=self.path)
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].submission_id, self.submission_id)
        job = claim("w3", path=self.path)
        self.assertIsNone(job)
        self.assertEqual(_job_row(self.path, self.job_id)[0], "failed")

    def test_nack_does_not_burn_attempt(self) -> None:
        job = claim("w1", path=self.path)
        self.assertIsNotNone(job)
        nack(job.id, path=self.path)
        status, attempts = _job_row(self.path, self.job_id)
        self.assertEqual(status, "queued")
        self.assertEqual(attempts, 0)

    def test_ack_marks_job_done(self) -> None:
        job = claim("w1", path=self.path)
        self.assertIsNotNone(job)
        ack(job.id, path=self.path)
        self.assertEqual(_job_row(self.path, self.job_id)[0], "done")

    def test_enqueue_is_idempotent_while_open(self) -> None:
        again = enqueue(self.submission_id, _payload(self.submission_id), path=self.path)
        self.assertEqual(again, self.job_id)

    def test_claim_keeps_payload(self) -> None:
        job = claim("w1", path=self.path)
        self.assertIsNotNone(job)
        self.assertEqual(job.payload["submission_id"], self.submission_id)
        self.assertEqual(job.payload["code"], "int main(){}")
        with Session(self.engine) as session:
            row = session.get(Job, job.id)
            self.assertIsNotNone(row)
            self.assertEqual(row.status, "leased")


if __name__ == "__main__":
    unittest.main()
