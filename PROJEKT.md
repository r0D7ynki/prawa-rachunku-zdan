# PROJEKT — jak pracujemy i co jest zrobione

## Cel

Strona do nauki 14 praw rachunku zdań. Odbiorca: student pierwszego roku, który nie miał
wcześniej logiki. Po przeczytaniu jednej strony ma rozumieć wzór, umieć go sprawdzić
w tablicy prawdy i wiedzieć, kiedy go użyć w przekształceniach.

## Kryterium sukcesu

1. Każde z 14 praw ma własną stronę: wzór, wyjaśnienie po ludzku, przykład, kroki, tablicę
   prawdy, rysunek i częste błędy.
2. Plac zabaw upraszcza dowolną formułę z zakresu rachunku zdań i pokazuje kroki.
3. Quiz działa i tłumaczy odpowiedź.
4. Bramka `./scripts/gate.sh` jest zielona.
5. Strona działa lokalnie jedną komendą.

## Jak pracujemy

- Tablica Kanban: `kanban/tasks/PRZ-XXX.md`. Przejścia tylko przez `sb move`.
- Kod pisze rój (`sb up`): 3 workery na modelu `deepseek` (DeepSeek V4.1 Flash).
- Reviewer: `claude` przez Antigravity (`agy -p --model claude-sonnet-4-6`).
- Kontrakt modułów: `docs/ARCHITEKTURA.md`. Zmiana kontraktu = wpis w `docs/DECISIONS.md`.
- Bramka: `./scripts/gate.sh`. Oceniamy po kodzie wyjścia.

## Stan

| Data | Stan |
|---|---|
| 2026-10-13 | Fundament: fabryka Flask, auto-rejestracja widoków, bramka, kontrakty, tablica Kanban i rój. |
| 2026-10-13 | Zamknięcie: 14 praw T1–T14 z pełną treścią, ścieżka kursu `/wstep`…`/kpn`, plac zabaw, quiz. Bramka `./scripts/gate.sh` zielona, tę samą bramkę uruchamia CI na GitHubie. |

## Rejestr długu

| # | Dług | Status | Kiedy spłacamy |
|---|---|---|---|
| 1 | Brak skanera sekretów `gitleaks` w bramce QA (D9) | **otwarty** — `./scripts/gate.sh` nadal go nie uruchamia | gdy właściciel zdecyduje o instalacji |
| 2 | Brak publikacji publicznej (GitHub Pages nie obsługuje Flask) | **spłacony w części** — CI publikuje wynik bramki (`.github/workflows/gate.yml`); publikacja samej strony zostaje otwarta | publikacja strony: osobna karta po zielonym roju |

Żadna pozycja nie jest spłacona w całości — obie czekają na decyzję właściciela.
Długi zebrane z przeglądów czekają jako karty `Uwaga z PRZ-…` w kolumnie `backlog`.
