"""Testy strony ``/formuly`` — języka rachunku zdań i wartościowania.

Testy nie wierzą stronie na słowo: wartości w tablicach liczą od nowa przez
``app.logic.formula.evaluate`` i porównują z tym, co jest w HTML-u. Wiersze
porównujemy po układzie wartości zmiennych, więc kolejność wierszy nie ma znaczenia.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterator
from html import unescape
from pathlib import Path

import pytest
from markupsafe import Markup

from app import create_app
from app.blueprints import formuly
from app.logic.formula import evaluate, parse, to_html

ADRES = "/formuly"

#: Pięć spójników z wykładu i ich nazwy.
NAZWY_SPOJNIKOW = ["negacja", "koniunkcja", "alternatywa", "implikacja", "równoważność"]

#: Jak czytamy każdy spójnik — fragmenty z tabeli.
CZYTANIE_SPOJNIKOW = [
    "nieprawda, że p",
    "p i q",
    "p lub q",
    "jeżeli p, to q",
    "p wtedy i tylko wtedy, gdy q",
]

#: Kolumny pełnej tablicy spójników (punkt 8 wykładu).
KOLUMNY_SPOJNIKOW = ["∼p", "p ∧ q", "p ∨ q", "p → q", "p ≡ q"]

#: Obie wersje niejednoznacznego zapisu — notacja z nawiasami, jak w wykładzie.
ZAPISY_WERSJI = ["(p ∨ q) → r", "p ∨ (q → r)"]

#: Wiersze, w których obie wersje dają inny wynik (p, q, r).
ROZNE_WIERSZE = {(1, 1, 0), (1, 0, 0)}

#: Podpisy (``<caption>``), po których znajdujemy tablice na stronie.
PODPIS_PODSTAWIENIA = "Wartościowanie dla podstawienia p = 1, q = 1"
PODPIS_WARTOSCIOWANIA = "Wartościowanie formuły dla p = 1, q = 0, r = 1"
PODPIS_SPOJNIKOW = "Pełna tablica pięciu spójników"

TABELA = re.compile(
    r'<table class="table table-sm tablica-prawdy align-middle">(?P<tresc>.*?)</table>',
    re.DOTALL,
)
WIERSZ = re.compile(r"<tr>(?P<tresc>.*?)</tr>", re.DOTALL)
KOMORKA = re.compile(r"<t[dh][^>]*>(?P<tresc>.*?)</t[dh]>", re.DOTALL)
SEKCJA_TABELI = re.compile(r"<tbody>(?P<tresc>.*?)</tbody>", re.DOTALL)
SEKCJA_NAGLOWKOW = re.compile(r"<thead>(?P<tresc>.*?)</thead>", re.DOTALL)

#: Wyrażenie wstawiane do HTML przez filtr ``|safe``.
WZORZEC_SAFE = re.compile(r"\{\{(?P<wyrazenie>.*?)\|\s*safe\s*\}\}", re.DOTALL)

#: Punkt montażu tablicy prawdy — partial czyta z niego formułę (karta PRZ-011).
PUNKT_MONTAZU = re.compile(r'<div class="truth-table-mount"[^>]*data-formula="(?P<wzor>[^"]+)"')

SZABLON = Path(__file__).resolve().parents[1] / "app" / "templates" / "formuly.html"


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


def _znak(wartosc: bool) -> str:
    """Wartość logiczna tak, jak na stronie: ``1`` albo ``0``."""
    return "1" if wartosc else "0"


def _wzor_html(wzor: str, styl: str = "wyklad") -> str:
    """Wzór jako HTML z ``formula.to_html`` — to samo, co wstawia strona."""
    return str(formuly.formula_to_html(wzor, styl))


def _tabela(html: str, podpis: str) -> str:
    """Treść tablicy, której podpis (``<caption>``) zawiera dany fragment."""
    pasujace = [tresc for tresc in TABELA.findall(html) if podpis in tresc]
    assert len(pasujace) == 1, f"nie znalazłem dokładnie jednej tablicy z {podpis!r}"
    return pasujace[0]


def _naglowki(tabela: str) -> list[str]:
    """Teksty nagłówków kolumn tablicy, w kolejności ze strony."""
    tresc = SEKCJA_NAGLOWKOW.search(tabela).group("tresc")
    return [_tekst(komorka) for komorka in KOMORKA.findall(tresc)]


def _wiersze(tabela: str) -> list[list[str]]:
    """Teksty komórek kolejnych wierszy tablicy."""
    tresc = SEKCJA_TABELI.search(tabela).group("tresc")
    return [
        [_tekst(komorka) for komorka in KOMORKA.findall(wiersz)] for wiersz in WIERSZ.findall(tresc)
    ]


def _wyniki(
    html: str, podpis: str, zmiennych: int
) -> tuple[list[str], dict[tuple[int, ...], list[str]]]:
    """Nagłówki tablicy i mapa: układ wartości zmiennych → wyniki kolejnych kolumn."""
    tabela = _tabela(html, podpis)
    wyniki: dict[tuple[int, ...], list[str]] = {}
    for wiersz in _wiersze(tabela):
        klucz = tuple(int(wartosc) for wartosc in wiersz[:zmiennych])
        assert klucz not in wyniki, f"powtórzony wiersz {klucz} w tablicy {podpis!r}"
        assert len(klucz) == zmiennych, f"wiersz {wiersz} bez wartości zmiennych"
        wyniki[klucz] = wiersz[zmiennych:]
    assert len(wyniki) == 2**zmiennych, f"tablica {podpis!r} nie ma wszystkich układów"
    return _naglowki(tabela), wyniki


def _oczekiwane(wzor: str, zmienne: str, uklad: tuple[int, ...]) -> str:
    """Liczy wartość wzoru dla układu zapisanego jako ``(1, 0, …)``."""
    wartosci = dict(zip(zmienne, (bool(int(znak)) for znak in uklad), strict=True))
    return _znak(evaluate(parse(wzor), wartosci))


def _uklady(zmienne: str) -> Iterator[tuple[int, ...]]:
    """Wszystkie układy wartości zmiennych jako krotki zer i jedynek."""
    yield from itertools.product((1, 0), repeat=len(zmienne))


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


# --- spójniki ----------------------------------------------------------------


@pytest.mark.parametrize("nazwa", NAZWY_SPOJNIKOW)
def test_tabela_spojnikow_podaje_nazwy(tekst, nazwa):
    assert nazwa in tekst, f"brak nazwy spójnika {nazwa!r}"


@pytest.mark.parametrize("czytanie", CZYTANIE_SPOJNIKOW)
def test_tabela_spojnikow_podaje_czytanie_po_polsku(tekst, czytanie):
    assert czytanie in tekst, f"brak czytania {czytanie!r}"


@pytest.mark.parametrize("wzor", KOLUMNY_SPOJNIKOW)
def test_tabela_spojnikow_pokazuje_wzor_przez_to_html(html, wzor):
    assert _wzor_html(wzor) in html, f"brak wzoru {wzor!r} z to_html"


def test_strona_pokazuje_inne_zapisy_spojnikow(html, tekst):
    """Notacja popularna też idzie przez ``to_html`` — wystarczy styl ``unicode``."""
    for wzor in formuly.INNE_ZAPISY:
        assert _wzor_html(wzor, "unicode") in html
    assert "To te same spójniki, tylko z innego podręcznika" in tekst


# --- definicja i przykłady formuł --------------------------------------------


def test_strona_podaje_indukcyjna_definicje_formuly(tekst):
    assert "Dowolna zmienna zdaniowa jest formułą logiczną" in tekst
    assert "Jeżeli ϕ i ψ są formułami" in tekst
    assert "też są formułami" in tekst


def test_strona_ma_co_najmniej_siedem_przykladow_formul(html):
    przyklady = re.findall(r'<li class="przyklad-formuly">(.*?)</li>', html, re.DOTALL)
    assert len(przyklady) >= 7, "definicja ma pokazać co najmniej siedem przykładów"
    assert len(przyklady) == len(formuly.PRZYKLADY_FORMUL)

    for tresc, wzor in zip(przyklady, formuly.PRZYKLADY_FORMUL, strict=True):
        assert _wzor_html(wzor) in tresc, f"przykład {wzor!r} nie pochodzi z to_html"


# --- nawiasy -----------------------------------------------------------------


def test_strona_pokazuje_zapis_niejednoznaczny(html, tekst):
    assert f'<code class="zapis-formuly">{formuly.FORMULA_NIEJEDNOZNACZNA}</code>' in html
    assert "niejednoznaczny" in tekst


@pytest.mark.parametrize("zapis", ZAPISY_WERSJI)
def test_strona_pokazuje_obie_wersje_z_nawiasami(html, zapis):
    assert f'<code class="zapis-formuly">{zapis}</code>' in html, f"brak zapisu {zapis!r}"


@pytest.mark.parametrize("wersja", formuly.WERSJE_NAWIASOW, ids=["A", "B"])
def test_kazda_wersja_ma_pelna_tablice_osem_wierszy(html, wersja):
    podpis = f"Tablica prawdy dla zapisu {wersja['zapis']}"
    naglowki, wyniki = _wyniki(html, podpis, 3)

    assert naglowki == ["p", "q", "r", _tekst(_wzor_html(wersja["wzor"]))]
    assert len(wyniki) == 8, "trzy zmienne to osiem wierszy"
    for klucz, wartosci in wyniki.items():
        assert wartosci == [_oczekiwane(wersja["wzor"], "pqr", klucz)]


def test_obie_wersje_roznia_sie_dokladnie_w_dwoch_wierszach(html, tekst):
    """Bez tego akapit uczyłby, że nawias nic nie zmienia."""
    pierwsza, druga = formuly.WERSJE_NAWIASOW
    _, wyniki_a = _wyniki(html, f"Tablica prawdy dla zapisu {pierwsza['zapis']}", 3)
    _, wyniki_b = _wyniki(html, f"Tablica prawdy dla zapisu {druga['zapis']}", 3)

    rozne = {klucz for klucz in wyniki_a if wyniki_a[klucz] != wyniki_b[klucz]}
    assert rozne == ROZNE_WIERSZE, f"wersje różnią się w {sorted(rozne)}"
    assert "różnią się w 2 z 8 wierszy" in tekst
    assert "dla p = 1, q = 1, r = 0 wersja A daje 0, a wersja B daje 1" in tekst


def test_strona_podaje_uwage_o_nawiasie_przy_negacji(tekst):
    assert "W zapisie (∼p) nawias możesz opuścić" in tekst


# --- formalizacja zdania -----------------------------------------------------


def test_strona_formalizuje_zdanie_o_uczeniu_sie(html, tekst):
    assert _wzor_html(formuly.FORMALIZACJA_UCZENIE) in html
    assert formuly.ZDANIE_UCZENIE in tekst
    for zmienna, zdanie in formuly.PODSTAWIENIE_UCZENIE:
        assert zdanie in tekst, f"brak podstawienia {zdanie!r} pod {zmienna!r}"


def test_strona_mowi_ze_formalizacja_jest_tautologia(tekst):
    assert "Ten wzór jest prawdziwy przy każdym wartościowaniu zmiennych" in tekst


# --- formuła to nie zdanie ---------------------------------------------------


def test_strona_podstawia_zdania_prawdziwe_pod_formule(html, tekst):
    assert _wzor_html(formuly.FORMULA_PODSTAWIENIA) in html
    for zmienna, zdanie in formuly.PODSTAWIENIE_LICZBY:
        assert zdanie in tekst, f"brak podstawienia {zdanie!r} pod {zmienna!r}"

    wiersze = _wiersze(_tabela(html, PODPIS_PODSTAWIENIA))
    assert len(wiersze) == 1, "pokazujemy jedno podstawienie, nie całą tablicę"
    oczekiwane = [
        _oczekiwane(wzor, "pq", (1, 1))
        for wzor in ["p → q", "∼q", "(p → q) ∧ ∼q", "∼p", formuly.FORMULA_PODSTAWIENIA]
    ]
    assert wiersze[0] == ["1", "1", *oczekiwane]
    assert wiersze[0][-1] == "1"
    assert "zdanie po podstawieniu jest prawdziwe" in tekst


# --- wartościowanie krok po kroku --------------------------------------------


def test_tabela_wartosciowania_ma_kolumny_alpha_beta_gamma(html):
    naglowki = _naglowki(_tabela(html, PODPIS_WARTOSCIOWANIA))

    assert naglowki[:3] == ["p", "q", "r"]
    assert naglowki[3] == _tekst(_wzor_html("∼q"))
    assert naglowki[4] == f"α = {_tekst(_wzor_html('p ∨ ∼q'))}"
    assert naglowki[5] == f"β = {_tekst(_wzor_html('p → q'))}"
    assert naglowki[6] == f"γ = {_tekst(_wzor_html('r ∧ (p → q)'))}"
    assert naglowki[7] == _tekst(_wzor_html(formuly.WARTOSCIOWANIE))


def test_tabela_wartosciowania_ma_jeden_wiersz_z_wynikiem_zero(html, tekst):
    wiersze = _wiersze(_tabela(html, PODPIS_WARTOSCIOWANIA))
    assert len(wiersze) == 1, "to jedno wartościowanie z wykładu, nie pełna tablica"

    oczekiwane = [
        _oczekiwane(wzor, "pqr", (1, 0, 1))
        for wzor in ["∼q", "p ∨ ∼q", "p → q", "r ∧ (p → q)", formuly.WARTOSCIOWANIE]
    ]
    assert wiersze[0] == ["1", "0", "1", *oczekiwane]
    assert oczekiwane[:4] == ["1", "1", "0", "0"], "α = 1, β = 0, γ = 0"
    assert oczekiwane[4] == wiersze[0][-1] == "0", "wynik wartościowania to 0"
    assert "formuła jest fałszywa przy tym wartościowaniu" in tekst


# --- wartości 1 i 0 ----------------------------------------------------------


def test_pelna_tablica_spojnikow_liczy_sie_z_evaluate(html):
    naglowki, wyniki = _wyniki(html, PODPIS_SPOJNIKOW, 2)

    assert naglowki == ["p", "q", *[_tekst(_wzor_html(wzor)) for wzor in KOLUMNY_SPOJNIKOW]]
    assert len(wyniki) == 4, "dwie zmienne to cztery wiersze"
    for klucz, wartosci in wyniki.items():
        assert wartosci == [_oczekiwane(wzor, "pq", klucz) for wzor in KOLUMNY_SPOJNIKOW]


@pytest.mark.parametrize(
    "podpis",
    [
        PODPIS_SPOJNIKOW,
        PODPIS_WARTOSCIOWANIA,
        PODPIS_PODSTAWIENIA,
        "Tablica prawdy dla zapisu (p ∨ q) → r",
        "Tablica prawdy dla zapisu p ∨ (q → r)",
    ],
)
def test_wartosci_w_tablicach_to_tylko_1_i_0(html, podpis):
    for wiersz in _wiersze(_tabela(html, podpis)):
        assert all(komorka in {"1", "0"} for komorka in wiersz), (
            f"tablica {podpis!r} ma wartość inną niż 1 albo 0: {wiersz}"
        )


def test_strona_objasnia_ze_jedynka_to_prawda(tekst):
    assert "Prawdę zapisujemy jako 1, a fałsz jako 0" in tekst
    assert "1 (prawda) i 0 (fałsz)" in tekst


def test_strona_wstawia_partial_tablicy_prawdy(html):
    """Punkt 8 wykładu: tablica prawdy dla formuły ``p → q`` (karta PRZ-011).

    Partial to dziś sam punkt montażu — tablicę dorysuje skrypt. Dlatego sprawdzamy
    także, że pełna tablica tej samej formuły jest już w HTML-u, policzona przez
    ``evaluate``: lekcja uczy wartościowań, zanim skrypt się wczyta.
    """
    assert "partials/_truth_table.html" in SZABLON.read_text("utf-8")

    punkt_montazu = PUNKT_MONTAZU.search(html)
    assert punkt_montazu, "brak punktu montażu tablicy prawdy"
    wzor = punkt_montazu.group("wzor")
    assert wzor == formuly.FORMULA_POKAZOWA, f"punkt montażu dostał {wzor!r}"

    naglowki, wyniki = _wyniki(html, PODPIS_SPOJNIKOW, 2)
    kolumny_wynikowe = naglowki[len(formuly.ZMIENNE_PQ) :]
    kolumna = kolumny_wynikowe.index(_tekst(_wzor_html(wzor)))
    for klucz, wartosci in wyniki.items():
        assert wartosci[kolumna] == _oczekiwane(wzor, "pq", klucz), (
            f"pełna tablica dla {wzor!r} nie zgadza się z evaluate w wierszu {klucz}"
        )


# --- nawigacja i bezpieczeństwo szablonu -------------------------------------


def test_strona_ma_odnosniki_poprzedniej_i_nastepnej_lekcji(html, tekst):
    assert 'href="/wstep"' in html
    assert 'href="/tautologie"' in html
    assert "Poprzednia lekcja" in tekst
    assert "Następna lekcja" in tekst


def test_wzory_na_stronie_sa_html_em_z_to_html(html):
    """Każdy wzór lekcji musi być w HTML, a nie cofnięty do zwykłego tekstu."""
    wzory = [wzor for wzor, _, _ in formuly.SPOJNIKI]
    wzory += [wzor for wzor in formuly.PRZYKLADY_FORMUL if len(wzor) > 1]
    wzory += [formuly.FORMALIZACJA_UCZENIE, formuly.FORMULA_PODSTAWIENIA, formuly.WARTOSCIOWANIE]

    for wzor in wzory:
        oczekiwany = _wzor_html(wzor)
        assert '<span class="op-' in oczekiwany, f"to_html zwrócił tekst dla {wzor!r}"
        assert oczekiwany in html, f"brak wyniku to_html dla {wzor!r}"


def test_szablon_uzywa_safe_tylko_na_wyniku_to_html():
    wyrazenia = [d["wyrazenie"].strip() for d in WZORZEC_SAFE.finditer(SZABLON.read_text("utf-8"))]

    assert wyrazenia, "szablon nie wstawia wzorów przez |safe"
    for wyrazenie in wyrazenia:
        assert "to_html" in wyrazenie, f"|safe na {wyrazenie!r}"


# --- funkcje pomocnicze modułu -----------------------------------------------


def test_formula_to_html_zamienia_zwykly_tekst_bez_bledu():
    wynik = formuly.formula_to_html("to nie jest formuła ((")

    assert isinstance(wynik, Markup)
    assert wynik == "to nie jest formuła (("


def test_formula_to_html_zwraca_html_dla_wzoru():
    assert str(formuly.formula_to_html("∼p")) == str(to_html(parse("∼p")))


def test_tabela_prawdy_liczy_wartosci_i_zapisuje_je_jako_1_i_0():
    kolumny = [formuly.Kolumna("p ∧ q"), formuly.Kolumna("∼q", nazwa="β")]

    tabela = formuly.tabela_prawdy(kolumny)

    assert tabela["zmienne"] == ["p", "q"]
    assert tabela["kolumny"] == [{"nazwa": "", "wzor": "p ∧ q"}, {"nazwa": "β", "wzor": "∼q"}]
    assert tabela["wiersze"] == [
        {"zmienne": ["1", "1"], "wyniki": ["1", "0"]},
        {"zmienne": ["1", "0"], "wyniki": ["0", "1"]},
        {"zmienne": ["0", "1"], "wyniki": ["0", "0"]},
        {"zmienne": ["0", "0"], "wyniki": ["0", "1"]},
    ]


def test_tabela_prawdy_ogranicza_sie_do_podanego_wartosciowania():
    tabela = formuly.tabela_prawdy(
        [formuly.Kolumna("p → q")], ["p", "q"], [{"p": True, "q": False}]
    )

    assert tabela["wiersze"] == [{"zmienne": ["1", "0"], "wyniki": ["0"]}]


def test_tabela_prawdy_ma_wiersz_dla_kazdego_ukladu_wartosci():
    tabela = formuly.tabela_prawdy([formuly.Kolumna("p ≡ q")], ["p", "q", "r"])

    uklady = {(tuple(int(z) for z in wiersz["zmienne"])) for wiersz in tabela["wiersze"]}
    assert uklady == set(_uklady("pqr"))
    assert all(len(wiersz["wyniki"]) == 1 for wiersz in tabela["wiersze"])


def test_rozne_wiersze_wskazuja_oba_wiersze_rozniace_wersje():
    rozne = formuly._rozne_wiersze(formuly._wersje_nawiasow())

    assert rozne == [
        {"p": "1", "q": "1", "r": "0", "wersja_a": "0", "wersja_b": "1"},
        {"p": "1", "q": "0", "r": "0", "wersja_a": "0", "wersja_b": "1"},
    ]


def test_wynik_wartosciowania_to_falsz_a_podstawienia_to_prawda():
    """Dwa wyniki z wykładu: 0 dla wartościowania i 1 po podstawieniu zdań."""
    assert formuly._wynik_wartosciowania() == "0"
    assert formuly._wynik_podstawienia() == "1"
    assert formuly._znak(True) == "1"
    assert formuly._znak(False) == "0"
