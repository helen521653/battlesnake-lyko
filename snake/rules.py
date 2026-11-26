"""Симулятор правил Battlesnake (standard / duels / royale / wrapped / constrictor).

Клетка кодируется одним числом p = y * W + x. Направления: 0 up, 1 down, 2 left, 3 right
(в Battlesnake ось y направлена вверх).

Тела змей хранятся кортежами и никогда не изменяются на месте, а еда хранится как frozenset.
Поэтому копия состояния для узла поиска дешёвая: копируются только два списка.
"""
from __future__ import annotations

UP, DOWN, LEFT, RIGHT = 0, 1, 2, 3
DIR_NAMES = ("up", "down", "left", "right")


class Rules:
    """Параметры игры, общие для всех узлов поиска в пределах одного хода."""

    __slots__ = ("w", "h", "n", "wrapped", "constrictor", "hazard_damage", "hazard", "nbd", "nbl")

    def __init__(self, w, h, wrapped=False, constrictor=False, hazard_damage=0, hazard=None):
        self.w, self.h, self.n = w, h, w * h
        self.wrapped = wrapped
        self.constrictor = constrictor
        self.hazard_damage = hazard_damage
        self.hazard = hazard or {}  # клетка -> число слоёв опасной зоны
        # nbd[p][d] — сосед в направлении d или -1; nbl[p] — список существующих соседей.
        self.nbd = []
        self.nbl = []
        for p in range(self.n):
            x, y = p % w, p // w
            row = []
            for dx, dy in ((0, 1), (0, -1), (-1, 0), (1, 0)):
                nx, ny = x + dx, y + dy
                if wrapped:
                    nx %= w
                    ny %= h
                if 0 <= nx < w and 0 <= ny < h:
                    row.append(ny * w + nx)
                else:
                    row.append(-1)
            self.nbd.append(tuple(row))
            self.nbl.append(tuple(q for q in row if q >= 0))

    def dist(self, a, b):
        ax, ay, bx, by = a % self.w, a // self.w, b % self.w, b // self.w
        dx, dy = abs(ax - bx), abs(ay - by)
        if self.wrapped:
            dx, dy = min(dx, self.w - dx), min(dy, self.h - dy)
        return dx + dy


class State:
    """Позиция. bodies[i] — кортеж клеток (голова первая) или None, если змея выбыла."""

    __slots__ = ("r", "food", "bodies", "health", "turn")

    def __init__(self, r, food, bodies, health, turn=0):
        self.r = r
        self.food = food  # frozenset
        self.bodies = bodies
        self.health = health
        self.turn = turn

    def clone(self):
        return State(self.r, self.food, self.bodies[:], self.health[:], self.turn)

    def alive(self, i):
        return self.bodies[i] is not None

    def alive_count(self):
        return sum(1 for b in self.bodies if b is not None)

    def step(self, moves):
        """Одновременный ход всех змей: движение, здоровье, опасные зоны, еда, выбывание."""
        r = self.r
        nbd = r.nbd
        bodies, health, food = self.bodies, self.health, self.food
        hazard, dmg, constrictor = r.hazard, r.hazard_damage, r.constrictor
        n = len(bodies)
        out = [False] * n
        eaten = None

        for i in range(n):
            b = bodies[i]
            if b is None:
                continue
            np_ = nbd[b[0]][moves[i]]
            if np_ < 0:
                out[i] = True
                continue
            b = (np_,) + b[:-1]
            health[i] -= 1
            on_food = np_ in food
            if dmg and not on_food and np_ in hazard:
                health[i] -= dmg * hazard[np_]
            if on_food or constrictor:
                health[i] = 100
                b = b + (b[-1],)
                if on_food:
                    if eaten is None:
                        eaten = set()
                    eaten.add(np_)
            bodies[i] = b

        if eaten:
            self.food = food - eaten

        # Этап 1: выход за поле и голод.
        survivors = [i for i in range(n) if bodies[i] is not None and not out[i] and health[i] > 0]
        # Этап 2: столкновения — только среди переживших этап 1.
        body_cells = set()
        for i in survivors:
            body_cells.update(bodies[i][1:])
        dead = []
        for i in survivors:
            b = bodies[i]
            h = b[0]
            if h in body_cells:
                dead.append(i)
                continue
            li = len(b)
            for j in survivors:
                if j != i and bodies[j][0] == h and len(bodies[j]) >= li:
                    dead.append(i)
                    break
        alive_set = set(survivors) - set(dead)
        for i in range(n):
            if i not in alive_set:
                bodies[i] = None
        self.turn += 1

    def blocked_cells(self):
        """Клетки, занятые телами, которые не освободятся к следующему ходу."""
        blocked = set()
        keep_tail = self.r.constrictor
        for b in self.bodies:
            if b is not None:
                blocked.update(b if keep_tail else b[:-1])
        return blocked

    def safe_moves(self, i, blocked):
        """Ходы змеи i, не ведущие сразу в стену или тело. Если таких нет — один «смертельный» ход."""
        row = self.r.nbd[self.bodies[i][0]]
        moves = [d for d in range(4) if row[d] >= 0 and row[d] not in blocked]
        if moves:
            return moves
        for d in range(4):
            if row[d] >= 0:
                return [d]
        return [UP]
