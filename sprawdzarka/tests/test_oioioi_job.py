import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sprawdzarka.oioioi_client import OioioiHttpError, OioioiSubmitUncertain
from sprawdzarka.oioioi_job import run_oioioi_job
from sprawdzarka.queue import claim, enqueue, oioioi_id_from_payload
from sprawdzarka.models import Base
from sqlalchemy import create_engine


def _payload(**extra) -> dict:
    data = {
        "submission_id": 42,
        "language": "cpp",
        "code": "int main(){}",
        "short_name": "sum",
        "time_limit_ms": 1000,
        "memory_limit_mb": 64,
        "tests": [],
    }
    data.update(extra)
    return data


class FakeClient:
    def __init__(self) -> None:
        self.submits = 0
        self.queue: list[tuple[dict | None, bool]] = []
        self.reports: list[dict | BaseException] = []

    def submit(self, short_name: str, code: str) -> int:
        self.submits += 1
        return 7

    def find_submission(self, short_name: str, oioioi_id: int) -> tuple[dict | None, bool]:
        if not self.queue:
            return None, False
        return self.queue.pop(0)

    def get_submission_report(self, oioioi_id: int) -> dict:
        if not self.reports:
            return {"complete": False}
        item = self.reports.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class OioioiJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.path = Path(self.tmp.name) / "jobs.db"
        engine = create_engine("sqlite:///" + self.path.resolve().as_posix())
        Base.metadata.create_all(engine)
        engine.dispose()
        self.beats: list[int] = []

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _job(self, **extra):
        job_id = enqueue(42, _payload(**extra), path=self.path)
        job = claim("w1", path=self.path)
        assert job is not None
        self.assertEqual(job.id, job_id)
        return job

    def test_saves_id_immediately_and_does_not_resubmit(self) -> None:
        job = self._job()
        client = FakeClient()
        client.reports = [
            {"complete": False},
            {"complete": False},
            {"complete": True, "verdict": "OK", "score": 100, "max_score": 100, "time_ms": 4, "memory_kb": 800},
        ]
        times = iter([0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 3.0, 3.0])
        result = run_oioioi_job(
            job,
            client,
            path=self.path,
            heartbeat_fn=self.beats.append,
            sleep_fn=lambda _s: None,
            monotonic_fn=lambda: next(times, 1000.0),
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.oioioi_id, 7)
        self.assertEqual(result.score, 100)
        self.assertEqual(result.status, "OK")
        self.assertEqual(result.time_ms, 4)
        self.assertEqual(result.memory_kb, 800)
        self.assertEqual(client.submits, 1)
        self.assertGreaterEqual(len(self.beats), 2)

        claimed = claim("w1", path=self.path)
        self.assertIsNone(claimed)
        from sprawdzarka.queue import _connect, _payload_dict

        conn = _connect(self.path)
        raw = conn.execute("SELECT payload FROM jobs WHERE id = ?", (job.id,)).fetchone()
        conn.close()
        stored = oioioi_id_from_payload(_payload_dict(raw[0]))
        self.assertEqual(stored, 7)

        job2_id = enqueue(99, _payload(submission_id=99, oioioi_submission_id=7), path=self.path)
        job2 = claim("w2", path=self.path)
        assert job2 is not None
        self.assertEqual(job2.id, job2_id)
        client.submits = 0
        client.reports = [{"complete": True, "verdict": "CE"}]
        again = run_oioioi_job(
            job2,
            client,
            path=self.path,
            heartbeat_fn=lambda _i: None,
            sleep_fn=lambda _s: None,
            monotonic_fn=lambda: 0.0,
        )
        self.assertTrue(again.ok)
        self.assertEqual(again.status, "CE")
        self.assertEqual(client.submits, 0)

    def test_http_400_fails_without_id(self) -> None:
        job = self._job()

        class Boom(FakeClient):
            def submit(self, short_name: str, code: str) -> int:
                self.submits += 1
                raise OioioiHttpError(400, '{"file":["required"]}')

        client = Boom()
        result = run_oioioi_job(job, client, path=self.path, sleep_fn=lambda _s: None)
        self.assertFalse(result.ok)
        self.assertIsNone(result.oioioi_id)
        self.assertIn("400", result.message or "")
        self.assertEqual(client.submits, 1)

    def test_uncertain_submit_does_not_retry(self) -> None:
        job = self._job()

        class Boom(FakeClient):
            def submit(self, short_name: str, code: str) -> int:
                self.submits += 1
                raise OioioiSubmitUncertain("timeout")

        client = Boom()
        result = run_oioioi_job(job, client, path=self.path, sleep_fn=lambda _s: None)
        self.assertFalse(result.ok)
        self.assertIsNone(result.oioioi_id)
        self.assertEqual(client.submits, 1)

    def test_report_404_retries_then_completes(self) -> None:
        job = self._job(oioioi_submission_id=74)
        client = FakeClient()
        client.reports = [
            OioioiHttpError(404, '{"detail": "Not found."}'),
            {"complete": True, "verdict": "OK", "score": 100, "time_ms": 1},
        ]
        result = run_oioioi_job(
            job,
            client,
            path=self.path,
            heartbeat_fn=lambda _i: None,
            sleep_fn=lambda _s: None,
            monotonic_fn=lambda: 0.0,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.score, 100)
        self.assertEqual(result.status, "OK")
        self.assertEqual(client.submits, 0)

    def test_missing_short_name(self) -> None:
        job_id = enqueue(7, _payload(short_name=""), path=self.path)
        from sprawdzarka.queue import merge_payload

        merge_payload(
            job_id,
            {"short_name": "", "external_id": "", "oioioi_short_name": ""},
            path=self.path,
        )
        job = claim("w3", path=self.path)
        assert job is not None
        result = run_oioioi_job(job, FakeClient(), path=self.path)
        self.assertFalse(result.ok)
        self.assertIn("short_name", result.message or "")

    def test_ini_ok_without_final_report_keeps_polling(self) -> None:
        job = self._job(oioioi_submission_id=7)
        client = FakeClient()
        client.reports = [{"complete": False}] * 5
        ticks = iter([0.0, 0.0, 10.0, 10.0, 700.0])
        result = run_oioioi_job(
            job,
            client,
            path=self.path,
            heartbeat_fn=lambda _i: None,
            sleep_fn=lambda _s: None,
            monotonic_fn=lambda: next(ticks, 700.0),
            poll_timeout=5,
        )
        self.assertFalse(result.ok)
        self.assertIn("timeout", result.message or "")

    def test_report_fills_time_memory_and_verdict(self) -> None:
        job = self._job(oioioi_submission_id=7)
        client = FakeClient()
        client.reports = [
            {
                "complete": True,
                "verdict": "OK",
                "score": 100,
                "max_score": 100,
                "time_ms": 15,
                "memory_kb": 4200,
            }
        ]
        result = run_oioioi_job(
            job,
            client,
            path=self.path,
            heartbeat_fn=lambda _i: None,
            sleep_fn=lambda _s: None,
            monotonic_fn=lambda: 0.0,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.time_ms, 15)
        self.assertEqual(result.memory_kb, 4200)
        self.assertEqual(result.status, "OK")
        self.assertEqual(result.score, 100)
        self.assertEqual(result.max_score, 100)

    def test_report_verdict_overrides_ini_ok(self) -> None:
        job = self._job(oioioi_submission_id=7)
        client = FakeClient()
        client.reports = [
            {"complete": True, "verdict": "WA", "score": 0, "max_score": 100, "time_ms": 18, "memory_kb": None}
        ]
        result = run_oioioi_job(
            job,
            client,
            path=self.path,
            heartbeat_fn=lambda _i: None,
            sleep_fn=lambda _s: None,
            monotonic_fn=lambda: 0.0,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.status, "WA")
        self.assertEqual(result.score, 0)
        self.assertEqual(result.time_ms, 18)
        self.assertIsNone(result.memory_kb)

    def test_report_error_retries_then_completes(self) -> None:
        job = self._job(oioioi_submission_id=7)
        client = FakeClient()
        client.reports = [
            OioioiHttpError(500, "x"),
            {"complete": True, "verdict": "OK", "score": 100, "time_ms": 1},
        ]
        result = run_oioioi_job(
            job,
            client,
            path=self.path,
            heartbeat_fn=lambda _i: None,
            sleep_fn=lambda _s: None,
            monotonic_fn=lambda: 0.0,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.score, 100)
        self.assertEqual(result.status, "OK")

    def test_poll_timeout(self) -> None:
        job = self._job(oioioi_submission_id=3)
        client = FakeClient()
        client.reports = [{"complete": False}] * 5
        ticks = iter([0.0, 0.0, 10.0, 10.0, 700.0])
        result = run_oioioi_job(
            job,
            client,
            path=self.path,
            heartbeat_fn=lambda _i: None,
            sleep_fn=lambda _s: None,
            monotonic_fn=lambda: next(ticks, 700.0),
            poll_timeout=5,
        )
        self.assertFalse(result.ok)
        self.assertIn("timeout", result.message or "")


if __name__ == "__main__":
    unittest.main()
