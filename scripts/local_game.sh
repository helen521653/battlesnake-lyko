#!/usr/bin/env bash
# Локальная дуэль двух копий змейки через официальный CLI battlesnake.
# Установка CLI:  go install github.com/BattlesnakeOfficial/rules/cli/battlesnake@latest
#   (или скачайте бинарник из https://github.com/BattlesnakeOfficial/rules/releases)
# Использование:  scripts/local_game.sh [число_игр] [weights_A.json] [weights_B.json]
set -euo pipefail
cd "$(dirname "$0")/.."
GAMES=${1:-5}
WA=${2:-snake/weights.json}
WB=${3:-snake/weights.json}

mkdir -p logs
WEIGHTS="$WA" PORT=8001 python3 server.py > logs/snake_a.log 2>&1 & PA=$!
WEIGHTS="$WB" PORT=8002 python3 server.py > logs/snake_b.log 2>&1 & PB=$!
trap 'kill $PA $PB 2>/dev/null' EXIT
sleep 1.5

for i in $(seq 1 "$GAMES"); do
  battlesnake play -W 11 -H 11 -g standard -t 500 \
    --name A --url http://localhost:8001 \
    --name B --url http://localhost:8002 2>&1 | tail -n 1
done
echo "Самый долгий ответ змейки A: $(grep -o '[0-9]*ms' logs/snake_a.log | sort -n | tail -n 1)"
