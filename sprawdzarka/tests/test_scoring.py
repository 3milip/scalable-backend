import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sprawdzarka.checker import exact
from sprawdzarka.judge import JobTest
from sprawdzarka.scoring import problem_max_score, score_groups, test_points, worst_verdict


class ScoringTests(unittest.TestCase):
    def test_exact_match_normalizes(self) -> None:
        self.assertEqual(exact("3\n", "3").verdict, "OK")
        self.assertEqual(exact("4", "3").verdict, "WA")

    def test_examples_do_not_count(self) -> None:
        rows = [
            ("0", "OK", 0),
            ("1", "OK", 1),
            ("2", "OK", 1),
        ]
        self.assertEqual(score_groups(rows), 2)

    def test_group_is_min(self) -> None:
        rows = [
            ("1", "OK", 1),
            ("1", "WA", 1),
            ("2", "OK", 1),
        ]
        self.assertEqual(score_groups(rows), 1)

    def test_all_ok(self) -> None:
        rows = [("1", "OK", 1), ("1", "OK", 1), ("2", "OK", 5)]
        self.assertEqual(score_groups(rows), 6)

    def test_full_ok_equals_max_when_own_groups(self) -> None:
        rows = [("1", "OK", 1), ("2", "OK", 1), ("3", "OK", 1)]
        tests = [
            JobTest(id=1, input="", output="", group="1", max_score=1),
            JobTest(id=2, input="", output="", group="2", max_score=1),
            JobTest(id=3, input="", output="", group="3", max_score=1),
        ]
        self.assertEqual(score_groups(rows), 3)
        self.assertEqual(problem_max_score(tests), 3)

    def test_oi_pack_max_is_group_not_sum_of_tests(self) -> None:
        tests = [
            JobTest(id=1, input="", output="", group="1", max_score=1),
            JobTest(id=2, input="", output="", group="1", max_score=1),
            JobTest(id=3, input="", output="", group="1", max_score=1),
        ]
        self.assertEqual(problem_max_score(tests), 1)
        self.assertEqual(score_groups([("1", "OK", 1), ("1", "OK", 1), ("1", "OK", 1)]), 1)

    def test_worst_verdict_order(self) -> None:
        self.assertEqual(worst_verdict(["OK", "WA"]), "WA")
        self.assertEqual(worst_verdict(["WA", "TLE", "OK"]), "TLE")
        self.assertEqual(worst_verdict(["MLE", "RE", "TLE"]), "RE")
        self.assertEqual(worst_verdict(["OK", "SI", "WA"]), "SI")
        self.assertEqual(worst_verdict(["OK", "OK"]), "OK")

    def test_test_points(self) -> None:
        self.assertEqual(test_points("OK", 1), 1)
        self.assertEqual(test_points("WA", 1), 0)
        self.assertEqual(test_points("OK", 0), 0)


if __name__ == "__main__":
    unittest.main()
