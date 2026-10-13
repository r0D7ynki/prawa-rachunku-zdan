#!/usr/bin/env bash
# Reviewer kart: Antigravity CLI (agy) z modelem Claude.
# swarmboard podaje prompt na standardowe wejście, a raport czyta ze standardowego wyjścia.
# Ostatnia linia raportu musi mieć postać `VERDICT: PASS` albo `VERDICT: FAIL`.
set -euo pipefail

model="${REVIEWER_MODEL:-claude-sonnet-4-6}"
prompt="$(cat)"

if [ -z "${prompt//[[:space:]]/}" ]; then
  echo "VERDICT: FAIL"
  echo "Powód: pusty prompt reviewera."
  exit 0
fi

exec agy --model "$model" --mode plan --sandbox -p="$prompt"
