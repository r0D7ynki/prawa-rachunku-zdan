# Architektura i kontrakty modułów

Ten plik jest **umową**. Karty implementują opisane niżej funkcje. Zmiana kontraktu wymaga
wpisu w `docs/DECISIONS.md` i nowej karty.

## Zasada naczelna: brak konfliktów między kartami

Trzy workery pracują równolegle. Dlatego:

1. **Każda karta tworzy własne pliki.** Nie edytuje plików innej karty.
2. `app/__init__.py` sam znajduje widoki w `app/blueprints/`. Nikt go nie edytuje.
3. `app/logic/laws.py` sam znajduje treść praw w `app/logic/laws_data/`. Nikt go nie edytuje.
4. Szablony współdzielone (`base.html`, partiale) mają jednego właściciela.
5. Odnośniki w menu to zwykłe ścieżki (`/prawa`), nie `url_for`. Dzięki temu brak widoku
   nie psuje innych stron.

## Mapa plików

| Plik / katalog | Rola | Właściciel (karta) |
|---|---|---|
| `app/__init__.py` | fabryka aplikacji, auto-rejestracja widoków | fundament (gotowe) |
| `app/blueprints/core.py` | `/zdrowie` | fundament (gotowe) |
| `app/logic/formula.py` | AST, parser, wypisywanie formuł | PRZ-001 |
| `app/logic/truth.py` | tablice prawdy, klasyfikacja, równoważność | PRZ-002 |
| `app/logic/law_model.py` | typy `Law` i `Step` | PRZ-003 |
| `app/logic/laws.py` | rejestr praw, auto-discovery `laws_data` | PRZ-003 |
| `app/logic/laws_data/podstawowe.py` | wyłączony środek, identyczność, podwójne przeczenie | PRZ-003 |
| `app/logic/laws_data/implikacja.py` | definiowanie implikacji, kontrapozycja | PRZ-003 |
| `app/logic/laws_data/algebra.py` | łączność, rozdzielność, przemienność | PRZ-004 |
| `app/logic/laws_data/de_morgan.py` | dwa prawa de Morgana | PRZ-005 |
| `app/logic/laws_data/zastepowanie.py` | prawo zastępowania równ. | PRZ-005 |
| `app/logic/laws_data/dodatkowe.py` | idempotencja i reguła podstawiania | PRZ-024 |
| `app/logic/simplify.py` | silnik przekształceń ze śladem kroków | PRZ-006 |
| `app/logic/quiz.py` | generator pytań | PRZ-007 |
| `app/blueprints/home.py` | `/`, `/slowniczek`, `/jak-czytac` | PRZ-008 |
| `app/blueprints/api_formula.py` | `/api/formula/*`, `/api/equivalence` | PRZ-009 |
| `app/blueprints/api_laws.py` | `/api/prawa` | PRZ-010 |
| `app/blueprints/laws.py` | `/prawa`, `/prawa/<slug>` | PRZ-010 |
| `app/blueprints/api_simplify.py` | `/api/formula/simplify` | PRZ-013 |
| `app/blueprints/api_quiz.py` | `/api/quiz/*` | PRZ-015 |
| `app/blueprints/wstep.py` | `/wstep` | PRZ-018 |
| `app/blueprints/formuly.py` | `/formuly` | PRZ-019 |
| `app/blueprints/tautologie.py` | `/tautologie` | PRZ-020 |
| `app/blueprints/przeksztalcanie.py` | `/przeksztalcanie` | PRZ-021 |
| `app/blueprints/kpn.py` | `/kpn` | PRZ-022 |
| `app/blueprints/playground.py` | `/plac-zabaw` | PRZ-014 |
| `app/blueprints/quiz.py` | `/quiz` | PRZ-015 |
| `app/templates/base.html` | szkielet strony, menu, stopka | PRZ-008 |
| `app/templates/partials/_truth_table.html` | komponent tablicy prawdy | PRZ-011 |
| `app/templates/partials/_gates.html` | komponent bramek | PRZ-012 |
| `app/templates/partials/_sets.html` | komponent diagramów zbiorów | PRZ-012 |
| `app/templates/partials/_steps.html` | komponent kroków | PRZ-013 |

## Notacja formuł

**Notacja z wykładu jest główna**: `∼` (negacja, U+223C), `≡` (równoważność, U+2261),
`∧`, `∨`, `→`, a wartości logiczne to `1` i `0`. Notacja popularna (`¬`, `↔`) jest
pokazywana obok jako ciekawostka.

Wejście parsera przyjmuje znaki Unicode oraz odpowiedniki ASCII:

| Znaczenie | Notacja wykładu | Inne dopuszczone |
|---|---|---|
| negacja | `∼` (U+223C) | `¬`, `~`, `!`, `not` |
| koniunkcja | `∧` | `&`, `^`, `and` |
| alternatywa | `∨` | `|`, `+`, `or` |
| implikacja | `→` | `->`, `=>`, `implies` |
| równoważność | `≡` (U+2261) | `↔`, `<->`, `<=>`, `iff` |

Kolejność wiązania od najsłabszego: `≡`, `→` (prawostronna), `∨`, `∧`, `∼`.
Nazwa zmiennej: litera albo wyraz (`[A-Za-z_][A-Za-z0-9_]*`), np. `p`, `q`, `deszcz`.

## `app/logic/formula.py`

```python
class FormulaError(ValueError):
    """Błąd składni formuły. Komunikat po polsku."""

@dataclass(frozen=True)
class Var:
    name: str

@dataclass(frozen=True)
class Not:
    child: Node

@dataclass(frozen=True)
class And:
    left: Node
    right: Node

@dataclass(frozen=True)
class Or:
    left: Node
    right: Node

@dataclass(frozen=True)
class Imp:
    left: Node
    right: Node

@dataclass(frozen=True)
class Iff:
    left: Node
    right: Node

Node = Var | Not | And | Or | Imp | Iff
```

```python
def parse(text: str) -> Node
def to_text(node: Node, style: str = "wyklad") -> str  # "wyklad" | "unicode" | "ascii" | "latex"
def to_html(node: Node, styl: str = "wyklad") -> str  # bezpieczny HTML, operator w <span class="op-...">
def variables(node: Node) -> list[str]                    # posortowane, bez powtórzeń
def evaluate(node: Node, env: Mapping[str, bool]) -> bool
def size(node: Node) -> int                               # liczba liści
def depth(node: Node) -> int
def subformulas(node: Node) -> list[Node]                 # bez powtórzeń, od najmniejszej
def replace(node: Node, target: Node, replacement: Node) -> Node
def normalize(node: Node) -> Node     # porządkuje strony ∧ i ∨ (stała kolejność)
def same(a: Node, b: Node) -> bool    # porównanie po normalize
```

Style wypisywania (`to_text` i `to_html` przyjmują ten sam zestaw):

| styl | negacja | koniunkcja | alternatywa | implikacja | równoważność |
|---|---|---|---|---|---|
| `"wyklad"` (domyślny) | `∼` | `∧` | `∨` | `→` | `≡` |
| `"unicode"` | `¬` | `∧` | `∨` | `→` | `↔` |
| `"ascii"` | `~` | `&` | `|` | `->` | `<->` |
| `"latex"` | `\neg` | `\land` | `\lor` | `\to` | `\leftrightarrow` |

Nieznany styl to `FormulaError` z komunikatem po polsku i listą dozwolonych stylów.

`to_html` używa tylko `str`, `Var`, `Not`, `And`, `Or`, `Imp`, `Iff` — nigdy `eval`.
Nawiasy stawia tylko tam, gdzie zmieniają sens. Wynik nadaje się do `|safe` w Jinja.

**Testy nie mogą zakładać konkretnego znaku operatora.** Sprawdzaj strukturę
(`isinstance`), wynik `to_text(..., style="ascii")` albo klasy HTML. Każdy operator ma
własną, stałą klasę: negacja `op-neg`, koniunkcja `op-and`, alternatywa `op-or`,
implikacja `op-imp`, równoważność `op-iff` (obsługuje `≡` i `↔`). Argument `style` różni
tylko znak operatora — struktura HTML i klasy są w obu stylach takie same.

## `app/logic/truth.py`

```python
@dataclass(frozen=True)
class TruthTable:
    variables: list[str]
    columns: list[str]                  # etykiety kolumn wynikowych (podformuły)
    rows: list[dict]                    # {"p": True, "q": False, "values": [True, False]}
    classification: str                 # "tautologia" | "kontrtautologia" | "spełnialna"
    def to_dict(self) -> dict

def build(node: Node, with_subformulas: bool = True) -> TruthTable
def classify(node: Node) -> str
def is_tautology(node: Node) -> bool
def is_contradiction(node: Node) -> bool
def equivalent(a: Node, b: Node) -> bool
def counterexample(a: Node, b: Node) -> dict[str, bool] | None
def markdown_table(table: TruthTable) -> str
```

`build` ogranicza liczbę zmiennych do 6. Więcej — `FormulaError` z komunikatem po polsku.

## `app/logic/law_model.py` i `laws.py`

```python
@dataclass(frozen=True)
class Step:
    opis: str        # co robimy, po polsku, jedno zdanie
    reguła: str      # slug prawa albo "założenie"
    przed: str       # formuła przed krokiem (Unicode)
    po: str          # formuła po kroku (Unicode)

@dataclass(frozen=True)
class Law:
    slug: str
    nazwa: str
    kategoria: str        # "podstawowe" | "implikacja" | "algebra" | "de Morgan" | "zastępowanie"
    formula: str          # np. "p ∨ ¬p"
    formula_ascii: str    # np. "p | ~p"
    lewa: str
    prawa: str
    po_ludzku: str        # 2-4 zdania prostym językiem, bez żargonu
    przyklad: str         # przykład z życia
    kroki: list[Step]     # krokowe przekształcenie lewej strony w prawą
    czeste_bledy: list[str]
    wizualizacja: str     # "gates" | "sets" | "switch" | "chain"
    quiz: list[dict]      # {"pytanie", "opcje": [...], "poprawna": int, "podpowiedz", "wyjasnienie"}
```

```python
def all_laws() -> list[Law]              # w kolejności nauki
def get(slug: str) -> Law | None
def by_category() -> dict[str, list[Law]]
def categories() -> list[str]
def validate() -> list[str]              # lista problemów; pusta = treść poprawna
```

Moduły w `laws_data/` wystawiają `LAWS: list[Law]`. `laws.py` znajduje je sam
(`pkgutil.iter_modules`) i sortuje po polu `kolejnosc` z `LAWS` — brak pola = 100.

## `app/logic/simplify.py`

```python
@dataclass(frozen=True)
class Rewrite:
    reguła: str          # slug prawa
    nazwa: str           # nazwa prawa po polsku
    przed: str
    po: str
    wyjaśnienie: str
    pozycja: str         # gdzie w formule, po polsku

@dataclass(frozen=True)
class Trace:
    start: str
    kroki: list[Rewrite]
    koniec: str
    forma: str           # "NNF" | "DNF" | "CNF" | "uproszczona"
    def to_dict(self) -> dict

def to_nnf(formula: str | Node) -> Trace
def to_dnf(formula: str | Node) -> Trace
def to_cnf(formula: str | Node) -> Trace
def simplify(formula: str | Node, cel: str = "auto", max_krokow: int = 60) -> Trace
def equivalence_steps(lewa: str, prawa: str) -> Trace   # ślad przejścia lewa → prawa
```

`simplify` przyjmuje tekst albo `Node`. Dla tekstu parsuje go i podnosi `FormulaError`.
Każdy krok musi być sprawdzony: `equivalent(przed, po)` ma być prawdą. Krok niesprawdzony
= `FormulaError` (to błąd w silniku, nie w danych).

## `app/logic/quiz.py`

```python
@dataclass(frozen=True)
class Question:
    id: str
    prawo: str            # slug
    pytanie: str
    opcje: list[str]
    poprawna: int         # indeks poprawnej odpowiedzi
    podpowiedz: str
    wyjasnienie: str
    def to_public_dict(self) -> dict   # bez pola "poprawna"

def generate(prawo: str | None = None, ile: int = 5, seed: int | None = None) -> list[Question]
def check(prawo: str | None, seed: int, pytanie_id: str, odpowiedz: int) -> bool
```

`generate` z tym samym `seed` daje ten sam zestaw. `check` generuje ponownie i porównuje
odpowiedź — dzięki temu serwer nie wysyła poprawnej odpowiedzi do przeglądarki.

## API

Każdy obszar API to **osobny moduł** w `app/blueprints/` (nazwa blueprintu w nawiasie).
Wszystkie endpointy to `POST` z JSON-em, o ile tabela nie mówi inaczej. Odpowiedź zawsze ma pole
`ok`. Błąd danych zwraca `ok: false` i `blad` po polsku (kod HTTP 200, nie 500).

`api_formula.py` (blueprint `api_formula`, `url_prefix="/api"`):

| Endpoint | Wejście | Wyjście |
|---|---|---|
| `/api/formula/parse` | `{"formula": str}` | `ok`, `unicode`, `ascii`, `html`, `ast`, `zmienne`, `blad` |
| `/api/formula/table` | `{"formula": str, "podformuly": bool}` | `ok`, `tabela`, `klasyfikacja`, `blad` |
| `/api/equivalence` | `{"lewa": str, "prawa": str}` | `ok`, `rownowazne`, `kontrprzyklad`, `blad` |

`ast` to drzewo JSON: `{"typ": "Var", "nazwa": "p"}`, `{"typ": "Not", "dziecko": {...}}`,
`{"typ": "And"|"Or"|"Imp"|"Iff", "lewy": {...}, "prawy": {...}}`. Rysunki robi JavaScript
z tego drzewa, więc nie zgaduje struktury z tekstu.

`api_laws.py` (blueprint `api_laws`): `GET /api/prawa` → `ok`, `prawa` (lista słowników
`{slug, nazwa, kategoria, formula, formula_ascii, wizualizacja}`).

`api_simplify.py` (blueprint `api_simplify`): `POST /api/formula/simplify`
`{"formula": str, "cel": "auto"|"nnf"|"dnf"|"cnf"}` → `ok`, `slad`, `blad`.

`api_quiz.py` (blueprint `api_quiz`):

| Endpoint | Wejście | Wyjście |
|---|---|---|
| `/api/quiz/generate` | `{"prawo": str\|null, "ile": int, "seed": int}` | `ok`, `seed`, `pytania`, `komunikat`, `blad` |
| `/api/quiz/check` | `{"prawo", "seed", "id", "odpowiedz"}` | `ok`, `poprawna`, `wyjasnienie`, `blad` |

`komunikat` w `/api/quiz/generate` to zdanie po polsku dla użytkownika, gdy `ok` jest prawdą,
ale zestaw różni się od zamówionego (np. mniej pytań niż `ile`, bo tyle jest dostępnych).
Przy pełnym zestawie pole jest puste. Dopisane po przeglądzie PRZ-015 (D27).

Widoki HTML: `home.py` → `/`, `/slowniczek`, `/jak-czytac`; `laws.py` → `/prawa`,
`/prawa/<slug>`; `playground.py` → `/plac-zabaw`; `quiz.py` → `/quiz`;
`wstep.py` → `/wstep`; `formuly.py` → `/formuly`; `tautologie.py` → `/tautologie`;
`przeksztalcanie.py` → `/przeksztalcanie`; `kpn.py` → `/kpn`.

Kolejność nauki na stronie (ścieżka kursu): `/wstep` → `/formuly` → `/tautologie` →
`/przeksztalcanie` → `/kpn` → `/prawa` → `/plac-zabaw` → `/quiz`. Każda strona kursu kończy
się odnośnikiem „następna lekcja” i „poprzednia lekcja” (zwykłe `href`, nie `url_for`).


## Frontend

- Bootstrap 5.3 z CDN. Własne style w `app/static/css/<nazwa>.css`.
- Skrypty jako `type="module"` w `app/static/js/`.
- Komunikacja z API przez `fetch`, JSON. Każdy komponent pokazuje stan błędu po polsku.
- Strony muszą działać bez JavaScriptu w zakresie treści (tekst i wzory są w HTML).
  JavaScript dodaje interakcję.
- Bez zależności z npm. Bez nowych bibliotek w `pyproject.toml`.
