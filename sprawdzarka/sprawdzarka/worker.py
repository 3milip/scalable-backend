import os
import signal
import socket
import sys
import threading
import uuid

from sprawdzarka.callback import post_results
from sprawdzarka.oioioi_client import OioioiClient, OioioiConfigError
from sprawdzarka.oioioi_job import run_oioioi_job
from sprawdzarka.oioioi_map import to_callback
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


def _new_worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


def main() -> None:
    ensure_db()
    try:
        client = OioioiClient.from_env()
    except OioioiConfigError as error:
        print(f"Brak konfiguracji OIOIOI: {error}")
        print("Ustaw OIOIOI_URL, OIOIOI_TOKEN, OIOIOI_CONTEST_ID (sprawdzarka/.env).")
        raise SystemExit(1) from error

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
                outcome = run_oioioi_job(job, client)
                body = to_callback(job.submission_id, outcome)
                sent = post_results(body, retries=3)
                if not sent:
                    nack(job.id)
                    print("  -> callback wyniku nie przeszedł, job wraca do kolejki")
                    continue
                ack(job.id)
                print(
                    f"  -> {body.get('status')} {body.get('verdict')} "
                    f"{body.get('score')}/{body.get('max_score')} {body.get('message') or ''}"
                )
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
