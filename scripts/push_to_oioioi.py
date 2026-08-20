"""Eksport SINOL + wgranie do lokalnego OIOIOI (manage.py addproblem)."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "backend"))
sys.path.insert(0, str(_ROOT))

from app.sinolpack import export_json

REPO = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPO / "oioioi" / "docker-compose.yml"
ATTACH = REPO / "oioioi" / "attach_problems.py"
ENABLE_COMPILERS = REPO / "oioioi" / "enable_system_compilers.py"
PACK_HOST = REPO / "data" / "sinolpack"
PACK_CONT = "/tmp/sinolpack"


def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), *args]
    return subprocess.run(cmd, cwd=REPO, check=check, text=True, capture_output=True)


def web_id() -> str:
    result = compose("ps", "-q", "web")
    cid = (result.stdout or "").strip().splitlines()
    if not cid:
        raise SystemExit(
            "Kontener oioioi-web nie działa. W oioioi/: docker compose up"
        )
    return cid[0]


def main() -> int:
    try:
        compose("ps")
    except FileNotFoundError:
        print("Brak dockera w PATH.", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(error.stderr or error, file=sys.stderr)
        return 1

    cid = web_id()
    paths = export_json()
    print(f"Zapisano {len(paths)} paczek.", flush=True)

    subprocess.run(["docker", "exec", "-u", "root", cid, "rm", "-rf", PACK_CONT], check=True)
    subprocess.run(
        ["docker", "cp", str(PACK_HOST.resolve()), f"{cid}:{PACK_CONT}"],
        check=True,
    )
    subprocess.run(
        ["docker", "exec", "-u", "root", cid, "chown", "-R", "oioioi:oioioi", PACK_CONT],
        check=True,
    )
    subprocess.run(
        ["docker", "cp", str(ENABLE_COMPILERS), f"{cid}:/tmp/enable_system_compilers.py"],
        check=True,
    )
    patched = subprocess.run(
        ["docker", "exec", cid, "python", "/tmp/enable_system_compilers.py"],
        text=True,
        capture_output=True,
    )
    sys.stdout.write(patched.stdout or "")
    if patched.returncode != 0:
        sys.stderr.write(patched.stderr or "enable_system_compilers failed\n")
        return patched.returncode
    if "enabled" in (patched.stdout or ""):
        print("Restart supervisor…", flush=True)
        subprocess.run(
            [
                "docker",
                "exec",
                "-w",
                "/sio2/deployment",
                cid,
                "./manage.py",
                "supervisor",
                "restart",
                "all",
            ],
            check=False,
        )
        for _ in range(30):
            probe = subprocess.run(
                [
                    "docker",
                    "exec",
                    cid,
                    "python",
                    "-c",
                    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=2)",
                ],
                capture_output=True,
            )
            if probe.returncode == 0:
                break
            time.sleep(2)
    subprocess.run(
        ["docker", "cp", str(ATTACH), f"{cid}:/tmp/attach_problems.py"],
        check=True,
    )
    uploaded = subprocess.run(
        [
            "docker",
            "exec",
            "-w",
            "/sio2/deployment",
            cid,
            "python",
            "/tmp/attach_problems.py",
        ]
    )
    if uploaded.returncode != 0:
        return uploaded.returncode
    print("Contest: http://127.0.0.1:8001/c/local/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
