import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Problem, Submission, Test, _now

ROOT = Path(__file__).resolve().parents[1]
ISO_SH = ROOT / "isolation" / "iso.sh"
ISOLATE_IMAGE = os.environ.get("ISOLATE_IMAGE", "python:3.12-slim-bookworm")
QUEUE_WAIT_SEC = int(os.environ.get("ISOLATE_QUEUE_WAIT", "120"))
SLOT_RETRIES = 3


def normalize(text: str) -> str:
    lines = text.replace("\r\n", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip()


def timeout_sec(time_limit_ms: int) -> int:
    return max(1, (time_limit_ms + 999) // 1000)


def isolate_env() -> dict[str, str]:
    """Env widziany przez iso.sh (tez przez wsl env ..., nie tylko PowerShell)."""
    allowed = os.environ.get("ISOLATE_ALLOWED_IMAGES", ISOLATE_IMAGE)
    tokens = allowed.split()
    if ISOLATE_IMAGE not in tokens:
        allowed = f"{allowed} {ISOLATE_IMAGE}".strip()
    return {
        "ISOLATE_IMAGE": ISOLATE_IMAGE,
        "ISOLATE_ALLOWED_IMAGES": allowed,
        "ISOLATE_QUEUE_WAIT": str(QUEUE_WAIT_SEC),
    }


def to_isolate_path(path: Path) -> str:
    """Sciezka zrozumiala dla iso.sh (Unix). Na Windowsie przez wslpath."""
    resolved = path.resolve()
    if os.name != "nt":
        return str(resolved)
    converted = subprocess.run(
        ["wsl", "-e", "wslpath", "-a", str(resolved)],
        capture_output=True,
        text=True,
    )
    if converted.returncode != 0:
        raise RuntimeError(converted.stderr.strip() or "wslpath nie działa (jest WSL?)")
    return converted.stdout.strip()


def isolate_command(folder: Path, time_limit_ms: int, memory_mb: int) -> tuple[list[str], dict[str, str] | None]:
    if not ISO_SH.is_file():
        raise FileNotFoundError(f"brak {ISO_SH}")
    extra = isolate_env()
    args = [
        "bash",
        to_isolate_path(ISO_SH),
        "-i",
        ISOLATE_IMAGE,
        "-m",
        f"{max(1, memory_mb)}m",
        "-t",
        str(timeout_sec(time_limit_ms)),
        "--mount",
        f"{to_isolate_path(folder)}:/work",
        "--",
        "python3",
        "/work/main.py",
    ]
    if os.name == "nt":
        env_pairs = [f"{key}={value}" for key, value in extra.items()]
        return ["wsl", "-e", "env", *env_pairs, *args], None
    env = os.environ.copy()
    env.update(extra)
    return args, env


def program_stderr(stderr: str) -> str:
    """Stderr programu, bez logów isolate / isolate-meta."""
    kept: list[str] = []
    for line in (stderr or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("[isolate]") or "[isolate-meta]" in stripped:
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def parse_isolate_meta(stderr: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in (stderr or "").splitlines():
        if "[isolate-meta]" not in line:
            continue
        payload = line.split("[isolate-meta]", 1)[1].strip()
        for token in payload.split():
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            if value != "":
                meta[key] = value
    return meta


def meta_int(meta: dict[str, str], key: str) -> int | None:
    raw = meta.get(key, "")
    if raw.isdigit():
        return int(raw)
    return None


def pick_time_ms(meta: dict[str, str], time_limit_ms: int, *, timed_out: bool) -> int | None:
    measured = meta_int(meta, "time_ms")
    if measured is not None:
        return measured
    if timed_out:
        return time_limit_ms
    return None


def pick_memory_kb(meta: dict[str, str], memory_mb: int, *, oom: bool) -> int | None:
    raw = meta_int(meta, "memory_bytes")
    if raw is not None:
        return raw // 1024
    if oom:
        return memory_mb * 1024
    return None


def run_one(
    code: str, stdin: str, time_limit_ms: int, memory_mb: int
) -> tuple[str, str, int | None, int | None]:
    """Zwraca (verdict, message, time_ms, memory_kb)."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "main.py"
        path.write_text(code, encoding="utf-8")
        path.chmod(0o644)
        Path(folder).chmod(0o755)
        cmd, env = isolate_command(Path(folder), time_limit_ms, memory_mb)
        wait_sec = QUEUE_WAIT_SEC + timeout_sec(time_limit_ms) + 30
        result = None
        try:
            for _attempt in range(SLOT_RETRIES):
                result = subprocess.run(
                    cmd,
                    input=stdin,
                    capture_output=True,
                    text=True,
                    timeout=wait_sec,
                    env=env,
                )
                if result.returncode != 75:
                    break
        except subprocess.TimeoutExpired:
            return "RE", "izolacja nie odpowiedziała (timeout workera)", None, None
        except FileNotFoundError as error:
            return "RE", f"brak izolacji (wsl/bash/iso.sh): {error}", None, None
        except Exception as error:
            return "RE", str(error), None, None

        assert result is not None
        raw_err = result.stderr or ""
        err = program_stderr(raw_err)
        meta = parse_isolate_meta(raw_err)
        oom = meta.get("oom") == "true" or "OOMKilled=true" in raw_err
        time_ms = pick_time_ms(meta, time_limit_ms, timed_out=result.returncode == 124)
        memory_kb = pick_memory_kb(meta, memory_mb, oom=oom)

        if result.returncode == 75:
            return "RE", "brak wolnego slotu", time_ms, memory_kb
        if result.returncode == 124:
            return "TLE", "Przekroczony limit czasu", time_ms, memory_kb
        if oom or result.returncode == 137:
            if oom:
                return "MLE", "Przekroczony limit pamięci", time_ms, memory_kb
            return "RE", err or "proces zabity (SIGKILL)", time_ms, memory_kb
        if result.returncode != 0:
            if "SyntaxError" in err:
                return "CE", err, time_ms, memory_kb
            return "RE", err or f"kod wyjścia {result.returncode}", time_ms, memory_kb
        return "OK", result.stdout, time_ms, memory_kb


def _finish(
    db: Session,
    submission: Submission,
    *,
    verdict: str,
    message: str | None,
    time_ms: int | None = None,
    memory_kb: int | None = None,
) -> None:
    submission.status = "done"
    submission.verdict = verdict
    submission.message = message
    submission.time_ms = time_ms
    submission.memory_kb = memory_kb
    submission.finished_at = _now()
    db.commit()


def judge(db: Session, submission: Submission) -> None:
    problem = db.query(Problem).filter(Problem.id == submission.problem_id).first()
    if problem is None:
        _finish(db, submission, verdict="RE", message="Nie ma takiego zadania")
        return

    tests = (
        db.query(Test)
        .filter(Test.problem_id == submission.problem_id)
        .order_by(Test.position, Test.id)
        .all()
    )

    submission.status = "running"
    db.commit()

    if submission.language != "python":
        _finish(db, submission, verdict="CE", message="Na razie tylko python")
        return

    if not tests:
        _finish(db, submission, verdict="RE", message="Brak testów do tego zadania")
        return

    total_ms = 0
    peak_kb: int | None = None
    for index, test in enumerate(tests, start=1):
        verdict, payload, elapsed, memory_kb = run_one(
            submission.code,
            test.input_text,
            problem.time_limit_ms,
            problem.memory_limit_mb,
        )
        if elapsed is not None:
            total_ms += elapsed
        if memory_kb is not None:
            peak_kb = memory_kb if peak_kb is None else max(peak_kb, memory_kb)

        if verdict != "OK":
            _finish(
                db,
                submission,
                verdict=verdict,
                message=f"test {index}: {payload}",
                time_ms=total_ms,
                memory_kb=peak_kb,
            )
            return

        if normalize(payload) != normalize(test.output_text):
            _finish(
                db,
                submission,
                verdict="WA",
                message=f"test {index}: zły wynik",
                time_ms=total_ms,
                memory_kb=peak_kb,
            )
            return

    _finish(
        db,
        submission,
        verdict="OK",
        message=None,
        time_ms=total_ms,
        memory_kb=peak_kb,
    )


def main() -> None:
    pull_script = ROOT / "isolation" / "pull_images.py"
    print("Sprawdzam obrazy Dockera...")
    pulled = subprocess.run([sys.executable, str(pull_script)])
    if pulled.returncode != 0:
        print("Nie mogę przygotować obrazów. Odpal: python isolation/pull_images.py")
        raise SystemExit(pulled.returncode)
    print("Worker działa. Ctrl+C żeby zatrzymać.")
    while True:
        db = SessionLocal()
        try:
            submission = (
                db.query(Submission)
                .filter(Submission.status == "queued")
                .order_by(Submission.id)
                .first()
            )
            if submission is None:
                time.sleep(1)
                continue
            print(f"Sprawdzam zgłoszenie #{submission.id}")
            judge(db, submission)
            print(f"  -> {submission.verdict}")
        finally:
            db.close()


if __name__ == "__main__":
    main()
