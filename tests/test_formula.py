"""Testy parsera, wypisywania i właściwości formuł (PRZ-001)."""

from __future__ import annotations

import itertools

import pytest

from app.logic.formula import (
    And,
    FormulaError,
    Iff,
    Imp,
    Not,
    Or,
    Var,
    depth,
    evaluate,
    normalize,
    parse,
    replace,
    same,
    size,
    subformulas,
    to_html,
    to_text,
    variables,
)

# ---------------------------------------------------------------------------
# Parsowanie: zapisy operatorów
# ---------------------------------------------------------------------------


def test_parse_zmienna():
    assert parse("p") == Var("p")
    assert parse("deszcz") == Var("deszcz")
    assert parse("p_1") == Var("p_1")


@pytest.mark.parametrize("tekst", ["¬p", "~p", "!p", "not p"])
def test_negacja_wszystkie_zapisy(tekst):
    assert parse(tekst) == Not(Var("p"))


@pytest.mark.parametrize("tekst", ["p ∧ q", "p & q", "p ^ q", "p and q"])
def test_koniunkcja_wszystkie_zapisy(tekst):
    assert parse(tekst) == And(Var("p"), Var("q"))


@pytest.mark.parametrize("tekst", ["p ∨ q", "p | q", "p + q", "p or q"])
def test_alternatywa_wszystkie_zapisy(tekst):
    assert parse(tekst) == Or(Var("p"), Var("q"))


@pytest.mark.parametrize("tekst", ["p → q", "p -> q", "p => q", "p implies q"])
def test_implikacja_wszystkie_zapisy(tekst):
    assert parse(tekst) == Imp(Var("p"), Var("q"))


@pytest.mark.parametrize("tekst", ["p ↔ q", "p <-> q", "p <=> q", "p iff q"])
def test_rownowaznosc_wszystkie_zapisy(tekst):
    assert parse(tekst) == Iff(Var("p"), Var("q"))


def test_spacje_i_wciecia_sa_pomijane():
    assert parse("  p   ∧\n\tq  ") == And(Var("p"), Var("q"))


def test_nawiasy_nie_zmieniaja_drzewa():
    assert parse("(p)") == Var("p")
    assert parse("((p ∧ q))") == And(Var("p"), Var("q"))


# ---------------------------------------------------------------------------
# Parsowanie: kolejność wiązania
# ---------------------------------------------------------------------------


def test_implikacja_wiaze_prawostronnie():
    assert parse("p → q → r") == Imp(Var("p"), Imp(Var("q"), Var("r")))


def test_kolejnosc_wiazania_operatorow():
    assert parse("p ∨ q ∧ r") == Or(Var("p"), And(Var("q"), Var("r")))
    assert parse("p ∧ q ∨ r") == Or(And(Var("p"), Var("q")), Var("r"))
    assert parse("p ∧ q → r") == Imp(And(Var("p"), Var("q")), Var("r"))


def test_negacja_wiaze_najmocniej():
    assert parse("¬p ∧ q") == And(Not(Var("p")), Var("q"))
    assert parse("¬¬p") == Not(Not(Var("p")))
    assert parse("¬(p ∧ q)") == Not(And(Var("p"), Var("q")))


def test_rownowaznosc_wiaze_najslabiej():
    assert parse("p ↔ q → r") == Iff(Var("p"), Imp(Var("q"), Var("r")))
    assert parse("p → q ↔ r") == Iff(Imp(Var("p"), Var("q")), Var("r"))


# ---------------------------------------------------------------------------
# Parsowanie: błędy
# ---------------------------------------------------------------------------


def test_pusty_tekst_to_blad():
    with pytest.raises(FormulaError) as blad:
        parse("   ")
    assert "pusta" in str(blad.value)


def test_brakujacy_nawias_to_blad():
    with pytest.raises(FormulaError) as blad:
        parse("(p ∧ q")
    assert "nawias" in str(blad.value)
    assert "1" in str(blad.value)


def test_nieoczekiwany_nawias_zamykajacy_to_blad():
    with pytest.raises(FormulaError) as blad:
        parse("p ∧ q)")
    assert ")" in str(blad.value)


def test_nieznany_znak_to_blad():
    with pytest.raises(FormulaError) as blad:
        parse("p @ q")
    assert "Nieznany znak" in str(blad.value)
    assert "@" in str(blad.value)


def test_brakujacy_argument_to_blad():
    with pytest.raises(FormulaError) as blad:
        parse("p ∧ )")
    assert "brakuje" in str(blad.value).lower()

    with pytest.raises(FormulaError) as blad:
        parse("∧ p")
    assert "brakuje" in str(blad.value).lower()


def test_nieoczekiwany_koniec_formuly_to_blad():
    with pytest.raises(FormulaError) as blad:
        parse("p ∧ q →")
    assert "koniec" in str(blad.value).lower()


def test_brakuje_operatora_miedzy_formulami():
    with pytest.raises(FormulaError) as blad:
        parse("p q")
    assert "operatora" in str(blad.value)


def test_formula_error_jest_value_error():
    assert issubclass(FormulaError, ValueError)
    with pytest.raises(ValueError):
        parse("")


# ---------------------------------------------------------------------------
# Wypisywanie
# ---------------------------------------------------------------------------


def test_to_text_unicode():
    assert to_text(parse("p → q ∧ ¬r")) == "p → q ∧ ¬r"


def test_to_text_ascii():
    assert to_text(parse("p → q ∧ ¬r"), "ascii") == "p -> q & ~r"


def test_to_text_latex():
    assert to_text(parse("p → q ∧ ¬r"), "latex") == r"p \to q \land \neg r"


def test_to_text_nieznany_styl_to_blad():
    with pytest.raises(FormulaError) as blad:
        to_text(parse("p"), "xml")
    assert "xml" in str(blad.value)


def test_nawiasy_tylko_gdy_zmieniaja_sens():
    assert to_text(parse("(p ∧ q) ∨ r")) == "p ∧ q ∨ r"
    assert to_text(parse("p ∧ (q ∨ r)")) == "p ∧ (q ∨ r)"
    assert to_text(parse("(¬p) ∧ q")) == "¬p ∧ q"
    assert to_text(parse("¬(p ∧ q)")) == "¬(p ∧ q)"
    assert to_text(parse("(p → q) → r")) == "(p → q) → r"
    assert to_text(parse("p → (q → r)")) == "p → q → r"


@pytest.mark.parametrize(
    "tekst",
    [
        "p",
        "¬p",
        "¬¬p",
        "p ∧ q",
        "p ∨ q → r",
        "¬(p ∧ q) ∨ ¬r",
        "p → q → r",
        "(p → q) → r",
        "p ↔ q ∧ ¬r",
        "p ∧ (q ∧ r)",
        "(p ∨ q) ∧ (r ∨ s)",
    ],
)
def test_tekst_parsuje_sie_z_powrotem_do_tego_samego_drzewa(tekst):
    formula = parse(tekst)
    assert parse(to_text(formula)) == formula


def test_to_html_operatory_w_span():
    wynik = to_html(parse("¬p ∧ (q ∨ r)"))
    assert wynik == (
        '<span class="op">¬</span>p <span class="op">∧</span> (q <span class="op">∨</span> r)'
    )


def test_to_html_escapuje_znaki_z_wejscia():
    assert to_html(Var("<script>alert(1)</script>")) == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert to_html(Not(Var('a"b&c'))) == '<span class="op">¬</span>a&quot;b&amp;c'


# ---------------------------------------------------------------------------
# Właściwości drzewa
# ---------------------------------------------------------------------------


def test_variables_posortowane_bez_powtorzen():
    assert variables(parse("q ∧ (p ∨ q) ∧ ¬r")) == ["p", "q", "r"]
    assert variables(parse("p")) == ["p"]


def test_size_liczy_wystapienia_zmiennych():
    assert size(parse("p")) == 1
    assert size(parse("¬¬p")) == 1
    assert size(parse("p ∧ (q ∨ p)")) == 3


def test_depth_liczy_poziomy():
    assert depth(parse("p")) == 1
    assert depth(parse("¬¬p")) == 3
    assert depth(parse("p ∧ q")) == 2
    assert depth(parse("p ∧ (q ∨ ¬r)")) == 4


def test_subformulas_bez_powtorzen_od_najmniejszej():
    formula = parse("p ∧ (q ∨ p)")
    assert subformulas(formula) == [Var("p"), Var("q"), Or(Var("q"), Var("p")), formula]

    # Kolejność rośnie z liczbą liści, a nie tylko „dzieci przed rodzicem”:
    # samo przejście drzewa dałoby [p, q, p ∧ q, r, (p ∧ q) ∨ r].
    wieksza = parse("(p ∧ q) ∨ r")
    assert subformulas(wieksza) == [
        Var("p"),
        Var("q"),
        Var("r"),
        And(Var("p"), Var("q")),
        wieksza,
    ]
    assert len(subformulas(wieksza)) == len(set(subformulas(wieksza)))


def test_replace_podmienia_kazde_wystapienie():
    formula = parse("p ∧ (q ∨ p)")
    assert replace(formula, Var("p"), Var("r")) == parse("r ∧ (q ∨ r)")
    assert replace(formula, Or(Var("q"), Var("p")), Var("s")) == And(Var("p"), Var("s"))
    assert replace(formula, Var("z"), Var("r")) == formula


def test_normalize_ustawia_stala_kolejnosc_stron():
    assert normalize(parse("q ∧ p")) == normalize(parse("p ∧ q"))
    assert normalize(parse("q ∨ p")) == normalize(parse("p ∨ q"))
    assert normalize(parse("¬q ∧ p")) == normalize(parse("p ∧ ¬q"))
    assert to_text(normalize(parse("q ∧ p"))) == "p ∧ q"


def test_normalize_nie_rusza_implikacji():
    assert normalize(parse("q → p")) == parse("q → p")
    assert normalize(parse("p → q")) != normalize(parse("q → p"))


def test_same_porownuje_po_normalize():
    assert same(parse("p ∧ q"), parse("q ∧ p"))
    assert same(parse("(p ∧ q) ∧ r"), parse("r ∧ (p ∧ q)"))
    assert same(parse("p ∨ (q ∨ p)"), parse("(p ∨ q) ∨ p"))
    assert not same(parse("p → q"), parse("q → p"))
    assert not same(parse("p ∧ q"), parse("p ∨ q"))


# ---------------------------------------------------------------------------
# Wartości logiczne
# ---------------------------------------------------------------------------


def test_evaluate_pelne_przypisanie():
    formula = parse("p → q")
    assert evaluate(formula, {"p": True, "q": True}) is True
    assert evaluate(formula, {"p": True, "q": False}) is False
    assert evaluate(formula, {"p": False, "q": False}) is True


def test_evaluate_rownowaznosc():
    formula = parse("p ↔ q")
    assert evaluate(formula, {"p": True, "q": True}) is True
    assert evaluate(formula, {"p": True, "q": False}) is False


def test_evaluate_brak_wartosci_zmiennej_to_blad():
    with pytest.raises(FormulaError) as blad:
        evaluate(parse("p ∧ q"), {"p": True})
    assert "q" in str(blad.value)


def test_implikacja_z_koniunkcja_i_negacja_osem_przypisan():
    """Tabela policzona ręcznie dla ``p → (q ∧ ¬r)``.

    p q r | ¬r | q ∧ ¬r | p → (q ∧ ¬r)
    F F F |  T |   F    |      T
    F F T |  F |   F    |      T
    F T F |  T |   T    |      T
    F T T |  F |   F    |      T
    T F F |  T |   F    |      F
    T F T |  F |   F    |      F
    T T F |  T |   T    |      T
    T T T |  F |   F    |      F
    """
    formula = parse("p → (q ∧ ¬r)")
    oczekiwane = [True, True, True, True, False, False, True, False]
    wyniki = [
        evaluate(formula, dict(zip(("p", "q", "r"), wartosci, strict=True)))
        for wartosci in itertools.product([False, True], repeat=3)
    ]
    assert wyniki == oczekiwane
