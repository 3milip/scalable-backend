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
        self.assertIsNone(body["time_ms"])
        self.assertIsNone(body["memory_kb"])

    def test_copies_time_and_memory(self) -> None:
        result = OioioiJobResult(
            True, 3, "INI_OK", 100, None, {"id": 3}, time_ms=15, memory_kb=4200
        )
        body = to_callback(42, result)
        self.assertEqual(body["time_ms"], 15)
        self.assertEqual(body["memory_kb"], 4200)
        self.assertEqual(body["tests"], [])

    def test_ini_ok_with_zero_from_list_stays_ok_without_report(self) -> None:
        result = OioioiJobResult(True, 3, "INI_OK", 0, None, {"id": 3})
        body = to_callback(42, result)
        self.assertEqual(body["verdict"], "OK")
        self.assertEqual(body["score"], 0)

    def test_wa_from_final_report(self) -> None:
        result = OioioiJobResult(
            True, 3, "WA", 0, None, {"id": 3}, time_ms=18, memory_kb=None, max_score=100
        )
        body = to_callback(42, result)
        self.assertEqual(body["verdict"], "WA")
        self.assertEqual(body["score"], 0)
        self.assertEqual(body["max_score"], 100)
        self.assertEqual(body["time_ms"], 18)
        self.assertIsNone(body["memory_kb"])

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
