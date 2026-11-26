"""Пул эталонных соперников для стенда. Написаны независимо от snake/ и намеренно разных стилей.
Их задача — регрессионная проверка, а не главный сигнал: главный сигнал — победы над чемпионом.

  survivor — максимизирует доступное пространство (flood fill), ест только при голоде;
  glutton  — жадно идёт к ближайшей еде, избегает лобовых с не меньшими змеями;
  bully    — растёт, а будучи длиннее, преследует голову соперника.
"""
from __future__ import annotations

from collections import deque

DELTA = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}


def _parse(req):
    b = req["board"]
    w, h = b["width"], b["height"]
    you = req["you"]
    me = [(c["x"], c["y"]) for c in you["body"]]
    snakes = [[(c["x"], c["y"]) for c in s["body"]] for s in b["snakes"]]
    others = [s for s, raw in zip(snakes, b["snakes"]) if raw["id"] != you["id"]]
    food = {(c["x"], c["y"]) for c in b["food"]}
    blocked = set()
    for s in snakes:
        blocked.update(s[:-1])  # хвосты уходят
    return w, h, me, others, food, blocked, you["health"]


def _inside(p, w, h):
    return 0 <= p[0] < w and 0 <= p[1] < h


def _step(p, m):
    return (p[0] + DELTA[m][0], p[1] + DELTA[m][1])


def _flood(start, blocked, w, h, limit=200):
    seen = {start}
    q = deque([start])
    while q and len(seen) < limit:
        p = q.popleft()
        for m in DELTA:
            n = _step(p, m)
            if n not in seen and n not in blocked and _inside(n, w, h):
                seen.add(n)
                q.append(n)
    return len(seen)


def _bfs_dist(start, targets, blocked, w, h):
    if not targets:
        return None
    seen = {start}
    q = deque([(start, 0)])
    while q:
        p, d = q.popleft()
        if p in targets:
            return d
        for m in DELTA:
            n = _step(p, m)
            if n not in seen and n not in blocked and _inside(n, w, h):
                seen.add(n)
                q.append((n, d + 1))
    return None


def _candidates(req):
    """Безопасные ходы с оценкой пространства и опасности лобового столкновения."""
    w, h, me, others, food, blocked, health = _parse(req)
    danger = set()
    prey = set()
    for o in others:
        for m in DELTA:
            n = _step(o[0], m)
            (danger if len(o) >= len(me) else prey).add(n)
    out = []
    for m in DELTA:
        n = _step(me[0], m)
        if not _inside(n, w, h) or n in blocked:
            continue
        space = _flood(n, blocked | {me[0]}, w, h, limit=len(me) * 2 + 10)
        out.append((m, n, space, n in danger, n in prey))
    return out, (w, h, me, others, food, blocked, health)


def _fallback(cands):
    if not cands:
        return "up"
    return max(cands, key=lambda c: (not c[3], c[2]))[0]


def survivor(req):
    cands, (w, h, me, others, food, blocked, health) = _candidates(req)
    if not cands:
        return {"move": "up"}
    best_space = max(c[2] for c in cands if not c[3]) if any(not c[3] for c in cands) else 0
    ok = [c for c in cands if not c[3] and c[2] >= best_space]
    if not ok:
        return {"move": _fallback(cands)}
    if health < 40:
        ok.sort(key=lambda c: _bfs_dist(c[1], food, blocked, w, h) or 99)
    return {"move": ok[0][0]}


def glutton(req):
    cands, (w, h, me, others, food, blocked, health) = _candidates(req)
    ok = [c for c in cands if not c[3] and c[2] >= len(me)]
    if not ok:
        return {"move": _fallback(cands)}
    ok.sort(key=lambda c: (_bfs_dist(c[1], food, blocked, w, h) or 99, -c[2]))
    return {"move": ok[0][0]}


def bully(req):
    cands, (w, h, me, others, food, blocked, health) = _candidates(req)
    ok = [c for c in cands if not c[3] and c[2] >= len(me)]
    if not ok:
        return {"move": _fallback(cands)}
    longest_other = max((len(o) for o in others), default=0)
    if others and len(me) > longest_other + 1 and health > 30:
        target = min(others, key=lambda o: abs(o[0][0] - me[0][0]) + abs(o[0][1] - me[0][1]))
        th = target[0]
        ok.sort(key=lambda c: (not c[4], abs(c[1][0] - th[0]) + abs(c[1][1] - th[1]), -c[2]))
    else:
        ok.sort(key=lambda c: (_bfs_dist(c[1], food, blocked, w, h) or 99, -c[2]))
    return {"move": ok[0][0]}


POOL = {"survivor": survivor, "glutton": glutton, "bully": bully}
