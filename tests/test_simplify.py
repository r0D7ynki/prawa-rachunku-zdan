"""Testy silnika przekształceń ze śladem kroków (PRZ-006)."""

from __future__ import annotations

import json

import pytest

from app.logic import simplify as silnik
from app.logic.formula import And, FormulaError, Not, Or, Var, parse, same, to_text
from app.logic.simplify import (
    Trace,
    equivalence_steps,
    simplify,
    to_cnf,
    to_dnf,
    to_nnf,
)
from app.logic.truth import equivalent

# ---------------------------------------------------------------------------
# Pomocnicze sprawdzenia kształtu drzewa
# ---------------------------------------------------------------------------


def _rozplatanie(node, typ):
    """Argumenty zagnieżdżonych węzłów danego typu, np. a ∧ b ∧ c → [a, b, c]."""
    if isinstance(node, typ):
        return _rozplatanie(node.left, typ) + _rozplatanie(node.right, typ)
    return [node]


def _litera(node) -> bool:
    """Zmienna albo zaprzeczona zmienna."""
    return isinstance(node, Var) or (isinstance(node, Not) and isinstance(node.child, Var))


def _koninkcja_literalow(node) -> bool:
    return all(_litera(czesc) for czesc in _rozplatanie(node, And))


def _alternatywa_literalow(node) -> bool:
    return all(_litera(czesc) for czesc in _rozplatanie(node, Or))


def _czy_nnf(node) -> bool:
    """Tylko ∼, ∧, ∨, a każde ∼ stoi bezpośrednio na zmiennej."""
    if isinstance(node, Var):
        return True
    if isinstance(node, Not):
        return isinstance(node.child, Var)
    if isinstance(node, (And, Or)):
        return _czy_nnf(node.left) and _czy_nnf(node.right)
    return False


def _czy_dnf(node) -> bool:
    return all(_koninkcja_literalow(czesc) for czesc in _rozplatanie(node, Or))


def _czy_cnf(node) -> bool:
    return all(_alternatywa_literalow(czesc) for czesc in _rozplatanie(node, And))


def _koniec(trace: Trace):
    return parse(trace.koniec)


# ---------------------------------------------------------------------------
# NNF
# ---------------------------------------------------------------------------


def test_to_nnf_de_morgan():
    trace = to_nnf("¬(p ∧ q)")

    assert trace.forma == "NNF"
    assert len(trace.kroki) >= 1
    assert same(_koniec(trace), parse("¬p ∨ ¬q"))
    assert _czy_nnf(_koniec(trace))


def test_to_nnf_kazdy_krok_ma_prawo():
    trace = to_nnf("¬(p ∧ q)")

    assert any(krok.reguła == "de-morgan-2" for krok in trace.kroki)


def test_to_nnf_z_implikacja_i_rownowaznoscia():
    trace = to_nnf("¬(p ↔ q) ∨ (r → s)")

    assert trace.forma == "NNF"
    assert _czy_nnf(_koniec(trace))
    reguły = {krok.reguła for krok in trace.kroki}
    assert "zastepowanie-rownych" in reguły
    assert "definiowanie-implikacji" in reguły


def test_to_nnf_podwojne_przeczenie():
    trace = to_nnf("¬¬¬p")

    assert same(_koniec(trace), parse("¬p"))
    assert any(krok.reguła == "podwojne-przeczenie" for krok in trace.kroki)


def test_to_nnf_formula_bez_zmian_nie_ma_krokow():
    trace = to_nnf("p ∧ ¬q")

    assert trace.kroki == []
    assert trace.start == trace.koniec


# ---------------------------------------------------------------------------
# DNF i CNF
# ---------------------------------------------------------------------------


def test_to_dnf_rozdzielnosc():
    trace = to_dnf("p ∧ (q ∨ r)")

    assert trace.forma == "DNF"
    assert same(_koniec(trace), parse("(p ∧ q) ∨ (p ∧ r)"))
    assert _czy_dnf(_koniec(trace))
    assert any(krok.reguła == "rozdzielnosc-1" for krok in trace.kroki)


def test_to_dnf_z_implikacja():
    trace = to_dnf("p → (q ∨ r)")

    assert trace.forma == "DNF"
    assert _czy_dnf(_koniec(trace))
    assert equivalent(_koniec(trace), parse("(¬p ∨ q) ∨ r"))


def test_to_cnf_rozdzielnosc():
    trace = to_cnf("p ∨ (q ∧ r)")

    assert trace.forma == "CNF"
    assert same(_koniec(trace), parse("(p ∨ q) ∧ (p ∨ r)"))
    assert _czy_cnf(_koniec(trace))
    assert any(krok.reguła == "rozdzielnosc-2" for krok in trace.kroki)


def test_to_cnf_de_morgan_i_rozdzielnosc():
    trace = to_cnf("¬(p ∧ q) ∨ r")

    assert trace.forma == "CNF"
    assert _czy_cnf(_koniec(trace))
    assert equivalent(_koniec(trace), parse("¬p ∨ ¬q ∨ r"))


def test_dnf_i_cnf_sa_rownowazne_wejściu():
    for tekst, wynik in [
        ("p ∧ (q ∨ r)", to_dnf("p ∧ (q ∨ r)")),
        ("p ∨ (q ∧ r)", to_cnf("p ∨ (q ∧ r)")),
    ]:
        assert equivalent(parse(tekst), _koniec(wynik))


# ---------------------------------------------------------------------------
# simplify: cel i typ wejścia
# ---------------------------------------------------------------------------


def test_simplify_nnf_z_implikacji():
    trace = simplify("p → q", "nnf")

    assert same(_koniec(trace), parse("¬p ∨ q"))
    assert any(krok.reguła == "definiowanie-implikacji" for krok in trace.kroki)


def test_simplify_przyjmuje_drzewo():
    drzewo = parse("p → q")

    assert simplify(drzewo, "nnf").koniec == simplify("p → q", "nnf").koniec


def test_simplify_bledny_tekst_podnosi_blad_parsera():
    with pytest.raises(FormulaError) as blad:
        simplify("p ∧ ", "nnf")

    assert "koniec" in str(blad.value).lower()


def test_simplify_nieznany_cel():
    with pytest.raises(FormulaError) as blad:
        simplify("p", "dnf-wiekszy")

    assert "dnf-wiekszy" in str(blad.value)


def test_simplify_auto_dla_malej_formuly_daje_dnf():
    assert simplify("p ∧ (q ∨ r)", "auto").forma == "DNF"


def test_simplify_auto_dla_pieciu_zmiennych_konczy_na_nnf():
    trace = simplify("p → (q ∨ r ∨ s ∨ t ∨ u)", "auto")

    assert trace.forma == "NNF"
    assert len(trace.kroki) <= 60
    assert _czy_nnf(_koniec(trace))


def test_simplify_za_duzo_zmiennych_to_blad():
    with pytest.raises(FormulaError) as blad:
        to_nnf("p ∨ q ∨ r ∨ s ∨ t ∨ u ∨ w")

    assert "6" in str(blad.value)


# ---------------------------------------------------------------------------
# Sprawdzenie każdego kroku
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tekst", ["p → q", "¬(p ∧ q)", "p ↔ q", "p ∧ (q ∨ r)", "p ∨ (q ∧ r)"])
@pytest.mark.parametrize("cel", ["nnf", "dnf", "cnf"])
def test_kazdy_krok_jest_pelen_i_rownowazny(tekst, cel):
    trace = simplify(tekst, cel)

    for krok in trace.kroki:
        assert krok.opis.strip()
        assert krok.reguła.strip()
        assert krok.nazwa.strip()
        assert krok.przed.strip()
        assert krok.po.strip()
        assert krok.wyjaśnienie.strip()
        assert krok.pozycja.strip()
        assert equivalent(parse(krok.przed), parse(krok.po))


def test_kroki_tworza_lancuch_od_startu_do_konca():
    trace = to_nnf("p ↔ q")

    assert trace.kroki[0].przed == trace.start
    assert trace.kroki[-1].po == trace.koniec
    for poprzedni, nastepny in zip(trace.kroki, trace.kroki[1:], strict=False):
        assert poprzedni.po == nastepny.przed


def test_zepsuty_krok_jest_wykrywany(monkeypatch):
    def zepsute_przeksztalcenie(kind, node):
        return Var("q")  # nie zachowuje równoważności

    monkeypatch.setattr(silnik, "_rewrite", zepsute_przeksztalcenie)

    with pytest.raises(FormulaError) as blad:
        to_nnf("¬(p ∧ q)")

    assert "błąd silnika" in str(blad.value)


def test_limit_krokow_konczy_prace_z_forma_uproszczona():
    trace = simplify("p → (q → r)", "nnf", max_krokow=1)

    assert len(trace.kroki) == 1
    assert trace.forma == "uproszczona"


# ---------------------------------------------------------------------------
# Przemienność, idempotencja, słownik śladu
# ---------------------------------------------------------------------------


def test_porzadkowanie_argumentow():
    trace = to_nnf("q ∨ p")

    assert any(krok.reguła == "przemiennosc-alternatywy" for krok in trace.kroki)
    assert to_text(_koniec(trace)) == "p ∨ q"


@pytest.mark.skipif(
    silnik._law_name("idempotencja-alternatywy", "") == "",
    reason="prawa idempotencji dochodzą w PRZ-024",
)
def test_idempotencja_usuwa_powtorzony_argument():
    trace = to_nnf("p ∨ p")

    assert same(_koniec(trace), parse("p"))
    assert any(krok.reguła == "idempotencja-alternatywy" for krok in trace.kroki)


def test_to_dict_jest_gotowe_na_json():
    trace = to_nnf("¬(p ∧ q)")
    dane = trace.to_dict()

    assert set(dane) == {"start", "kroki", "koniec", "forma"}
    assert set(dane["kroki"][0]) == {
        "opis",
        "reguła",
        "nazwa",
        "przed",
        "po",
        "wyjaśnienie",
        "pozycja",
    }
    assert json.loads(json.dumps(dane)) == dane


# ---------------------------------------------------------------------------
# equivalence_steps
# ---------------------------------------------------------------------------


def test_equivalence_steps_dochodzi_do_prawej():
    trace = equivalence_steps("p → q", "¬p ∨ q")

    assert equivalent(_koniec(trace), parse("¬p ∨ q"))
    assert trace.start == to_text(parse("p → q"))


def test_equivalence_steps_dla_nierownowaznych_podnosi_blad():
    with pytest.raises(FormulaError) as blad:
        equivalence_steps("p", "q")

    assert "równoważne" in str(blad.value)


def test_equivalence_steps_wybiera_krotszy_slad():
    krotki = equivalence_steps("p → q", "¬p ∨ q")
    dlugi = equivalence_steps("p → q", "(p ∧ q) ∨ (¬p ∧ q) ∨ (¬p ∧ ¬q)")

    assert len(krotki.kroki) <= len(dlugi.kroki)
