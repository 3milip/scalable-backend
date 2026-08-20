import os
import signal
import socket
import subprocess
import sys
import threading
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "backend"))
sys.path.insert(0, str(_ROOT))

from app.db import SessionLocal
from app.models import Submission
from isolation.judge import judge
from isolation.queue import (
    HEARTBEAT_EVERY,
    ack,
    claim,
    ensure_db,
    heartbeat,
    nack,
    remove_worker,
    touch_worker,
)

PACKAGE_DIR = Path(__file__).resolve().parent


def _new_worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


def main() -> None:
    ensure_db()
    pull_script = PACKAGE_DIR / "pull_images.py"
    print("Sprawdzam obrazy Dockera...")
    pulled = subprocess.run([sys.executable, str(pull_script)])
    if pulled.returncode != 0:
        print("Nie mogę przygotować obrazów. Odpal: python isolation/pull_images.py")
        raise SystemExit(pulled.returncode)

    worker_id = _new_worker_id()
    touch_worker(worker_id)
    stop = threading.Event()
    lock = threading.Lock()
    current: dict[str, int | None] = {"id": None}

    def beat() -> None:
        while not stop.wait(HEARTBEAT_EVERY):
            try:
                touch_worker(worker_id)
                with lock:
                    job_id = current["id"]
                if job_id is not None:
                    heartbeat(job_id)
            except Exception as error:
                print(f"heartbeat: {error}")

    threading.Thread(target=beat, daemon=True, name="heartbeat").start()

    def request_stop(*_args: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    print(f"Worker {worker_id} działa. Ctrl+C żeby zatrzymać.")
    try:
        while not stop.is_set():
            touch_worker(worker_id)
            job = claim(worker_id)
            if job is None:
                stop.wait(1)
                continue
            with lock:
                current["id"] = job.id
            db = SessionLocal()
            try:
                submission = db.get(Submission, job.submission_id)
                if submission is None:
                    nack(job.id)
                    continue
                print(
                    f"Job #{job.id} zgłoszenie #{submission.id} "
                    f"({job.kind}, próba {job.attempts})"
                )
                judge(db, submission, job.id)
                ack(job.id)
                print(f"  -> {submission.verdict} {submission.score}/{submission.max_score}")
            except KeyboardInterrupt:
                stop.set()
                nack(job.id)
                break
            finally:
                db.close()
                with lock:
                    current["id"] = None
    finally:
        stop.set()
        leftover: int | None
        with lock:
            leftover = current["id"]
            current["id"] = None
        if leftover is not None:
            nack(leftover)
        remove_worker(worker_id)


if __name__ == "__main__":
    main()
