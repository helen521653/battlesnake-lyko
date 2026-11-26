"""Оценка позиции: территория по Вороному с учётом освобождающихся клеток тела,
перевес по длине, доступ к еде, здоровье, ловушки."""
from __future__ import annotations


def evaluate(s, me, w):
    r = s.r
    n = r.n
    nbl = r.nbl
    hazard = r.hazard
    food = s.food
    bodies = s.bodies

    # free_at[p]: через сколько ходов клетка освободится (сегмент k змеи длины L — через L-k ходов).
    free_at = [0] * n
    owner = [-1] * n  # -1 никто, -2 спорная клетка, иначе номер змеи
    lens = [0] * len(bodies)
    frontier = []
    big = 10000 if r.constrictor else 0
    for i, b in enumerate(bodies):
        if b is None:
            continue
        L = len(b)
        lens[i] = L
        for k, p in enumerate(b):
            t = big or (L - k)
            if t > free_at[p]:
                free_at[p] = t
    for i, b in enumerate(bodies):
        if b is not None and owner[b[0]] == -1:
            owner[b[0]] = i
            frontier.append(b[0])

    area = [0.0] * len(bodies)
    hazard_cell = w["hazard_cell"]
    my_food_dist = -1
    food_owned = 0
    d = 0
    # Одновременный BFS по уровням от всех голов.
    while frontier:
        d += 1
        level = {}  # клетка -> владелец на этом уровне
        for p in frontier:
            o = owner[p]
            if o < 0:
                continue
            lo = lens[o]
            for q in nbl[p]:
                if owner[q] != -1 or free_at[q] > d:
                    continue
                prev = level.get(q)
                if prev is None:
                    level[q] = o
                elif prev >= 0 and prev != o:
                    lp = lens[prev]
                    if lo > lp:
                        level[q] = o
                    elif lo == lp:
                        level[q] = -2
        frontier = list(level)
        for q, o in level.items():
            owner[q] = o
            if o < 0:
                continue
            area[o] += hazard_cell if q in hazard else 1.0
            if o == me and q in food:
                food_owned += 1
                if my_food_dist < 0:
                    my_food_dist = d

    mine = bodies[me]
    my_len = len(mine)
    my_head = mine[0]
    my_area = area[me]
    my_health = s.health[me]

    score = 0.0
    opp_max_len = 0
    opp_max_area = 0.0
    opp_alive = 0
    for i, b in enumerate(bodies):
        if i == me or b is None:
            continue
        opp_alive += 1
        ol = len(b)
        if ol > opp_max_len:
            opp_max_len = ol
        if area[i] > opp_max_area:
            opp_max_area = area[i]
        if area[i] < ol:
            score += w["trap_opp"] * (ol - area[i])
        if ol >= my_len and r.dist(b[0], my_head) <= 2:
            score -= w["h2h"]

    score += w["area"] * (my_area - opp_max_area)
    score += w["area_self"] * min(my_area, 2 * my_len)
    if my_area < my_len:
        score -= w["trap"] * (my_len - my_area)
    score -= w["opp_alive"] * opp_alive

    cap = w["len_cap"]
    len_diff = (my_len - opp_max_len) if opp_alive else cap
    score += w["length"] * max(-cap, min(cap, len_diff))

    hungry = my_health < w["hunger_health"] or (opp_alive and len_diff < w["len_target"])
    fd = my_food_dist if my_food_dist >= 0 else r.w + r.h
    score -= (w["food_need"] if hungry else w["food_idle"]) * fd
    if my_health < fd:
        score -= w["starve"]
    score += w["food_control"] * food_owned
    score += w["health"] * my_health / 100.0
    return score
