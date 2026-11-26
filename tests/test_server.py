"""Сквозной тест HTTP-обработчиков (Flask test client). Пропускается, если Flask не установлен."""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_rules import request  # noqa: E402

try:
    import flask  # noqa: F401
    HAVE_FLASK = True
except ImportError:
    HAVE_FLASK = False


@unittest.skipUnless(HAVE_FLASK, "Flask не установлен: pip install -r requirements.txt")
class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from main import HANDLERS
        from server import create_app
        cls.client = create_app(HANDLERS).test_client()

    def test_info(self):
        info = self.client.get("/").get_json()
        self.assertEqual(info["apiversion"], "1")

    def test_game_flow(self):
        req = request(you=[(1, 1), (1, 0), (0, 0)], opp=[(9, 9), (9, 10), (10, 10)], food=[(5, 5)])
        self.assertEqual(self.client.post("/start", json=req).status_code, 200)
        t = time.perf_counter()
        resp = self.client.post("/move", json=req).get_json()
        self.assertLess(time.perf_counter() - t, 0.5)
        self.assertIn(resp["move"], ("up", "right"))
        self.assertEqual(self.client.post("/end", json=req).status_code, 200)


if __name__ == "__main__":
    unittest.main()
