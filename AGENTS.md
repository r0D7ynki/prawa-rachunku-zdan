# AGENTS — jak pracować w prawa-rachunku-zdan

Jedno źródło zasad dla **wszystkich agentów** (DeepSeek, Claude, człowiek) i ludzi.
`CLAUDE.md` tylko tu odsyła — **zasady zmieniaj wyłącznie w tym pliku**.

## Produkt w trzech zdaniach

Interaktywna strona do nauki 14 praw i tautologii rachunku zdań. Odbiorca to student bez
wcześniejszej logiki: każdy wzór ma wyjaśnienie prostym językiem, tablicę prawdy, krokowe
przekształcenia i rysunek. Twarde ograniczenie: brak zależności npm i brak nowych bibliotek
Pythona poza Flasketem — frontend to Bootstrap z CDN i czysty JavaScript.

## Mapa kodu

| Plik / katalog | Rola |
|---|---|
| `app/__init__.py` | fabryka aplikacji; sam znajduje widoki w `app/blueprints/` |
| `app/logic/formula.py` | AST, parser i wypisywanie formuł |
| `app/logic/truth.py` | tablice prawdy, klasyfikacja, równoważność |
| `app/logic/law_model.py`, `laws.py`, `laws_data/` | typy praw, rejestr i treść 14 praw |
| `app/logic/simplify.py` | silnik przekształceń ze śladem kroków |
| `app/logic/quiz.py` | generator pytań quizu |
| `app/blueprints/` | widoki: `core`, `home`, `api`, `laws`, `playground`, `quiz` |
| `app/templates/` | szablony Jinja; partiale komponentów w `app/templates/partials/` |
| `app/static/` | `css/` i `js/` bez kroku budowania |
| `docs/ARCHITEKTURA.md` | **kontrakt modułów — czytaj przed kodowaniem** |
| `docs/TRESC-PRAW.md` | co ma zawierać treść każdego prawa |
| `docs/DECISIONS.md` | rejestr decyzji projektu |
| `kanban/tasks/` | karty Kanban |

## Twarde zasady

1. **Zależności**: tylko `flask` w `pyproject.toml`. Frontend wyłącznie Bootstrap 5.3 z CDN
   i czysty JavaScript (moduły ES). Zero npm, zero `node_modules`.
2. **Kontrakt**: implementujesz dokładnie funkcje i typy z `docs/ARCHITEKTURA.md`.
   Nie zmieniasz plików innej karty. Nowy widok = nowy moduł w `app/blueprints/`
   z wystawioną zmienną `bp`. Nowa treść praw = nowy plik w `app/logic/laws_data/`.
3. **Bezpieczeństwo**: nigdy `eval` ani `exec` na tekście użytkownika. Wynik HTML buduj
   z AST. Serwer nie zwraca poprawnej odpowiedzi quizu przed sprawdzeniem.
4. **Język**: interfejs i komunikaty po polsku. Nazwy w kodzie po angielsku
   (`parse`, `truth_table`), treść strony po polsku. Zdanie w treści ma najwyżej 15–20 słów.
   Strona czynna.
5. **Dostępność**: każdy element interaktywny działa z klawiatury, ma `aria-label`,
   a wynik jest opisany tekstem (kolor nie jest jedynym nośnikiem informacji).
6. **Test**: nowe zachowanie ma test, który pada bez zmiany. Testy logiki nie wymagają
   przeglądarki — używaj `flask.test_client()`.
7. **Zakres**: zmieniasz tylko pliki z sekcji `## Files` karty. Potrzebny inny plik —
   wpis w `## Log`, karta wraca do `ready`, stop.

## Komendy

```bash
./scripts/gate.sh                                   # PEŁNA BRAMKA — oceniaj po kodzie wyjścia
python3 scripts/kanban/kanban.py board              # tablica Kanban (z swarmboard: `sb board`)
python3 scripts/kanban/kanban.py next deepseek --start   # weź kartę (bramka DoR + WIP)
python3 scripts/kanban/kanban.py submit PRZ-001     # oddaj: kryteria + Evidence + bramka → review
python3 scripts/kanban/kanban.py check              # walidacja wszystkich kart
# --json przy board/check/next/submit; kody wyjścia: 0 ok, 1 bramka/walidacja, 2 użycie, 3 brak karty
```

## Proces pracy (Kanban)

Karty: `kanban/tasks/PRZ-XXX.md`. Kolumny: `backlog → ready → in-progress → review → done`.
Przesuwaj **tylko** przez `scripts/kanban/kanban.py` — skrypt pilnuje bramek
(DoR, WIP, kryteria + Evidence, DoD + bramka).

1. Weź kartę: `python3 scripts/kanban/kanban.py next deepseek --start` — tworzy gałąź
   `<id>-<tytuł>` i przesuwa kartę do `in-progress` przez bramkę. Pracuj tylko nad kartami
   ze swoim `model:`.
2. Drzewo robocze musi być czyste przed startem.
3. Zmieniaj **tylko pliki z sekcji `## Files`**.
4. Odhacz kryteria, wypełnij **`## Evidence`** realnym wyjściem komend (kod wyjścia bramki!).
5. `python3 scripts/kanban/kanban.py submit <ID>` — bramka projektu musi przejść, inaczej
   karta zostaje w `in-progress` z ostatnimi liniami wyjścia. **Nie przenoś własnej karty
   do `done`** — robi to reviewer (inny model lub człowiek), który odhacza DoD i wpisuje się
   w `reviewer:`.
6. Niejasność → pytanie w `## Log` karty, karta zostaje, koniec przebiegu.
7. Karta wymaga decyzji człowieka (UX, treść merytoryczna, publikacja) — oznacz
   `human_review: true` albo kryterium `(ręcznie)`.
8. Nie zmieniaj `status:` ręcznie.

### W roju (watcher + most Kanban)

Kartę dostajesz promptem `[NOWE ZADANIE: PRZ-XXX]` w swoim worktree. Nie przesuwasz karty
i nie zmieniasz jej nagłówka ani `## Log` — robi to watcher. Kod, odhaczone kryteria
i `## Evidence` idą w **jednym commicie, dopiero gdy praca jest skończona**.

Oszczędne tokeny: jedna karta = jedna sesja; bez cronów i cyklicznych raportów; czytaj pliki
z sekcji `## Files` i to, czego bezpośrednio potrzebują; po komunikacie o limicie nie ponawiaj
zapytań — watcher wstrzyma przydział dla modelu.

Identyfikatory modeli w kartach (`models` w `kanban/config.json`): `deepseek` (wykonawca,
DeepSeek V4.1 Flash), `claude` (reviewer, Antigravity `claude-sonnet-4-6`), `human`.
