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
4. **Nawigacja układa materiał wykładami**: menu z podziałem na wykłady, okruszki, boczny spis
   treści, „poprzednia/następna lekcja” i strona `/spis-tresci`. Dodanie wykładu 2 to wpis
   w `app/lessons.py`, bez zmian w szablonach.
5. **Wizualizacje prowadzą krok po kroku**: tablica prawdy rośnie kolumna po kolumnie, bramki
   pokazują propagację sygnału ze strzałkami, diagramy zbiorów przechodzą kolejne kroki dowodu,
   a dowód tautologii odkrywa kolumny α, β, γ ze strzałkami.
6. Bramka `./scripts/gate.sh` jest zielona.
7. Strona działa lokalnie jedną komendą.

## Jak pracujemy

- Tablica Kanban: `kanban/tasks/PRZ-XXX.md`. Przejścia tylko przez `sb move`.
- Kod pisze rój (`sb up`): 3 workery na modelu `deepseek` (DeepSeek V4.1 Flash).
- Reviewer: łańcuch modeli — Antigravity (`claude-sonnet-4-6`, potem `gemini-3.8-flash-high`),
  a przy wyczerpanym limicie DeepSeek V4 Pro po API (D19, D22). Skrypt: `scripts/reviewer-agy.sh`
  i `~/projekty/.swarm-reviewer/reviewer.sh`.
- Kontrakt modułów: `docs/ARCHITEKTURA.md`. Nowe pole API wymaga wpisu w tym pliku w tym samym
  commicie (D27).
- Bramka: `./scripts/gate.sh`. Oceniamy po kodzie wyjścia.

## Stan

| Data | Stan |
|---|---|
| 2026-10-13 | Fundament: fabryka Flask, auto-rejestracja widoków, bramka, kontrakty, tablica Kanban i rój. |
| 2026-10-13 | Wykład 1 zamknięty: 14 praw T1–T14 z pełną treścią, ścieżka kursu `/wstep`…`/kpn`, plac zabaw, quiz, CI na GitHubie. Wszystkie 12 adresów działa. |
| 2026-10-13 | Uwagi właściciela w kartach: nawigacja wykładami (PRZ-069 … PRZ-071) i interaktywne wizualizacje krok po kroku (PRZ-072 … PRZ-077). |
| — | **Wykład 2 (rachunek predykatów) czeka na notatki właściciela.** Miejsce w rejestrze już jest (D30). |

## Rejestr długu

| # | Dług | Status | Kiedy spłacamy |
|---|---|---|---|
| 1 | Brak skanera sekretów `gitleaks` w bramce QA (D9) | **otwarty** — `./scripts/gate.sh` nadal go nie uruchamia | gdy właściciel zdecyduje o instalacji |
| 2 | Brak publikacji publicznej (GitHub Pages nie obsługuje Flask) | **spłacony w części** — CI publikuje wynik bramki (`.github/workflows/gate.yml`); publikacja samej strony zostaje otwarta | publikacja strony: osobna karta po zielonym roju |
| 3 | Publikacja treści publicznie bez serwera aplikacji | **otwarty** | karta po zamknięciu wizualizacji; wymaga decyzji o hostingu |
| 4 | Drobne uwagi z przeglądów w kolumnie `backlog` (m.in. porządek `_key` w `simplify.py`, walidacja `max_krokow`) | **otwarty** | po kartach z uwag właściciela |

Długi zebrane z przeglądów czekają jako karty `Uwaga z PRZ-…` w kolumnie `backlog`.
