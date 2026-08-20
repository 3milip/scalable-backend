import os
import signal
import socket
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from sprawdzarka.callback import post_results
from sprawdzarka.judge import JobPayload, judge
from sprawdzarka.queue import (
    HEARTBEAT_EVERY,
    ack,
    claim,
    ensure_db,
    heartbeat,
    nack,
    reap,
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
        print("Nie mogę przygotować obrazów. Odpal: python -m sprawdzarka.pull_images")
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
            for failed in reap():
                post_results(
                    {
                        "submission_id": failed.submission_id,
                        "status": "failed",
                        "message": failed.reason,
                    },
                    retries=3,
                )
            job = claim(worker_id)
            if job is None:
                stop.wait(1)
                continue
            with lock:
                current["id"] = job.id
            try:
                print(
                    f"Job #{job.id} zgłoszenie #{job.submission_id} "
                    f"({job.kind}, próba {job.attempts})"
                )
                post_results(
                    {"submission_id": job.submission_id, "status": "running"},
                    retries=1,
                )
                payload = JobPayload.from_dict(job.payload)
                outcome = judge(payload, job.id)
                sent = post_results(outcome.to_callback(), retries=3)
                if not sent:
                    nack(job.id)
                    print("  -> callback wyniku nie przeszedł, job wraca do kolejki")
                    continue
                ack(job.id)
                print(f"  -> {outcome.verdict} {outcome.score}/{outcome.max_score}")
            except KeyboardInterrupt:
                stop.set()
                nack(job.id)
                break
            finally:
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
