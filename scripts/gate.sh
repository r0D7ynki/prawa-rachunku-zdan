#!/usr/bin/env bash
# Bramka projektu: lint, format, testy i walidacja kart Kanban.
# Ocena wyniku: kod wyjścia tego skryptu (0 = zielona).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== ruff check =="
uv run --frozen ruff check .

echo "== ruff format --check =="
uv run --frozen ruff format --check .

echo "== pytest =="
uv run --frozen pytest

echo "== kanban check =="
if [ -f scripts/kanban/kanban.py ]; then
  python3 scripts/kanban/kanban.py check
else
  echo "brak scripts/kanban/kanban.py — pomijam (uruchom sb init)"
fi

echo "BRAMKA OK"
