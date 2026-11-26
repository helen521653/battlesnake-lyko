"""Сквозной тест HTTP-сервера: поднимаем его в потоке на свободном порту."""
import json
import os
import sys
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import Handler  # noqa: E402
from tests.test_rules import request  # noqa: E402


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.url = "http://127.0.0.1:%d" % cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def post(self, path, obj):
        req = urllib.request.Request(self.url + path, data=json.dumps(obj).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as r:
            return json.loads(r.read())

    def test_info(self):
        with urllib.request.urlopen(self.url + "/", timeout=2) as r:
            info = json.loads(r.read())
        self.assertEqual(info["apiversion"], "1")

    def test_game_flow(self):
        req = request(you=[(1, 1), (1, 0), (0, 0)], opp=[(9, 9), (9, 10), (10, 10)], food=[(5, 5)])
        self.assertEqual(self.post("/start", req), {})
        t = time.perf_counter()
        resp = self.post("/move", req)
        self.assertLess(time.perf_counter() - t, 0.5)
        self.assertIn(resp["move"], ("up", "right"))
        self.assertEqual(self.post("/end", req), {})


if __name__ == "__main__":
    unittest.main()
