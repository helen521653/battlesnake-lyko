"""Поиск хода: параноидальный минимакс с альфа-бета отсечением и итеративным углублением.

Ходы одновременные, поэтому один «ход игры» — это два полуузла: max (выбираем свой ход)
и min (соперники выбирают ответ, зная наш ход — пессимистичное, но надёжное допущение).
В дуэли перебирается единственный соперник. В мультиплеере перебираются до MAX_SEARCHED_OPPS
ближайших соперников, остальные ходят по простой жадной политике.
"""
from __future__ import annotations

import itertools
import time

from .evaluate import evaluate

WIN = 1_000_000.0
PLY = 1_000.0          # смерть позже лучше смерти раньше, победа раньше лучше победы позже
DRAW = -WIN / 2        # взаимное уничтожение в дуэли — не победа
MAX_SEARCHED_OPPS = 2
SEARCH_RADIUS = 7      # соперники дальше этого (по манхэттену) не перебираются


class Timeout(Exception):
    pass


class Searcher:
    def __init__(self, root, me, weights, budget_s, max_depth=64):
        self.root = root
        self.me = me
        self.w = weights
        self.deadline = time.perf_counter() + budget_s
        self.max_depth = max_depth
        self.nodes = 0
        self.root_opps = sum(1 for i, b in enumerate(root.bodies) if b is not None and i != me)
        head = root.bodies[me][0]
        opps = [i for i, b in enumerate(root.bodies) if b is not None and i != me]
        opps.sort(key=lambda i: root.r.dist(root.bodies[i][0], head))
        self.searched = [i for i in opps if root.r.dist(root.bodies[i][0], head) <= SEARCH_RADIUS][
            :MAX_SEARCHED_OPPS
        ]
        if not self.searched and opps:
            self.searched = opps[:1]

    # --- терминальные позиции ---------------------------------------------------------
    def terminal(self, s, ply):
        bodies = s.bodies
        opps_alive = sum(1 for i, b in enumerate(bodies) if b is not None and i != self.me)
        if bodies[self.me] is None:
            if opps_alive == 0 and self.root_opps > 0:
                return DRAW + ply * PLY
            return -WIN + ply * PLY
        if self.root_opps > 0 and opps_alive == 0:
            return WIN - ply * PLY
        return None

    def check_time(self):
        self.nodes += 1
        if self.nodes & 63 == 0 and time.perf_counter() > self.deadline:
            raise Timeout

    # --- жадная политика для неперебираемых соперников ---------------------------------
    @staticmethod
    def greedy_move(s, i, blocked):
        moves = s.safe_moves(i, blocked)
        if len(moves) == 1:
            return moves[0]
        nbd, nbl = s.r.nbd, s.r.nbl
        best, best_v = moves[0], -1
        for d in moves:
            q = nbd[s.bodies[i][0]][d]
            v = sum(1 for z in nbl[q] if z not in blocked) * 2 + (q in s.food)
            if v > best_v:
                best, best_v = d, v
        return best

    # --- сам поиск ----------------------------------------------------------------------
    def max_node(self, s, depth, ply, alpha, beta):
        self.check_time()
        t = self.terminal(s, ply)
        if t is not None:
            return t
        if depth == 0:
            return evaluate(s, self.me, self.w)
        blocked = s.blocked_cells()
        best = -float("inf")
        for m in s.safe_moves(self.me, blocked):
            v = self.min_node(s, blocked, m, depth, ply, alpha, beta)
            if v > best:
                best = v
                if v > alpha:
                    alpha = v
                    if alpha >= beta:
                        break
        return best

    def min_node(self, s, blocked, my_move, depth, ply, alpha, beta):
        n = len(s.bodies)
        base = [0] * n
        base[self.me] = my_move
        searched = [i for i in self.searched if s.bodies[i] is not None]
        for i in range(n):
            if i != self.me and s.bodies[i] is not None and i not in searched:
                base[i] = self.greedy_move(s, i, blocked)
        options = [s.safe_moves(i, blocked) for i in searched]
        best = float("inf")
        for combo in itertools.product(*options):
            moves = base[:]
            for i, d in zip(searched, combo):
                moves[i] = d
            child = s.clone()
            child.step(moves)
            v = self.max_node(child, depth - 1, ply + 1, alpha, beta)
            if v < best:
                best = v
                if v < beta:
                    beta = v
                    if alpha >= beta:
                        break
        return best

    def run(self):
        """Итеративное углубление. Возвращает (ход, оценка, достигнутая глубина)."""
        s = self.root
        blocked = s.blocked_cells()
        moves = s.safe_moves(self.me, blocked)
        if len(moves) == 1:
            return moves[0], 0.0, 0
        order = list(moves)
        best_move, best_val, done_depth = order[0], -float("inf"), 0
        for depth in range(1, self.max_depth + 1):
            scores = {}
            alpha = -float("inf")
            try:
                for m in order:
                    v = self.min_node(s, blocked, m, depth, 0, alpha, float("inf"))
                    scores[m] = v
                    if v > alpha:
                        alpha = v
            except Timeout:
                # Полностью просчитанные ходы этой итерации корректны (первым идёт прошлый лучший).
                if scores and order[0] in scores:
                    m = max(scores, key=scores.get)
                    if scores[m] >= scores[order[0]]:
                        best_move, best_val = m, scores[m]
                break
            order.sort(key=lambda m: -scores[m])
            best_move, best_val, done_depth = order[0], scores[order[0]], depth
            # Исход определён — глубже искать незачем.
            if abs(best_val) > WIN / 4 and all(abs(v) > WIN / 4 for v in scores.values()):
                break
            if time.perf_counter() > self.deadline:
                break
        return best_move, best_val, done_depth


def choose_move(state, me, weights, budget_s, max_depth=64):
    return Searcher(state, me, weights, budget_s, max_depth).run()
