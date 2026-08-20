from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.request

OIOIOI_URL = os.environ.get("OIOIOI_URL", "http://127.0.0.1:8001").rstrip("/")
OIOIOI_CONTEST = os.environ.get("OIOIOI_CONTEST_ID", "local")

DONE = {"OK", "WA", "TLE", "MLE", "RE", "CE", "SE", "WA_OLE", "RV"}
PENDING = {"?", "PENDING"}


def map_status(oioioi_status: str | None, score: int | None = None) -> tuple[str, str | None]:
    if not oioioi_status or oioioi_status in PENDING:
        return "queued", None
    if oioioi_status == "INI_ERR":
        return "done", "WA"
    if oioioi_status == "INI_OK":
        if score is None:
            return "running", None
        return "done", "OK"
    if oioioi_status in {"ERR", "FAILED"}:
        return "failed", None
    if oioioi_status in DONE:
        return "done", oioioi_status
    return "running", None


def _request(url: str, token: str, data: bytes | None = None, content_type: str | None = None, method: str = "GET") -> tuple[int, str]:
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


def submit(token: str, short_name: str, code: str, language: str = "cpp") -> int:
    ext = {"python": "py", "c": "c", "cpp": "cpp", "c++": "cpp"}.get(language.lower(), "txt")
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
    status, body = _request(url, token, data=payload, content_type=f"multipart/form-data; boundary={boundary}", method="POST")
    if status >= 400:
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
    if status >= 400:
        raise RuntimeError(f"OIOIOI list {status}: {body[:400]}")
    payload = json.loads(body)
    for item in payload.get("submissions", []):
        if int(item["id"]) == int(oioioi_id):
            return item
    return None
