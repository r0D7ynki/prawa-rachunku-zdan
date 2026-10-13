# Przerwa w pracy — jak wznowić

Zatrzymane 2026-10-13 na prośbę właściciela (koniec dnia). Nic nie zostało skasowane: worktree, konfiguracja
roju, karty i historia gita czekają na miejscu.

## Co jest zatrzymane

| Element | Stan | Jak włączyć |
|---|---|---|
| Watcher i panel roju | zatrzymane | `sb up` |
| Agenci (3 workery) | zamknięte sesje | `sb up` |
| Nadzorca zadań (`watchdog.py`) | zatrzymany | patrz niżej |
| Podgląd strony (port 5000) | zatrzymany | patrz niżej |

## Jak wznowić pracę roju

```bash
cd ~/projekty/prawa-rachunku-zdan
sb up                    # sesja Herdr, 3 workery, watcher i panel
sb status                # co robią zadania i workerzy
python3 /home/grz3chu/projekty/.swarm-reviewer/watchdog.py &   # nadzorca zawieszonych zadań
```

Panel roju: http://127.0.0.1:8765/

## Jak obejrzeć stronę bez roju

```bash
cd ~/projekty/prawa-rachunku-zdan
uv run flask --app app run --debug --port 5000
```

Podgląd: http://127.0.0.1:5000/ — działa dwanaście adresów z wykładu 1:
`/`, `/wstep`, `/formuly`, `/tautologie`, `/przeksztalcanie`, `/kpn`, `/prawa`,
`/prawa/<slug>`, `/jak-czytac`, `/slowniczek`, `/plac-zabaw`, `/quiz`.

Bramka jakości: `./scripts/gate.sh` (kod wyjścia 0 = zielona).

## Stan tablicy w chwili zatrzymania

- **Zrobione: 64 karty.** Wykład 1 i wykład 2 są kompletne, wszystkie poprawki właściciela scalone.
- **W toku: 0 kart.** Wszystko, o co prosił właściciel, jest zrobione i na `main`.
- **Przegląd: 0 kart.**
- **Gotowe do startu: 0 kart.**
- **Backlog: 88 kart** — wyłącznie drobne uwagi z przeglądów, świadomie odłożone przez właściciela.

Wersja `sb`: **0.6.34** (zaktualizowana z repo `tom3k5/swarmboard`).

## O czym pamiętać przy wznowieniu

1. **Zadanie „w toku” z bezczynnym workerem i pustą gałęzią nie ruszy samo.** Ten wzorzec
   zdarzył się trzy razy. Ratunek: „Cofnij” w panelu (albo
   `POST /api/tasks/<ID>/requeue` z tokenem z panelu) — zadanie wraca do kolejki.
   Dlatego warto od razu włączyć `watchdog.py`: sprawdza to co 2 minuty i zwalnia sam.
2. **Limit Antigravity.** Modele Claude i Gemini mają osobne okna. Gdy jedno się kończy,
   przegląd idzie dalej drugim, a potem DeepSeek V4 Pro po API. Nic nie trzeba przestawiać.
3. **Rewizja karty bez zmiany kodu daje FAIL przeglądu** — reviewer widzi tylko ostatnie
   scalenie. Takie karty zamyka człowiek (decyzja D29).
4. **Wykład 2 czeka na notatki właściciela.** Miejsce w rejestrze `app/lessons.py` już jest:
   wystarczy dopisać lekcje do wpisu „Rachunek predykatów”.

## Gdzie co leży

| Co | Gdzie |
|---|---|
| Repozytorium projektu | `~/projekty/prawa-rachunku-zdan` |
| Repozytorium na GitHubie | https://github.com/r0D7ynki/prawa-rachunku-zdan (publiczne) |
| Konfiguracja roju | `~/projekty/prawa-rachunku-zdan/.git/swarm/config.json` |
| Karty Kanban | `~/projekty/prawa-rachunku-zdan/kanban/tasks/` |
| Kontrakt modułów | `~/projekty/prawa-rachunku-zdan/docs/ARCHITEKTURA.md` |
| Decyzje projektu | `~/projekty/prawa-rachunku-zdan/docs/DECISIONS.md` |
| Skrypt reviewera i nadzorca | `~/projekty/.swarm-reviewer/` |
| Worktree roju | `~/projekty/.worktrees-prawa-rachunku-zdan/` |
| Referencja swarmboard | `~/Documents/deepseek-harness/default-workspace/.ref/swarmboard` |
