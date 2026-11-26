# Battlesnake: точка входа (структура официального стартового шаблона).
#
# Логика змейки находится в пакете snake/:
#   snake/rules.py    — симулятор правил
#   snake/search.py   — параноидальный альфа-бета поиск с итеративным углублением
#   snake/evaluate.py — оценка позиции (территория по Вороному, длина, еда, ловушки)
# Улучшается методом hill-climbing, см. HILLCLIMB.md.
#
# Запуск:  python main.py   (порт из $PORT, по умолчанию 8000)

import os
import time
import typing

from snake.api import move as search_move


# info is called when you create your Battlesnake on play.battlesnake.com
# and controls your Battlesnake's appearance
def info() -> typing.Dict:
    print("INFO")

    return {
        "apiversion": "1",
        "author": os.environ.get("BS_AUTHOR", ""),  # ваш логин на play.battlesnake.com
        "color": os.environ.get("BS_COLOR", "#7b2ff7"),
        "head": os.environ.get("BS_HEAD", "evil"),
        "tail": os.environ.get("BS_TAIL", "bolt"),
        "version": "1.0.0",
    }


# start is called when your Battlesnake begins a game
def start(game_state: typing.Dict):
    print("GAME START", game_state.get("game", {}).get("id", ""))


# end is called when your Battlesnake finishes a game
def end(game_state: typing.Dict):
    you = game_state.get("you", {}).get("id")
    alive = any(s.get("id") == you for s in game_state.get("board", {}).get("snakes", []))
    print("GAME OVER turn=%s %s\n" % (game_state.get("turn"), "won/alive" if alive else "dead"))


# move is called on every turn and returns your next move
# Valid moves are "up", "down", "left", or "right"
def move(game_state: typing.Dict) -> typing.Dict:
    t0 = time.perf_counter()
    try:
        resp, details = search_move(game_state)
    except Exception as e:  # никогда не падаем: любой ход лучше таймаута
        print(f"MOVE {game_state.get('turn')}: ERROR {e!r}, fallback to up")
        return {"move": "up"}
    print(
        f"MOVE {game_state['turn']}: {resp['move']} depth={details['depth']} "
        f"score={details['score']:.1f} {(time.perf_counter() - t0) * 1000:.0f}ms"
    )
    return resp


HANDLERS = {"info": info, "start": start, "move": move, "end": end}

# Start server when `python main.py` is run
if __name__ == "__main__":
    from server import run_server

    run_server(HANDLERS)
