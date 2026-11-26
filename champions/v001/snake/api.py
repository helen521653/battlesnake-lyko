"""Преобразование запроса Battlesnake API в State и выбор хода."""
from __future__ import annotations

import os
import time

from .rules import DIR_NAMES, Rules, State
from .search import choose_move
from . import weights as weights_mod

LATENCY_MS = int(os.environ.get("LATENCY_MS", "150"))  # запас на сеть и накладные расходы
MAX_MS = int(os.environ.get("MAX_MS", "380"))          # верхняя граница времени на поиск
WEIGHTS = weights_mod.load(os.environ.get("WEIGHTS"))


def parse(req):
    """Возвращает (state, индекс нашей змеи, ids змей)."""
    game, board = req["game"], req["board"]
    w, h = board["width"], board["height"]
    ruleset = game.get("ruleset", {}) or {}
    name = ruleset.get("name", "standard")
    settings = ruleset.get("settings", {}) or {}
    hazard = {}
    for c in board.get("hazards", []) or []:
        p = c["y"] * w + c["x"]
        hazard[p] = hazard.get(p, 0) + 1
    rules = Rules(
        w, h,
        wrapped=(name == "wrapped"),
        constrictor=(name == "constrictor"),
        hazard_damage=settings.get("hazardDamagePerTurn", 14 if hazard else 0) if hazard else 0,
        hazard=hazard,
    )
    food = frozenset(c["y"] * w + c["x"] for c in board.get("food", []))
    bodies, health, ids = [], [], []
    for sn in board["snakes"]:
        bodies.append(tuple(c["y"] * w + c["x"] for c in sn["body"]))
        health.append(sn["health"])
        ids.append(sn["id"])
    me = ids.index(req["you"]["id"])
    return State(rules, food, bodies, health, req.get("turn", 0)), me, ids


def budget_seconds(req):
    timeout = (req.get("game", {}) or {}).get("timeout", 500) or 500
    ms = max(30, min(MAX_MS, timeout - LATENCY_MS))
    return ms / 1000.0


def move(req, weights=None):
    t0 = time.perf_counter()
    state, me, _ = parse(req)
    d, val, depth = choose_move(state, me, weights or WEIGHTS, budget_seconds(req) - (time.perf_counter() - t0))
    return {"move": DIR_NAMES[d], "shout": ""}, {"depth": depth, "score": val}
