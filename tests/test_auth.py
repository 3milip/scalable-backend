import unittest

from app.auth import hash_password, verify_password
from sprawdzarka.map_status import map_status


class AuthTests(unittest.TestCase):
    def test_password_roundtrip(self) -> None:
        stored = hash_password("sekret1")
        self.assertTrue(verify_password("sekret1", stored))
        self.assertFalse(verify_password("inne", stored))

    def test_map_status(self) -> None:
        self.assertEqual(map_status("?"), ("running", None))
        self.assertEqual(map_status("OK"), ("done", "OK"))
        self.assertEqual(map_status("WA"), ("done", "WA"))
        self.assertEqual(map_status("ERR"), ("failed", None))
        self.assertEqual(map_status("INI_ERR", 0), ("done", "WA"))
        self.assertEqual(map_status("INI_OK"), ("running", None))
        self.assertEqual(map_status("INI_OK", 3), ("done", "OK"))
        self.assertEqual(map_status("INI_OK", 1, 3), ("done", "WA"))
