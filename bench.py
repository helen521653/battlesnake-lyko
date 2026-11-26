"""Стенд для hill-climbing: оценивает текущую версию змейки (snake/) против чемпиона.

  python3 bench.py run --idea "что изменено"   # полная проверка + вердикт ACCEPT/REJECT
  python3 bench.py run --quick --idea "..."    # быстрая прикидка (вердикт не выносится)
  python3 bench.py promote --idea "..."        # сделать текущую версию новым чемпионом
  python3 bench.py timing                      # время ответа на одном ядре в боевых настройках

Протокол и правила — в HILLCLIMB.md. Стенд (bench.py, harness/, champions/) в ходе
экспериментов не изменяется.
"""
from __future__ import annotations

import argparse
import datetime
import importlib
import importlib.util
import json
import math
import multiprocessing as mp
import os
import random
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from harness.opponents import POOL  # noqa: E402
from harness.referee import Player, play_game  # noqa: E402

CHAMPS = os.path.join(ROOT, "champions")
LOG = os.path.join(ROOT, "experiments", "log.jsonl")
TIMING_LIMIT_MS = 450


# --- загрузка версий змейки -----------------------------------------------------------------
_loaded = {}


def load_snake_api(pkg_dir, alias):
    """Импортирует пакет snake из произвольной папки под уникальным именем и возвращает его api."""
    if alias in _loaded:
        return _loaded[alias]
    spec = importlib.util.spec_from_file_location(
        alias, os.path.join(pkg_dir, "__init__.py"), submodule_search_locations=[pkg_dir])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    api = importlib.import_module(alias + ".api")
    _loaded[alias] = api
    return api


def make_player(ref):
    kind, arg = ref
    if kind == "pool":
        return Player(arg, POOL[arg])
    alias = "snake_" + "".join(ch if ch.isalnum() else "_" for ch in arg)
    api = load_snake_api(arg, alias)
    return Player(arg, lambda req, api=api: api.move(req)[0])


def champion_dirs():
    if not os.path.isdir(CHAMPS):
        return []
    return sorted(d for d in os.listdir(CHAMPS) if d.startswith("v") and d[1:].isdigit())


def champion_meta(name):
    path = os.path.join(CHAMPS, name, "meta.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


# --- игры --------------------------------------------------------------------------------
def _job(args):
    refs, seed, ms, hard = args
    players = [make_player(r) for r in refs]
    return play_game(players, seed, timeout_ms=ms, hard_limit_ms=hard)


def series(cand_ref, opp_ref, pairs, ms, seed, pool):
    """pairs пар игр: каждая раздача играется дважды со сменой сторон."""
    hard = 2 * ms + 50  # грубые нарушения; точный лимит проверяет timing
    jobs, sides = [], []
    for k in range(pairs):
        s = seed * 1000003 + k
        jobs.append(([cand_ref, opp_ref], s, ms, hard))
        sides.append(0)
        jobs.append(([opp_ref, cand_ref], s, ms, hard))
        sides.append(1)
    results = pool.map(_job, jobs)
    w = l = d = 0
    timeouts = errors = 0
    max_ms = 0.0
    turns = 0
    for r, side in zip(results, sides):
        if r["winner"] is None:
            d += 1
        elif r["winner"] == side:
            w += 1
        else:
            l += 1
        st = r["stats"][side]
        timeouts += st["timeouts"]
        errors += st["errors"]
        max_ms = max(max_ms, st["max_ms"])
        turns += r["turns"]
    n = w + l + d
    return {"w": w, "l": l, "d": d, "score": round((w + d / 2) / n, 3) if n else 0.0,
            "los": round(los(w, l), 3), "timeouts": timeouts, "errors": errors,
            "max_ms": round(max_ms), "avg_turns": round(turns / max(1, n))}


def los(w, l):
    """Likelihood of superiority: вероятность, что кандидат сильнее (ничьи не учитываются)."""
    if w + l == 0:
        return 0.5
    return 0.5 * (1 + math.erf((w - l) / math.sqrt(2 * (w + l))))


# --- проверки-«ворота» -----------------------------------------------------------------------
def run_tests():
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-q", "tests"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or r.stdout).strip().splitlines()[-1:]


def run_timing_subprocess():
    env = {k: v for k, v in os.environ.items() if k not in ("LATENCY_MS", "MAX_MS")}
    r = subprocess.run([sys.executable, os.path.join(ROOT, "bench.py"), "timing", "--json"],
                       cwd=ROOT, capture_output=True, text=True, env=env)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"ok": False, "error": (r.stderr or r.stdout)[-500:]}


def cmd_timing(a):
    """Боевые настройки (timeout 500, LATENCY_MS по умолчанию), одно ядро."""
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {sorted(os.sched_getaffinity(0))[0]})
    cand = make_player(("dir", os.path.join(ROOT, "snake")))
    worst, moves = 0.0, 0
    for seed in (11, 12):
        r = play_game([cand, Player("survivor", POOL["survivor"])], seed, timeout_ms=500,
                      max_turns=60, hard_limit_ms=10 ** 9)
        worst = max(worst, r["stats"][0]["max_ms"])
        moves += r["stats"][0]["moves"]
    res = {"ok": worst < TIMING_LIMIT_MS, "max_ms": round(worst), "moves": moves,
           "limit_ms": TIMING_LIMIT_MS}
    print(json.dumps(res) if a.json else "max move time %(max_ms)s ms over %(moves)s moves "
          "(limit %(limit_ms)s) -> %(ok)s" % res)


# --- основной прогон -----------------------------------------------------------------------
def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip()


def cmd_run(a):
    t_start = time.time()
    champs = champion_dirs()
    if not champs:
        sys.exit("Нет чемпиона. Сначала: python3 bench.py promote --idea baseline")
    current = champs[-1]
    seed = a.seed if a.seed is not None else random.randrange(1 << 30)
    pairs = a.pairs if not a.quick else max(4, a.pairs // 4)
    pool_pairs = a.pool_pairs if not a.quick else 2

    report = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "idea": a.idea,
              "base_commit": git("rev-parse", "--short", "HEAD"), "champion": current,
              "seed": seed, "ms": a.ms, "quick": a.quick}

    ok_tests, tail = run_tests()
    report["tests"] = "ok" if ok_tests else "FAIL: " + " ".join(tail)
    print("tests:", report["tests"], flush=True)
    timing = run_timing_subprocess() if not a.quick else {"ok": True, "skipped": True}
    report["timing"] = timing
    print("timing:", timing, flush=True)

    # Бюджет для игр стенда: змейка получает timeout = ms и думает, что сетевой задержки нет.
    os.environ["LATENCY_MS"] = "0"
    os.environ["MAX_MS"] = str(a.ms)
    cand = ("dir", os.path.join(ROOT, "snake"))
    with mp.Pool(a.procs or os.cpu_count()) as pool:
        champ_ref = ("dir", os.path.join(CHAMPS, current, "snake"))
        report["vs_champion"] = series(cand, champ_ref, pairs, a.ms, seed, pool)
        print("vs %s:" % current, report["vs_champion"], flush=True)
        report["vs_older"] = {}
        for old in champs[-3:-1]:
            r = series(cand, ("dir", os.path.join(CHAMPS, old, "snake")), max(2, pairs // 4),
                       a.ms, seed + 1, pool)
            report["vs_older"][old] = r
            print("vs %s:" % old, r, flush=True)
        report["vs_pool"] = {}
        for name in POOL:
            r = series(cand, ("pool", name), pool_pairs, a.ms, seed + 2, pool)
            report["vs_pool"][name] = r
            print("vs %s:" % name, r, flush=True)

    pool_score = sum(r["score"] for r in report["vs_pool"].values()) / len(POOL)
    report["pool_score"] = round(pool_score, 3)
    champ_pool = champion_meta(current).get("pool_score")

    all_series = [report["vs_champion"], *report["vs_older"].values(), *report["vs_pool"].values()]
    reasons = []
    if not ok_tests:
        reasons.append("tests failed")
    if not timing.get("ok"):
        reasons.append("timing gate failed")
    if any(s["errors"] for s in all_series):
        reasons.append("candidate raised errors")
    if any(s["timeouts"] for s in all_series):
        reasons.append("candidate timed out")
    vc = report["vs_champion"]
    if not (vc["los"] >= a.los and vc["score"] > 0.5):
        reasons.append("not significantly better than %s (LOS %.2f < %.2f)" % (current, vc["los"], a.los))
    for old, r in report["vs_older"].items():
        if r["score"] < 0.45:
            reasons.append("regression vs %s (%.2f)" % (old, r["score"]))
    if champ_pool is not None and pool_score < champ_pool - 0.05:
        reasons.append("pool regression (%.2f < %.2f)" % (pool_score, champ_pool))

    if a.quick:
        verdict = "QUICK (no verdict)"
    else:
        verdict = "ACCEPT" if not reasons else "REJECT"
    report["verdict"] = verdict
    report["reasons"] = reasons
    report["seconds"] = round(time.time() - t_start)
    print("\nVERDICT:", verdict, *(["-"] + ["; ".join(reasons)] if reasons else []))
    print("pool score %.3f (champion %s)" % (pool_score, champ_pool))
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False) + "\n")


def cmd_promote(a):
    champs = champion_dirs()
    name = "v%03d" % (int(champs[-1][1:]) + 1 if champs else 1)
    dst = os.path.join(CHAMPS, name)
    shutil.copytree(os.path.join(ROOT, "snake"), os.path.join(dst, "snake"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    meta = {"name": name, "idea": a.idea, "time": datetime.datetime.now().isoformat(timespec="seconds"),
            "base_commit": git("rev-parse", "--short", "HEAD")}
    # Последний ACCEPT в журнале даёт эталонный pool_score для проверки регрессий.
    if os.path.exists(LOG):
        with open(LOG, encoding="utf-8") as f:
            rows = [json.loads(x) for x in f if x.strip()]
        acc = [r for r in rows if r.get("verdict") == "ACCEPT"]
        if acc:
            meta["pool_score"] = acc[-1]["pool_score"]
            meta["accepted_with"] = {k: acc[-1][k] for k in ("vs_champion", "seed")}
    if a.pool_score is not None:
        meta["pool_score"] = a.pool_score
    with open(os.path.join(dst, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("promoted ->", name)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--idea", required=True, help="краткое описание проверяемого изменения")
    r.add_argument("--pairs", type=int, default=40, help="пар игр против чемпиона (x2 игр)")
    r.add_argument("--pool-pairs", type=int, default=5, help="пар игр против каждого из пула")
    r.add_argument("--ms", type=int, default=40, help="бюджет на ход в играх стенда, мс")
    r.add_argument("--los", type=float, default=0.95, help="порог LOS для принятия")
    r.add_argument("--seed", type=int)
    r.add_argument("--procs", type=int)
    r.add_argument("--quick", action="store_true")
    r.set_defaults(fn=cmd_run)
    pr = sub.add_parser("promote")
    pr.add_argument("--idea", required=True)
    pr.add_argument("--pool-score", type=float)
    pr.set_defaults(fn=cmd_promote)
    t = sub.add_parser("timing")
    t.add_argument("--json", action="store_true")
    t.set_defaults(fn=cmd_timing)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
