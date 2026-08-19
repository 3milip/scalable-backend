import unittest

from app.models import SubmissionResult, Test
from app.results import meta_from_sample, problem_max_score, public_result_payload


class ResultsModelTests(unittest.TestCase):
    def test_import_v1_examples_and_hidden(self) -> None:
        self.assertEqual(meta_from_sample(False), ("0", 0))
        self.assertEqual(meta_from_sample(True), ("1", 1))
        self.assertEqual(meta_from_sample(True, position=2), ("2", 1))
        self.assertEqual(meta_from_sample(True, group="2", max_score=5), ("2", 5))

    def test_problem_max_score_is_sum_of_groups(self) -> None:
        example = Test(
            problem_id=1,
            input_text="1",
            output_text="1",
            hidden=False,
            group="0",
            max_score=0,
        )
        g1a = Test(
            problem_id=1,
            input_text="2",
            output_text="2",
            hidden=True,
            group="1",
            max_score=1,
        )
        g1b = Test(
            problem_id=1,
            input_text="3",
            output_text="3",
            hidden=True,
            group="1",
            max_score=1,
        )
        g2 = Test(
            problem_id=1,
            input_text="4",
            output_text="4",
            hidden=True,
            group="2",
            max_score=1,
        )
        self.assertEqual(problem_max_score([example, g1a, g1b]), 1)
        self.assertEqual(problem_max_score([example, g1a, g2]), 2)

    def test_hidden_result_hides_io(self) -> None:
        test = Test(
            id=7,
            problem_id=1,
            input_text="SEKRET",
            output_text="TAK",
            hidden=True,
            position=1,
            group="1",
            max_score=1,
        )
        result = SubmissionResult(
            submission_id=1,
            test_id=7,
            verdict="OK",
            score=1,
        )
        payload = public_result_payload(result, test)
        self.assertIsNone(payload["input"])
        self.assertIsNone(payload["output"])
        self.assertEqual(payload["verdict"], "OK")
        self.assertEqual(payload["group"], "1")

    def test_example_result_shows_io(self) -> None:
        test = Test(
            id=1,
            problem_id=1,
            input_text="1 2\n",
            output_text="3\n",
            hidden=False,
            position=0,
            group="0",
            max_score=0,
        )
        result = SubmissionResult(
            submission_id=1,
            test_id=1,
            verdict="OK",
            score=0,
        )
        payload = public_result_payload(result, test)
        self.assertEqual(payload["input"], "1 2\n")
        self.assertEqual(payload["output"], "3\n")


if __name__ == "__main__":
    unittest.main()
