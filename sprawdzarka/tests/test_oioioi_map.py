import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sprawdzarka.oioioi_job import OioioiJobResult
from sprawdzarka.oioioi_map import map_verdict, to_callback


class MapTests(unittest.TestCase):
    def test_ini_ok_with_score_is_ok_100(self) -> None:
        result = OioioiJobResult(True, 3, "INI_OK", 100, None, {"id": 3})
        body = to_callback(42, result)
        self.assertEqual(body["status"], "done")
        self.assertEqual(body["verdict"], "OK")
        self.assertEqual(body["score"], 100)
        self.assertEqual(body["max_score"], 100)
        self.assertEqual(body["tests"], [])

    def test_rte_se_ce(self) -> None:
        self.assertEqual(map_verdict("RTE"), "RE")
        self.assertEqual(map_verdict("SE"), "SI")
        self.assertEqual(map_verdict("CE"), "CE")
        self.assertEqual(map_verdict("INI_ERR"), "WA")

    def test_failed_adapter(self) -> None:
        result = OioioiJobResult(False, None, None, None, "OIOIOI HTTP 400: x")
        body = to_callback(42, result)
        self.assertEqual(body["status"], "failed")
        self.assertIn("400", body["message"])
        self.assertNotIn("verdict", body)


if __name__ == "__main__":
    unittest.main()
