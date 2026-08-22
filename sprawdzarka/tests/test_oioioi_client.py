import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sprawdzarka.oioioi_client import (
    OioioiClient,
    OioioiHttpError,
    OioioiSubmitUncertain,
    is_terminal,
    parse_score,
    parse_submit_id,
)


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _client(urlopen) -> OioioiClient:
    return OioioiClient(
        "http://127.0.0.1:8001",
        "tok",
        "demo",
        urlopen=urlopen,
    )


class ParseTests(unittest.TestCase):
    def test_submit_id_json_number(self) -> None:
        self.assertEqual(parse_submit_id(b"3"), 3)

    def test_submit_id_text(self) -> None:
        self.assertEqual(parse_submit_id(" 12\n"), 12)

    def test_score_int_or_string_or_null(self) -> None:
        self.assertEqual(parse_score(100), 100)
        self.assertEqual(parse_score("100"), 100)
        self.assertIsNone(parse_score(None))
        self.assertIsNone(parse_score(""))

    def test_ini_ok_without_score_is_running(self) -> None:
        self.assertFalse(is_terminal("INI_OK", None))
        self.assertFalse(is_terminal("?", None))
        self.assertFalse(is_terminal("QUE", None))

    def test_ini_ok_with_score_is_done(self) -> None:
        self.assertTrue(is_terminal("INI_OK", 100))
        self.assertTrue(is_terminal("INI_OK", 0))

    def test_ce_is_terminal(self) -> None:
        self.assertTrue(is_terminal("CE", None))
        self.assertTrue(is_terminal("WA", 0))


class SubmitTests(unittest.TestCase):
    def test_submit_200_returns_id_once(self) -> None:
        urlopen = MagicMock(return_value=FakeResponse(b"3"))
        client = _client(urlopen)
        self.assertEqual(client.submit("sum", "int main(){}"), 3)
        self.assertEqual(urlopen.call_count, 1)
        request = urlopen.call_args[0][0]
        self.assertIn("/api/c/demo/submit/sum", request.full_url)
        body = request.data.decode("utf-8")
        self.assertIn('filename="main.cpp"', body)
        self.assertIn("int main(){}", body)
        self.assertEqual(request.get_header("Authorization"), "Token tok")

    def test_submit_400_form_errors_no_retry(self) -> None:
        payload = json.dumps({"file": ["This field is required."]}).encode()
        error = urllib.error.HTTPError(
            "http://x",
            400,
            "Bad Request",
            hdrs=None,
            fp=io.BytesIO(payload),
        )
        urlopen = MagicMock(side_effect=error)
        client = _client(urlopen)
        with self.assertRaises(OioioiHttpError) as ctx:
            client.submit("sum", "int main(){}")
        self.assertEqual(ctx.exception.status, 400)
        self.assertIn("required", ctx.exception.message)
        self.assertEqual(urlopen.call_count, 1)

    def test_submit_timeout_is_uncertain_no_retry(self) -> None:
        urlopen = MagicMock(side_effect=TimeoutError("timed out"))
        client = _client(urlopen)
        with self.assertRaises(OioioiSubmitUncertain):
            client.submit("sum", "int main(){}")
        self.assertEqual(urlopen.call_count, 1)

    def test_submit_429(self) -> None:
        error = urllib.error.HTTPError(
            "http://x",
            429,
            "Too Many",
            hdrs=None,
            fp=io.BytesIO(b'{"detail":"throttled"}'),
        )
        urlopen = MagicMock(side_effect=error)
        with self.assertRaises(OioioiHttpError) as ctx:
            _client(urlopen).submit("sum", "int main(){}")
        self.assertEqual(ctx.exception.status, 429)


class ListTests(unittest.TestCase):
    def test_find_by_id_not_newest(self) -> None:
        body = json.dumps(
            {
                "submissions": [
                    {"id": 9, "status": "INI_OK", "score": 100},
                    {"id": 3, "status": "CE", "score": None},
                ],
                "is_truncated_to_20": False,
            }
        ).encode()
        urlopen = MagicMock(return_value=FakeResponse(body))
        item, truncated = _client(urlopen).find_submission("sum", 3)
        self.assertFalse(truncated)
        assert item is not None
        self.assertEqual(item["id"], 3)
        self.assertEqual(item["status"], "CE")

    def test_missing_and_truncated(self) -> None:
        body = json.dumps(
            {
                "submissions": [{"id": 99, "status": "OK", "score": 1}],
                "is_truncated_to_20": True,
            }
        ).encode()
        urlopen = MagicMock(return_value=FakeResponse(body))
        item, truncated = _client(urlopen).find_submission("sum", 3)
        self.assertIsNone(item)
        self.assertTrue(truncated)

    def test_missing_not_truncated_means_not_on_list_yet(self) -> None:
        body = json.dumps({"submissions": [], "is_truncated_to_20": False}).encode()
        urlopen = MagicMock(return_value=FakeResponse(body))
        item, truncated = _client(urlopen).find_submission("sum", 3)
        self.assertIsNone(item)
        self.assertFalse(truncated)


if __name__ == "__main__":
    unittest.main()
