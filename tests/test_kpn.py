"""Testy strony ``/kpn`` — klauzul, koniunkcyjnej postaci normalnej i testu tautologii.

Testy nie wierzą stronie na słowo. Wzory porównują z wynikiem ``formula.to_html``,
a nazwy i odnośniki praw — z rejestrem ``app.logic.laws``. Dzięki temu zmiana treści
praw albo wyprowadzenia nie może przejść niezauważona.

Kluczowe kryterium karty sprawdzamy dwoma drogami:

* ``truth.is_tautology`` liczy wynik dla formuły z przykładu i dla kontrprzykładu,
* ta sama reguła liczona lokalnie (para ``x`` i ``∼x`` w każdej klauzuli) musi dać
  ten sam werdykt — inaczej lekcja uczyłaby złej reguły.
"""

from __future__ import annotations

import re
from html import unescape
from pathlib import Path

import pytest
from markupsafe import Markup

from app import create_app
from app.blueprints import kpn
from app.logic import laws, truth
from app.logic.formula import FormulaError, evaluate, parse, to_html

ADRES = "/kpn"

#: Formuły z wykładu, wpisane w teście dosłownie — test ma padać, gdy znikną ze strony.
PRZYKLAD_TAUTOLOGII = "(p ∨ q ∨ ∼p) ∧ (∼p ∨ q ∨ r ∨ ∼q) ∧ (∼s ∨ s)"
PRZYKLAD_NIE_TAUTOLOGII = "(p ∨ q) ∧ (∼p ∨ r)"

#: Nagłówek kolumny z klauzulą na stronie — po nim znajdujemy tabelę testu tautologii.
PODPIS_KLAUZUL = "każdą klauzulę przykładu"

#: Wyrażenie wstawiane do HTML przez filtr ``|safe``.
WZORZEC_SAFE = re.compile(r"\{\{(?P<wyrazenie>.*?)\|\s*safe\s*\}\}", re.DOTALL)

SZABLON = Path(__file__).resolve().parents[1] / "app" / "templates" / "kpn.html"

TABELA = re.compile(r"<table\b[^>]*>(?P<tresc>.*?)</table>", re.DOTALL)
WIERSZ = re.compile(r"<tr>(?P<tresc>.*?)</tr>", re.DOTALL)
KOMORKA = re.compile(r"<t[dh][^>]*>(?P<tresc>.*?)</t[dh]>", re.DOTALL)
SEKCJA_TABELI = re.compile(r"<tbody>(?P<tresc>.*?)</tbody>", re.DOTALL)


@pytest.fixture(scope="module")
def klient():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def html(klient):
    odpowiedz = klient.get(ADRES)
    assert odpowiedz.status_code == 200
    return odpowiedz.get_data(as_text=True)


@pytest.fixture(scope="module")
def tekst(html):
    """Cała strona jako tekst: bez znaczników, z pojedynczymi spacjami."""
    return _tekst(html)


# --- narzędzia ---------------------------------------------------------------


def _tekst(fragment: str) -> str:
    """Zamienia fragment HTML na tekst: usuwa znaczniki, odmienia encje i skleja spacje."""
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment))).strip()


def _wzor_html(wzor: str, styl: str = "wyklad") -> str:
    """Wzór jako HTML z ``formula.to_html`` — to samo, co wstawia strona."""
    return str(kpn.formula_to_html(wzor, styl))


def _wiersze(tabela: str) -> list[list[str]]:
    """Teksty komórek kolejnych wierszy tablicy."""
    tresc = SEKCJA_TABELI.search(tabela).group("tresc")
    return [
        [_tekst(komorka) for komorka in KOMORKA.findall(wiersz)] for wiersz in WIERSZ.findall(tresc)
    ]


def _tabela(html: str, podpis: str) -> str:
    """Treść tablicy, której podpis (``<caption>``) zawiera dany fragment."""
    pasujace = [tresc for tresc in TABELA.findall(html) if podpis in tresc]
    assert len(pasujace) == 1, f"nie znalazłem dokładnie jednej tablicy z {podpis!r}"
    return pasujace[0]


def _pary_z_reguly(formula: str) -> list[bool]:
    """Werdykt reguły z lekcji: czy każda klauzula ma parę ``x`` i ``∼x``."""
    return [bool(klauzula.pary) for klauzula in kpn.klauzule_i_pary(formula)]


# --- szkielet strony ---------------------------------------------------------


def test_strona_odpowiada_200_i_html_utf8(klient):
    odpowiedz = klient.get(ADRES)
    assert odpowiedz.status_code == 200
    typ_tresci = odpowiedz.headers["Content-Type"]
    assert typ_tresci.startswith("text/html")
    assert "charset=utf-8" in typ_tresci.lower()


def test_strona_ma_jezyk_polski_i_dokladnie_jeden_h1(html):
    assert 'lang="pl"' in html
    assert len(re.findall(r"<h1\b", html)) == 1


def test_strona_nie_zostawia_nieuzupelnionych_szablonow(html):
    assert "{{" not in html
    assert "{%" not in html


# --- klauzula ----------------------------------------------------------------


def test_strona_podaje_definicje_klauzuli(tekst):
    assert "klauzula" in tekst.lower()
    assert "alternatywa zmiennych zdaniowych" in tekst
    assert "lista warunków połączonych słowem lub" in tekst


@pytest.mark.parametrize("klauzula", kpn.PRZYKLADY_KLAUZUL)
def test_strona_pokazuje_trzy_klauzule_z_wykladu(html, klauzula):
    assert _wzor_html(klauzula) in html
    assert klauzula in kpn.PRZYKLADY_KLAUZUL


def test_klauzule_z_wykladu_to_trzy_przyklady():
    assert len(kpn.PRZYKLADY_KLAUZUL) == 3


# --- koniunkcyjna postać normalna --------------------------------------------


def test_strona_podaje_definicje_kpn(tekst):
    assert "koniunkcyjna postać normalna" in tekst.lower()
    assert "koniunkcją pewnej liczby klauzul" in tekst


@pytest.mark.parametrize("wzor", kpn.PRZYKLADY_KPN)
def test_strona_pokazuje_oba_przyklady_kpn(html, wzor):
    assert _wzor_html(wzor) in html


def test_przyklady_kpn_to_konjunkcje_klauzul():
    for wzor in kpn.PRZYKLADY_KPN:
        assert len(kpn.podziel_na_klauzule(parse(wzor))) >= 2


# --- wyprowadzenie (p → q) → ∼r ----------------------------------------------


def test_strona_pokazuje_cale_wyprowadzenie_implikacji(html):
    assert _wzor_html(kpn.FORMULA_IMPLIKACJI) in html
    for krok in kpn.KROKI_IMPLIKACJI:
        assert _wzor_html(krok.po) in html, f"brak kroku wyprowadzenia: {krok.po!r}"


def test_wyprowadzenie_implikacji_konczy_sie_wnioskiem_z_karty(html):
    ostatni = kpn.KROKI_IMPLIKACJI[-1].po
    assert ostatni == "(p ∨ ∼r) ∧ (∼q ∨ ∼r)"
    assert _wzor_html(ostatni) in html


def test_wyprowadzenie_implikacji_ma_tyle_krokow_co_wyklad():
    assert [krok.po for krok in kpn.KROKI_IMPLIKACJI] == [
        "(∼p ∨ q) → ∼r",
        "∼(∼p ∨ q) ∨ ∼r",
        "(p ∧ ∼q) ∨ ∼r",
        "(p ∨ ∼r) ∧ (∼q ∨ ∼r)",
    ]


def test_krok_implikacji_rozdzielnosci_powoluje_II_prawo_rozdzielnosci():
    assert kpn.KROKI_IMPLIKACJI[-1].prawa == ("rozdzielnosc-2",)


# --- wyprowadzenie p ≡ q -----------------------------------------------------


def test_strona_pokazuje_wyprowadzenie_rownowaznosci(html):
    assert _wzor_html(kpn.FORMULA_ROWNOZNOSCI) in html
    for krok in kpn.KROKI_ROWNOZNOSCI:
        assert _wzor_html(krok.po) in html, f"brak kroku wyprowadzenia: {krok.po!r}"


def test_wyprowadzenie_rownowaznosci_konczy_sie_wzorem_z_karty(html):
    ostatni = kpn.KROKI_ROWNOZNOSCI[-1].po
    assert ostatni == "∼(∼(∼p ∨ q) ∨ ∼(∼q ∨ p))"
    assert _wzor_html(ostatni) in html


# --- nazwy praw przy krokach -------------------------------------------------


def test_kroki_powoluja_prawa_z_rejestru(html, tekst):
    slugi = {
        slug
        for kroki in (kpn.KROKI_IMPLIKACJI, kpn.KROKI_ROWNOZNOSCI)
        for krok in kroki
        for slug in krok.prawa
    }

    assert slugi, "wyprowadzenia muszą powoływać prawa z rejestru"
    for slug in slugi:
        prawo = laws.get(slug)
        assert prawo is not None, f"krok powołuje prawo spoza rejestru: {slug}"
        assert f'href="/prawa/{slug}"' in html
        assert prawo.nazwa in tekst


def test_kazdy_krok_ma_co_najmniej_jedno_prawo():
    for kroki in (kpn.KROKI_IMPLIKACJI, kpn.KROKI_ROWNOZNOSCI):
        assert all(krok.prawa for krok in kroki)


# --- test tautologiczności ---------------------------------------------------


def test_strona_podaje_regule_testu_tautologicznosci(tekst):
    assert "każdej klauzuli" in tekst
    assert "zmienna zdaniowa i jej negacja" in tekst


def test_strona_pokazuje_przyklad_tautologii(html, tekst):
    assert _wzor_html(PRZYKLAD_TAUTOLOGII) in html
    assert _wzor_html(kpn.PRZYKLAD_TAUTOLOGII) in html
    assert "Formuła jest tautologią" in tekst


def test_truth_mowi_ze_przyklad_jest_tautologia():
    assert truth.is_tautology(parse(PRZYKLAD_TAUTOLOGII)) is True


def test_truth_mowi_ze_kontrprzyklad_nie_jest_tautologia():
    assert truth.is_tautology(parse(PRZYKLAD_NIE_TAUTOLOGII)) is False


def test_regula_z_lekcji_daje_ten_sam_werdykt_co_truth():
    """Reguła z lekcji i ``truth.is_tautology`` muszą się zgadzać w obie strony."""
    for formula, werdykt in ((PRZYKLAD_TAUTOLOGII, True), (PRZYKLAD_NIE_TAUTOLOGII, False)):
        assert all(_pary_z_reguly(formula)) is werdykt
        assert truth.is_tautology(parse(formula)) is werdykt


def test_strona_pokazuje_pary_uzupelniajace_w_klauzulach_tautologii(html):
    wiersze = _wiersze(_tabela(html, PODPIS_KLAUZUL))

    assert [wiersz[0] for wiersz in wiersze] == [
        _tekst(_wzor_html(wzor)) for wzor in ("p ∨ q ∨ ∼p", "∼p ∨ q ∨ r ∨ ∼q", "∼s ∨ s")
    ]
    assert [wiersz[1] for wiersz in wiersze] == ["p", "q", "s"]


# --- kontrprzykład -----------------------------------------------------------


def test_strona_pokazuje_kontrprzyklad_z_wyjasnieniem(html, tekst):
    assert _wzor_html(PRZYKLAD_NIE_TAUTOLOGII) in html
    assert "nie jest tautologią" in tekst
    assert "nie ma pary" in tekst
    assert "∼p" in tekst


def test_kontrprzyklad_ma_klauzule_bez_pary():
    klauzule = kpn.klauzule_i_pary(PRZYKLAD_NIE_TAUTOLOGII)

    assert [klauzula.wzor for klauzula in klauzule] == ["p ∨ q", "∼p ∨ r"]
    assert [klauzula.pary for klauzula in klauzule] == [[], []]


def test_kontrprzyklad_podaje_wartosciowanie_falsyfikujace(html):
    uklad = kpn.falsyfikujacy_uklad(PRZYKLAD_NIE_TAUTOLOGII)

    assert uklad is not None
    assert evaluate(parse(PRZYKLAD_NIE_TAUTOLOGII), uklad) is False
    for nazwa, wartosc in uklad.items():
        assert f"{nazwa} = {1 if wartosc else 0}" in _tekst(html)


# --- dlaczego KPN jest przydatna i wynik silnika -----------------------------


def test_strona_mowi_po_co_jest_kpn(tekst):
    assert "bez wypisywania całej tablicy prawdy" in tekst


def test_klauzule_silnika_dziela_wynik_to_cnf():
    wynik = kpn.klauzule_silnika("(p → q) → ∼r")

    assert wynik["koniec"] == "(p ∨ ∼r) ∧ (∼q ∨ ∼r)"
    assert wynik["klauzule"] == ["p ∨ ∼r", "∼q ∨ ∼r"]


def test_strona_pokazuje_klauzule_z_silnika(html):
    wynik = kpn.klauzule_silnika(kpn.FORMULA_IMPLIKACJI)
    for klauzula in wynik["klauzule"]:
        assert _wzor_html(klauzula) in html


def test_strona_linkuje_do_placu_zabaw_z_formula(html):
    assert 'href="/plac-zabaw?formula=' in html
    assert "cel=cnf" in html


# --- nawigacja i bezpieczeństwo szablonu -------------------------------------


def test_strona_ma_odnosniki_poprzedniej_i_nastepnej_lekcji(html, tekst):
    assert 'href="/przeksztalcanie"' in html
    assert 'href="/prawa"' in html
    assert "Poprzednia lekcja" in tekst
    assert "Następna lekcja" in tekst


def test_szablon_uzywa_safe_tylko_na_wyniku_to_html():
    wyrazenia = [d["wyrazenie"].strip() for d in WZORZEC_SAFE.finditer(SZABLON.read_text("utf-8"))]

    assert wyrazenia, "szablon nie wstawia wzorów przez |safe"
    for wyrazenie in wyrazenia:
        assert "to_html" in wyrazenie, f"|safe na {wyrazenie!r}"


# --- funkcje pomocnicze modułu -----------------------------------------------


def test_formula_to_html_zamienia_zwykly_tekst_bez_bledu():
    wynik = kpn.formula_to_html("to nie jest formuła ((")

    assert isinstance(wynik, Markup)
    assert wynik == "to nie jest formuła (("


def test_formula_to_html_zwraca_html_dla_wzoru():
    assert str(kpn.formula_to_html("∼p")) == str(to_html(parse("∼p")))


def test_podziel_na_klauzule_zwraca_skladniki_koniunkcji():
    klauzule = kpn.podziel_na_klauzule(parse("(p ∨ q) ∧ ∼p ∧ (r ∨ ∼s)"))

    assert [to_html(kl) for kl in klauzule] == [
        to_html(parse("p ∨ q")),
        to_html(parse("∼p")),
        to_html(parse("r ∨ ∼s")),
    ]


def test_podziel_na_klauzule_nie_gubi_pojedynczej_klauzuli():
    assert len(kpn.podziel_na_klauzule(parse("p ∨ ∼q"))) == 1


def test_pary_uzupelniajace_znajduje_zmienna_z_negacja():
    assert kpn.pary_uzupelniajace("p ∨ q ∨ ∼p") == ["p"]
    assert kpn.pary_uzupelniajace("∼p ∨ q ∨ r ∨ ∼q") == ["q"]
    assert kpn.pary_uzupelniajace("∼s ∨ s") == ["s"]
    assert kpn.pary_uzupelniajace("p ∨ q") == []


def test_pary_uzupelniajace_odrzucaja_cos_co_nie_jest_klauzula():
    with pytest.raises(FormulaError):
        kpn.pary_uzupelniajace("p → q")


def test_klauzule_i_pary_zwracaja_tekst_i_pary():
    klauzule = kpn.klauzule_i_pary(PRZYKLAD_NIE_TAUTOLOGII)

    assert [klauzula.wzor for klauzula in klauzule] == ["p ∨ q", "∼p ∨ r"]
    assert [klauzula.pary for klauzula in klauzule] == [[], []]


def test_falsyfikujacy_uklad_dla_tautologii_to_none():
    assert kpn.falsyfikujacy_uklad(PRZYKLAD_TAUTOLOGII) is None


def test_kroki_do_widoku_bierze_nazwy_praw_z_rejestru():
    krok = kpn.Krok(po="∼p ∨ q", prawa=("definiowanie-implikacji",))

    widok = kpn.kroki_do_widoku([krok])

    assert widok == [
        {
            "po": "∼p ∨ q",
            "prawa": [
                {"slug": "definiowanie-implikacji", "nazwa": "Prawo definiowania implikacji"}
            ],
        }
    ]
