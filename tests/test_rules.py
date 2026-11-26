"""Тесты правил и поиска:  python3 -m unittest discover tests"""
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from snake.api import move, parse  # noqa: E402
from snake.rules import DOWN, LEFT, RIGHT, UP, Rules, State  # noqa: E402
from snake import weights  # noqa: E402

W = 11


def P(x, y):
    return y * W + x


def make(bodies, food=(), health=None):
    r = Rules(W, W)
    return State(r, frozenset(food), [tuple(P(*c) for c in b) for b in bodies],
                 health or [100] * len(bodies))


class RulesTest(unittest.TestCase):
    def test_move_and_eat(self):
        s = make([[(5, 5), (5, 4), (5, 3)]], food=[P(5, 6)])
        s.step([UP])
        self.assertEqual(s.bodies[0], (P(5, 6), P(5, 5), P(5, 4), P(5, 4)))
        self.assertEqual(s.health[0], 100)
        self.assertFalse(s.food)

    def test_wall(self):
        s = make([[(0, 5), (1, 5), (2, 5)]])
        s.step([LEFT])
        self.assertIsNone(s.bodies[0])

    def test_head_to_head_longer_wins(self):
        s = make([[(4, 5), (3, 5), (2, 5), (1, 5)], [(6, 5), (7, 5), (8, 5)]])
        s.step([RIGHT, LEFT])
        self.assertIsNotNone(s.bodies[0])
        self.assertIsNone(s.bodies[1])

    def test_head_to_head_equal_both_die(self):
        s = make([[(4, 5), (3, 5), (2, 5)], [(6, 5), (7, 5), (8, 5)]])
        s.step([RIGHT, LEFT])
        self.assertEqual(s.alive_count(), 0)

    def test_chase_tail_is_safe(self):
        s = make([[(5, 5), (5, 6), (6, 6), (6, 5)]])
        s.step([RIGHT])
        self.assertIsNotNone(s.bodies[0])

    def test_starvation(self):
        s = make([[(5, 5), (5, 4), (5, 3)]], health=[1])
        s.step([UP])
        self.assertIsNone(s.bodies[0])


def request(you, opp, food, timeout=500):
    def sn(i, body):
        return {"id": i, "name": i, "health": 90, "length": len(body),
                "body": [{"x": x, "y": y} for x, y in body], "head": {"x": body[0][0], "y": body[0][1]}}
    me = sn("me", you)
    return {
        "game": {"id": "g", "ruleset": {"name": "standard", "settings": {}}, "timeout": timeout},
        "turn": 10,
        "board": {"width": W, "height": W, "food": [{"x": x, "y": y} for x, y in food],
                  "hazards": [], "snakes": [me, sn("opp", opp)]},
        "you": me,
    }


class SearchTest(unittest.TestCase):
    def test_avoids_dead_end(self):
        # Вверх — тупик из одной клетки у стены, вниз — открытое поле.
        req = request(you=[(0, 9), (1, 9), (1, 10), (2, 10)], opp=[(8, 2), (8, 1), (8, 0)], food=[])
        resp, _ = move(req, weights.load())
        self.assertIn(resp["move"], ("down",))

    def test_avoids_losing_head_to_head(self):
        # Соперник длиннее и может войти в клетку (5,6); надо уйти в сторону.
        req = request(you=[(5, 5), (5, 4), (5, 3)], opp=[(5, 7), (5, 8), (5, 9), (5, 10)], food=[(5, 6)])
        resp, _ = move(req, weights.load())
        self.assertNotEqual(resp["move"], "up")

    def test_kills_shorter_head_to_head(self):
        # Мы длиннее; соперник зажат так, что может пойти только в (5,6).
        req = request(you=[(5, 5), (5, 4), (5, 3), (5, 2), (5, 1)],
                      opp=[(5, 7), (4, 7), (4, 8), (5, 8), (6, 8), (6, 7)], food=[])
        req["board"]["snakes"][1]["body"] = [{"x": 5, "y": 7}, {"x": 4, "y": 7}, {"x": 4, "y": 6}]
        resp, _ = move(req, weights.load())
        self.assertIn(resp["move"], ("up", "left", "right"))

    def test_time_limit(self):
        req = request(you=[(2, 2), (2, 1), (2, 0)], opp=[(8, 8), (8, 9), (8, 10)], food=[(5, 5), (0, 10)])
        t = time.perf_counter()
        move(req, weights.load())
        self.assertLess(time.perf_counter() - t, 0.45)

    def test_parse_roundtrip(self):
        s, me, ids = parse(request(you=[(1, 1), (1, 0), (0, 0)], opp=[(9, 9), (9, 10)], food=[(3, 3)]))
        self.assertEqual(me, 0)
        self.assertEqual(s.bodies[0][0], P(1, 1))
        self.assertIn(P(3, 3), s.food)
        json.dumps({"ok": True})


if __name__ == "__main__":
    unittest.main()
