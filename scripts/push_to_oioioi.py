"""Eksport SINOL + wgranie do lokalnego OIOIOI (manage.py addproblem)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.sinolpack import export_json

REPO = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPO / "oioioi" / "docker-compose.yml"
ATTACH = REPO / "oioioi" / "attach_problems.py"
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
