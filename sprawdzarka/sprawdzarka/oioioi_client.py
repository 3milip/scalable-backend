"""Klient HTTP do oficjalnego API OIOIOI. Bez RabbitMQ. Worker na razie go nie woła."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

UrlOpen = Callable[..., Any]

STILL_RUNNING = frozenset({"", "?", "QUE", None})
FAILED_STATUS = frozenset({"CE", "SE", "INI_ERR", "ERR"})


class OioioiError(Exception):
    pass


class OioioiConfigError(OioioiError):
    pass


class OioioiHttpError(OioioiError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class OioioiSubmitUncertain(OioioiError):
    """POST mógł przejść, odpowiedzi nie mamy — nie submitować drugi raz."""


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def parse_score(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return int(float(text))


def parse_submit_id(body: bytes | str) -> int:
    if isinstance(body, bytes):
        text = body.decode("utf-8").strip()
    else:
        text = body.strip()
    if not text:
        raise OioioiError("submit: puste ciało odpowiedzi")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = text
    return int(parsed)


def is_terminal(status: str | None, score: int | None) -> bool:
    """INI_OK + score = ocena skończona (ProgrammingContestController). INI_OK bez score = jeszcze przykłady."""
    if status in STILL_RUNNING:
        return False
    if status == "INI_OK":
        return score is not None
    return True


class OioioiClient:
    def __init__(
        self,
        url: str,
        token: str,
        contest_id: str,
        timeout: float = 30,
        urlopen: UrlOpen | None = None,
    ) -> None:
        if not url or not token or not contest_id:
            raise OioioiConfigError("OIOIOI_URL, OIOIOI_TOKEN i OIOIOI_CONTEST_ID są wymagane")
        self.url = url.rstrip("/")
        self.token = token
        self.contest_id = contest_id
        self.timeout = timeout
        self._urlopen = urlopen or urllib.request.urlopen

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> OioioiClient:
        if env_file is None:
            env_file = Path(__file__).resolve().parents[1] / ".env"
        load_env_file(env_file)
        return cls(
            url=os.environ.get("OIOIOI_URL", ""),
            token=os.environ.get("OIOIOI_TOKEN", ""),
            contest_id=os.environ.get("OIOIOI_CONTEST_ID", ""),
        )

    def submit(self, short_name: str, code: str) -> int:
        """Jeden POST. Timeout/utrata odpowiedzi → OioioiSubmitUncertain, bez retry."""
        boundary = "----OioioiForm" + uuid4().hex
        payload = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="main.cpp"\r\n'
            "Content-Type: text/x-c++src\r\n"
            "\r\n"
            f"{code}"
            "\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.url}/api/c/{self.contest_id}/submit/{short_name}",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Token {self.token}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )
        try:
            with self._urlopen(request, timeout=self.timeout) as response:
                body = response.read()
                status = getattr(response, "status", 200)
                if status != 200:
                    raise OioioiHttpError(int(status), body.decode("utf-8", "replace"))
                return parse_submit_id(body)
        except OioioiError:
            raise
        except urllib.error.HTTPError as error:
            raise self._http_error(error) from error
        except TimeoutError as error:
            raise OioioiSubmitUncertain("timeout po POST submit — nie retry") from error
        except urllib.error.URLError as error:
            reason = str(getattr(error, "reason", error))
            if "timed out" in reason.lower() or "timeout" in reason.lower():
                raise OioioiSubmitUncertain("timeout po POST submit — nie retry") from error
            raise OioioiError(f"submit nie doszedł: {reason}") from error

    def list_submissions(self, short_name: str) -> dict:
        request = urllib.request.Request(
            f"{self.url}/api/c/{self.contest_id}/problem_submission_list/{short_name}/",
            method="GET",
            headers={
                "Authorization": f"Token {self.token}",
                "Accept": "application/json",
            },
        )
        try:
            with self._urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise self._http_error(error) from error
        except TimeoutError as error:
            raise OioioiError("timeout listy zgłoszeń") from error
        except urllib.error.URLError as error:
            raise OioioiError(f"lista zgłoszeń: {error.reason}") from error

    def find_submission(self, short_name: str, oioioi_id: int) -> tuple[dict | None, bool]:
        data = self.list_submissions(short_name)
        truncated = bool(data.get("is_truncated_to_20") or data.get("is_truncated"))
        wanted = int(oioioi_id)
        for item in data.get("submissions") or []:
            if int(item["id"]) == wanted:
                return item, truncated
        return None, truncated

    def _http_error(self, error: urllib.error.HTTPError) -> OioioiHttpError:
        raw = error.read().decode("utf-8", "replace")
        status = int(getattr(error, "code", 0) or getattr(error, "status", 0))
        message = raw
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                message = json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
        if status == 429:
            return OioioiHttpError(429, "429 rate limit: " + message)
        if status == 400:
            return OioioiHttpError(400, message)
        return OioioiHttpError(status, message or f"HTTP {status}")
