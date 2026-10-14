"""Testy wizualizacji: schemat bramek i diagram zbiorów (karty PRZ-012, PRZ-074, PRZ-075, PRZ-123).

Od PRZ-123 rysunki liczy serwer (``app/logic/diagrams.py``), więc testy sprawdzają:

* co partial oddaje serwerowi — gotowy ``<svg>``, dwie strzałki, listę opisów kroków,
* jak zbudowany jest ``wizualizacje.js``: podmienia krok z ``<template>``, nie pisze
  przez ``innerHTML`` i nic nie pobiera z API,
* że strona prawa nie wraca już do rysowania w przeglądarce.

Sekcje o ``gates.js`` i ``sets.js`` opisują pliki, które zostały w repozytorium jako
nieużywane („Do zgłoszenia” w karcie PRZ-123). Testy pilnują, że nie zmieniły się
przypadkiem, dopóki ktoś ich nie usunie razem z tymi testami.

Wzorzec testu źródłowego jest ten sam, co w ``tests/test_czesc_kroki.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from flask import render_template
from markupsafe import Markup, escape

from app import create_app
from app.blueprints import laws as widoki
from app.logic.diagrams import kroki_sets
from app.logic.formula import parse, to_text
from app.logic.laws import all_laws

KATALOG_STATYCZNY = Path(__file__).resolve().parents[1] / "app" / "static"

#: Pliki komponentu — karta PRZ-012 wymaga, żeby istniały i nie były puste.
PLIKI = ("js/gates.js", "js/sets.js", "css/wizualizacje.css")

#: Pięć typów węzłów drzewa formuły, które musi obsłużyć ``gates.js``.
TYPY_WEZLOW = ("Var", "Not", "And", "Or", "Imp", "Iff")

FORMULA_BRAMKI = "p ∨ ∼p"
FORMULA_ZBIORY = "∼(p ∨ q) ≡ (∼p ∧ ∼q)"

#: Slugi praw rysowanych diagramami zbiorów — dla testów kroków (PRZ-075).
PRAWA_ZBIOROW = [law.slug for law in all_laws() if law.wizualizacja == "sets"]

#: Prawa używane w testach partiali: jedno z bramkami, jedno ze zbiorami.
PRAWO_BRAMKI = next(law for law in all_laws() if law.wizualizacja == "gates")
PRAWO_ZBIOROW = next(law for law in all_laws() if law.wizualizacja == "sets")


@pytest.fixture
def aplikacja():
    return create_app({"TESTING": True})


@pytest.fixture(scope="module")
def klient():
    return create_app({"TESTING": True}).test_client()


def _renderuj(aplikacja, partial: str, **zmienne):
    with aplikacja.test_request_context():
        return render_template(partial, **zmienne)


def _rysunki(prawo) -> dict:
    """Kontekst rysunków taki, jaki do szablonu podaje ``strona_prawa``."""
    return {"formula": prawo.formula, **widoki.diagramy(prawo)}


# ---------------------------------------------------------------------------
# Partiale rysunków — rysunek powstaje na serwerze (karta PRZ-123)
# ---------------------------------------------------------------------------

#: Partial rysunków razem z klasą montażu, rolą, rolą rysunku i tytułem figury.
PARTIALE = (
    ("partials/_gates.html", PRAWO_BRAMKI, "gates-mount", "bramki-logiczne", "rysunek-bramek"),
    ("partials/_sets.html", PRAWO_ZBIOROW, "sets-mount", "diagramy-zbiorow", "rysunek-zbiorow"),
)

#: Partial rysunków razem ze słownikiem kroków, z którego korzysta ``diagramy()``.
PARTIALE_Z_KROKAMI = (
    ("partials/_gates.html", PRAWO_BRAMKI, "bramki"),
    ("partials/_sets.html", PRAWO_ZBIOROW, "zbiory"),
)


@pytest.mark.parametrize(
    ("partial", "prawo", "klasa", "rola", "rola_rysunku"), PARTIALE, ids=["bramki", "zbiory"]
)
def test_partial_wstawia_gotowy_svg_z_serwera(aplikacja, partial, prawo, klasa, rola, rola_rysunku):
    """Kryterium PRZ-123: rysunek liczy Python, a partial wstawia gotowy ``<svg>``."""
    html = _renderuj(aplikacja, partial, **_rysunki(prawo))

    poczatek = html.index(f'data-rola="{rola_rysunku}"')
    koniec = html.index("</svg>", poczatek)

    assert f'class="{klasa}"' in html
    assert f'data-rola="{rola}"' in html
    assert f'data-formula="{escape(prawo.formula)}"' in html, "komponent nie zna wzoru prawa"
    assert "<svg" in html[poczatek:koniec], "rysunek musi stać w kontenerze, nie w szablonie"


def test_partial_bramek_pokazuje_oba_rysunki(aplikacja):
    """Kryterium PRZ-123: strona prawa ma schemat bramek i diagram zbiorów."""
    html = _renderuj(aplikacja, "partials/_gates.html", **_rysunki(PRAWO_BRAMKI))

    assert 'class="gates-mount"' in html
    assert 'class="sets-mount"' in html
    assert "Schemat bramek" in html
    assert "Diagram zbiorów" in html


def test_partial_zbiorow_stawia_zbior_pierwszy(aplikacja):
    html = _renderuj(aplikacja, "partials/_sets.html", **_rysunki(PRAWO_ZBIOROW))

    assert html.index('class="sets-mount"') < html.index('class="gates-mount"')


def test_partial_dolacza_skrypt_strzalek_i_arkusz(aplikacja):
    html = _renderuj(aplikacja, "partials/_gates.html", **_rysunki(PRAWO_BRAMKI))

    assert "/static/js/wizualizacje.js" in html
    assert 'type="module"' in html, "skrypt musi być modułem ES"
    assert html.count("/static/css/wizualizacje.css") == 1
    assert "url_for" not in html, "adresy plików statycznych rozwiązuje url_for"


def test_partial_nie_rysuje_juz_w_przegladarce(aplikacja):
    """Kryterium PRZ-123: stare skrypty i API zniknęły z partialu."""
    html = _renderuj(aplikacja, "partials/_sets.html", **_rysunki(PRAWO_ZBIOROW))

    assert "/static/js/gates.js" not in html
    assert "/static/js/sets.js" not in html
    assert "/api/formula" not in html, "rysunek nie potrzebuje API"


@pytest.mark.parametrize(
    ("partial", "prawo", "zbior"), PARTIALE_Z_KROKAMI, ids=["bramki", "zbiory"]
)
def test_partial_ma_dwie_strzalki_i_tyle_szablonow_co_krokow(aplikacja, partial, prawo, zbior):
    """Dwie strzałki i gotowe kroki w ``<template>`` na każdym z trzech rysunków.

    Partial pokazuje oba rysunki (kryterium PRZ-123), więc strzałek jest dwa razy
    tyle, ile ma jeden rysunek. Od PRZ-182 diagram zbiorów to **dwie osobne figury
    kroków** — lewa i prawa strona prawa — a schemat bramek idzie po podformułach,
    dlatego szablony i punkty listy liczymy osobno dla każdej figury.
    """
    rysunki = widoki.diagramy(prawo)
    wszystkie = (
        len(rysunki["bramki"]["kroki"])
        + len(rysunki["zbiory"]["lewa"]["kroki"])
        + len(rysunki["zbiory"]["prawa"]["kroki"])
    )

    html = _renderuj(aplikacja, partial, **_rysunki(prawo))

    assert html.count("<button") == 6, "dwie strzałki na każdy z trzech rysunków"
    assert 'aria-label="Poprzedni krok"' in html
    assert 'aria-label="Następny krok"' in html
    assert html.count("<template") == wszystkie
    assert html.count("</li>") == wszystkie, "lista opisów ma po jednym punkcie na krok"
    pierwszy = (
        rysunki["bramki"]["kroki"][0]["opis"]
        if zbior == "bramki"
        else rysunki["zbiory"]["lewa"]["kroki"][0]["opis"]
    )

    assert pierwszy in html


def test_partial_ma_noscript(aplikacja):
    html = _renderuj(aplikacja, "partials/_gates.html", **_rysunki(PRAWO_BRAMKI))

    assert "<noscript>" in html
    assert "JavaScript" in html


@pytest.mark.parametrize("partial", ["partials/_gates.html", "partials/_sets.html"])
def test_partial_nie_zostawia_nieuzupelnionych_szablonow(aplikacja, partial):
    prawo = PRAWO_BRAMKI if "gates" in partial else PRAWO_ZBIOROW
    html = _renderuj(aplikacja, partial, **_rysunki(prawo))

    assert "{{" not in html
    assert "{%" not in html


@pytest.mark.parametrize("partial", ["partials/_gates.html", "partials/_sets.html"])
def test_partial_bez_danych_rysunkow_pokazuje_komunikat(aplikacja, partial):
    """``_steps.html`` renderuje się także bez kontekstu rysunków — nie może się wywrócić."""
    html = _renderuj(aplikacja, partial, formula=FORMULA_BRAMKI)

    assert "Rysunek pojawi się" in html
    assert "{{" not in html


def test_partial_escapuja_wzor_w_atrybucie(aplikacja):
    """Wzór idzie do atrybutu, więc cudzysłów nie może wyjść z atrybutu."""
    kroki = [
        {
            "opis": "Opis kroku.",
            "wzor": Markup("<i>p</i>"),
            "svg": Markup('<svg class="wiz-svg"><title>Rysunek</title></svg>'),
        }
    ]

    html = _renderuj(
        aplikacja,
        "partials/_gates.html",
        formula='" onmouseover="alert(1)',
        bramki={"kroki": kroki},
        zbiory=None,
    )

    assert 'onmouseover="alert(1)"' not in html, "cudzysłów we wzorze nie może wyjść z atrybutu"
    assert "&#34;" in html
    assert 'data-rola="bramki-logiczne">' in html, "znacznik kontenera musi się domykać"


def test_partial_mowi_o_limicie_zbiorow(aplikacja):
    """Kryterium PRZ-075: partial mówi po polsku, ile zbiorów zmieści rysunek."""
    html = _renderuj(aplikacja, "partials/_sets.html", formula="p ∧ q")

    assert "co najwyżej trzy zbiory" in html


# ---------------------------------------------------------------------------
# Pliki statyczne
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sciezka", PLIKI)
def test_pliki_komponentu_istnieja_i_nie_sa_puste(sciezka):
    plik = KATALOG_STATYCZNY / sciezka

    assert plik.is_file(), f"brak pliku {sciezka}"
    assert plik.read_text(encoding="utf-8").strip(), f"plik {sciezka} jest pusty"


@pytest.fixture(scope="module")
def skrypt_bramek() -> str:
    return (KATALOG_STATYCZNY / "js" / "gates.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def skrypt_zbiorow() -> str:
    return (KATALOG_STATYCZNY / "js" / "sets.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def style() -> str:
    return (KATALOG_STATYCZNY / "css" / "wizualizacje.css").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# gates.js — drzewo na rysunek
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("typ", TYPY_WEZLOW)
def test_bramki_znaja_wszystkie_typy_wezlow(skrypt_bramek, typ):
    assert f'"{typ}"' in skrypt_bramek, f"brak obsługi węzła {typ}"


def test_bramki_rysuja_svg_w_przestrzeni_nazw(skrypt_bramek):
    assert "createElementNS(NS_SVG" in skrypt_bramek
    assert '"http://www.w3.org/2000/svg"' in skrypt_bramek


def test_bramki_skaluja_rysunek_do_kontenera(skrypt_bramek):
    assert "viewBox" in skrypt_bramek
    assert "preserveAspectRatio" in skrypt_bramek


def test_bramki_wstawiaja_tresc_tylko_przez_textcontent(skrypt_bramek):
    assert "textContent" in skrypt_bramek
    assert "innerHTML" not in skrypt_bramek
    assert "insertAdjacentHTML" not in skrypt_bramek
    assert "document.write" not in skrypt_bramek


def test_bramki_daja_kazdemu_elementowi_tytul(skrypt_bramek):
    """Jedna droga tworzenia elementu SVG — i w niej zawsze ``<title>`` z opisem."""
    assert 'createElementNS(NS_SVG, "title")' in skrypt_bramek
    assert re.search(r"function nowyElement\([^)]*\)[^{]*\{[^}]*title", skrypt_bramek), (
        "opis musi powstawać razem z elementem, w jednej funkcji"
    )
    # Nazwa zmiennej z API trafia do DOM wyłącznie przez `textContent`.
    assert re.search(r"\.textContent = nazwa;", skrypt_bramek)


def test_bramki_wola_api_i_obsluguja_jego_bledy(skrypt_bramek):
    assert "/api/formula/parse" in skrypt_bramek
    assert "pobierzJson(" in skrypt_bramek, "skrypt nie korzysta ze wspólnego klienta API"
    assert "if (!dane.ok)" in skrypt_bramek


def test_bramki_maja_polskie_komunikaty(skrypt_bramek):
    assert "Nie udało się połączyć z serwerem" in skrypt_bramek, "błąd sieci"
    assert "Serwer nie przysłał drzewa formuły" in skrypt_bramek, "brak ast"
    assert "Nie udało się narysować schematu" in skrypt_bramek, "pozostały błąd"


def test_bramki_maja_legende_z_symbolami(skrypt_bramek):
    for symbol in ("∼", "∧", "∨", "→", "↔"):
        assert f'symbol: "{symbol}"' in skrypt_bramek


# ---------------------------------------------------------------------------
# gates.js — kroki, strzałki i wartości na przewodach (PRZ-074)
# ---------------------------------------------------------------------------


def test_bramki_uzywaja_wspolnego_komponentu_krokow(skrypt_bramek):
    """Kryterium PRZ-074: kroki prowadzi ``createStepper``, a nie własny pasek."""
    assert 'from "/static/js/stepper.js"' in skrypt_bramek
    assert "createStepper({" in skrypt_bramek
    assert "onStep:" in skrypt_bramek


def test_bramki_maja_przelaczniki_wejsc(skrypt_bramek):
    """Kryterium PRZ-074: nad rysunkiem są przyciski ``0``/``1`` z ``aria-pressed``."""
    assert "[1, 0]" in skrypt_bramek, "przyciski powstają dla obu wartości"
    assert "wiz-przelacznik" in skrypt_bramek
    assert 'setAttribute("aria-pressed"' in skrypt_bramek
    assert "Wartości wejść układu" in skrypt_bramek


def test_bramki_zmieniaja_wartosci_bez_przerysowania_montazu(skrypt_bramek):
    """Zmiana wejścia przelicza kroki, ale pasek i rysunek zostają na miejscu."""
    assert "znajdzWiersz(" in skrypt_bramek, "wiersz tablicy wybieramy po wartościowaniu"
    assert "odswiez(" in skrypt_bramek
    assert "stepper.destroy()" in skrypt_bramek, "stary pasek musi zniknąć przed nowym"


def test_bramki_znak_zapytania_dla_nieznanych_przewodow(skrypt_bramek):
    """Kryterium PRZ-074: nieznana wartość przewodu to ``?``, nie pusty napis."""
    assert 'znakNieznany: "?"' in skrypt_bramek
    assert "wiz-nieznane" in skrypt_bramek


def test_bramki_rysuja_strzalki_na_przewodach(skrypt_bramek):
    """Kryterium PRZ-074: każdy przewód kończy się grotem (``marker-end``)."""
    assert '"marker-end"' in skrypt_bramek
    assert 'nowyElement("marker"' in skrypt_bramek
    assert 'setAttribute("orient", "auto")' in skrypt_bramek


def test_bramki_oznaczaja_biezaca_bramke(skrypt_bramek):
    """Kryterium PRZ-074: bieżąca bramka ma ``aria-current="true"``."""
    assert 'setAttribute("aria-current", "true")' in skrypt_bramek
    assert 'removeAttribute("aria-current")' in skrypt_bramek


def test_bramki_opisuja_wartosci_slowami(skrypt_bramek):
    """Kryterium PRZ-074: wartość przewodu niesie słowo, nie tylko kolor."""
    assert 'prawda: "PRAWDA"' in skrypt_bramek
    assert 'falsz: "FAŁSZ"' in skrypt_bramek
    assert "wiz-prawda" in skrypt_bramek
    assert "wiz-falsz" in skrypt_bramek


def test_bramki_krok_opisuje_bramke_po_polsku(skrypt_bramek):
    """Kryterium PRZ-074: krok mówi np. „Bramka AND: 1 i 0 daje 0”."""
    assert "Bramka ${node.typ}: ${lewy} i ${prawy} daje ${wynik}" in skrypt_bramek
    assert "Bramka NOT: z ${" in skrypt_bramek


def test_bramki_ostatni_krok_mowi_o_calej_formule(skrypt_bramek):
    """Kryterium PRZ-074: ostatni krok opisuje wynik całej formuły słowami."""
    assert 'wynikCalkowity: "Cała formuła ma wartość"' in skrypt_bramek


def test_bramki_biora_wartosci_z_tablicy_podformul(skrypt_bramek):
    """Kryterium PRZ-074: wartości podformuł są gotowe z API, bez liczenia logiki w JS."""
    assert "/api/formula/table" in skrypt_bramek
    assert "podformuly: true" in skrypt_bramek
    assert '"values"' in skrypt_bramek, "pole z wynikami kolumn tablicy"
    assert "evaluate" not in skrypt_bramek, "logikę liczy serwer, nie przeglądarka"


def test_bramki_sprawdzaja_zgodnosc_kolumn_z_podformulami(skrypt_bramek):
    """Wartość bierzemy z kolumny o tym samym indeksie — rozjazd to komunikat, nie błąd."""
    assert "kolumny.length !== kolejnosc.length" in skrypt_bramek


def test_bramki_nie_wstawiaja_danych_z_api_przez_innerhtml(skrypt_bramek):
    """Kryterium PRZ-074: drzewo i wartości z API trafiają do DOM tylko przez tekst."""
    assert "innerHTML" not in skrypt_bramek
    assert "insertAdjacentHTML" not in skrypt_bramek
    assert ".textContent = opis;" in skrypt_bramek
    assert ".textContent = TEKSTY.znakNieznany;" in skrypt_bramek


# ---------------------------------------------------------------------------
# sets.js — obszary liczone z drzewa
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("typ", TYPY_WEZLOW)
def test_zbiory_znaja_wszystkie_typy_wezlow(skrypt_zbiorow, typ):
    assert f'case "{typ}"' in skrypt_zbiorow, f"brak obsługi węzła {typ}"


def test_zbiory_rysuja_obie_strony_prawa(skrypt_zbiorow):
    assert "dataset.lewa" in skrypt_zbiorow
    assert "dataset.prawa" in skrypt_zbiorow
    assert "Lewa strona:" in skrypt_zbiorow
    assert "Prawa strona:" in skrypt_zbiorow


def test_zbiory_licza_obszary_z_drzewa(skrypt_zbiorow):
    assert "function ocena(" in skrypt_zbiorow, "brak liczenia wartości formuły"
    assert "function obszary(" in skrypt_zbiorow
    assert "1 << zmienne.length" in skrypt_zbiorow, "obszarów jest tyle, ile wartościowań"


def test_zbiory_licza_obszary_na_siatce(skrypt_zbiorow):
    """Kryterium PRZ-075: obszary liczymy na siatce próbek, a nie z kombinacji figur."""
    kolumny = re.search(r"KOLUMNY_SIATKI = (\d+)", skrypt_zbiorow)
    wiersze = re.search(r"WIERSZE_SIATKI = (\d+)", skrypt_zbiorow)

    assert kolumny and wiersze, "brak gęstości siatki próbek"
    gestosc = int(kolumny.group(1)) * int(wiersze.group(1))
    assert 100 * 100 <= gestosc <= 500 * 500, "siatka ma być gęsta, ale nie ogromna"
    assert "function wKole(" in skrypt_zbiorow, "próbka pyta, czy leży w kole zbioru"
    assert "function sciezkaObszaru(" in skrypt_zbiorow, "brak ścieżki z próbek"
    assert 'nowyElement("path"' in skrypt_zbiorow, "obszar rysuje ścieżka"
    assert "clipPath" not in skrypt_zbiorow, "obszarów nie składamy z przyciętych figur"


def test_zbiory_skaluja_rysunek_do_kontenera(skrypt_zbiorow):
    assert "viewBox" in skrypt_zbiorow
    assert "preserveAspectRatio" in skrypt_zbiorow


def test_zbiory_wstawiaja_tresc_tylko_przez_textcontent(skrypt_zbiorow):
    assert "textContent" in skrypt_zbiorow
    assert "innerHTML" not in skrypt_zbiorow
    assert "insertAdjacentHTML" not in skrypt_zbiorow
    assert "document.write" not in skrypt_zbiorow
    assert re.search(r"\.textContent = zmienne\[indeks\];", skrypt_zbiorow)


def test_zbiory_daja_kazdemu_elementowi_tytul(skrypt_zbiorow):
    assert 'createElementNS(NS_SVG, "title")' in skrypt_zbiorow
    assert "function nowyElement(" in skrypt_zbiorow


def test_zbiory_maja_podpis_o_tym_samym_obszarze(skrypt_zbiorow):
    assert (
        "Zamalowany obszar jest taki sam po obu stronach — dlatego wzory są równoważne."
        in skrypt_zbiorow
    )


def test_zbiory_maja_polskie_komunikaty(skrypt_zbiorow):
    assert "Nie udało się połączyć z serwerem" in skrypt_zbiorow, "błąd sieci"
    assert "Serwer nie przysłał drzewa formuły" in skrypt_zbiorow, "brak ast"
    assert "if (!dane.ok)" in skrypt_zbiorow, "błąd danych z API"
    assert "Diagram zbiorów rysuje tylko negację" in skrypt_zbiorow, "brak sensu zbiorowego"
    assert "co najwyżej" in skrypt_zbiorow, "za dużo zmiennych"


def test_zbiory_nie_rysuja_wiecej_niz_trzy_kola(skrypt_zbiorow):
    assert "MAKS_ZBIOROW = 3" in skrypt_zbiorow
    assert "UKLADY" in skrypt_zbiorow


# ---------------------------------------------------------------------------
# sets.js — kroki, strzałka i przełącznik (PRZ-075)
# ---------------------------------------------------------------------------


def _cialo_funkcji(skrypt: str, nazwa: str) -> str:
    """Treść funkcji ``nazwa`` — od jej nawiasu klamrowego do zamykającego.

    Kolejność wywołań w ciele funkcji jest tym, co odróżnia „komunikat zamiast rysunku”
    od „rysunek i komunikat”: nawiasy liczymy ręcznie, bo w ciele są także literały
    szablonowe z ``${...}``.
    """
    poczatek = skrypt.index(f"function {nazwa}(")
    otwarcie = skrypt.index("{", poczatek)
    glebokosc = 0
    for pozycja in range(otwarcie, len(skrypt)):
        if skrypt[pozycja] == "{":
            glebokosc += 1
        elif skrypt[pozycja] == "}":
            glebokosc -= 1
            if glebokosc == 0:
                return skrypt[otwarcie:pozycja]
    raise AssertionError(f"nie znalazłem ciała funkcji {nazwa}")


def test_zbiory_uzywaja_wspolnego_komponentu_krokow(skrypt_zbiorow):
    """Kryterium PRZ-075: kroki prowadzi ``createStepper``, a nie własny pasek."""
    assert 'from "/static/js/stepper.js"' in skrypt_zbiorow
    assert "createStepper({" in skrypt_zbiorow
    assert "onStep:" in skrypt_zbiorow
    assert 'setAttribute("data-stepper", "")' in skrypt_zbiorow


@pytest.mark.parametrize("slug", PRAWA_ZBIOROW)
def test_zbiory_biora_kroki_z_formuly_prawa(aplikacja, slug):
    """Kryterium PRZ-123: kroki rysunku powstają z wzoru prawa, a nie z pola ``kroki``."""
    prawo = next(law for law in all_laws() if law.slug == slug)
    zbiory = widoki.diagramy(prawo)["zbiory"]
    kroki = zbiory["lewa"]["kroki"] + zbiory["prawa"]["kroki"]

    html = _renderuj(aplikacja, "partials/_sets.html", **_rysunki(prawo))

    assert kroki, f"brak kroków rysunku dla {slug}"
    assert kroki[0]["opis"] in html, "partial gubi opisy kroków rysunku"
    assert len(kroki) == len(kroki_sets(parse(prawo.formula))), f"zła liczba kroków dla {slug}"


@pytest.mark.parametrize("slug", PRAWA_ZBIOROW)
def test_zbiory_kroki_pokrywaja_operacje_obu_stron(slug):
    """Kryterium PRZ-172: krok to jedna operacja, a ostatni domyka prawą stronę.

    Karta PRZ-172 zastąpiła dla diagramu zbiorów kryterium PRZ-123 „każdy krok to
    jedna podformuła”: kroki liczą się teraz po operacjach na zbiorach i idą
    najpierw po lewej stronie prawa, potem po prawej. Od PRZ-182 każda strona to
    osobny panel kroków, więc listę widoku składamy z obu paneli.
    """
    prawo = next(law for law in all_laws() if law.slug == slug)
    zbiory = widoki.diagramy(prawo)["zbiory"]
    kroki = zbiory["lewa"]["kroki"] + zbiory["prawa"]["kroki"]
    zrodlo = kroki_sets(parse(prawo.formula))
    pary = [(krok["strona"], krok["wzor"]) for krok in zrodlo]

    assert len(kroki) == len(zrodlo), "kroki rysunku pochodzą z wzoru prawa"
    assert len(pary) == len(set(pary)), "operacja nie może powtórzyć się na tej samej stronie"
    assert zrodlo[0]["strona"] == "lewa", "lista zaczyna się od lewej strony prawa"
    assert zrodlo[-1]["wzor"] == to_text(parse(prawo.prawa)), "ostatni krok domyka prawą stronę"


def test_zbiory_rysuja_strzalke_rownowaznosci(skrypt_zbiorow):
    """Kryterium PRZ-075: między diagramami jest strzałka z opisem „≡”."""
    assert 'elementHtml("div", "wiz-strzalka", "≡")' in skrypt_zbiorow
    assert 'setAttribute("data-rola", "strzalka-rownowaznosci")' in skrypt_zbiorow
    assert "Lewa strona jest równoważna prawej" in skrypt_zbiorow, "brak opisu strzałki"


def test_zbiory_kazdy_krok_ma_polski_opis(skrypt_zbiorow):
    """Kryterium PRZ-075: nazwa operacji i opis kroku stoją po polsku przy diagramie."""
    assert "krok.opis" in skrypt_zbiorow, "opis kroku pochodzi z prawa"
    assert 'setAttribute("data-rola", "opis-kroku")' in skrypt_zbiorow
    assert 'setAttribute("data-rola", "nazwa-operacji")' in skrypt_zbiorow
    assert "${indeks + 1}: ${op.nazwa} — ${op.opis}" in skrypt_zbiorow
    for nazwa in ('nazwa: "suma"', 'nazwa: "część wspólna"', 'nazwa: "dopełnienie"'):
        assert nazwa in skrypt_zbiorow, f"brak nazwy operacji {nazwa}"


def test_zbiory_podpisuja_poprzednie_obszary_obrysem(skrypt_zbiorow):
    """Kryterium PRZ-075: wcześniejsze obszary zostają widoczne jako obrys."""
    assert "wiz-obrys-obszaru" in skrypt_zbiorow
    assert "sciezkiKrokow.slice(0, indeks)" in skrypt_zbiorow


def test_zbiory_rysuja_obrys_obszaru_ponad_wypelnieniem(skrypt_zbiorow):
    """Kryterium PRZ-075: obrys wcześniejszego kroku leży nad wypełnieniem bieżącego.

    SVG nie zna ``z-index`` — późniejszy element zasłania wcześniejszy. Przy przekształceniach
    równoważnych (na przykład krok 3 i krok 1 w prawie de Morgana) oba obszary mają ten sam
    kształt, więc wypełnienie dołożone po obrysach zasłoniłoby obrys i student nie zobaczyłby,
    że to ten sam obszar. Pilnujemy kolejności argumentów ``append`` na rysunku.
    """
    cialo = _cialo_funkcji(skrypt_zbiorow, "zbudujDiagram")
    argumenty = [
        dopasowanie.group(1) for dopasowanie in re.finditer(r"rysunek\.append\(([^)]*)\)", cialo)
    ]
    razem = [
        argument for argument in argumenty if "wypelnienie" in argument and "obrysy" in argument
    ]

    assert razem, "wypełnienie i obrysy muszą trafić na rysunek jednym `append`"
    kolejnosc = [czesc.strip() for czesc in razem[0].split(",")]
    assert kolejnosc.index("wypelnienie") < kolejnosc.index("obrysy"), (
        "wypełnienie bieżącego kroku powstaje po obrysach — zasłoni obrys obszaru o tym samym "
        "kształcie, więc student nie zobaczy, że obszar się nie zmienił"
    )


def test_zbiory_nie_rysuja_kroku_bez_formuly(skrypt_zbiorow):
    """Krok prawa z pustym ``po`` nie przewraca rysunku.

    Przegląd PRZ-075 (raport ``f3ff62b``) wskazał, że ``drzewa.get(undefined)`` rzuca
    wyjątkiem, gdy krok nie ma formuły. Krok bez drzewa musi więc zawrócić do kroków
    z podformuł obu stron, zamiast sięgać po ``undefined``.
    """
    cialo = _cialo_funkcji(skrypt_zbiorow, "wypelnij")

    assert "krokiPrawa.every((krok) => drzewa.has(krok.po))" in cialo, "brak sprawdzenia drzew"
    assert "krokiZapasowe(" in cialo, "brak kroków zapasowych dla kroku bez formuły"


def test_zbiory_pokazuja_oba_obszary_naraz(skrypt_zbiorow):
    """Kryterium PRZ-075: przełącznik pokazuje oba docelowe obszary jednocześnie."""
    assert 'pokazOba: "Pokaż oba naraz"' in skrypt_zbiorow
    assert "function przelaczOba(" in skrypt_zbiorow
    assert 'setAttribute("aria-pressed", widokOba ? "true" : "false")' in skrypt_zbiorow
    assert "ustawObszar(diagramLewy, sciezkaLewa, [])" in skrypt_zbiorow
    assert "ustawObszar(diagramPrawy, sciezkaPrawa, [])" in skrypt_zbiorow


def test_zbiory_komunikat_o_zbyt_wielu_zbiorach_przed_rysunkiem(skrypt_zbiorow):
    """Kryterium PRZ-075: przy czterech zbiorach zostaje komunikat, a nie rysunek.

    Sprawdzamy kolejność w ciele ``wypelnij``: strażnik liczby zmiennych kończy pracę
    (``return``) zanim powstanie pierwszy diagram, więc dla czterech zmiennych żaden
    element SVG nie jest tworzony.
    """
    cialo = _cialo_funkcji(skrypt_zbiorow, "wypelnij")
    straznik = cialo.index("co najwyżej")
    rysunek = cialo.index("zbudujDiagram(")

    assert straznik < rysunek, "rysunek powstaje przed sprawdzeniem liczby zbiorów"
    assert "return" in cialo[straznik:rysunek], "strażnik musi przerwać rysowanie"


# ---------------------------------------------------------------------------
# wizualizacje.js — dwie strzałki i gotowe kroki (karta PRZ-123)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def skrypt_wizualizacji() -> str:
    return (KATALOG_STATYCZNY / "js" / "wizualizacje.js").read_text(encoding="utf-8")


def test_wizualizacje_podmieniaja_gotowy_krok_z_szablonu(skrypt_wizualizacji):
    """Kryterium PRZ-123: kroki czekają w ``<template>``, a skrypt je tylko podmienia."""
    assert "template[data-wiz-krok]" in skrypt_wizualizacji
    assert "cloneNode(true)" in skrypt_wizualizacji
    assert "replaceWith(" in skrypt_wizualizacji


def test_wizualizacje_nie_rysuja_i_nie_pobieraja_nic_z_api(skrypt_wizualizacji):
    assert "createElementNS" not in skrypt_wizualizacji, "rysunek powstaje na serwerze"
    assert "fetch(" not in skrypt_wizualizacji
    assert "/api/" not in skrypt_wizualizacji


def test_wizualizacje_nie_pisza_przez_innerhtml(skrypt_wizualizacji):
    for zakazane in ("innerHTML", "insertAdjacentHTML", "document.write"):
        assert zakazane not in skrypt_wizualizacji


def test_wizualizacje_obsluguja_dwie_strzalki(skrypt_wizualizacji):
    assert '"[data-wiz-poprzedni]"' in skrypt_wizualizacji
    assert '"[data-wiz-nastepny]"' in skrypt_wizualizacji
    assert "disabled" in skrypt_wizualizacji
    assert 'setAttribute("aria-disabled"' in skrypt_wizualizacji, "stan strzałki słownie"


def test_wizualizacje_oglaszaja_biezacy_krok(skrypt_wizualizacji):
    assert 'setAttribute("aria-current", "step")' in skrypt_wizualizacji
    assert 'removeAttribute("aria-current")' in skrypt_wizualizacji


def test_wizualizacje_obsluguja_klawiature(skrypt_wizualizacji):
    assert "keydown" in skrypt_wizualizacji
    assert '"ArrowLeft"' in skrypt_wizualizacji
    assert '"ArrowRight"' in skrypt_wizualizacji


def test_wizualizacje_przycinaja_numer_kroku(skrypt_wizualizacji):
    """Numer spoza listy jest przycinany — tak samo jak w ``stepper.js``."""
    assert "Math.max(0, Math.min(" in skrypt_wizualizacji


# ---------------------------------------------------------------------------
# Dostępność i style
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sciezka", PLIKI[:2])
def test_skrypty_oglaszaja_wynik_czytnikowi_ekranu(sciezka):
    """Rysunek jest obrazem, więc wynik musi być opisany tekstem i ogłoszony."""
    skrypt = (KATALOG_STATYCZNY / sciezka).read_text(encoding="utf-8")

    assert 'setAttribute("role", "status")' in skrypt
    assert 'setAttribute("aria-live", "polite")' in skrypt
    assert '"role", "img"' in skrypt
    assert "aria-label" in skrypt


def _wywolania_replace_children(skrypt: str) -> list[tuple[int, str]]:
    """Pozycja i tekst argumentów każdego wywołania ``replaceChildren(...)``.

    Nawiasy liczymy ręcznie, bo argumenty bywają zagnieżdżone
    (``zbudujLegende(zbierzTypy(...))``) — prosty wzorzec urwałby się na pierwszym ``)``
    i przeoczył ``status`` stojący na końcu listy argumentów.
    """
    wywolania = []
    for trafienie in re.finditer(r"replaceChildren\(", skrypt):
        glebokosc = 1
        koniec = trafienie.end()
        while glebokosc and koniec < len(skrypt):
            if skrypt[koniec] == "(":
                glebokosc += 1
            elif skrypt[koniec] == ")":
                glebokosc -= 1
            koniec += 1
        wywolania.append((trafienie.start(), skrypt[trafienie.end() : koniec - 1]))
    return wywolania


def _numer_linii(skrypt: str, pozycja: int) -> int:
    return skrypt.count("\n", 0, pozycja) + 1


@pytest.mark.parametrize("sciezka", PLIKI[:2])
def test_przerysowanie_montazu_zostawia_status_w_dom(sciezka):
    """Region ``aria-live`` musi zostać w dokumencie, inaczej czytnik ekranu milczy.

    Przegląd PRZ-012 (raport ``35045ee``) wykrył, że ``replaceChildren`` podmieniał dzieci
    montażu bez elementu ``status``, a ustawienie ``status.textContent`` szło wtedy w węzeł
    odłączony od dokumentu. Po utworzeniu ``status`` każde przerysowanie montażu musi go
    dołożyć; wolno je pominąć wyłącznie w początkowym czyszczeniu, zanim ``status`` powstanie.
    """
    skrypt = (KATALOG_STATYCZNY / sciezka).read_text(encoding="utf-8")
    utworzenie = skrypt.index("const status")

    odlaczajace = [
        f"linia {_numer_linii(skrypt, pozycja)}"
        for pozycja, argumenty in _wywolania_replace_children(skrypt)
        if "status" not in argumenty and not (pozycja < utworzenie and not argumenty.strip())
    ]

    assert not odlaczajace, (
        f"{sciezka}: {', '.join(odlaczajace)} — `replaceChildren` bez elementu `status` "
        "odłącza go od DOM, więc czytnik ekranu nie ogłosi wyniku"
    )


def test_style_maja_klasy_rysunkow(style):
    """Klasy, które wypisuje ``app/logic/diagrams.py`` — bez nich rysunek zniknie."""
    for klasa in (
        ".wiz-svg",
        ".wiz-przewod",
        ".wiz-obrys",
        ".wiz-przestrzen",
        ".obszar-1",
        ".obszar-2",
    ):
        assert klasa in style, f"brak stylu {klasa}"


def test_style_maja_kroki_bramek(style):
    """Klasy kroków z PRZ-074: grot strzałki, wartości przewodów i strzałki paska."""
    for klasa in (
        ".wiz-grot",
        ".wiz-prawda",
        ".wiz-falsz",
        ".wiz-nieznane",
        ".wiz-biezaca",
        ".wiz-wartosc",
        ".wiz-strzalka",
    ):
        assert klasa in style, f"brak stylu {klasa}"


def test_style_grubosc_przewodu_niesie_wartosc(style):
    """Przewód z wartością 1 jest grubszy od tego z 0 — grubość widać bez koloru."""
    gruby = re.search(r"\.wiz-przewod\.wiz-prawda\s*\{[^}]*stroke-width:\s*([\d.]+)", style)
    cienki = re.search(r"\.wiz-przewod\.wiz-falsz\s*\{[^}]*stroke-width:\s*([\d.]+)", style)

    assert gruby and cienki, "brak grubości przewodów PRAWDA/FAŁSZ"
    assert float(gruby.group(1)) > float(cienki.group(1))


# ---------------------------------------------------------------------------
# Strona prawa (integracja z PRZ-010)
# ---------------------------------------------------------------------------


def test_strona_prawa_nie_rysuje_juz_w_przegladarce(klient):
    """Kryterium PRZ-123: strona prawa nie ładuje starych skryptów ani sięga do API."""
    prawa = [law for law in all_laws() if law.wizualizacja in ("gates", "switch", "sets")]
    assert prawa, "rejestr nie ma praw z wizualizacją „gates” ani „sets”"

    for law in prawa:
        html = klient.get(f"/prawa/{law.slug}").get_data(as_text=True)

        assert "/static/js/gates.js" not in html, f"stary skrypt na stronie {law.slug}"
        assert "/static/js/sets.js" not in html, f"stary skrypt na stronie {law.slug}"
        assert "/static/js/wizualizacje.js" in html, f"brak skryptu strzałek dla {law.slug}"
        assert "/static/css/wizualizacje.css" in html, f"brak arkusza rysunków dla {law.slug}"
