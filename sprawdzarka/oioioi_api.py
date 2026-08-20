from __future__ import annotations

import json
import os
import secrets
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

OIOIOI_URL = os.environ.get("OIOIOI_URL", "http://127.0.0.1:8001").rstrip("/")
OIOIOI_CONTEST = os.environ.get("OIOIOI_CONTEST_ID", "local")
REPO = Path(__file__).resolve().parents[1]
COMPOSE_FILE = Path(os.environ.get("OIOIOI_COMPOSE", REPO / "oioioi" / "docker-compose.yml"))
ENSURE = Path(__file__).resolve().parent / "oioioi_ensure_service.py"


def _request(
    url: str,
    token: str,
    data: bytes | None = None,
    content_type: str | None = None,
    method: str = "GET",
) -> tuple[int, str]:
    headers = {"Authorization": f"Token {token}"}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return error.code, body
    except urllib.error.URLError as error:
        return 0, str(error)


def health_oioioi() -> str:
    try:
        with urllib.request.urlopen(OIOIOI_URL + "/", timeout=5) as resp:
            return "ok" if resp.status < 500 else "down"
    except Exception:
        return "down"


def submit(token: str, short_name: str, code: str, language: str = "cpp") -> int:
    ext = {"cpp": "cpp", "c++": "cpp", "c": "c"}.get(language.lower(), "txt")
    filename = f"solution.{ext}"
    boundary = "----Judge" + secrets.token_hex(8)
    payload = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
        f"{code}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    url = f"{OIOIOI_URL}/api/c/{OIOIOI_CONTEST}/submit/{short_name}"
    status, body = _request(
        url, token, data=payload, content_type=f"multipart/form-data; boundary={boundary}", method="POST"
    )
    if status >= 400 or status == 0:
        raise RuntimeError(f"OIOIOI submit {status}: {body[:400]}")
    parsed = json.loads(body)
    if isinstance(parsed, int):
        return parsed
    if isinstance(parsed, dict) and "id" in parsed:
        return int(parsed["id"])
    return int(parsed)


def fetch_status(token: str, short_name: str, oioioi_id: int) -> dict | None:
    url = f"{OIOIOI_URL}/api/c/{OIOIOI_CONTEST}/problem_submission_list/{short_name}/"
    status, body = _request(url, token)
    if status >= 400 or status == 0:
        raise RuntimeError(f"OIOIOI list {status}: {body[:400]}")
    payload = json.loads(body)
    for item in payload.get("submissions", []):
        if int(item["id"]) == int(oioioi_id):
            return item
    return None


def service_token() -> str:
    env = os.environ.get("OIOIOI_SERVICE_TOKEN", "").strip()
    if env:
        return env
    user = os.environ.get("OIOIOI_SERVICE_USER", "judgebot")
    password = os.environ.get("OIOIOI_SERVICE_PASSWORD", "judgebot")
    if not COMPOSE_FILE.exists():
        raise RuntimeError("Brak compose OIOIOI")
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "ps", "-q", "web"],
        cwd=REPO,
        check=False,
        text=True,
        capture_output=True,
    )
    cid = (result.stdout or "").strip().splitlines()
    if result.returncode != 0 or not cid:
        raise RuntimeError("OIOIOI nie działa")
    ensure = Path(__file__).resolve().parent.parent / "oioioi" / "ensure_user.py"
    if not ensure.exists():
        ensure = Path(__file__).resolve().parent / "ensure_user.py"
    subprocess.run(
        ["docker", "cp", str(ensure), f"{cid[0]}:/tmp/ensure_user.py"],
        check=True,
        capture_output=True,
    )
    ran = subprocess.run(
        [
            "docker",
            "exec",
            "-e",
            f"OIOIOI_NEW_USER={user}",
            "-e",
            f"OIOIOI_NEW_PASSWORD={password}",
            "-e",
            "OIOIOI_MAKE_ADMIN=1",
            "-w",
            "/sio2/deployment",
            cid[0],
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
        raise RuntimeError("OIOIOI nie zwróciło tokenu serwisowego")
    return token
