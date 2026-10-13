"""Testy tablic prawdy, klasyfikacji i równoważności (PRZ-002)."""

from __future__ import annotations

import json

import pytest

from app.logic.formula import FormulaError, evaluate, parse, subformulas, to_text
from app.logic.truth import (
    MAX_VARIABLES,
    TruthTable,
    build,
    classify,
    counterexample,
    equivalent,
    is_contradiction,
    is_tautology,
    markdown_table,
)


def _wyrazenie(*nazwy: str) -> str:
    """Formuła ``p0 ∨ p1 ∨ …`` — do testów granicy zmiennych."""
    return " ∨ ".join(nazwy)


def _wartosci(formula: str) -> list[bool]:
    """Wartości całej formuły w kolejności wierszy (ostatnia kolumna wynikowa)."""
    return [row["values"][-1] for row in build(parse(formula), with_subformulas=False).rows]


# ---------------------------------------------------------------------------
# Budowa tablicy
# ---------------------------------------------------------------------------


def test_build_dla_p_ma_dokladnie_dwa_wiersze():
    table = build(parse("p"))

    assert isinstance(table, TruthTable)
    assert table.variables == ["p"]
    assert len(table.rows) == 2


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("p ∧ q", [True, False, False, False]),
        ("p ∨ q", [True, True, True, False]),
        ("p → q", [True, False, True, True]),
        ("p ↔ q", [True, False, False, True]),
        ("¬p", [False, True]),
    ],
)
def test_build_wartosci_policzone_recznie(formula, expected):
    assert _wartosci(formula) == expected


@pytest.mark.parametrize("formula", ["p", "p ∧ q", "p ∨ q → r", "p ↔ q", "¬p", "p ∨ ¬p"])
def test_build_pelna_liczba_wierszy(formula):
    table = build(parse(formula))

    assert len(table.rows) == 2 ** len(table.variables)


def test_pierwsza_zmienna_zmienia_sie_najrzadziej():
    table = build(parse("p ∧ q ∧ r"), with_subformulas=False)

    assert [row["p"] for row in table.rows] == [True] * 4 + [False] * 4
    assert [row["q"] for row in table.rows] == [True, True, False, False] * 2
    assert [row["r"] for row in table.rows] == [True, False] * 4


def test_wiersz_ma_klucz_dla_kazdej_zmiennej():
    table = build(parse("p ∧ q"))

    assert all(set(row) == {"p", "q", "values"} for row in table.rows)


# ---------------------------------------------------------------------------
# Kolumny wynikowe
# ---------------------------------------------------------------------------


def test_bez_podformul_jest_jedna_kolumna():
    formula = parse("p ∨ ¬p")
    table = build(formula, with_subformulas=False)

    assert table.columns == [to_text(formula)]
    assert all(len(row["values"]) == 1 for row in table.rows)


def test_z_podformulami_kolumny_to_kazda_podformula():
    formula = parse("p ∨ ¬p")
    table = build(formula, with_subformulas=True)

    assert table.columns == [to_text(part) for part in subformulas(formula)]
    assert len(set(table.columns)) == len(table.columns)
    assert table.columns[-1] == to_text(formula)


def test_kolumny_w_kolejnosci_od_najmniejszej():
    # Karta: „kolumny wynikowe to kolejne podformuły, od najkrótszej do całej formuły”.
    formula = parse("¬(p ∧ q)")
    columns = build(formula).columns

    assert columns == [to_text(part) for part in subformulas(formula)]
    assert len(columns) == 4  # p, q, p ∧ q oraz cała formuła
    assert columns[-1] == to_text(formula)


def test_build_ustala_klasyfikacje():
    assert build(parse("p ∨ ¬p")).classification == "tautologia"
    assert build(parse("p ∧ ¬p")).classification == "kontrtautologia"
    assert build(parse("p ∧ q")).classification == "spełnialna"


def test_to_dict_jest_gotowe_na_json():
    dane = build(parse("p ∧ q")).to_dict()

    assert set(dane) == {"variables", "columns", "rows", "classification"}
    assert dane["variables"] == ["p", "q"]
    assert dane["rows"][0]["p"] is True
    assert dane["classification"] == "spełnialna"
    assert json.loads(json.dumps(dane)) == dane  # wartości jako true/false, nie True/False


def test_to_dict_nie_udostepnia_wewnetrznych_list():
    table = build(parse("p"))
    dane = table.to_dict()

    dane["rows"].append({})
    dane["variables"].append("x")

    assert len(table.to_dict()["rows"]) == 2
    assert table.variables == ["p"]


# ---------------------------------------------------------------------------
# Granica liczby zmiennych i nazwa zarezerwowana
# ---------------------------------------------------------------------------


def test_szesc_zmiennych_dziala():
    formula = parse(_wyrazenie(*[f"p{i}" for i in range(6)]))
    table = build(formula, with_subformulas=False)

    assert len(table.variables) == MAX_VARIABLES
    assert len(table.rows) == 2**MAX_VARIABLES


def test_siedem_zmiennych_to_blad():
    formula = parse(_wyrazenie(*[f"p{i}" for i in range(7)]))

    with pytest.raises(FormulaError) as blad:
        build(formula)

    assert str(MAX_VARIABLES) in str(blad.value)


def test_rownowaznosc_siedmiu_zmiennych_tez_jest_odrzucana():
    formula = parse(_wyrazenie(*[f"p{i}" for i in range(7)]))

    with pytest.raises(FormulaError):
        equivalent(formula, parse("p0"))


def test_nazwa_values_jest_zarezerwowana():
    with pytest.raises(FormulaError) as blad:
        build(parse("values ∧ p"))

    assert "values" in str(blad.value)


# ---------------------------------------------------------------------------
# Klasyfikacja
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("p ∨ ¬p", "tautologia"),
        ("(p → q) ↔ (¬q → ¬p)", "tautologia"),
        ("p ∧ ¬p", "kontrtautologia"),
        ("p ∧ q", "spełnialna"),
    ],
)
def test_classify(formula, expected):
    assert classify(parse(formula)) == expected


def test_is_tautology_i_is_contradiction():
    assert is_tautology(parse("p ∨ ¬p")) is True
    assert is_tautology(parse("p ∧ q")) is False
    assert is_contradiction(parse("p ∧ ¬p")) is True
    assert is_contradiction(parse("p ∨ q")) is False


# ---------------------------------------------------------------------------
# Równoważność i kontrprzykład
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("p → q", "¬p ∨ q"),
        ("¬(p ∧ q)", "¬p ∨ ¬q"),
    ],
)
def test_equivalent_prawda(left, right):
    assert equivalent(parse(left), parse(right))
    assert counterexample(parse(left), parse(right)) is None


def test_equivalent_falsz():
    assert not equivalent(parse("p ∧ q"), parse("p ∨ q"))


def test_counterexample_naprawde_rozni_formuly():
    lewa, prawa = parse("p ∧ q"), parse("p ∨ q")
    env = counterexample(lewa, prawa)

    assert env is not None
    assert set(env) == {"p", "q"}
    assert evaluate(lewa, env) != evaluate(prawa, env)


def test_counterexample_to_pierwsze_przypisanie_rozniace():
    # Wiersze od samych jedynek: (1,1) daje 1 i 1 (równe), (1,0) daje 0 i 1 — pierwsza różnica.
    assert counterexample(parse("p ∧ q"), parse("p ∨ q")) == {"p": True, "q": False}


def test_counterexample_dopisuje_zmienne_z_obu_formul():
    assert counterexample(parse("p"), parse("p ∧ q")) == {"p": True, "q": False}


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def test_markdown_table_ma_naglowek_separator_i_wiersze():
    formula = parse("p ∧ q")
    linie = markdown_table(build(formula, with_subformulas=False)).splitlines()

    assert linie[0] == f"| p | q | {to_text(formula)} |"
    assert linie[1] == "|---|---|---|"
    assert len(linie) == 2 + 4
    assert linie[2] == "| 1 | 1 | 1 |"
    assert linie[3] == "| 1 | 0 | 0 |"
    assert linie[5] == "| 0 | 0 | 0 |"


def test_markdown_table_z_podformulami_ma_kolumny_podformul():
    formula = parse("(p ∨ q) ∧ p")
    naglowek = markdown_table(build(formula)).splitlines()[0]

    assert naglowek.startswith("| p | q | ")
    assert to_text(parse("p ∨ q")) in naglowek
    assert naglowek.endswith(f"| {to_text(formula)} |")


def test_markdown_table_tautologia_ma_same_jedynki():
    linie = markdown_table(build(parse("p ∨ ¬p"), with_subformulas=False)).splitlines()

    assert linie[2].endswith("| 1 |")
    assert linie[3].endswith("| 1 |")
