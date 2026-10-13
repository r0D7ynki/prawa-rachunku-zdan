"""Silnik przekształceń formuł ze śladem kroków.

Moduł przekształca formułę krok po kroku i zapisuje każdy krok razem z prawem, którego
użył. Obsługuje formę normalną negacji (NNF), DNF i CNF.

Każdy krok jest **sprawdzany**: przed zapisaniem moduł liczy ``truth.equivalent(przed, po)``.
Gdy krok nie zachowuje równoważności, podnosi ``FormulaError`` — to błąd silnika, nie danych.
Sprawdzenie wymaga tablicy prawdy, więc przekształcanie obsługuje formuły do 6 zmiennych.

Nazwy praw biorą się z rejestru ``laws.py``, a nie z kopii w tym pliku.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.logic import laws
from app.logic.formula import (
    And,
    FormulaError,
    Iff,
    Imp,
    Node,
    Not,
    Or,
    Var,
    parse,
    same,
    to_text,
    variables,
)
from app.logic.truth import MAX_VARIABLES, equivalent

#: Domyślny limit kroków — chroni przed pętlą w silniku.
DEFAULT_MAX_KROKOW = 60

#: Przy tylu zmiennych lub mniej ``cel="auto"`` liczy jeszcze DNF.
AUTO_DNF_LIMIT = 4


@dataclass(frozen=True)
class Rewrite:
    """Jeden krok przekształcenia.

    ``opis`` mówi, co robimy, ``wyjaśnienie`` — dlaczego wolno (po ludzku),
    a ``pozycja`` — w którym miejscu formuły.
    """

    opis: str
    reguła: str
    nazwa: str
    przed: str
    po: str
    wyjaśnienie: str
    pozycja: str


@dataclass(frozen=True)
class Trace:
    """Cały ślad przekształcenia: formuła startowa, kroki i wynik."""

    start: str
    kroki: list[Rewrite]
    koniec: str
    forma: str  # "NNF" | "DNF" | "CNF" | "uproszczona"

    def to_dict(self) -> dict:
        """Zwraca ślad gotowy na JSON."""
        return {
            "start": self.start,
            "kroki": [asdict(krok) for krok in self.kroki],
            "koniec": self.koniec,
            "forma": self.forma,
        }


@dataclass(frozen=True)
class _Rule:
    """Przepis przekształcenia: nazwa wewnętrzna, prawo i teksty dla użytkownika."""

    kind: str
    slug: str
    nazwa_zapasowa: str
    opis: str
    wyjaśnienie: str


#: Przepisy w kolejności pierwszeństwa (pierwszy pasujący wygrywa).
_RULES: tuple[_Rule, ...] = (
    _Rule(
        "iff",
        "zastepowanie-rownych",
        "Prawo zastępowania równych",
        "Zamieniam równoważność na koniunkcję implikacji",
        "Prawo zastępowania równych: p ≡ q znaczy to samo, co (p → q) ∧ (q → p).",
    ),
    _Rule(
        "imp",
        "definiowanie-implikacji",
        "Prawo definiowania implikacji",
        "Zastępuję implikację alternatywą",
        "Prawo definiowania implikacji: p → q znaczy to samo, co ∼p ∨ q.",
    ),
    _Rule(
        "dneg",
        "podwojne-przeczenie",
        "Prawo podwójnego przeczenia",
        "Usuwam podwójną negację",
        "Prawo podwójnego przeczenia: ∼∼p znaczy to samo, co p.",
    ),
    _Rule(
        "dm_and",
        "de-morgan-2",
        "II prawo de Morgana",
        "Wnoszę negację do koniunkcji",
        "II prawo de Morgana: ∼(p ∧ q) znaczy to samo, co ∼p ∨ ∼q.",
    ),
    _Rule(
        "dm_or",
        "de-morgan-1",
        "I prawo de Morgana",
        "Wnoszę negację do alternatywy",
        "I prawo de Morgana: ∼(p ∨ q) znaczy to samo, co ∼p ∧ ∼q.",
    ),
    _Rule(
        "dist_and",
        "rozdzielnosc-1",
        "I prawo rozdzielności",
        "Rozdzielam koniunkcję po alternatywie",
        "I prawo rozdzielności: (p ∨ q) ∧ r znaczy to samo, co (p ∧ r) ∨ (q ∧ r).",
    ),
    _Rule(
        "dist_or",
        "rozdzielnosc-2",
        "II prawo rozdzielności",
        "Rozdzielam alternatywę po koniunkcji",
        "II prawo rozdzielności: (p ∧ q) ∨ r znaczy to samo, co (p ∨ r) ∧ (q ∨ r).",
    ),
    _Rule(
        "idem_or",
        "idempotencja-alternatywy",
        "Prawo idempotencji alternatywy",
        "Usuwam powtórzony argument alternatywy",
        "Prawo idempotencji: p ∨ p znaczy to samo, co p.",
    ),
    _Rule(
        "idem_and",
        "idempotencja-koniunkcji",
        "Prawo idempotencji koniunkcji",
        "Usuwam powtórzony argument koniunkcji",
        "Prawo idempotencji: p ∧ p znaczy to samo, co p.",
    ),
    _Rule(
        "commute",
        "przemiennosc-alternatywy",
        "Prawo przemienności alternatywy",
        "Porządkuję argumenty alternatywy",
        "Prawo przemienności: p ∨ q znaczy to samo, co q ∨ p.",
    ),
)

#: Przemienność koniunkcji — ten sam przepis ``commute``, ale inne prawo w rejestrze.
_COMMUTE_AND = _Rule(
    "commute",
    "przemiennosc-koniunkcji",
    "Prawo przemienności koniunkcji",
    "Porządkuję argumenty koniunkcji",
    "Prawo przemienności: p ∧ q znaczy to samo, co q ∧ p.",
)

_BY_KIND = {rule.kind: rule for rule in _RULES}

#: Kolejność pracy: NNF, potem ewentualna rozdzielność.
_PHASES = {
    "nnf": ("iff", "imp", "dneg", "dm_and", "dm_or"),
    "dnf": ("iff", "imp", "dneg", "dm_and", "dm_or", "dist_and"),
    "cnf": ("iff", "imp", "dneg", "dm_and", "dm_or", "dist_or"),
}

_OPIS_RODZAJU = {
    Or: "alternatywy",
    And: "koniunkcji",
    Imp: "implikacji",
    Iff: "równoważności",
    Not: "negacji",
}


def _law_name(slug: str, zapasowa: str) -> str:
    """Nazwa prawa z rejestru ``laws.py`` (albo zapasowa, gdy prawa jeszcze nie ma)."""
    law = laws.get(slug)
    return law.nazwa if law is not None else zapasowa


def _enabled(kinds: tuple[str, ...]) -> tuple[str, ...]:
    """Dokłada przepisy, które mają sens tylko wtedy, gdy prawo jest w rejestrze."""
    extra = [kind for kind in ("idem_or", "idem_and") if _rule_available(kind)]
    return (*kinds, *extra, "commute")


def _rule_available(kind: str) -> bool:
    return laws.get(_BY_KIND[kind].slug) is not None


def _as_node(formula: str | Node) -> Node:
    """Zamienia tekst na drzewo; drzewo zostawia bez zmian."""
    if isinstance(formula, str):
        return parse(formula)
    if isinstance(formula, (Var, Not, And, Or, Imp, Iff)):
        return formula
    raise FormulaError(
        f"Nieznany typ formuły: {type(formula).__name__}. Podaj tekst albo drzewo z formula.py."
    )


def _prepared(formula: str | Node) -> Node:
    """Wspólny start: drzewo + sprawdzenie granicy zmiennych (kroki są liczone tablicą)."""
    node = _as_node(formula)
    names = variables(node)
    if len(names) > MAX_VARIABLES:
        raise FormulaError(
            f"Przekształcanie sprawdza każdy krok tablicą prawdy, więc obsługuje najwyżej "
            f"{MAX_VARIABLES} zmiennych. Ta formuła ma {len(names)}."
        )
    return node


# ---------------------------------------------------------------------------
# Wyszukiwanie i stosowanie przepisu
# ---------------------------------------------------------------------------


def _children(node: Node) -> tuple[tuple[str, Node], ...]:
    if isinstance(node, Var):
        return ()
    if isinstance(node, Not):
        return (("child", node.child),)
    return (("left", node.left), ("right", node.right))


def _key(node: Node) -> str:
    """Klucz porządku argumentów — ten sam dla obu stron przemienności."""
    return to_text(node)


def _matches(kind: str, node: Node) -> bool:
    """Czy przepis pasuje do tego węzła."""
    if kind == "iff":
        return isinstance(node, Iff)
    if kind == "imp":
        return isinstance(node, Imp)
    if kind == "dneg":
        return isinstance(node, Not) and isinstance(node.child, Not)
    if kind == "dm_and":
        return isinstance(node, Not) and isinstance(node.child, And)
    if kind == "dm_or":
        return isinstance(node, Not) and isinstance(node.child, Or)
    if kind == "dist_and":
        return isinstance(node, And) and _ma_dziecko(node, Or)
    if kind == "dist_or":
        return isinstance(node, Or) and _ma_dziecko(node, And)
    if kind == "idem_or":
        return isinstance(node, Or) and node.left == node.right
    if kind == "idem_and":
        return isinstance(node, And) and node.left == node.right
    if kind == "commute":
        if not isinstance(node, (And, Or)):
            return False
        return _key(node.right) < _key(node.left)
    return False


def _rewrite(kind: str, node: Node) -> Node:
    """Zwraca węzeł po zastosowaniu przepisu."""
    if kind == "iff":
        return And(Imp(node.left, node.right), Imp(node.right, node.left))
    if kind == "imp":
        return Or(Not(node.left), node.right)
    if kind == "dneg":
        return node.child.child
    if kind == "dm_and":
        return Or(Not(node.child.left), Not(node.child.right))
    if kind == "dm_or":
        return And(Not(node.child.left), Not(node.child.right))
    if kind == "dist_and":
        return _distribute_and(node)
    if kind == "dist_or":
        return _distribute_or(node)
    if kind in ("idem_or", "idem_and"):
        return node.left
    if kind == "commute":
        return type(node)(node.right, node.left)
    raise FormulaError(f"Nieznany przepis przekształcenia: {kind}.")


def _ma_dziecko(node: Node, typ: type) -> bool:
    """Czy któryś argument węzła jest danego typu."""
    return isinstance(node.left, typ) or isinstance(node.right, typ)


def _distribute_and(node: Node) -> Node:
    """I prawo rozdzielności: ``(a ∨ b) ∧ c`` daje ``(a ∧ c) ∨ (b ∧ c)``.

    Drugi wariant (``c ∧ (a ∨ b)``) to to samo prawo z przemiennością.
    """
    if isinstance(node.left, Or):
        a, b, c = node.left.left, node.left.right, node.right
    else:
        a, b, c = node.right.left, node.right.right, node.left
    return Or(And(a, c), And(b, c))


def _distribute_or(node: Node) -> Node:
    """II prawo rozdzielności: ``(a ∧ b) ∨ c`` daje ``(a ∨ c) ∧ (b ∨ c)``."""
    if isinstance(node.left, And):
        a, b, c = node.left.left, node.left.right, node.right
    else:
        a, b, c = node.right.left, node.right.right, node.left
    return And(Or(a, c), Or(b, c))


def _find_redex(node: Node, kinds: tuple[str, ...], path: tuple[str, ...] = ()):
    """Pierwszy pasujący przepis (węzeł idzie przed dziećmi, przepisy po kolei)."""
    for kind in kinds:
        if _matches(kind, node):
            return path, kind
    for step, child in _children(node):
        found = _find_redex(child, kinds, (*path, step))
        if found is not None:
            return found
    return None


def _at(node: Node, path: tuple[str, ...]) -> Node:
    """Węzeł pod ścieżką (kolejne kroki: ``left``, ``right``, ``child``)."""
    for step in path:
        if step == "child":
            node = node.child
        elif step == "left":
            node = node.left
        else:
            node = node.right
    return node


def _replace_at(node: Node, path: tuple[str, ...], nowy: Node) -> Node:
    """Nowe drzewo z podmienionym węzłem pod ścieżką."""
    if not path:
        return nowy
    step, *rest = path
    reszta = tuple(rest)
    if step == "child":
        return Not(_replace_at(node.child, reszta, nowy))
    if step == "left":
        return type(node)(_replace_at(node.left, reszta, nowy), node.right)
    return type(node)(node.left, _replace_at(node.right, reszta, nowy))


def _position(root: Node, path: tuple[str, ...]) -> str:
    """Opis miejsca w formule, po polsku."""
    if not path:
        return "cała formuła"
    opis: list[str] = []
    node = root
    for step in path:
        if step == "child":
            opis.append("wnętrze negacji")
            node = node.child
        else:
            strona = "lewa" if step == "left" else "prawa"
            opis.append(f"{strona} strona {_OPIS_RODZAJU[type(node)]}")
            node = node.left if step == "left" else node.right
    return " → ".join(opis)


def _rule_text(kind: str, node: Node) -> tuple[str, str, str, str]:
    """``(slug, nazwa, opis, wyjaśnienie)`` dla zastosowania przepisu na węźle."""
    # Uwaga: przemienność ma osobne prawo dla ∧ i dla ∨.
    rule = _COMMUTE_AND if kind == "commute" and isinstance(node, And) else _BY_KIND[kind]
    return (rule.slug, _law_name(rule.slug, rule.nazwa_zapasowa), rule.opis, rule.wyjaśnienie)


def _check_step(przed: Node, po: Node) -> None:
    """Sprawdza, że krok zachowuje równoważność. Inaczej to błąd silnika."""
    if not equivalent(przed, po):
        raise FormulaError(
            "Krok przekształcenia zmienia sens formuły — to błąd silnika, nie danych."
        )


def _run(node: Node, kinds: tuple[str, ...], limit: int, forma: str) -> tuple[Trace, Node]:
    """Wykonuje przekształcenie do wyczerpania przepisów albo do limitu kroków."""
    steps: list[Rewrite] = []
    current = node
    forma_koncowa = forma
    while True:
        found = _find_redex(current, kinds)
        if found is None:
            break
        if len(steps) >= limit:
            forma_koncowa = "uproszczona"
            break
        path, kind = found
        before = _at(current, path)
        candidate = _replace_at(current, path, _rewrite(kind, before))
        _check_step(current, candidate)
        slug, nazwa, opis, wyjaśnienie = _rule_text(kind, before)
        steps.append(
            Rewrite(
                opis=opis,
                reguła=slug,
                nazwa=nazwa,
                przed=to_text(current),
                po=to_text(candidate),
                wyjaśnienie=wyjaśnienie,
                pozycja=_position(current, path),
            )
        )
        current = candidate
    trace = Trace(
        start=to_text(node),
        kroki=steps,
        koniec=to_text(current),
        forma=forma_koncowa,
    )
    return trace, current


# ---------------------------------------------------------------------------
# Publiczne API
# ---------------------------------------------------------------------------


def to_nnf(formula: str | Node, *, max_krokow: int = DEFAULT_MAX_KROKOW) -> Trace:
    """Sprowadza formułę do formy normalnej negacji."""
    trace, _ = _run(_prepared(formula), _enabled(_PHASES["nnf"]), max_krokow, "NNF")
    return trace


def to_dnf(formula: str | Node, *, max_krokow: int = DEFAULT_MAX_KROKOW) -> Trace:
    """Sprowadza formułę do dysjunkcyjnej formy normalnej."""
    trace, _ = _run(_prepared(formula), _enabled(_PHASES["dnf"]), max_krokow, "DNF")
    return trace


def to_cnf(formula: str | Node, *, max_krokow: int = DEFAULT_MAX_KROKOW) -> Trace:
    """Sprowadza formułę do koniunkcyjnej formy normalnej."""
    trace, _ = _run(_prepared(formula), _enabled(_PHASES["cnf"]), max_krokow, "CNF")
    return trace


def simplify(formula: str | Node, cel: str = "auto", max_krokow: int = DEFAULT_MAX_KROKOW) -> Trace:
    """Przekształca formułę do wybranego celu: ``auto``, ``nnf``, ``dnf`` albo ``cnf``.

    ``auto`` liczy DNF, gdy formuła ma najwyżej 4 zmienne; inaczej kończy na NNF.
    """
    node = _prepared(formula)
    if cel == "nnf":
        return _run(node, _enabled(_PHASES["nnf"]), max_krokow, "NNF")[0]
    if cel == "dnf":
        return _run(node, _enabled(_PHASES["dnf"]), max_krokow, "DNF")[0]
    if cel == "cnf":
        return _run(node, _enabled(_PHASES["cnf"]), max_krokow, "CNF")[0]
    if cel != "auto":
        raise FormulaError(
            f"Nieznany cel przekształcania: '{cel}'. Dozwolone cele to auto, nnf, dnf, cnf."
        )
    if len(variables(node)) <= AUTO_DNF_LIMIT:
        return _run(node, _enabled(_PHASES["dnf"]), max_krokow, "DNF")[0]
    return _run(node, _enabled(_PHASES["nnf"]), max_krokow, "NNF")[0]


def equivalence_steps(
    lewa: str | Node, prawa: str | Node, max_krokow: int = DEFAULT_MAX_KROKOW
) -> Trace:
    """Ślad przejścia od ``lewa`` do ``prawa``.

    Gdy formuły nie są równoważne, podnosi ``FormulaError``.
    """
    start = _prepared(lewa)
    cel = _prepared(prawa)
    if not equivalent(start, cel):
        raise FormulaError(
            "Te formuły nie są równoważne, więc nie da się przejść od lewej do prawej "
            "samymi prawami rachunku zdań."
        )

    kandydaci = [
        _run(start, _enabled(_PHASES["nnf"]), max_krokow, "NNF"),
        _run(start, _enabled(_PHASES["dnf"]), max_krokow, "DNF"),
        _run(start, _enabled(_PHASES["cnf"]), max_krokow, "CNF"),
    ]
    # Najpierw ślady, które dochodzą dokładnie do formy z prawej; potem najkrótszy.
    najlepszy = min(
        kandydaci, key=lambda para: (0 if same(para[1], cel) else 1, len(para[0].kroki))
    )
    return najlepszy[0]
