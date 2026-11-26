"""Веса оценочной функции. Их подбирает hill-climbing в arena.py (режим tune)."""
from __future__ import annotations

import json
import math
import os

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights.json")

# Описание каждого параметра (порядок задаёт порядок в JSON).
DESCRIPTIONS = {
    "area": "за каждую клетку перевеса по территории (диаграмма Вороного)",
    "area_self": "за собственную территорию (учитывается до 2*длины)",
    "length": "за каждую единицу перевеса по длине",
    "len_cap": "выше этого перевеса длина больше не ценится",
    "len_target": "желаемый перевес по длине: пока его нет, змея голодна",
    "trap": "штраф за каждую недостающую клетку, если территория меньше длины",
    "trap_opp": "бонус, если соперник в ловушке",
    "food_need": "штраф за расстояние до еды, когда еда нужна",
    "food_idle": "штраф за расстояние до еды, когда еда не нужна",
    "food_control": "за каждую еду на своей территории",
    "health": "за здоровье (0..1)",
    "hunger_health": "ниже этого здоровья змея голодна",
    "hazard_cell": "ценность клетки опасной зоны в территории (0..1)",
    "starve": "штраф, если до ближайшей еды дальше, чем хватит здоровья",
    "opp_alive": "штраф за каждого живого соперника (мультиплеер)",
    "h2h": "штраф за голову рядом с головой не меньшего соперника",
}

FALLBACK = {
    "area": 1.0, "area_self": 0.5, "length": 10.0, "len_cap": 4.0, "len_target": 2.0,
    "trap": 40.0, "trap_opp": 20.0, "food_need": 3.0, "food_idle": 0.3, "food_control": 1.0,
    "health": 3.0, "hunger_health": 35.0, "hazard_cell": 0.3, "starve": 300.0,
    "opp_alive": 40.0, "h2h": 30.0,
}


def load(path=None):
    """Загружает веса; недостающие ключи берутся из FALLBACK."""
    w = dict(FALLBACK)
    path = path or DEFAULT_PATH
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            w.update(json.load(f))
    return w


def save(w, path=None):
    with open(path or DEFAULT_PATH, "w", encoding="utf-8") as f:
        json.dump({k: round(w[k], 4) for k in FALLBACK}, f, indent=2)
        f.write("\n")


def mutate(w, rng, k=2, sigma=0.3):
    """Копия весов с k случайно изменёнными параметрами (мультипликативный гауссов шум)."""
    c = dict(w)
    names = rng.sample(list(FALLBACK), k)
    for name in names:
        x = c[name]
        if x == 0:
            x = rng.random() * 0.5
        else:
            x *= math.exp(rng.gauss(0, sigma))
        if name == "hazard_cell":
            x = min(x, 1.0)
        c[name] = x
    return c, names
