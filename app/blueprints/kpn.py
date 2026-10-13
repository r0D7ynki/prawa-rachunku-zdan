"""Lekcja czwarta kursu: ``/kpn`` — klauzule i koniunkcyjna postać normalna (KPN).

Treść odwzorowuje wykład 1 („Logika pragmatyczna”, PWr), slajdy „Przekształcanie
formuł”: czym jest klauzula, czym jest KPN, jak sprowadzić formułę do KPN i jak
w KPN sprawdzić tautologię.

Dwie rzeczy strona liczy, zamiast wpisywać je na sztywno:

* które klauzule mają parę ``x`` i ``∼x`` — czyta to z drzewa formuły
  (``formula.parse``), więc wniosek o tautologii nie rozjedzie się z wzorem,
* wynik ``simplify.to_cnf`` z silnika przekształceń — pokazujemy go jako listę klauzul.

Wzory zamienia na HTML ``formula.to_html`` (nigdy ``eval``), a nazwy praw
w wyprowadzeniach pochodzą z rejestru ``app.logic.laws`` — dzięki temu odnośniki
i nazwy nie rozjadą się z treścią praw.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from flask import Blueprint, render_template
from markupsafe import Markup, escape

from app.logic import laws, simplify, truth
from app.logic.formula import (
    And,
    FormulaError,
    Node,
    Not,
    Or,
    Var,
    parse,
    to_html,
    to_text,
    variables,
)

#: Nazwa blueprintu i trasa to tokeny interfejsu (adres ``/kpn`` z mapy kodu) —
#: zostają jak w adresie, tak samo jak nazwy stron w pozostałych lekcjach.
bp = Blueprint("kpn", __name__)

#: Trzy klauzule z wykładu — punkt 1 slajdu „Klauzule”.
CLAUSE_EXAMPLES: tuple[str, ...] = (
    "p ∨ q ∨ r",
    "∼p ∨ q",
    "p ∨ ∼q ∨ ∼r ∨ s",
)

#: Dwa zapisy KPN z wykładu — punkt 2 slajdu.
CNF_EXAMPLES: tuple[str, ...] = (
    "(p ∨ ∼q ∨ ∼r ∨ s) ∧ (∼p ∨ q) ∧ (r ∨ s ∨ ∼t)",
    "p ∧ q ∧ (∼p ∨ ∼q)",
)

#: Formuła wyprowadzana do KPN — punkt 3 slajdu.
IMPLICATION_FORMULA = "(p → q) → ∼r"

#: Formuła z równoważnością, sprowadzana do KPN bez implikacji — punkt 3 slajdu.
EQUIVALENCE_FORMULA = "p ≡ q"


@dataclass(frozen=True)
class Step:
    """Jeden krok wyprowadzenia.

    ``formula`` to formuła, do której dochodzimy (formuła startowa stoi nad listą
    kroków), a ``laws`` to slugi praw z rejestru ``app.logic.laws``, które na ten
    krok pozwalają. Krok oparty na dwóch prawach ma dwa slugi — wtedy pokazujemy oba.
    """

    formula: str
    laws: tuple[str, ...]


#: Wyprowadzenie ``(p → q) → ∼r`` do KPN, krok po kroku jak w wykładzie.
IMPLICATION_STEPS: tuple[Step, ...] = (
    Step(formula="(∼p ∨ q) → ∼r", laws=("definiowanie-implikacji",)),
    Step(formula="∼(∼p ∨ q) ∨ ∼r", laws=("definiowanie-implikacji",)),
    Step(formula="(p ∧ ∼q) ∨ ∼r", laws=("de-morgan-1", "podwojne-przeczenie")),
    Step(formula="(p ∨ ∼r) ∧ (∼q ∨ ∼r)", laws=("rozdzielnosc-2",)),
)

#: Wyprowadzenie ``p ≡ q`` do KPN — krok po kroku jak w wykładzie.
EQUIVALENCE_STEPS: tuple[Step, ...] = (
    Step(formula="(p → q) ∧ (q → p)", laws=("zastepowanie-rownych",)),
    Step(formula="(∼p ∨ q) ∧ (∼q ∨ p)", laws=("definiowanie-implikacji",)),
    Step(formula="∼(∼(∼p ∨ q) ∨ ∼(∼q ∨ p))", laws=("de-morgan-1",)),
)

#: Przykład tautologii z wykładu: w każdej klauzuli jest jakaś para ``x`` i ``∼x``.
TAUTOLOGY_EXAMPLE = "(p ∨ q ∨ ∼p) ∧ (∼p ∨ q ∨ r ∨ ∼q) ∧ (∼s ∨ s)"

#: Kontrprzykład z wykładu: w żadnej klauzuli nie ma pary ``x`` i ``∼x``.
NON_TAUTOLOGY_EXAMPLE = "(p ∨ q) ∧ (∼p ∨ r)"


@dataclass(frozen=True)
class Clause:
    """Klauzula gotowa dla szablonu: wzór i pary ``x``/``∼x`` znalezione w środku."""

    formula: str
    pairs: list[str]


def formula_to_html(text: str, style: str = "wyklad") -> Markup:
    """Zwraca wzór jako bezpieczny HTML z ``formula.to_html``.

    Gdy napis nie jest poprawną formułą, oddajemy go jako zwykły tekst — treść lekcji
    nigdy nie kończy się błędem 500. Wynik wstawiamy w szablonie przez ``|safe``,
    tak samo jak ``app/blueprints/tautologie.py`` i ``formuly.py``.
    """
    try:
        return Markup(to_html(parse(text), style))
    except FormulaError:
        return escape(text)


def split_clauses(node: Node) -> list[Node]:
    """Dzieli formułę w KPN na klauzule: koniunkcja to lista swoich składników.

    Formuła spoza KPN (np. implikacja) nie jest rozbijana — wraca jako jedna klauzula,
    a ``complementary_pairs`` zgłosi wtedy ``FormulaError``.
    """
    if isinstance(node, And):
        return split_clauses(node.left) + split_clauses(node.right)
    return [node]


def complementary_pairs(clause: str | Node) -> list[str]:
    """Zmienne, które w klauzuli stoją raz bez negacji, a raz z negacją.

    Klauzula jest tautologią dokładnie wtedy, gdy ta lista nie jest pusta — stąd
    cały test tautologiczności w KPN. Dla napisu, który nie jest klauzulą, podnosimy
    ``FormulaError``: to błąd treści strony, nie danych użytkownika.
    """
    node = parse(clause) if isinstance(clause, str) else clause
    literals = _literals(node)
    positive = {name for name, is_positive in literals if is_positive}
    negative = {name for name, is_positive in literals if not is_positive}
    return sorted(positive & negative)


def clauses_with_pairs(formula: str) -> list[Clause]:
    """Klauzule formuły w KPN razem z parami znalezionymi w każdej z nich."""
    return [
        Clause(formula=to_text(clause), pairs=complementary_pairs(clause))
        for clause in split_clauses(parse(formula))
    ]


def falsifying_assignment(formula: str) -> dict[str, bool] | None:
    """Pierwsze wartościowanie, przy którym formuła jest fałszywa.

    ``None`` znaczy, że formuła jest tautologią. Kolejność wartościowań bierzemy
    z ``truth.build``, więc kontrprzykład na stronie zgadza się z tablicą prawdy.
    """
    table = truth.build(parse(formula))
    for row in table.rows:
        if not row["values"][-1]:
            return {name: row[name] for name in table.variables}
    return None


def engine_clauses(formula: str) -> dict[str, Any]:
    """Wynik ``simplify.to_cnf`` jako lista klauzul.

    Silnik zwraca cały ślad przekształcenia; lekcja pokazuje tylko jego koniec,
    rozbity na pojedyncze klauzule.
    """
    trace = simplify.to_cnf(formula)
    return {
        "cnf": trace.koniec,
        "clauses": [to_text(clause) for clause in split_clauses(parse(trace.koniec))],
    }


def steps_for_view(steps: Sequence[Step]) -> list[dict[str, Any]]:
    """Przygotowuje kroki dla szablonu: wzór i nazwy praw z rejestru."""
    return [
        {"formula": step.formula, "laws": [_law_for_view(slug) for slug in step.laws]}
        for step in steps
    ]


def _literals(node: Node) -> list[tuple[str, bool]]:
    """Rozkłada klauzulę na literały: ``(nazwa zmiennej, czy bez negacji)``."""
    if isinstance(node, Or):
        return _literals(node.left) + _literals(node.right)
    if isinstance(node, Var):
        return [(node.name, True)]
    if isinstance(node, Not) and isinstance(node.child, Var):
        return [(node.child.name, False)]
    raise FormulaError(f"To nie jest klauzula: {to_text(node)}")


def _law_for_view(slug: str) -> dict[str, str]:
    """Prawo z rejestru jako para ``(slug, nazwa)`` dla szablonu."""
    law = laws.get(slug)
    if law is None:
        raise RuntimeError(f"Nie ma prawa o slugu {slug!r} w rejestrze.")
    return {"slug": law.slug, "name": law.nazwa}


def _truth_table_rows(formula: str) -> int:
    """Liczba wierszy pełnej tablicy prawdy: ``2`` do potęgi liczby zmiennych."""
    return 2 ** len(variables(parse(formula)))


@bp.get("/kpn")
def lesson() -> str:
    """Lekcja: klauzula, KPN, sprowadzanie formuł do KPN i test tautologiczności."""
    return render_template(
        "kpn.html",
        formula_to_html=formula_to_html,
        clause_examples=CLAUSE_EXAMPLES,
        cnf_examples=CNF_EXAMPLES,
        implication_formula=IMPLICATION_FORMULA,
        implication_steps=steps_for_view(IMPLICATION_STEPS),
        equivalence_formula=EQUIVALENCE_FORMULA,
        equivalence_steps=steps_for_view(EQUIVALENCE_STEPS),
        tautology_example=TAUTOLOGY_EXAMPLE,
        tautology_clauses=clauses_with_pairs(TAUTOLOGY_EXAMPLE),
        tautology_holds=truth.is_tautology(parse(TAUTOLOGY_EXAMPLE)),
        tautology_row_count=_truth_table_rows(TAUTOLOGY_EXAMPLE),
        non_tautology_example=NON_TAUTOLOGY_EXAMPLE,
        non_tautology_clauses=clauses_with_pairs(NON_TAUTOLOGY_EXAMPLE),
        falsifying_assignment=falsifying_assignment(NON_TAUTOLOGY_EXAMPLE),
        engine_result=engine_clauses(IMPLICATION_FORMULA),
    )
