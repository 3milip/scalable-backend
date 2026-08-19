import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ISO_SH = PACKAGE_DIR / "iso.sh"
ISOLATE_IMAGE = os.environ.get("ISOLATE_IMAGE", "python:3.12-slim-bookworm")
QUEUE_WAIT_SEC = int(os.environ.get("ISOLATE_QUEUE_WAIT", "120"))
SLOT_RETRIES = 3


@dataclass
class RunResult:
    verdict: str
    stdout: str
    message: str
    time_ms: int | None
    memory_kb: int | None


def timeout_sec(time_limit_ms: int) -> int:
    return max(1, (time_limit_ms + 999) // 1000)


def isolate_env() -> dict[str, str]:
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


def isolate_command(
    folder: Path,
    time_limit_ms: int,
    memory_mb: int,
    program: list[str],
    extra_mounts: list[tuple[Path, str]] | None = None,
) -> tuple[list[str], dict[str, str] | None]:
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
    ]
    for host, dest in extra_mounts or []:
        args.extend(["--mount", f"{to_isolate_path(host)}:{dest}"])
    args.extend(["--", *program])
    if os.name == "nt":
        env_pairs = [f"{key}={value}" for key, value in extra.items()]
        return ["wsl", "-e", "env", *env_pairs, *args], None
    env = os.environ.copy()
    env.update(extra)
    return args, env


def program_stderr(stderr: str) -> str:
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


def prepare_work(code: str) -> tempfile.TemporaryDirectory:
    folder = tempfile.TemporaryDirectory()
    path = Path(folder.name) / "main.py"
    path.write_text(code, encoding="utf-8")
    path.chmod(0o644)
    Path(folder.name).chmod(0o755)
    return folder


@dataclass
class RawRun:
    returncode: int
    stdout: str
    stderr: str
    time_ms: int | None
    memory_kb: int | None
    oom: bool
    isolate_error: str | None = None


def run_raw(
    folder: Path,
    stdin: str,
    time_limit_ms: int,
    memory_mb: int,
    program: list[str],
    extra_mounts: list[tuple[Path, str]] | None = None,
) -> RawRun:
    cmd, env = isolate_command(
        folder, time_limit_ms, memory_mb, program, extra_mounts=extra_mounts
    )
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
        return RawRun(-1, "", "", None, None, False, "izolacja nie odpowiedziała (timeout workera)")
    except FileNotFoundError as error:
        return RawRun(-1, "", "", None, None, False, f"brak izolacji (wsl/bash/iso.sh): {error}")
    except Exception as error:
        return RawRun(-1, "", "", None, None, False, str(error))

    assert result is not None
    raw_err = result.stderr or ""
    err = program_stderr(raw_err)
    meta = parse_isolate_meta(raw_err)
    oom = meta.get("oom") == "true" or "OOMKilled=true" in raw_err
    time_ms = pick_time_ms(meta, time_limit_ms, timed_out=result.returncode == 124)
    memory_kb = pick_memory_kb(meta, memory_mb, oom=oom)
    isolate_error = None
    if result.returncode == 75:
        isolate_error = err or "brak wolnego slotu"
    return RawRun(
        result.returncode,
        result.stdout or "",
        err,
        time_ms,
        memory_kb,
        oom,
        isolate_error,
    )


def run_in(
    folder: Path,
    stdin: str,
    time_limit_ms: int,
    memory_mb: int,
    program: list[str],
    extra_mounts: list[tuple[Path, str]] | None = None,
) -> RunResult:
    raw = run_raw(folder, stdin, time_limit_ms, memory_mb, program, extra_mounts=extra_mounts)
    if raw.isolate_error and raw.returncode < 0:
        return RunResult("RE", "", raw.isolate_error, raw.time_ms, raw.memory_kb)
    if raw.returncode == 75:
        return RunResult("RE", raw.stdout, raw.isolate_error or "brak wolnego slotu", raw.time_ms, raw.memory_kb)
    if raw.returncode == 124:
        return RunResult("TLE", raw.stdout, raw.stderr or "Przekroczony limit czasu", raw.time_ms, raw.memory_kb)
    if raw.oom or raw.returncode == 137:
        if raw.oom:
            return RunResult("MLE", raw.stdout, raw.stderr or "Przekroczony limit pamięci", raw.time_ms, raw.memory_kb)
        return RunResult("RE", raw.stdout, raw.stderr or "proces zabity (SIGKILL)", raw.time_ms, raw.memory_kb)
    if raw.returncode != 0:
        if "SyntaxError" in raw.stderr:
            return RunResult("CE", raw.stdout, raw.stderr, raw.time_ms, raw.memory_kb)
        return RunResult("RE", raw.stdout, raw.stderr or f"kod wyjścia {raw.returncode}", raw.time_ms, raw.memory_kb)
    return RunResult("OK", raw.stdout, raw.stderr, raw.time_ms, raw.memory_kb)


COMPILE_PROGRAM = [
    "python3",
    "-c",
    "import py_compile; py_compile.compile('/work/main.py', cfile='/tmp/main.pyc', doraise=True)",
]
RUN_PROGRAM = ["python3", "/work/main.py"]
