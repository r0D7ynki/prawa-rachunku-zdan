"""Testy strony ``/tautologie`` — definicji tautologii, dowodu i metody skróconej.

Testy nie wierzą stronie na słowo: wartości w tablicach liczą od nowa przez
``app.logic.formula.evaluate``, a wzory porównują z wynikiem ``formula.to_html``.
Dzięki temu test nie zakłada konkretnego znaku operatora — sprawdza to, co strona
naprawdę narysowała. Spis T1–T14 porównujemy z rejestrem ``all_laws()``, więc test
nie rozjedzie się z treścią praw.
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
from app.blueprints import tautologie
from app.logic.formula import And, Imp, Node, Not, Var, evaluate, parse, to_html
from app.logic.laws import all_laws

ADRES = "/tautologie"

#: Podpisy (``<caption>``), po których znajdujemy tablice na stronie.
PODPIS_SRODKA = "Tablica prawdy dla prawa wyłączonego środka"
PODPIS_DOWODU = "Pełna tablica prawdy: cztery wiersze"
PODPIS_METODY = "Dwa przypadki, w których formuła mogłaby być fałszywa"
PODPIS_SPISU = "Spis tautologii z wykładu"

#: Wiersze pełnej tablicy dowodu, dokładnie jak na wykładzie: p, q, p → q, ∼q,
#: α = (p → q) ∧ ∼q, ∼p i α → ∼p.
WIERSZE_DOWODU = [
    ["0", "0", "1", "1", "1", "1", "1"],
    ["0", "1", "1", "0", "0", "1", "1"],
    ["1", "0", "0", "1", "0", "0", "1"],
    ["1", "1", "1", "0", "0", "0", "1"],
]

#: Wiersze tablicy metody skróconej, dokładnie jak na wykładzie: p, q, r, α, β, γ, δ
#: i γ → δ.
WIERSZE_METODY = [
    ["1", "1", "0", "1", "0", "0", "0", "1"],
    ["1", "0", "0", "0", "1", "0", "0", "1"],
]

#: Formuły, które strona pokazuje jako wzory — każda musi dojść przez ``to_html``.
WZORY_STRONY = [
    tautologie.WYLACZONY_SRODEK,
    tautologie.FORMULA_DOWODU,
    tautologie.ALFA_DOWODU,
    tautologie.NASTEPNIK_METODY,
    tautologie.FORMULA_METODY,
]

TABELA = re.compile(r"<table\b[^>]*>(?P<tresc>.*?)</table>", re.DOTALL)
WIERSZ = re.compile(r"<tr>(?P<tresc>.*?)</tr>", re.DOTALL)
KOMORKA = re.compile(r"<t[dh][^>]*>(?P<tresc>.*?)</t[dh]>", re.DOTALL)
SEKCJA_TABELI = re.compile(r"<tbody>(?P<tresc>.*?)</tbody>", re.DOTALL)
SEKCJA_NAGLOWKOW = re.compile(r"<thead>(?P<tresc>.*?)</thead>", re.DOTALL)
KROKI = re.compile(r'<ol class="kroki-metody">(?P<tresc>.*?)</ol>', re.DOTALL)
PUNKT_KROKU = re.compile(r"<li>(?P<tresc>.*?)</li>", re.DOTALL)
ODNOSNIK_PRAWA = re.compile(r'<a\s+href="(?P<href>/prawa/[^"]+)">(?P<nazwa>[^<]+)</a>')

#: Wyrażenie wstawiane do HTML przez filtr ``|safe``.
WZORZEC_SAFE = re.compile(r"\{\{(?P<wyrazenie>.*?)\|\s*safe\s*\}\}", re.DOTALL)

SZABLON = Path(__file__).resolve().parents[1] / "app" / "templates" / "tautologie.html"


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
    return str(tautologie.formula_to_html(wzor, styl))


def _wzor_tekstem(wzor: Node) -> str:
    """Tekst wzoru z drzewa — do nagłówków, których nie da się wpisać do parsera."""
    return _tekst(str(to_html(wzor)))


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


# --- definicja tautologii ----------------------------------------------------


def test_strona_podaje_definicje_tautologii(tekst):
    assert "tautologią" in tekst
    assert "jest prawdziwa dla każdego wartościowania zmiennych zdaniowych" in tekst


def test_strona_mowi_o_podstawianiu_dowolnych_zdan_pod_zmienne(tekst):
    assert "niezależnie od tego, jakie zdania podstawimy pod zmienne" in tekst


def test_strona_mowi_o_schematach_wnioskowania(tekst):
    assert "poprawne schematy wnioskowania" in tekst


# --- prawo wyłączonego środka ------------------------------------------------


def test_tabela_wylaczonego_srodka_ma_dwa_wiersze(html):
    tabela = _tabela(html, PODPIS_SRODKA)
    naglowki = _naglowki(tabela)
    oczekiwane_naglowki = [
        "p",
        _wzor_tekstem(parse("∼p")),
        _wzor_tekstem(parse(tautologie.WYLACZONY_SRODEK)),
    ]
    assert naglowki == oczekiwane_naglowki

    wiersze = _wiersze(tabela)
    assert len(wiersze) == 2, "jedna zmienna to dwa wartościowania"
    assert [w[:1] for w in wiersze] == [["1"], ["0"]]
    for wiersz in wiersze:
        assert wiersz[1:] == [
            _oczekiwane(wzor, "p", (int(wiersz[0]),))
            for wzor in ["∼p", tautologie.WYLACZONY_SRODEK]
        ]


def test_wniosek_o_wylaczonym_srodku_mowi_o_tautologii(tekst):
    assert "same jedynki" in tekst
    assert "Formuła jest więc tautologią" in tekst
    assert "w każdym z 2 wierszy jest 1" in tekst


# --- dowód pełną tablicą -----------------------------------------------------


def test_tabela_dowodu_ma_siedem_kolumn_i_cztery_wiersze(html):
    tabela = _tabela(html, PODPIS_DOWODU)

    assert len(_naglowki(tabela)) == 7, "dwie zmienne i pięć kolumn wynikowych"
    assert len(_wiersze(tabela)) == 4, "dwie zmienne to cztery wartościowania"


def test_naglowki_dowodu_ida_przez_to_html(html):
    """Także nagłówek ``α → ∼p``: litera α jest nazwą podformuły, nie zmienną."""
    naglowki = _naglowki(_tabela(html, PODPIS_DOWODU))

    assert naglowki[:2] == ["p", "q"]
    assert naglowki[2] == _wzor_tekstem(parse("p → q"))
    assert naglowki[3] == _wzor_tekstem(parse("∼q"))
    assert naglowki[5] == _wzor_tekstem(parse("∼p"))

    assert naglowki[4] == "α = " + _wzor_tekstem(parse(tautologie.ALFA_DOWODU))
    assert naglowki[6] == _wzor_tekstem(Imp(Var("α"), Not(Var("p"))))


def test_tabela_dowodu_ma_wartosci_z_wykladu(html):
    assert _wiersze(_tabela(html, PODPIS_DOWODU)) == WIERSZE_DOWODU


def test_tabela_dowodu_liczy_sie_z_evaluate(html):
    """Wartości z wykładu muszą zgadzać się z tym, co liczy ``evaluate``."""
    kolumny = ["p → q", "∼q", tautologie.ALFA_DOWODU, "∼p", tautologie.FORMULA_DOWODU]

    for wiersz in _wiersze(_tabela(html, PODPIS_DOWODU)):
        uklad = (int(wiersz[0]), int(wiersz[1]))
        assert wiersz[2:] == [_oczekiwane(wzor, "pq", uklad) for wzor in kolumny]


def test_wniosek_dowodu_mowi_ze_to_tautologia(tekst):
    assert "w każdym z 4 wierszy jest 1" in tekst


# --- metoda skrócona ---------------------------------------------------------


def test_sekcja_metody_ma_cztery_kroki(html, tekst):
    tresc = KROKI.search(html)
    assert tresc is not None, "brak listy kroków metody skróconej"

    kroki = [_tekst(krok) for krok in PUNKT_KROKU.findall(tresc.group("tresc"))]
    assert len(kroki) == 4, f"metoda skrócona ma cztery kroki, a ma {len(kroki)}"

    assert "fałszywa tylko wtedy, gdy poprzednik jest prawdziwy" in kroki[0]
    assert "fałszywy jest jej następnik" in kroki[1]
    assert "dokładnie dla r = 0 i p = 1" in kroki[2]
    assert "Zostają więc dwa przypadki: q = 1 oraz q = 0" in kroki[3]
    assert "Zostają więc dwa przypadki" in tekst


def test_kroki_metody_pokazuja_formuly_przez_to_html(html):
    tresc = KROKI.search(html).group("tresc")

    for wzor in [tautologie.FORMULA_METODY, tautologie.NASTEPNIK_METODY]:
        assert _wzor_html(wzor) in tresc, f"krok bez wyniku to_html dla {wzor!r}"


def test_tabela_metody_ma_dwa_przypadki_z_wykladu(html):
    tabela = _tabela(html, PODPIS_METODY)
    naglowki = _naglowki(tabela)

    assert naglowki[:3] == ["p", "q", "r"]
    assert naglowki[3] == "α = " + _wzor_tekstem(parse("p → q"))
    assert naglowki[4] == "β = " + _wzor_tekstem(parse("q → r"))
    assert naglowki[5] == "γ = " + _wzor_tekstem(And(Var("α"), Var("β")))
    assert naglowki[6] == "δ = " + _wzor_tekstem(parse(tautologie.NASTEPNIK_METODY))
    assert naglowki[7] == _wzor_tekstem(Imp(Var("γ"), Var("δ")))

    assert len(naglowki) == 8
    assert _wiersze(tabela) == WIERSZE_METODY


def test_tabela_metody_liczy_sie_z_evaluate(html):
    kolumny = [
        "p → q",
        "q → r",
        tautologie.POPRZEDNIK_METODY,
        tautologie.NASTEPNIK_METODY,
        tautologie.FORMULA_METODY,
    ]

    for wiersz in _wiersze(_tabela(html, PODPIS_METODY)):
        uklad = (int(wiersz[0]), int(wiersz[1]), int(wiersz[2]))
        assert wiersz[3:] == [_oczekiwane(wzor, "pqr", uklad) for wzor in kolumny]


def test_strona_podaje_po_co_jest_metoda_skrocona(tekst):
    assert "2^n" in tekst
    assert "zamiast" in tekst
    assert "w których formuła mogłaby być fałszywa" in tekst


# --- spis T1–T14 -------------------------------------------------------------


def test_spis_powstaje_z_rejestru_praw(html):
    zwykle = tautologie.prawa_spisu()
    wiersze = _wiersze(_tabela(html, PODPIS_SPISU))

    assert len(wiersze) == len(zwykle), "liczba wierszy to liczba praw spoza kategorii dodatkowych"
    assert [wiersz[0] for wiersz in wiersze] == [f"T{n}" for n in range(1, len(zwykle) + 1)]


def test_spis_ma_czternascie_tautologii_z_wykladu(html):
    zwykle = tautologie.prawa_spisu()

    assert len(zwykle) == 14, "wykład wymienia czternaście tautologii w spisie"
    assert len(_wiersze(_tabela(html, PODPIS_SPISU))) == 14


def test_kazda_nazwa_w_spisie_linkuje_do_istniejacego_prawa(html):
    odnosniki = ODNOSNIK_PRAWA.findall(_tabela(html, PODPIS_SPISU))
    znane = {prawo.slug: prawo.nazwa for prawo in all_laws()}

    assert len(odnosniki) == 14, "każda z czternastu nazw ma odnośnik"
    for href, nazwa in odnosniki:
        slug = href.removeprefix("/prawa/")
        assert slug in znane, f"odnośnik do prawa, którego nie ma w rejestrze: {slug}"
        assert nazwa == znane[slug]


def test_spis_liczy_wzory_przez_to_html(html):
    tresc = _tabela(html, PODPIS_SPISU)
    for prawo in tautologie.prawa_spisu():
        assert _wzor_html(prawo.formula) in tresc


def test_strona_pokazuje_prawa_dodatkowe(html, tekst):
    dodatkowe = tautologie.prawa_dodatkowe()

    assert dodatkowe, "rejestr ma prawa kategorii 'dodatkowe'"
    assert "Prawa dodatkowe" in tekst
    assert "nie należą do wykładowego spisu T1–T14" in tekst
    for prawo in dodatkowe:
        assert _wzor_html(prawo.formula) in html
        assert f'href="/prawa/{prawo.slug}"' in html


def test_rejestr_dzieli_sie_na_spis_i_prawa_dodatkowe():
    """Suma obu list to cały rejestr, bez powtórzeń i bez zgubionego prawa."""
    spis = {prawo.slug for prawo in tautologie.prawa_spisu()}
    dodatkowe = {prawo.slug for prawo in tautologie.prawa_dodatkowe()}

    assert not spis & dodatkowe
    assert spis | dodatkowe == {prawo.slug for prawo in all_laws()}


def test_tabela_tautologii_numeruje_prawa_od_t1():
    wiersze = tautologie.tabela_tautologii()

    assert [wiersz["numer"] for wiersz in wiersze] == [
        f"T{numer}" for numer in range(1, len(wiersze) + 1)
    ]
    assert [wiersz["slug"] for wiersz in wiersze] == [
        prawo.slug for prawo in tautologie.prawa_spisu()
    ]


# --- partial, nawigacja i bezpieczeństwo szablonu ----------------------------


def test_strona_wstawia_partial_tablicy_prawdy(html):
    """Punkt 3 wykładu: tablica dla ``((p → q) ∧ ∼q) → ∼p`` przez partial (PRZ-011)."""
    assert 'class="truth-table-mount"' in html
    assert f'data-formula="{tautologie.FORMULA_DOWODU}"' in html
    assert "partials/_truth_table.html" in SZABLON.read_text("utf-8")


def test_strona_ma_odnosniki_poprzedniej_i_nastepnej_lekcji(html, tekst):
    assert 'href="/formuly"' in html
    assert 'href="/przeksztalcanie"' in html
    assert "Poprzednia lekcja" in tekst
    assert "Następna lekcja" in tekst


def test_wzory_na_stronie_sa_html_em_z_to_html(html):
    """Każdy wzór lekcji musi być w HTML, a nie cofnięty do zwykłego tekstu."""
    wzory = [*WZORY_STRONY, *(prawo.formula for prawo in all_laws())]

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
    wynik = tautologie.formula_to_html("to nie jest formuła ((")

    assert isinstance(wynik, Markup)
    assert wynik == "to nie jest formuła (("


def test_formula_to_html_zwraca_html_dla_wzoru():
    assert str(tautologie.formula_to_html("∼p")) == str(to_html(parse("∼p")))


def test_naglowek_to_html_dokleja_nazwe_z_wykladu():
    kolumna = tautologie.tabela_prawdy([tautologie.Kolumna("p → q", nazwa="α")])["kolumny"][0]

    assert tautologie.naglowek_to_html(kolumna) == "α = " + _wzor_html("p → q")


def test_naglowek_to_html_rysuje_drzewo_bez_parsowania():
    """Nagłówek ``γ = α ∧ β`` powstaje z drzewa, bo α i β nie są zmiennymi parsera."""
    naglowek = And(Var("α"), Var("β"))
    kolumna = tautologie.Kolumna("p → q", nazwa="γ", naglowek=naglowek)
    tabela = tautologie.tabela_prawdy([kolumna])

    assert tautologie.naglowek_to_html(tabela["kolumny"][0]) == "γ = " + str(to_html(naglowek))


def test_tabela_prawdy_liczy_wartosci_i_zapisuje_je_jako_1_i_0():
    kolumny = [tautologie.Kolumna("p ∧ q"), tautologie.Kolumna("∼q", nazwa="β")]

    tabela = tautologie.tabela_prawdy(kolumny)

    assert tabela["zmienne"] == ["p", "q"]
    assert tabela["kolumny"] == [
        {"wzor": "p ∧ q", "nazwa": "", "naglowek": None},
        {"wzor": "∼q", "nazwa": "β", "naglowek": None},
    ]
    assert tabela["wiersze"] == [
        {"zmienne": ["1", "1"], "wyniki": ["1", "0"]},
        {"zmienne": ["1", "0"], "wyniki": ["0", "1"]},
        {"zmienne": ["0", "1"], "wyniki": ["0", "0"]},
        {"zmienne": ["0", "0"], "wyniki": ["0", "1"]},
    ]


def test_tabela_prawdy_ogranicza_sie_do_podanego_wartosciowania():
    tabela = tautologie.tabela_prawdy(
        [tautologie.Kolumna("p → q")], ["p", "q"], [{"p": True, "q": False}]
    )

    assert tabela["wiersze"] == [{"zmienne": ["1", "0"], "wyniki": ["0"]}]


def test_tabela_prawdy_ma_wiersz_dla_kazdego_ukladu_wartosci():
    tabela = tautologie.tabela_prawdy([tautologie.Kolumna("p ≡ q")], ["p", "q", "r"])

    uklady = {(tuple(int(znak) for znak in wiersz["zmienne"])) for wiersz in tabela["wiersze"]}
    assert uklady == set(_uklady("pqr"))


def test_wniosek_wykrywa_formule_bez_samych_jedynek():
    """Gdyby ktoś podmienił wzór, wniosek na stronie też musi to powiedzieć."""
    tabela = tautologie.tabela_prawdy([tautologie.Kolumna("p ∧ q")])

    wniosek = tautologie.wniosek_tautologii(tabela)

    assert "nie jest tautologią" in wniosek
    assert "jedynka stoi tylko w 1 z 4 wierszy" in wniosek
