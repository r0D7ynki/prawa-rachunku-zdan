@AGENTS.md

## Specyficzne dla Claude Code

- Twój identyfikator w kartach Kanban: `claude` (reviewer).
- Przed `review` przeczytaj diff scalenia i `docs/ARCHITEKTURA.md`.
- Zgłoś `[BLOCKER] plik:linia` przy: niespełnionym kryterium, nowej zależności, użyciu
  `eval`, braku testu dla nowego zachowania, treści niezrozumiałej dla początkującego.

## Dla reviewera: co nie jest naruszeniem zakresu

Diff karty zmienia zawsze także **plik karty** `kanban/tasks/<ID>.md`. To nie jest wyjście
poza sekcję `## Files`. Worker i watcher aktualizują w karcie kryteria, `## Evidence`
i `## Log` — wymaga tego `AGENTS.md`. Nie zgłaszaj tego jako `[BLOCKER]`.

Nie jest też naruszeniem zakresu plik `docs/DECISIONS.md`, gdy zmiana zachowania wymaga
wpisu decyzyjnego, oraz `app/templates/base.html` z kartą PRZ-023, która ma go w `## Files`.

Reviewer działa w worktree tylko do odczytu. Brak możliwości uruchomienia `./scripts/gate.sh`
nie jest znaleziskiem — bramkę uruchamia QA roju przed scaleniem. Sprawdzaj kod i testy
czytaniem, nie uruchamianiem.

