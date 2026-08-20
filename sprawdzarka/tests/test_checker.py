import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sprawdzarka.checker import _map_custom, check, exact, floats, tokens
from sprawdzarka.isolate import RawRun


class CheckerTests(unittest.TestCase):
    def test_exact(self) -> None:
        self.assertEqual(exact("3\n", "3").verdict, "OK")
        self.assertEqual(exact("4", "3").verdict, "WA")

    def test_tokens(self) -> None:
        self.assertEqual(tokens("1  2\n3", "1 2 3").verdict, "OK")
        self.assertEqual(tokens("1 2", "1 3").verdict, "WA")

    def test_float(self) -> None:
        self.assertEqual(floats("0.3333333", "0.333333").verdict, "OK")
        self.assertEqual(floats("1.0", "2.0").verdict, "WA")
        self.assertEqual(floats("TAK", "TAK").verdict, "OK")

    def test_check_skips_when_program_failed(self) -> None:
        result = check("exact", "", "1 2\n", "3\n", "TLE", "")
        self.assertEqual(result.verdict, "TLE")

    def test_check_dispatches_exact(self) -> None:
        self.assertEqual(check("exact", "", "1 2\n", "3\n", "OK", "3").verdict, "OK")

    def test_custom_exit_codes(self) -> None:
        self.assertEqual(_map_custom(RawRun(0, "", "", 1, 1, False)).verdict, "OK")
        self.assertEqual(_map_custom(RawRun(1, "", "zle", 1, 1, False)).verdict, "WA")
        self.assertEqual(_map_custom(RawRun(2, "", "fmt", 1, 1, False)).verdict, "WA")
        self.assertEqual(_map_custom(RawRun(124, "", "", 1, 1, False)).verdict, "SI")
        self.assertEqual(_map_custom(RawRun(99, "", "boom", 1, 1, False)).verdict, "SI")
        self.assertEqual(
            _map_custom(RawRun(-1, "", "", None, None, False, "brak izolacji")).verdict,
            "SI",
        )


if __name__ == "__main__":
    unittest.main()
