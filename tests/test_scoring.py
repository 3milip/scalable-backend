import unittest

from app.results import exact_match, problem_max_score, score_groups, test_points, worst_verdict
from app.models import Test


class ScoringTests(unittest.TestCase):
    def test_exact_match_normalizes(self) -> None:
        self.assertTrue(exact_match("3\n", "3"))
        self.assertFalse(exact_match("4", "3"))

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
            Test(problem_id=1, input_text="", output_text="", group="1", max_score=1),
            Test(problem_id=1, input_text="", output_text="", group="2", max_score=1),
            Test(problem_id=1, input_text="", output_text="", group="3", max_score=1),
        ]
        self.assertEqual(score_groups(rows), 3)
        self.assertEqual(problem_max_score(tests), 3)

    def test_oi_pack_max_is_group_not_sum_of_tests(self) -> None:
        tests = [
            Test(problem_id=1, input_text="", output_text="", group="1", max_score=1),
            Test(problem_id=1, input_text="", output_text="", group="1", max_score=1),
            Test(problem_id=1, input_text="", output_text="", group="1", max_score=1),
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
