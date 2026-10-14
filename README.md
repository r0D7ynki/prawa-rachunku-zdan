# Prawa rachunku zdań — interaktywna strona

Strona do nauki praw i tautologii rachunku zdań. Wyjaśnia każdy wzór prostym językiem,
pokazuje tablicę prawdy, krokowe przekształcenia i rysunek. Materiał dla osoby, która
zaczyna logikę na studiach.

## 14 praw

Numeracja i wzory z wykładu (T1–T14). Główny zapis to `∼` (negacja) i `≡` (równoważność).

| # | Prawo | Formuła |
|---|---|---|
| 1 | Wyłączonego środka | `p ∨ ∼p` |
| 2 | Identyczności | `p → p` |
| 3 | Podwójnego przeczenia | `∼(∼p) ≡ p` |
| 4 | Definiowania implikacji | `(p → q) ≡ (∼p ∨ q)` |
| 5 | Kontrapozycji | `(p → q) ≡ (∼q → ∼p)` |
| 6 | Łączności alternatywy | `((p ∨ q) ∨ r) ≡ (p ∨ (q ∨ r))` |
| 7 | Łączności koniunkcji | `((p ∧ q) ∧ r) ≡ (p ∧ (q ∧ r))` |
| 8 | I rozdzielności | `((p ∨ q) ∧ r) ≡ ((p ∧ r) ∨ (q ∧ r))` |
| 9 | II rozdzielności | `((p ∧ q) ∨ r) ≡ ((p ∨ r) ∧ (q ∨ r))` |
| 10 | Przemienności alternatywy | `(p ∨ q) ≡ (q ∨ p)` |
| 11 | Przemienności koniunkcji | `(p ∧ q) ≡ (q ∧ p)` |
| 12 | I de Morgana | `∼(p ∨ q) ≡ (∼p ∧ ∼q)` |
| 13 | II de Morgana | `∼(p ∧ q) ≡ (∼p ∨ ∼q)` |
| 14 | Zastępowania równ. | `(p ≡ q) ≡ ((p → q) ∧ (q → p))` |

W innych książkach spotkasz `¬p` i `p ↔ q` — to ten sam spójnik.

## Ścieżka kursu

Materiał idzie w kolejności wykładu. Każda lekcja kończy się odnośnikiem „następna lekcja”:

`/wstep` → `/formuly` → `/tautologie` → `/przeksztalcanie` → `/kpn` → `/prawa` →
`/plac-zabaw` → `/quiz`

## Funkcje strony

- ścieżka kursu — osiem lekcji od wstępu do quizu, w kolejności wykładu,
- interaktywne tablice prawdy — klikasz wartość zmiennej i widzisz wynik,
- krokowe przekształcenia — każdy krok z nazwą użytego prawa,
- strona KPN — klauzule i koniunkcyjna postać normalna krok po kroku,
- wizualizacje — bramki logiczne oraz diagramy zbiorów dla de Morgana,
- plac zabaw — wpisujesz formułę, dostajesz uproszczenie i tablicę prawdy,
- quiz z podpowiedziami,
- słowniczek pojęć.

## Jak korzystać ze strony

1. Przejdź lekcje po kolei — od `/wstep` do `/kpn`. Każda tłumaczy jeden temat wykładu.
2. Na stronie prawa znajdziesz wyjaśnienie, przykład, kroki, tablicę prawdy i częste błędy.
3. W tablicy prawdy klikasz wartości zmiennych, a wynik widzisz jako słowo i liczbę.
4. W plac zabaw wpisz formułę i sprawdź jej uproszczenie oraz tablicę prawdy.
5. Quiz sprawdza odpowiedzi i pokazuje wyjaśnienie po polsku.

## Uruchomienie

```bash
uv sync
uv run flask --app app run --debug
# http://127.0.0.1:5000/
```

**Pierwszy raz na MacBooku?** Instrukcja krok po kroku dla osoby, która nie zna terminala:
`docs/URUCHOMIENIE-MACBOOK.md`. Wszystkie komendy wklejasz do Terminala. Instrukcja używa
portu 5001, bo macOS trzyma port 5000 dla AirPlay.

## Bramka jakości

```bash
./scripts/gate.sh          # ruff, pytest, walidacja kart Kanban
echo $?                    # 0 = zielona
```

## CI

[![Bramka jakości](https://github.com/r0D7ynki/prawa-rachunku-zdan/actions/workflows/gate.yml/badge.svg)](https://github.com/r0D7ynki/prawa-rachunku-zdan/actions/workflows/gate.yml)

Każdy push na `main` lub `swarm/integration` i każdy pull request uruchamiają na GitHubie tę samą bramkę.

## Praca z agentami

Projekt używa tablicy Kanban i roju **swarmboard**. Zasady pracy: `AGENTS.md`.
Architektura i kontrakty modułów: `docs/ARCHITEKTURA.md`. Treść praw: `docs/TRESC-PRAW.md`.

Kod pisze rój na modelu `deepseek` (DeepSeek V4.1 Flash), a karty sprawdza reviewer
`claude` (Antigravity, `claude-sonnet-4-6`).
