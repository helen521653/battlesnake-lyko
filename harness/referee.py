"""Независимый рефери Battlesnake (правила standard: дуэль и мультиплеер на 11x11).

ВАЖНО: этот файл — часть стенда для hill-climbing. Он намеренно НЕ использует код из snake/,
чтобы изменения змейки не могли повлиять на подсчёт результатов. Менять его в ходе
экспериментов запрещено (см. HILLCLIMB.md).

Порядок фаз хода повторяет официальный движок:
движение -> здоровье -1 -> еда -> выбывание (голод/стена, затем столкновения) -> появление еды.
Игрок, не уложившийся во время или упавший с ошибкой, повторяет свой предыдущий ход
(так же поступает настоящий движок при таймауте).
"""
from __future__ import annotations

import random
import time

DELTA = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}
MIN_FOOD = 1
FOOD_SPAWN_CHANCE = 15


class Player:
    """Обёртка над функцией move(req) -> {"move": ...} со счётчиками таймаутов и ошибок."""

    def __init__(self, name, move_fn):
        self.name = name
        self.move_fn = move_fn


class Game:
    def __init__(self, n_snakes, seed, size=11, timeout_ms=500):
        self.rng = random.Random(seed)
        self.w = self.h = size
        self.timeout_ms = timeout_ms
        self.turn = 0
        self.snakes = []
        corners = [(1, 1), (1, size - 2), (size - 2, 1), (size - 2, size - 2)]
        cardinal = [(1, size // 2), (size // 2, 1), (size // 2, size - 2), (size - 2, size // 2)]
        if n_snakes <= 4:
            starts = self.rng.choice([corners, cardinal])[:]
        else:
            starts = corners + cardinal
        self.rng.shuffle(starts)
        c = size // 2
        self.food = {(c, c)}
        for i in range(n_snakes):
            x, y = starts[i]
            self.snakes.append({
                "id": "s%d" % i, "health": 100, "body": [(x, y)] * 3, "alive": True,
                "last": "up", "death": None,
            })
            diag = [(x + dx, y + dy) for dx in (-1, 1) for dy in (-1, 1)]
            diag = [p for p in diag if abs(p[0] - c) + abs(p[1] - c) < abs(x - c) + abs(y - c)]
            diag = [p for p in diag if p not in self.food]
            if diag:
                self.food.add(self.rng.choice(diag))

    # --- запрос в формате Battlesnake API ------------------------------------------------
    def request(self, i):
        def snake_json(s):
            body = [{"x": x, "y": y} for x, y in s["body"]]
            return {"id": s["id"], "name": s["id"], "health": s["health"], "body": body,
                    "head": body[0], "length": len(body), "latency": "0", "shout": ""}

        alive = [snake_json(s) for s in self.snakes if s["alive"]]
        you = snake_json(self.snakes[i])
        return {
            "game": {"id": "bench", "ruleset": {"name": "standard", "version": "bench",
                                                "settings": {"foodSpawnChance": FOOD_SPAWN_CHANCE,
                                                             "minimumFood": MIN_FOOD,
                                                             "hazardDamagePerTurn": 0}},
                     "map": "standard", "timeout": self.timeout_ms, "source": "bench"},
            "turn": self.turn,
            "board": {"height": self.h, "width": self.w,
                      "food": [{"x": x, "y": y} for x, y in sorted(self.food)],
                      "hazards": [], "snakes": alive},
            "you": you,
        }

    # --- один ход ------------------------------------------------------------------------
    def apply(self, moves):
        live = [s for s in self.snakes if s["alive"]]
        for s, m in zip(self.snakes, moves):
            if not s["alive"]:
                continue
            dx, dy = DELTA[m]
            hx, hy = s["body"][0]
            s["body"] = [(hx + dx, hy + dy)] + s["body"][:-1]
            s["health"] -= 1
        eaten = set()
        for s in live:
            head = s["body"][0]
            if head in self.food:
                s["health"] = 100
                s["body"].append(s["body"][-1])
                eaten.add(head)
        self.food -= eaten

        # Выбывание: сначала голод и выход за поле.
        for s in live:
            x, y = s["body"][0]
            if s["health"] <= 0:
                s["death"] = "starvation"
            elif not (0 <= x < self.w and 0 <= y < self.h):
                s["death"] = "wall"
        survivors = [s for s in live if s["death"] is None]
        # Затем столкновения среди переживших первый этап.
        for s in survivors:
            head = s["body"][0]
            for o in survivors:
                if head in o["body"][1:]:
                    s["death"] = "self" if o is s else "body"
                    break
            else:
                for o in survivors:
                    if o is not s and o["body"][0] == head and len(o["body"]) >= len(s["body"]):
                        s["death"] = "head-to-head"
                        break
        for s in live:
            if s["death"] is not None:
                s["alive"] = False
        self.turn += 1
        self.spawn_food()

    def spawn_food(self):
        need = 0
        if len(self.food) < MIN_FOOD:
            need = MIN_FOOD - len(self.food)
        elif self.rng.randrange(100) < FOOD_SPAWN_CHANCE:
            need = 1
        if not need:
            return
        occupied = set(self.food)
        for s in self.snakes:
            if s["alive"]:
                occupied.update(s["body"])
        free = [(x, y) for x in range(self.w) for y in range(self.h) if (x, y) not in occupied]
        for p in self.rng.sample(free, min(need, len(free))):
            self.food.add(p)

    def alive_ids(self):
        return [i for i, s in enumerate(self.snakes) if s["alive"]]


def play_game(players, seed, timeout_ms, max_turns=600, hard_limit_ms=None):
    """Играет одну игру. Возвращает dict: winner (индекс или None), turns, статистику по игрокам."""
    g = Game(len(players), seed, timeout_ms=timeout_ms)
    hard = hard_limit_ms if hard_limit_ms is not None else timeout_ms
    stats = [{"timeouts": 0, "errors": 0, "max_ms": 0.0, "moves": 0} for _ in players]
    while g.turn < max_turns:
        alive = g.alive_ids()
        if len(alive) <= 1:
            break
        moves = [None] * len(players)
        for i in alive:
            req = g.request(i)
            t0 = time.perf_counter()
            try:
                m = players[i].move_fn(req)["move"]
                if m not in DELTA:
                    raise ValueError("bad move %r" % (m,))
            except Exception:
                stats[i]["errors"] += 1
                m = g.snakes[i]["last"]
            ms = (time.perf_counter() - t0) * 1000
            st = stats[i]
            st["moves"] += 1
            st["max_ms"] = max(st["max_ms"], ms)
            if ms > hard:
                st["timeouts"] += 1
                m = g.snakes[i]["last"]
            g.snakes[i]["last"] = m
            moves[i] = m
        g.apply(moves)
    alive = g.alive_ids()
    winner = alive[0] if len(alive) == 1 else None
    deaths = [s["death"] for s in g.snakes]
    return {"winner": winner, "turns": g.turn, "stats": stats, "deaths": deaths}
