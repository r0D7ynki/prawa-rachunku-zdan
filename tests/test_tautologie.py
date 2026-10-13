"""Testy strony ``/tautologie`` — definicji tautologii, dowodu i metody skróconej.

Testy nie wierzą stronie na słowo: wartości w tablicach liczą od nowa przez
``app.logic.formula.evaluate``, a wzory porównują z wynikiem ``formula.to_html``.
Dzięki temu test nie zakłada konkretnego znaku operatora — sprawdza to, co strona
naprawdę narysowała. Spis T1–T14 porównujemy z rejestrem ``all_laws()``, więc test
nie rozjedzie się z treścią praw.

Kroki dowodów (karta PRZ-076) sprawdzamy w JSON-ie z atrybutu ``data-kroki``:
pola kroku, liczbę kroków, strzałki, gaszenie odrzuconych wierszy i wnioski.
Do tego testy źródłowe skryptu ``tautologie.js`` — bez przeglądarki nie da się
przejść kroków, więc sprawdzamy to, co skrypt ma w kodzie.
"""

from __future__ import annotations

import itertools
import json
import re
from collections.abc import Iterator
from html import unescape
from pathlib import Path

import pytest
from markupsafe import Markup

from app import create_app
from app.blueprints import tautologie
from app.logic.formula import And, Imp, Node, Not, Var, evaluate, parse, to_html, to_text
from app.logic.laws import all_laws

ADRES = "/tautologie"

#: Podpisy (``<caption>``), po których znajdujemy tablice na stronie.
PODPIS_SRODKA = "Tablica prawdy dla prawa wyłączonego środka"
PODPIS_DOWODU = "Pełna tablica prawdy: cztery wiersze"
PODPIS_METODY = "Cała tablica metody skróconej"
PODPIS_SPISU = "Spis tautologii z wykładu"

#: Wiersze pełnej tablicy dowodu, dokładnie jak na wykładzie: p, q, p → q, ∼q,
#: α = (p → q) ∧ ∼q, ∼p i α → ∼p.
WIERSZE_DOWODU = [
    ["0", "0", "1", "1", "1", "1", "1"],
    ["0", "1", "1", "0", "0", "1", "1"],
    ["1", "0", "0", "1", "0", "0", "1"],
    ["1", "1", "1", "0", "0", "0", "1"],
]

#: Dwa przypadki, które zostają po metodzie skróconej — jak na wykładzie:
#: p, q, r, α, β, γ, δ i γ → δ.
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

#: Blok ``<noscript>`` z listą kroków, którą wypisuje partial paska kroków.
NOSCRIPT = re.compile(r"<noscript>(?P<tresc>.*?)</noscript>", re.DOTALL)

#: Wyrażenie wstawiane do HTML przez filtr ``|safe``.
WZORZEC_SAFE = re.compile(r"\{\{(?P<wyrazenie>.*?)\|\s*safe\s*\}\}", re.DOTALL)

#: Panel z krokami: nazwa panelu i JSON kroków w ``data-kroki``.
PANEL_KROKOWY = re.compile(
    r'<div class="tablica-krokowa"[^>]*data-krokowa="(?P<panel>[^"]+)"'
    r'[^>]*data-kroki="(?P<kroki>[^"]*)"[^>]*>',
    re.DOTALL,
)

KATALOG_STATYCZNY = Path(__file__).resolve().parents[1] / "app" / "static"
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


@pytest.fixture(scope="module")
def skrypt():
    """Treść skryptu ``tautologie.js`` — bez przeglądarki sprawdzamy to, co ma w kodzie."""
    return (KATALOG_STATYCZNY / "js" / "tautologie.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def styl():
    """Treść arkusza ``tautologie.css``."""
    return (KATALOG_STATYCZNY / "css" / "tautologie.css").read_text(encoding="utf-8")


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


def _kroki(html: str) -> dict[str, list[dict]]:
    """Kroki obu paneli: nazwa panelu → lista kroków z atrybutu ``data-kroki``."""
    return {panel: json.loads(unescape(kroki)) for panel, kroki in PANEL_KROKOWY.findall(html)}


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


def test_tabela_metody_ma_osiem_wierszy_i_dwa_przypadki_z_wykladu(html):
    """Krok pierwszy metody to cała tabela; wykład rozważa z niej dwa przypadki."""
    tabela = _tabela(html, PODPIS_METODY)
    naglowki = _naglowki(tabela)

    assert naglowki[:3] == ["p", "q", "r"]
    assert naglowki[3] == "α = " + _wzor_tekstem(parse("p → q"))
    assert naglowki[4] == "β = " + _wzor_tekstem(parse("q → r"))
    assert naglowki[5] == "γ = " + _wzor_tekstem(And(Var("α"), Var("β")))
    assert naglowki[6] == "δ = " + _wzor_tekstem(parse(tautologie.NASTEPNIK_METODY))
    assert naglowki[7] == _wzor_tekstem(Imp(Var("γ"), Var("δ")))
    assert len(naglowki) == 8

    wiersze = _wiersze(tabela)
    assert len(wiersze) == 8, "trzy zmienne to osiem wartościowań"

    # Dwa przypadki z wykładu: następnik δ fałszywy, czyli p = 1 i r = 0.
    przypadki = [wiersz for wiersz in wiersze if wiersz[0] == "1" and wiersz[2] == "0"]
    assert przypadki == WIERSZE_METODY


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


# --- kroki dowodów (PRZ-076) -------------------------------------------------


def test_strona_ma_oba_panele_krokowe(html):
    """Dowód pełną tablicą i metoda skrócona mają własne panele z krokami."""
    assert set(_kroki(html)) == {"dowod", "metoda"}


def test_obie_tabele_krokowe_sa_w_html_w_pelnej_wersji(html):
    """Bez JavaScriptu kroki nic nie ujawniają, więc obie tabele są w HTML w całości."""
    dowod = _tabela(html, PODPIS_DOWODU)
    metoda = _tabela(html, PODPIS_METODY)

    assert len(_naglowki(dowod)) == 7
    assert _wiersze(dowod) == WIERSZE_DOWODU
    assert len(_naglowki(metoda)) == 8
    assert len(_wiersze(metoda)) == 8


def test_panel_krokow_dolacza_arkusz_i_skrypt(html):
    assert 'href="/static/css/tautologie.css"' in html
    assert 'src="/static/js/tautologie.js"' in html


def test_kazdy_krok_ma_wymagane_pola(html):
    kroki = [krok for lista_krokow in _kroki(html).values() for krok in lista_krokow]

    assert kroki, "strona nie ma ani jednego kroku"
    for krok in kroki:
        for pole in ("tytul", "opis", "kolumny", "strzalki", "wiersze"):
            assert pole in krok, f"krok bez pola {pole}: {krok.get('tytul')!r}"
        assert krok["tytul"] and krok["opis"], "krok bez tytułu albo opisu"


def test_liczba_krokow_dowodu_rowna_sie_liczbie_kolumn(html):
    """Krok pierwszy to kolumny zmiennych, dalej po jednej kolumnie wynikowej i wniosek."""
    kroki = _kroki(html)["dowod"]
    naglowki = _naglowki(_tabela(html, PODPIS_DOWODU))

    assert len(kroki) == len(naglowki) == 7


def test_kroki_dowodu_odslaniaja_kolumny_od_lewej_do_prawej(html):
    kroki = _kroki(html)["dowod"]

    assert kroki[0]["kolumny"] == [0, 1], "na starcie widać tylko kolumny p i q"
    assert [len(krok["kolumny"]) for krok in kroki[1:-1]] == [3, 4, 5, 6, 7]
    assert kroki[-1]["kolumny"] == list(range(7)), "wniosek pokazuje całą tablicę"


def test_strzalki_dowodu_mowia_z_ktorych_kolumn_liczy_sie_kolumna(html):
    kroki = _kroki(html)["dowod"]

    pierwsza = kroki[1]["strzalki"][0]
    assert pierwsza["od"] == [0, 1] and pierwsza["do"] == [2], "od p i q do p → q"
    assert pierwsza["opis"] == "implikacja"
    assert pierwsza["jednostka"] == "kolumna"

    alfa = next(krok for krok in kroki if krok["tytul"].endswith("α"))["strzalki"][0]
    assert alfa["od"] == [2, 3] and alfa["do"] == [4], "od p → q i ∼q do α"
    assert alfa["opis"] == "koniunkcja"


def test_opis_kolumny_alfa_podaje_rachunek_z_wykladu(html):
    """Zdanie z wykładu: „Kolumna α: koniunkcja (p → q) i ∼q. W wierszu 3: 0 ∧ 1 = 0”."""
    kroki = _kroki(html)["dowod"]
    opis = next(krok["opis"] for krok in kroki if krok["tytul"].endswith("α"))

    assert opis.startswith(f"Kolumna α: koniunkcja ({_wzor_tekstem(parse('p → q'))}) i ∼q.")

    # Wiersz trzeci tablicy: p = 1 i q = 0. Wartości muszą zgadzać się z ``evaluate``.
    wiersz = WIERSZE_DOWODU[2]
    assert wiersz[2:] == [
        _oczekiwane(wzor, "pq", (1, 0))
        for wzor in ["p → q", "∼q", tautologie.ALFA_DOWODU, "∼p", tautologie.FORMULA_DOWODU]
    ]
    rachunek = to_text(And(Var(wiersz[2]), Var(wiersz[3])))
    assert f"W wierszu 3: {rachunek} = {wiersz[4]}" in opis


def test_kroki_metody_gasza_odrzucone_wiersze(html):
    """Krok drugi zostawia odrzucone wiersze na stronie, ale je gasi."""
    gaszenie = _kroki(html)["metoda"][1]

    assert gaszenie["wiersze"] == [1, 3]
    assert len(gaszenie["odrzucone"]) == 6
    assert set(gaszenie["odrzucone"]) | set(gaszenie["wiersze"]) == set(range(8))

    strzalka = gaszenie["strzalki"][0]
    assert strzalka["jednostka"] == "wiersz"
    assert strzalka["od"] == gaszenie["odrzucone"] and strzalka["do"] == gaszenie["wiersze"]
    assert strzalka["opis"] == "zawężenie"

    nastepnik = to_text(parse(tautologie.NASTEPNIK_METODY))
    assert "Zostają tylko przypadki" in gaszenie["opis"]
    assert f"w których {nastepnik} jest fałszywa" in gaszenie["opis"]
    assert "r = 0 i p = 1" in gaszenie["opis"]


def test_kroki_metody_koncza_sie_dwoma_wierszami(html):
    kroki = _kroki(html)["metoda"]

    assert len(kroki) == 4
    assert kroki[0]["wiersze"] == list(range(8)), "krok pierwszy to cała tabela"
    assert kroki[2]["wiersze"] == [1, 3] and kroki[2]["odrzucone"] == []
    assert "Zostają dwa wiersze" in kroki[2]["opis"]


def test_ostatni_krok_dowodu_dodaje_wiersz_wniosku(html, tekst):
    kroki = _kroki(html)["dowod"]
    tabela = _tabela(html, PODPIS_DOWODU)
    liczba_wierszy = len(_wiersze(tabela))

    assert kroki[-1]["wiersze"] == [*range(liczba_wierszy), liczba_wierszy]
    assert "Wszystkie wiersze mają 1 — to tautologia" in kroki[-1]["opis"]

    # Wiersz podsumowania jest w HTML (stopka) i rozciąga się na całą tabelę.
    assert "<tfoot>" in tabela
    assert f'<td colspan="{len(_naglowki(tabela))}">' in tabela
    assert "Wszystkie wiersze mają 1 — to tautologia" in tekst


def test_ostatni_krok_obu_tabel_podaje_wniosek(html):
    for panel, kroki in _kroki(html).items():
        wniosek = kroki[-1]["opis"]
        assert "tautolog" in wniosek, f"krok końcowy panelu {panel} bez wniosku"
        assert wniosek.endswith("."), f"krok końcowy panelu {panel} nie jest zdaniem"


def test_bez_javascriptu_widac_liste_krokow(html):
    """Partial paska wypisuje kroki w ``<noscript>`` — bez JS nic nie ginie."""
    bloki = "\n".join(NOSCRIPT.findall(html))

    assert bloki, "strona nie ma bloku <noscript> z krokami"
    for kroki in _kroki(html).values():
        for krok in kroki:
            assert krok["tytul"] in bloki, f"brak kroku w <noscript>: {krok['tytul']!r}"


# --- skrypt i style kroków ----------------------------------------------------


def test_pliki_panelu_krokow_istnieja():
    for sciezka in ("js/tautologie.js", "css/tautologie.css"):
        plik = KATALOG_STATYCZNY / sciezka
        assert plik.is_file(), f"brak pliku {sciezka}"
        assert plik.stat().st_size > 0


def test_skrypt_importuje_wspolny_komponent_krokow(skrypt):
    assert 'import { createStepper } from "/static/js/stepper.js";' in skrypt
    assert "createStepper({" in skrypt
    assert "onStep:" in skrypt


def test_skrypt_czyta_kroki_z_atrybutu(skrypt):
    """Kroki przychodzą gotowe z serwera — skrypt ich nie liczy ani nie wymyśla."""
    assert "panel.dataset.kroki" in skrypt
    assert "JSON.parse" in skrypt


def test_skrypt_rysuje_strzalki_nad_tabela(skrypt, styl):
    assert 'nowyElement("span", "strzalka-tabeli")' in skrypt
    assert '"strzalka-linia"' in skrypt
    assert '"strzalka-operacja"' in skrypt
    assert "[data-strzalki]" in skrypt
    assert ".strzalka-tabeli" in styl


def test_skrypt_gasi_odrzucone_wiersze(skrypt, styl):
    """Odrzucone wiersze gasną i znikają z czytnika — klasa i ``aria-hidden``."""
    assert 'const KLASA_ODRZUCONY = "wiersz-odrzucony";' in skrypt
    assert "classList.toggle(KLASA_ODRZUCONY, odrzucony)" in skrypt
    assert 'setAttribute("aria-hidden", "true")' in skrypt
    assert ".wiersz-odrzucony" in styl


def test_skrypt_ukrywa_kolummy_i_wiersze_poza_krokiem(skrypt):
    assert "komorka.hidden" in skrypt
    assert "wiersz.hidden" in skrypt
    assert "wniosek.hidden" in skrypt


def test_skrypt_nie_wstawia_tresci_przez_innerhtml(skrypt):
    assert ".innerHTML" not in skrypt
    assert "insertAdjacentHTML" not in skrypt
    assert "document.write" not in skrypt


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
