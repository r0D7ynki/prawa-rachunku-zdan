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

bp = Blueprint("kpn", __name__)

#: Trzy klauzule z wykładu — punkt 1 slajdu „Klauzule”.
PRZYKLADY_KLAUZUL: tuple[str, ...] = (
    "p ∨ q ∨ r",
    "∼p ∨ q",
    "p ∨ ∼q ∨ ∼r ∨ s",
)

#: Dwa zapisy KPN z wykładu — punkt 2 slajdu.
PRZYKLADY_KPN: tuple[str, ...] = (
    "(p ∨ ∼q ∨ ∼r ∨ s) ∧ (∼p ∨ q) ∧ (r ∨ s ∨ ∼t)",
    "p ∧ q ∧ (∼p ∨ ∼q)",
)

#: Formuła wyprowadzana do KPN — punkt 3 slajdu.
FORMULA_IMPLIKACJI = "(p → q) → ∼r"

#: Formuła z równoważnością, sprowadzana do KPN bez implikacji — punkt 3 slajdu.
FORMULA_ROWNOZNOSCI = "p ≡ q"


@dataclass(frozen=True)
class Krok:
    """Jeden krok wyprowadzenia.

    ``po`` to formuła, do której dochodzimy (formuła startowa stoi nad listą kroków),
    a ``prawa`` to slugi praw z rejestru ``app.logic.laws``, które na ten krok pozwalają.
    Krok oparty na dwóch prawach ma dwa slugi — wtedy pokazujemy oba.
    """

    po: str
    prawa: tuple[str, ...]


#: Wyprowadzenie ``(p → q) → ∼r`` do KPN, krok po kroku jak w wykładzie.
KROKI_IMPLIKACJI: tuple[Krok, ...] = (
    Krok(po="(∼p ∨ q) → ∼r", prawa=("definiowanie-implikacji",)),
    Krok(po="∼(∼p ∨ q) ∨ ∼r", prawa=("definiowanie-implikacji",)),
    Krok(po="(p ∧ ∼q) ∨ ∼r", prawa=("de-morgan-1", "podwojne-przeczenie")),
    Krok(po="(p ∨ ∼r) ∧ (∼q ∨ ∼r)", prawa=("rozdzielnosc-2",)),
)

#: Wyprowadzenie ``p ≡ q`` do KPN — krok po kroku jak w wykładzie.
KROKI_ROWNOZNOSCI: tuple[Krok, ...] = (
    Krok(po="(p → q) ∧ (q → p)", prawa=("zastepowanie-rownych",)),
    Krok(po="(∼p ∨ q) ∧ (∼q ∨ p)", prawa=("definiowanie-implikacji",)),
    Krok(po="∼(∼(∼p ∨ q) ∨ ∼(∼q ∨ p))", prawa=("de-morgan-1",)),
)

#: Przykład tautologii z wykładu: w każdej klauzuli jest jakaś para ``x`` i ``∼x``.
PRZYKLAD_TAUTOLOGII = "(p ∨ q ∨ ∼p) ∧ (∼p ∨ q ∨ r ∨ ∼q) ∧ (∼s ∨ s)"

#: Kontrprzykład z wykładu: w żadnej klauzuli nie ma pary ``x`` i ``∼x``.
PRZYKLAD_NIE_TAUTOLOGII = "(p ∨ q) ∧ (∼p ∨ r)"


@dataclass(frozen=True)
class Klauzula:
    """Klauzula gotowa dla szablonu: wzór i pary ``x``/``∼x`` znalezione w środku."""

    wzor: str
    pary: list[str]


def formula_to_html(text: str, styl: str = "wyklad") -> Markup:
    """Zwraca wzór jako bezpieczny HTML z ``formula.to_html``.

    Gdy napis nie jest poprawną formułą, oddajemy go jako zwykły tekst — treść lekcji
    nigdy nie kończy się błędem 500. Wynik wstawiamy w szablonie przez ``|safe``,
    tak samo jak ``app/blueprints/tautologie.py`` i ``formuly.py``.
    """
    try:
        return Markup(to_html(parse(text), styl))
    except FormulaError:
        return escape(text)


def podziel_na_klauzule(node: Node) -> list[Node]:
    """Dzieli formułę w KPN na klauzule: koniunkcja to lista swoich składników.

    Formuła spoza KPN (np. implikacja) nie jest rozbijana — wraca jako jedna klauzula,
    a ``pary_uzupelniajace`` zgłosi wtedy ``FormulaError``.
    """
    if isinstance(node, And):
        return podziel_na_klauzule(node.left) + podziel_na_klauzule(node.right)
    return [node]


def pary_uzupelniajace(klauzula: str | Node) -> list[str]:
    """Zmienne, które w klauzuli stoją raz bez negacji, a raz z negacją.

    Klauzula jest tautologią dokładnie wtedy, gdy ta lista nie jest pusta — stąd
    cały test tautologiczności w KPN. Dla napisu, który nie jest klauzulą, podnosimy
    ``FormulaError``: to błąd treści strony, nie danych użytkownika.
    """
    node = parse(klauzula) if isinstance(klauzula, str) else klauzula
    literals = _literals(node)
    dodatnie = {name for name, bez_negacji in literals if bez_negacji}
    ujemne = {name for name, bez_negacji in literals if not bez_negacji}
    return sorted(dodatnie & ujemne)


def klauzule_i_pary(formula: str) -> list[Klauzula]:
    """Klauzule formuły w KPN razem z parami znalezionymi w każdej z nich."""
    return [
        Klauzula(wzor=to_text(klauzula), pary=pary_uzupelniajace(klauzula))
        for klauzula in podziel_na_klauzule(parse(formula))
    ]


def falsyfikujacy_uklad(formula: str) -> dict[str, bool] | None:
    """Pierwsze wartościowanie, przy którym formuła jest fałszywa.

    ``None`` znaczy, że formuła jest tautologią. Kolejność wartościowań bierzemy
    z ``truth.build``, więc kontrprzykład na stronie zgadza się z tablicą prawdy.
    """
    tabela = truth.build(parse(formula))
    for wiersz in tabela.rows:
        if not wiersz["values"][-1]:
            return {nazwa: wiersz[nazwa] for nazwa in tabela.variables}
    return None


def klauzule_silnika(formula: str) -> dict[str, Any]:
    """Wynik ``simplify.to_cnf`` jako lista klauzul.

    Silnik zwraca cały ślad przekształcenia; lekcja pokazuje tylko jego koniec,
    rozbity na pojedyncze klauzule.
    """
    slad = simplify.to_cnf(formula)
    return {
        "koniec": slad.koniec,
        "klauzule": [to_text(klauzula) for klauzula in podziel_na_klauzule(parse(slad.koniec))],
    }


def kroki_do_widoku(kroki: Sequence[Krok]) -> list[dict[str, Any]]:
    """Przygotowuje kroki dla szablonu: wzór i nazwy praw z rejestru."""
    return [
        {"po": krok.po, "prawa": [_prawo_do_widoku(slug) for slug in krok.prawa]} for krok in kroki
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


def _prawo_do_widoku(slug: str) -> dict[str, str]:
    """Prawo z rejestru jako para ``(slug, nazwa)`` dla szablonu."""
    prawo = laws.get(slug)
    if prawo is None:
        raise RuntimeError(f"Nie ma prawa o slugu {slug!r} w rejestrze.")
    return {"slug": prawo.slug, "nazwa": prawo.nazwa}


def _liczba_wierszy(formula: str) -> int:
    """Liczba wierszy pełnej tablicy prawdy: ``2`` do potęgi liczby zmiennych."""
    return 2 ** len(variables(parse(formula)))


@bp.get("/kpn")
def kpn() -> str:
    """Lekcja: klauzula, KPN, sprowadzanie formuł do KPN i test tautologiczności."""
    return render_template(
        "kpn.html",
        formula_to_html=formula_to_html,
        przyklady_klauzul=PRZYKLADY_KLAUZUL,
        przyklady_kpn=PRZYKLADY_KPN,
        formula_implikacji=FORMULA_IMPLIKACJI,
        kroki_implikacji=kroki_do_widoku(KROKI_IMPLIKACJI),
        formula_rownowaznosci=FORMULA_ROWNOZNOSCI,
        kroki_rownowaznosci=kroki_do_widoku(KROKI_ROWNOZNOSCI),
        przyklad_tautologii=PRZYKLAD_TAUTOLOGII,
        klauzule_tautologii=klauzule_i_pary(PRZYKLAD_TAUTOLOGII),
        tautologia_przykladu=truth.is_tautology(parse(PRZYKLAD_TAUTOLOGII)),
        liczba_wierszy_przykladu=_liczba_wierszy(PRZYKLAD_TAUTOLOGII),
        przyklad_nie_tautologii=PRZYKLAD_NIE_TAUTOLOGII,
        klauzule_nie_tautologii=klauzule_i_pary(PRZYKLAD_NIE_TAUTOLOGII),
        uklad_falsyfikujacy=falsyfikujacy_uklad(PRZYKLAD_NIE_TAUTOLOGII),
        wynik_silnika=klauzule_silnika(FORMULA_IMPLIKACJI),
    )
