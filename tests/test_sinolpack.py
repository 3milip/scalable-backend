import unittest
import zipfile
from io import BytesIO

from app.sinolpack import files_for_problem, short_name_for, zip_problem


class SinolpackTests(unittest.TestCase):
    def test_short_name(self) -> None:
        self.assertEqual(short_name_for("local-01"), "loca")
        self.assertEqual(short_name_for("local-02"), "locb")
        self.assertEqual(short_name_for("local-27"), "locaa")

    def test_zip_has_in_out_config_and_model(self) -> None:
        item = {
            "external_id": "local-01",
            "title": "Suma dwóch liczb",
            "statement": "Wczytaj a i b.",
            "time_limit_ms": 1000,
            "memory_limit_mb": 256,
            "solution": "print(sum(map(int, input().split())))\n",
            "tests": [
                {"input": "1 2\n", "output": "3\n", "hidden": False},
                {"input": "0 0\n", "output": "0\n", "hidden": True},
                {"input": "-5 10\n", "output": "5\n", "hidden": True},
            ],
        }
        names = set(files_for_problem(item))
        self.assertIn("loca/config.yml", names)
        self.assertIn("loca/in/loca0.in", names)
        self.assertIn("loca/out/loca0.out", names)
        self.assertIn("loca/in/loca1.in", names)
        self.assertIn("loca/in/loca2.in", names)
        self.assertNotIn("loca/prog/loca.py", names)
        self.assertIn("loca/attachments/wzorcowka.py", names)
        config = files_for_problem(item)["loca/config.yml"].decode()
        self.assertIn("time_limit: 1000", config)
        self.assertIn("memory_limit: 262144", config)
        self.assertIn("no_outgen: true", config)
        self.assertIn("  1: 1", config)
        raw = zip_problem(item)
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            names = archive.namelist()
            self.assertIn("loca/in/", names)
            self.assertIn("loca/out/", names)
            self.assertTrue(any(info.is_dir() for info in archive.infolist()))
            self.assertTrue(any(name.startswith("loca/in/") and name.endswith(".in") for name in names))
