# Правила для агента

Проект — змейка для arena.battlesnake.com, которая улучшается методом hill-climbing.
Полный протокол описан в HILLCLIMB.md.

- Меняй только `snake/`. Тесты в `tests/` можно добавлять, существующие — не ослаблять.
- НЕ меняй `bench.py`, `harness/`, `champions/`, `experiments/log.jsonl`: это сигнал, и его правка — reward hacking.
  Если стенд кажется неправильным, остановись и спроси человека.
- Одна идея — один прогон `python3 bench.py run --idea "<что изменено>"`.
- ACCEPT → `python3 bench.py promote --idea "..."` и коммит. REJECT → `git checkout -- snake/`.
- После каждого прогона добавляй строку в `experiments/JOURNAL.md` (идея, счёт, LOS, вердикт, вывод).
- Змейка обязана отвечать быстрее 450 мс на одном ядре (`python3 bench.py timing`).
- Только стандартная библиотека Python 3.8+.
