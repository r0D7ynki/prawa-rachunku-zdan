#!/usr/bin/env bash
# Reviewer kart: Antigravity CLI (agy).
# swarmboard podaje prompt na standardowe wejście, a raport czyta ze standardowego wyjścia.
# Ostatnia linia raportu musi mieć postać `VERDICT: PASS` albo `VERDICT: FAIL`.
#
# Modele próbowane po kolei (REVIEWER_MODELS): najpierw Claude, potem Gemini z tego samego konta
# Antigravity. Konto ma osobne limity dla „Claude/GPT” i dla „Gemini”, więc wyczerpanie jednego
# nie zatrzymuje przeglądów. Reviewer zawsze pochodzi z innego modelu niż wykonawca (DeepSeek).
# Gdy żaden model nie zwróci werdyktu, raport nie ma linii VERDICT — karta zostaje w `review`
# i czeka na ponowienie (`sb review <ID>`), zamiast wracać do pracy bez powodu.
set -uo pipefail

instrukcja_oszczednosci='Zasady oszczędności limitu: czytaj wyłącznie kartę, diff scalenia i pliki wymienione w diffie. Nie czytaj całego repozytorium. Nie uruchamiaj testów ani bramki (worktree przeglądu jest tylko do odczytu). Odpowiedz zwięźle — najwyżej 40 linii. Zakończ odpowiedź linią VERDICT: PASS albo VERDICT: FAIL.'

prompt="$(cat)"

if [ -z "${prompt//[[:space:]]/}" ]; then
  echo "Powód: pusty prompt reviewera."
  echo "VERDICT: FAIL"
  exit 0
fi

prompt="$instrukcja_oszczednosci

$prompt"

models="${REVIEWER_MODELS:-claude-sonnet-4-6 gemini-3.8-flash-high}"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

for model in $models; do
  : >"$tmp"
  agy --model "$model" --mode plan --sandbox -p="$prompt" >"$tmp" 2>/dev/null || true
  if grep -qE "RESOURCE_EXHAUSTED|quota reached|Individual quota" "$tmp"; then
    echo "Reviewer $model: limit dostawcy wyczerpany — próbuję następny model." >&2
    continue
  fi
  if grep -qE "^[[:space:]]*VERDICT:[[:space:]]*(PASS|FAIL)" "$tmp"; then
    cat "$tmp"
    exit 0
  fi
  echo "Reviewer $model: brak werdyktu w odpowiedzi — próbuję następny model." >&2
done

cat "$tmp"
echo "Reviewer: żaden model nie zwrócił werdyktu (limit dostawcy albo błąd narzędzia)." >&2
exit 0
