"""Testy praw dodatkowych (``app.logic.laws_data.dodatkowe``).

Prawa dodatkowe nie należą do listy T1–T14 (decyzje D16 i D17). Testy pilnują
trzech rzeczy: treść spełnia kontrakt ``Law``, kategoria ``dodatkowe`` nie miesza
się z czternastoma prawami katalogu, a wzory i formuły z treści są tautologiami.
"""

from __future__ import annotations

import pytest

from app.logic import formula, truth
from app.logic.laws import all_laws, by_category, validate
from app.logic.laws_data import dodatkowe

#: Slugi praw dodatkowych w kolejności z tabeli karty PRZ-024.
DODATKOWE = (
    "idempotencja-alternatywy",
    "idempotencja-koniunkcji",
    "podstawianie",
)

#: Czternaście praw katalogu T1–T14 z ``docs/TRESC-PRAW.md``.
KATALOG_T1_T14 = (
    "wylaczony-srodek",
    "identycznosci",
    "podwojne-przeczenie",
    "definiowanie-implikacji",
    "kontrapozycji",
    "lacznosc-alternatywy",
    "lacznosc-koniunkcji",
    "rozdzielnosc-1",
    "rozdzielnosc-2",
    "przemiennosc-alternatywy",
    "przemiennosc-koniunkcji",
    "de-morgan-1",
    "de-morgan-2",
    "zastepowanie-rownych",
)

#: Minimalna długość pola ``po_ludzku`` wymagana przez ``docs/TRESC-PRAW.md``.
MIN_DLUGOSC_PO_LUDZKU = 80


def _equivalent(lewa: str, prawa: str) -> bool:
    """Czy dwie formuły z treści praw są równoważne. Parsuje oba napisy."""
    return truth.equivalent(formula.parse(lewa), formula.parse(prawa))


# ---------------------------------------------------------------------------
# Rejestr praw: kategoria ``dodatkowe``
# ---------------------------------------------------------------------------


def test_modul_wystawia_trzy_prawa_dodatkowe():
    assert len(dodatkowe.LAWS) == 3
    assert tuple(prawo.slug for prawo in dodatkowe.LAWS) == DODATKOWE


def test_by_category_zwraca_trzy_prawa_dodatkowe():
    prawa = by_category()["dodatkowe"]
    assert len(prawa) == 3
    assert [prawo.slug for prawo in prawa] == list(DODATKOWE)
    assert all(prawo.kategoria == "dodatkowe" for prawo in prawa)


def test_kategoria_dodatkowe_jest_akceptowana_bez_zmian_w_rejestrze():
    """``laws.py`` nie narzuca listy kategorii — walidacja ma być czysta."""
    assert validate() == []


def test_all_laws_ma_czternascie_praw_katalogu_i_trzy_dodatkowe():
    prawa = all_laws()
    katalog = [prawo for prawo in prawa if prawo.kategoria != "dodatkowe"]
    dodatkowe_prawa = [prawo for prawo in prawa if prawo.kategoria == "dodatkowe"]
    assert len(katalog) == 14
    assert {prawo.slug for prawo in katalog} == set(KATALOG_T1_T14)
    assert len(dodatkowe_prawa) == 3


def test_prawa_dodatkowe_stoja_na_koncu_listy():
    """Moduł ma ``kolejnosc = 101``, więc nie wchodzi w numerację T1–T14."""
    slugi = [prawo.slug for prawo in all_laws()]
    assert slugi[-3:] == list(DODATKOWE)


# ---------------------------------------------------------------------------
# Formuły praw dodatkowych
# ---------------------------------------------------------------------------


def test_lewa_i_prawa_kazdego_prawa_dodatkowego_sa_rownowazne():
    for prawo in dodatkowe.LAWS:
        assert _equivalent(prawo.lewa, prawo.prawa), f"{prawo.slug}: strony nie są równoważne"


def test_formula_kazdego_prawa_dodatkowego_jest_tautologia():
    for prawo in dodatkowe.LAWS:
        wzor = formula.parse(prawo.formula)
        assert truth.is_tautology(wzor), f"{prawo.slug}: wzór {prawo.formula} nie jest tautologią"
        formula.parse(prawo.formula_ascii)


@pytest.mark.parametrize("wzor", ["(p ∨ p) ≡ p", "(p ∧ p) ≡ p"])
def test_idempotencja_jest_tautologia(wzor: str):
    assert truth.is_tautology(formula.parse(wzor))


def test_formula_ascii_idempotencji_jest_rownowazna_formule_wykladu():
    for prawo in dodatkowe.LAWS:
        assert _equivalent(prawo.formula, prawo.formula_ascii), (
            f"{prawo.slug}: zapis ASCII nie zgadza się z zapisem wykładu"
        )


# ---------------------------------------------------------------------------
# Treść praw dodatkowych
# ---------------------------------------------------------------------------


def test_kazde_prawo_dodatkowe_ma_pelna_tresc():
    for prawo in dodatkowe.LAWS:
        where = prawo.slug
        assert prawo.kategoria == "dodatkowe", f"{where}: zła kategoria"
        assert prawo.przyklad.strip(), f"{where}: brak przykładu"
        assert len(prawo.po_ludzku) >= MIN_DLUGOSC_PO_LUDZKU, f"{where}: krótkie 'po_ludzku'"
        assert 3 <= len(prawo.kroki) <= 6, f"{where}: kroków jest {len(prawo.kroki)}"
        assert 2 <= len(prawo.czeste_bledy) <= 3, f"{where}: zła liczba częstych błędów"
        assert 2 <= len(prawo.quiz) <= 3, f"{where}: zła liczba pytań quizu"


def test_kroki_praw_dodatkowych_koncza_sie_na_prawej_stronie():
    for prawo in dodatkowe.LAWS:
        assert prawo.kroki[0].reguła == "założenie", f"{prawo.slug}: pierwszy krok bez założenia"
        assert prawo.kroki[-1].po == prawo.prawa, f"{prawo.slug}: ostatni krok nie kończy na prawa"
        for krok in prawo.kroki:
            assert _equivalent(krok.przed, krok.po), (
                f"{prawo.slug}: krok „{krok.opis}” nie jest równoważny"
            )


def test_pytania_quizy_praw_dodatkowych_maja_poprawny_indeks():
    for prawo in dodatkowe.LAWS:
        for numer, pytanie in enumerate(prawo.quiz, start=1):
            where = f"{prawo.slug}, pytanie {numer}"
            assert 3 <= len(pytanie["opcje"]) <= 4, f"{where}: zła liczba odpowiedzi"
            assert 0 <= pytanie["poprawna"] < len(pytanie["opcje"]), f"{where}: zły indeks"
