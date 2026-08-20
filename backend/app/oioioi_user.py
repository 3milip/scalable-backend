from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPO / "oioioi" / "docker-compose.yml"
ENSURE = REPO / "oioioi" / "ensure_user.py"


def _web_id() -> str:
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "ps", "-q", "web"],
        cwd=REPO,
        check=False,
        text=True,
        capture_output=True,
    )
    cid = (result.stdout or "").strip().splitlines()
    if result.returncode != 0 or not cid:
        raise RuntimeError("OIOIOI nie działa. W oioioi/: docker compose up")
    return cid[0]


def provision_user(username: str, password: str) -> str:
    cid = _web_id()
    subprocess.run(
        ["docker", "cp", str(ENSURE), f"{cid}:/tmp/ensure_user.py"],
        check=True,
        capture_output=True,
    )
    ran = subprocess.run(
        [
            "docker",
            "exec",
            "-e",
            f"OIOIOI_NEW_USER={username}",
            "-e",
            f"OIOIOI_NEW_PASSWORD={password}",
            "-w",
            "/sio2/deployment",
            cid,
            "python",
            "/tmp/ensure_user.py",
        ],
        text=True,
        capture_output=True,
    )
    if ran.returncode != 0:
        raise RuntimeError((ran.stderr or ran.stdout or "ensure_user failed")[:400])
    token = (ran.stdout or "").strip().splitlines()[-1].strip()
    if not token:
        raise RuntimeError("OIOIOI nie zwróciło tokenu")
    return token
