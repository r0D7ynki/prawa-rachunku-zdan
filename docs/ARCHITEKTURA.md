# Architektura i kontrakty modułów

Ten plik jest **umową**. Karty implementują opisane niżej funkcje. Zmiana kontraktu wymaga
wpisu w `docs/DECISIONS.md` i nowej karty.

## Zasada naczelna: brak konfliktów między kartami

Trzy workery pracują równolegle. Dlatego:

1. **Każda karta tworzy własne pliki.** Nie edytuje plików innej karty.
2. `app/__init__.py` sam znajduje widoki w `app/blueprints/`. Nikt go nie edytuje.
   Jedyny wyjątek: `app.context_processor` z `NAV` (karta PRZ-070) — patrz sekcja
   „`app/lessons.py` — rejestr wykładów i lekcji”.
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
| `app/logic/rules.py` | rejestr reguł wnioskowania (wykład 2) | PRZ-090 |
| `app/lessons.py` | rejestr wykładów i lekcji (nawigacja) | PRZ-070 |
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
| `app/blueprints/spis_tresci.py` | `/spis-tresci` | PRZ-069 |
| `app/blueprints/reguly.py` | `/reguly` | PRZ-090 |
| `app/blueprints/konsekwencja.py` | `/konsekwencja` | PRZ-083 |
| `app/blueprints/api_wynikanie.py` | `/api/wynikanie` | PRZ-083 |
| `app/templates/base.html` | szkielet strony, menu, okruszki, nawigacja lekcji, stopka | PRZ-008, PRZ-069 |
| `app/templates/spis_tresci.html` | spis treści kursu (wykłady i lekcje) | PRZ-069 |
| `app/static/css/nawigacja.css` | style menu, okruszków, spisu lekcji i kart sąsiadów | PRZ-069 |
| `app/templates/reguly.html` | karty reguł wnioskowania | PRZ-090 |
| `app/static/css/reguly.css` | style kart reguł | PRZ-090 |
| `app/templates/partials/_truth_table.html` | komponent tablicy prawdy | PRZ-011 |
| `app/templates/partials/_gates.html` | komponent bramek | PRZ-012 |
| `app/templates/partials/_sets.html` | komponent diagramów zbiorów | PRZ-012 |
| `app/templates/partials/_steps.html` | komponent kroków | PRZ-013 |
| `app/templates/partials/_stepper.html` | wspólny pasek kroków (stepper) | PRZ-072 |

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

## `app/logic/rules.py` — reguły wnioskowania

Treść pochodzi z `docs/TRESC-WYKLAD2.md`, sekcja „2. Reguły wnioskowania”; ten plik jest dla
niej źródłem prawdy (tak samo jak `laws.py` dla praw wykładu 1).

```python
@dataclass(frozen=True)
class Rule:
    kod: str                 # "RO", "OK", …
    nazwa: str               # "Reguła odrywania"
    pelna_nazwa: str         # "Modus Ponens" albo ""
    typ: str                 # "pierwotna" | "dodatkowa"
    przeslanki: list[str]    # ["Φ → Ψ", "Φ"]
    wniosek: str             # "Ψ"
    tautologia: str          # "((p → q) ∧ p) → q"
    przyklad: str
    opis: str
    wnioski_dodatkowe: list[str] = []       # patrz niżej
    tautologie_dodatkowe: list[str] = []    # patrz niżej

PIERWOTNA = "pierwotna"
DODATKOWA = "dodatkowa"

def rules() -> list[Rule]        # kopie listy: pierwotne wg tabeli, potem dodatkowe
def get(kod: str) -> Rule | None # kod bez wielkości liter i spacji (" ro " → RO)
```

**Dwa dodatkowe pola (decyzja karty PRZ-090).** Wykład podaje dwie reguły w dwóch wersjach:
**OK** (`Φ ∧ Ψ ⊢ Φ` oraz `Φ ∧ Ψ ⊢ Ψ`, z osobną tautologią dla każdej wersji) i **OR**
(`Φ ≡ Ψ ⊢ Φ → Ψ` oraz `Φ ≡ Ψ ⊢ Ψ → Φ`, z jedną wspólną tautologią). Żeby każde pole było
pojedynczym wzorem przepisanym z tabeli, a nie sklejoną listą, drugą wersję trzymamy
w `wnioski_dodatkowe` i `tautologie_dodatkowe`. U pozostałych ośmiu reguł oba pola są puste.

**Notacja.** `tautologia` i `tautologie_dodatkowe` mają zwykłe zmienne (`p`, `q`) — parsują się
przez `formula.parse` i przechodzą przez `formula.to_html`. Pola `przeslanki`, `wniosek`
i `wnioski_dodatkowe` używają **metazmiennych** `Φ`, `Ψ`, `Θ` — to dowolne formuły, a nie
zmienne zdaniowe, więc parser ich nie przyjmie. Rysuje je dopiero widok
(`app/blueprints/reguly.py`), zamieniając metazmienne na litery przed parsowaniem i wracając
do nich w drzewie (`formula.replace`). **Kod spoza `app/logic/` nie może zakładać, że te pola
są formułami.**

Kolejność kodów: `RO`, `OK`, `DK`, `OA`, `DA`, `DR`, `OR` (pierwotne), `DM1`, `DM2`, `KP`
(dodatkowe) — jak dwie tabele wykładu.

## `app/blueprints/reguly.py` — strona `/reguly`

Lekcja „Reguły wnioskowania”: wyjaśnienie, czym jest reguła, sekcje „Reguły pierwotne”
i „Reguły dodatkowe” i karta na każdą regułę. Karta pokazuje kod i nazwę, przesłanki nad
kreską, wniosek pod kreską, tautologię, przykład z życia i opis. Kreska to `div.regula-kreska`
(`aria-hidden`), malowany w `app/static/css/reguly.css` — nie znak `—`. Każda karta ma
odnośnik „Sprawdź w placu zabaw” z tautologią reguły w parametrze `formula`
(`/plac-zabaw?formula=…`), więc plac zabaw otwiera się z gotowym wzorem, także bez JavaScriptu.

Sekcje powstają z pola `Rule.typ` — widok nie zna kodów reguł ani ich liczby. Metazmienne
rysuje `metazmienne_to_html`, tautologie `formula_to_html`; oba oddają napis jako tekst
(bez znaczników), gdy wzór się nie parsuje, żeby błąd w treści nie dawał strony 500.

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

`api_wynikanie.py` (blueprint `api_wynikanie`, `url_prefix="/api"`, karta PRZ-083):

| Endpoint | Wejście | Wyjście |
|---|---|---|
| `/api/wynikanie` | `{"zalozenia": [str], "teza": str}` | `ok`, `wynika`, `kontrprzyklad`, `blad` |

`wynika` odpowiada na pytanie, czy teza wynika logicznie z listy założeń. `kontrprzyklad`
to pierwsze wartościowanie, przy którym założenia są prawdziwe, a teza fałszywa — słownik
`{"p": 1, "q": 0}` (wartości jako `1`/`0`) albo `null`, gdy teza wynika. Granice: 10 założeń,
6 zmiennych i 500 znaków na formułę; przekroczenie to `ok: false` z komunikatem po polsku.

`api_wynikanie.check_entailment(zalozenia, teza)` to cała logika wynikania (bez Flaska):
buduje koniunkcję założeń i porównuje ją przez `truth.equivalent` z tą samą koniunkcją
poszerzoną o tezę. Funkcji używa też widok `/konsekwencja`, więc formularz strony
i endpoint API liczą wynik tym samym kodem. Błędne dane zwracają słownik z `ok: false`
i `blad` zamiast wyjątku.

Widoki HTML: `home.py` → `/`, `/slowniczek`, `/jak-czytac`; `laws.py` → `/prawa`,
`/prawa/<slug>`; `playground.py` → `/plac-zabaw`; `quiz.py` → `/quiz`;
`wstep.py` → `/wstep`; `formuly.py` → `/formuly`; `tautologie.py` → `/tautologie`;
`przeksztalcanie.py` → `/przeksztalcanie`; `kpn.py` → `/kpn`; `reguly.py` → `/reguly`;
`konsekwencja.py` → `/konsekwencja` (GET oraz POST z formularza testu wynikania).

Kolejność nauki na stronie (ścieżka kursu): `/wstep` → `/formuly` → `/tautologie` →
`/przeksztalcanie` → `/kpn` → `/prawa` → `/plac-zabaw` → `/quiz`. Każda strona kursu kończy
się odnośnikiem „następna lekcja” i „poprzednia lekcja” (zwykłe `href`, nie `url_for`).
Kolejność tę wypisuje rejestr lekcji — patrz niżej.

## `app/lessons.py` — rejestr wykładów i lekcji

Jedno źródło prawdy dla nawigacji (karta PRZ-070). Menu, spis treści, okruszki i odnośniki
„poprzednia/następna lekcja” czytają dane z tego modułu, a nie z szablonów. Nowy wykład
albo nowa lekcja to wpis w tym jednym pliku.

```python
@dataclass(frozen=True)
class Lesson:
    slug: str          # "formuly"
    sciezka: str       # "/formuly"
    tytul: str         # "Formuły i wartościowanie"
    opis: str          # jedno zdanie, do 20 słów
    wyklad: int        # numer wykładu
    ikona: str         # krótki znak, np. "≡"

@dataclass(frozen=True)
class Lecture:
    numer: int
    tytul: str
    opis: str
    lekcje: tuple[Lesson, ...]
    gotowy: bool       # False = „wkrótce”
```

```python
def lectures() -> list[Lecture]        # w kolejności numerów
def lessons() -> list[Lesson]          # wszystkie lekcje po kolei (płaska lista)
def lesson(sciezka: str) -> Lesson | None
def lecture(numer: int) -> Lecture | None
def previous(sciezka: str) -> Lesson | None   # sąsiad w płaskiej liście
def next(sciezka: str) -> Lesson | None       # sąsiad w płaskiej liście
def tool_links() -> list[dict]         # {"sciezka", "tytul", "ikona"}; pozycje narzędziowe
```

Rejestr zawiera wykład 1 (klasyczny rachunek zdań, osiem lekcji) oraz wykłady 2 i 3 jako
zapowiedź (`gotowy=False`, pusta lista lekcji). Pozycje narzędziowe to Prawa `/prawa`,
Plac zabaw `/plac-zabaw`, Quiz `/quiz`, Słowniczek `/slowniczek` i Jak czytać `/jak-czytac`.

`create_app` (karta PRZ-070 — jedyny wyjątek od zasady „nikt nie edytuje `app/__init__.py`”)
dodaje `app.context_processor`, który wstrzykuje do **każdego** szablonu:

```python
NAV = {
    "lectures": lectures(),
    "lesson": lesson(request.path),      # None poza kursem
    "previous": previous(request.path),  # None na początku i poza kursem
    "next": next(request.path),          # None na końcu i poza kursem
    "tools": tool_links(),
}
```

Dzięki temu szablony nie wołają funkcji Pythona — czytają `NAV.lesson.tytul`,
`NAV.previous.sciezka` albo `NAV.tools`. Szablon sprawdza `None` (`{% if NAV.previous %}`),
bo strony spoza kursu (np. `/slowniczek`) też dostają `NAV`, tyle że bez lekcji.


## Komponent kroków: `stepper.js`, `_stepper.html`, `stepper.css`

Jeden pasek prowadzi użytkownika krok po kroku. Korzystają z niego tablica prawdy,
bramki, diagramy zbiorów i dowód tautologii — dzięki temu zachowanie jest wszędzie takie samo.

Pliki: `app/static/js/stepper.js` (moduł ES), `app/static/css/stepper.css`,
`app/templates/partials/_stepper.html`.

### Kontrakt `createStepper`

```js
import { createStepper } from "/static/js/stepper.js";

const stepper = createStepper({
  mount: document.querySelector("#kroki"),   // element, w którym powstaje pasek (wymagany)
  steps: [{ tytul: "...", opis: "..." }],    // co najmniej 1 krok
  onStep: (index, step) => { ... },          // co pokazać po wejściu w krok
  autoMs: 1500,                              // tempo odtwarzania (domyślnie 1500 ms)
  labels: { prev: "Wstecz", next: "Dalej", play: "Odtwórz", pause: "Pauza", reset: "Od nowa" },
});
```

Pola `onStep`, `autoMs` i `labels` są opcjonalne. `labels` nadpisuje pojedyncze napisy —
brakujące zostają domyślne. Krok `step` to obiekt z polami `tytul` i `opis` (oba napisy po polsku);
komponent czyta tylko te dwa pola i przekazuje cały obiekt dalej do `onStep`.

Zwrócony obiekt:

| Pole | Znaczenie |
|---|---|
| `index` | numer bieżącego kroku, **liczony od zera** |
| `length` | liczba kroków |
| `playing` | `true`, gdy trwa odtwarzanie |
| `go(index)` | przejście do kroku o indeksie od zera; numer spoza listy jest przycinany |
| `next()` / `prev()` | krok dalej / wstecz; na końcach listy nic się nie dzieje |
| `play()` / `pause()` | włączenie i zatrzymanie odtwarzania |
| `reset()` | zatrzymanie odtwarzania i powrót do pierwszego kroku |
| `destroy()` | zatrzymanie odtwarzania, zdjęcie nasłuchów i usunięcie paska |

**Numeracja.** `index`, argument `go` i pierwszy argument `onStep` liczą kroki od zera
(`stepper.go(2)` to trzeci krok). Widoczny wskaźnik pokazuje numer od jednego („Krok 3 z 7”).

**Kto rysuje co.** Komponent pisze wyłącznie do własnego kontenera `mount` (podmienia jego
zawartość na pasek) i do swojego elementu opisu. Resztę rysuje karta, która go używa —
w `onStep(index, step)`. `onStep` jest wołane od razu przy tworzeniu (krok pierwszy)
i przy każdej zmianie kroku; samo odświeżenie paska go nie powtarza.

**Autoodtwarzanie.** `play()` przechodzi do kolejnego kroku co `autoMs`. Na ostatnim kroku
odtwarzanie samo się zatrzymuje i przycisk wraca do napisu „Odtwórz”. `play()` na ostatnim
kroku zaczyna od pierwszego. Ręczne `go`, `next` i `prev` nie zatrzymują odtwarzania.

**Klawiatura.** Pasek ma `tabindex="0"`; strzałki `ArrowLeft`/`ArrowRight`, `Home` i `End`
przechodzą między krokami, a spacja włącza i zatrzymuje odtwarzanie. Spacja na przycisku
jest pomijana — tam klawisz ma już swoje znaczenie (klik).

**Dostępność.** Kropki kroków są przyciskami `<button>`; bieżąca ma `aria-current="step"`,
a jej etykieta to „Krok n: tytuł”. Treść kroku jest ogłaszana przez `aria-live="polite"`.
Bieżący krok widać nie tylko po kolorze, ale też po obramowaniu i pogrubieniu.

**Brak JavaScriptu.** Partial pokazuje w `<noscript>` pełną listę kroków jako `<ol>`
(gdy w kontekście przekazano `steps`), a bez kroków — jedno zdanie po polsku.

**Brak kroków.** `createStepper` nie rzuca błędu: bez `steps` pokazuje w kontenerze komunikat
po polsku, bez `mount` nie dotyka dokumentu. W obu razach zwrócony obiekt ma te same metody
(nic nie robią), więc karta, która go używa, nie musi ich sprawdzać.

### Użycie partialu

```jinja
{% include "partials/_stepper.html" %}
```

Partial renderuje kontener `[data-stepper]` i dołącza `stepper.css` oraz `stepper.js`
(moduł ES) przez `url_for('static', ...)`. Strona podaje mu opcjonalnie `steps` wyłącznie
po to, żeby `<noscript>` miał co pokazać — pasek i tak rysuje `createStepper` z konfiguracji
podanej w JavaScripcie:

```js
const kroki = [{ tytul: "Założenie", opis: "Zapisujemy wzór wyjściowy." }, /* ... */];
createStepper({
  mount: document.querySelector("[data-stepper]"),
  steps: kroki,
  onStep: (index, step) => { /* karta rysuje swoją wizualizację kroku */ },
});
```

## Frontend

- Bootstrap 5.3 z CDN. Własne style w `app/static/css/<nazwa>.css`.
- Skrypty jako `type="module"` w `app/static/js/`.
- Komunikacja z API przez `fetch`, JSON. Każdy komponent pokazuje stan błędu po polsku.
- Strony muszą działać bez JavaScriptu w zakresie treści (tekst i wzory są w HTML).
  JavaScript dodaje interakcję.
- Bez zależności z npm. Bez nowych bibliotek w `pyproject.toml`.
