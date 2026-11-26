"""HTTP-сервер змейки по протоколу Battlesnake API v1. Только стандартная библиотека.

Запуск:  python3 server.py            (порт из $PORT, по умолчанию 8000)
"""
from __future__ import annotations

import json
import logging
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from snake.api import move

INFO = {
    "apiversion": "1",
    "author": os.environ.get("BS_AUTHOR", ""),
    "color": os.environ.get("BS_COLOR", "#7b2ff7"),
    "head": os.environ.get("BS_HEAD", "evil"),
    "tail": os.environ.get("BS_TAIL", "bolt"),
    "version": "1.0.0",
}

log = logging.getLogger("snake")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(INFO)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._send({"error": "bad json"}, 400)
        path = self.path.rstrip("/")
        if path == "/move":
            t0 = time.perf_counter()
            try:
                resp, info = move(req)
            except Exception:  # никогда не падаем — лучше любой ход, чем таймаут
                log.exception("move failed")
                resp, info = {"move": "up"}, {}
            log.info(
                "game=%s turn=%s move=%s depth=%s score=%.1f %.0fms",
                req.get("game", {}).get("id", "?")[:8], req.get("turn"), resp["move"],
                info.get("depth"), info.get("score", 0.0), (time.perf_counter() - t0) * 1000,
            )
            return self._send(resp)
        if path == "/end":
            you = req.get("you", {}).get("id")
            alive = any(s.get("id") == you for s in req.get("board", {}).get("snakes", []))
            log.info("game=%s END turn=%s %s", req.get("game", {}).get("id", "?")[:8], req.get("turn"),
                     "alive" if alive else "dead")
        return self._send({})

    def log_message(self, *args):  # подавить стандартный access-log
        pass


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    port = int(os.environ.get("PORT", "8000"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    log.info("Battlesnake listening on :%d", port)
    srv.serve_forever()


if __name__ == "__main__":
    main()
