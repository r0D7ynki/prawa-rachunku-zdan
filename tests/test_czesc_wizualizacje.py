"""Testy wizualizacji: schemat bramek i diagramy zbiorów (karty PRZ-012, PRZ-074, PRZ-075).

Rysunki powstają w przeglądarce z drzewa ``ast``, więc testy nie mogą narysować SVG.
Sprawdzają więc dwie rzeczy, które da się sprawdzić bez przeglądarki:

* co partial oddaje serwerowi (atrybuty kontenera, pliki statyczne, ``<noscript>``,
  kroki prawa wpisane w ``[data-kroki]``),
* jak zbudowany jest skrypt — czy drzewo z API trafia do DOM wyłącznie przez
  ``textContent`` i ``document.createElementNS``, czy każdy element dostaje ``<title>``,
  czy kroki prowadzi ``createStepper`` i czy każdy błąd ma komunikat po polsku.

Wzorzec testu źródłowego jest ten sam, co w ``tests/test_czesc_kroki.py``.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import render_template
from markupsafe import escape

from app import create_app
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


@pytest.fixture
def aplikacja():
    return create_app({"TESTING": True})


@pytest.fixture(scope="module")
def klient():
    return create_app({"TESTING": True}).test_client()


def _renderuj(aplikacja, partial: str, **zmienne):
    with aplikacja.test_request_context():
        return render_template(partial, **zmienne)


# ---------------------------------------------------------------------------
# Partial _gates.html
# ---------------------------------------------------------------------------


def test_bramki_renderuja_kontener_z_formula(aplikacja):
    html = _renderuj(aplikacja, "partials/_gates.html", formula=FORMULA_BRAMKI)

    assert 'class="gates-mount"' in html
    assert f'data-formula="{FORMULA_BRAMKI}"' in html
    assert 'data-rola="bramki-logiczne"' in html


def test_bramki_dolaczaja_skrypt_i_style(aplikacja):
    html = _renderuj(aplikacja, "partials/_gates.html", formula=FORMULA_BRAMKI)

    assert "/static/js/gates.js" in html
    assert "/static/css/wizualizacje.css" in html
    assert 'type="module"' in html, "skrypt musi być modułem ES"


def test_bramki_obsluguja_brak_javascriptu(aplikacja):
    html = _renderuj(aplikacja, "partials/_gates.html", formula=FORMULA_BRAMKI)

    assert "<noscript>" in html
    assert "JavaScript" in html


def test_bramki_nie_zostawiaja_nieuzupelnionych_szablonow(aplikacja):
    html = _renderuj(aplikacja, "partials/_gates.html", formula=FORMULA_BRAMKI)

    assert "{{" not in html
    assert "{%" not in html


def test_bramki_escapuja_formule_w_atrybucie(aplikacja):
    html = _renderuj(aplikacja, "partials/_gates.html", formula='" onmouseover="alert(1)')

    assert 'onmouseover="' not in html, "cudzysłów we wzorze nie może wyjść z atrybutu"
    assert "&#34;" in html
    assert 'data-rola="bramki-logiczne">' in html, "znacznik kontenera musi się domykać"


def test_bramki_pokazuja_wzor_bez_javascriptu(aplikacja):
    """Kryterium PRZ-074: bez JavaScriptu zostaje wzór i komunikat, nie pusty kontener."""
    html = _renderuj(aplikacja, "partials/_gates.html", formula=FORMULA_BRAMKI)

    assert "Wzór:" in html
    assert FORMULA_BRAMKI in html


def test_bramki_pokazuja_opis_slowny_gdy_strona_go_podaje(aplikacja):
    """Strona prawa (PRZ-010) wstawia partial z obiektem ``prawo`` w kontekście."""
    prawo = SimpleNamespace(
        formula=FORMULA_BRAMKI, po_ludzku="Zdanie jest prawdziwe albo fałszywe."
    )

    html = _renderuj(aplikacja, "partials/_gates.html", formula=FORMULA_BRAMKI, prawo=prawo)

    assert "Zdanie jest prawdziwe albo fałszywe." in html


# ---------------------------------------------------------------------------
# Partial _sets.html
# ---------------------------------------------------------------------------


def test_zbiory_renderuja_kontener_z_formula(aplikacja):
    html = _renderuj(aplikacja, "partials/_sets.html", formula=FORMULA_ZBIORY)

    assert 'class="sets-mount"' in html
    assert f'data-formula="{FORMULA_ZBIORY}"' in html
    assert 'data-rola="diagramy-zbiorow"' in html


def test_zbiory_biora_obie_strony_z_zmiennych(aplikacja):
    html = _renderuj(
        aplikacja,
        "partials/_sets.html",
        formula=FORMULA_ZBIORY,
        lewa="∼(p ∨ q)",
        prawa="∼p ∧ ∼q",
    )

    assert 'data-lewa="∼(p ∨ q)"' in html
    assert 'data-prawa="∼p ∧ ∼q"' in html


def test_zbiory_biora_obie_strony_z_prawa(aplikacja):
    """Strona prawa (PRZ-010) wstawia partial z obiektem ``prawo`` w kontekście."""
    prawo = SimpleNamespace(lewa="(p ∨ q) ∧ r", prawa="(p ∧ r) ∨ (q ∧ r)")

    html = _renderuj(aplikacja, "partials/_sets.html", formula=FORMULA_ZBIORY, prawo=prawo)

    assert 'data-lewa="(p ∨ q) ∧ r"' in html
    assert 'data-prawa="(p ∧ r) ∨ (q ∧ r)"' in html
    assert f'data-formula="{FORMULA_ZBIORY}"' in html


def test_zbiory_bez_stron_rysuja_formule_po_obu_stronach(aplikacja):
    html = _renderuj(aplikacja, "partials/_sets.html", formula=FORMULA_ZBIORY)

    assert f'data-lewa="{FORMULA_ZBIORY}"' in html
    assert f'data-prawa="{FORMULA_ZBIORY}"' in html


def test_zbiory_dolaczaja_skrypt_i_style(aplikacja):
    html = _renderuj(aplikacja, "partials/_sets.html", formula=FORMULA_ZBIORY)

    assert "/static/js/sets.js" in html
    assert "/static/css/wizualizacje.css" in html
    assert 'type="module"' in html, "skrypt musi być modułem ES"


def test_zbiory_obsluguja_brak_javascriptu(aplikacja):
    html = _renderuj(aplikacja, "partials/_sets.html", formula=FORMULA_ZBIORY)

    assert "<noscript>" in html
    assert "JavaScript" in html


def test_zbiory_nie_zostawiaja_nieuzupelnionych_szablonow(aplikacja):
    html = _renderuj(aplikacja, "partials/_sets.html", formula=FORMULA_ZBIORY)

    assert "{{" not in html
    assert "{%" not in html


@pytest.mark.parametrize(
    "partial", ["partials/_gates.html", "partials/_sets.html"], ids=["bramki", "zbiory"]
)
def test_kazdy_partial_ma_tyle_samo_skryptow_co_stylow(aplikacja, partial):
    """Partial sam dołącza swój skrypt i arkusz — nie zależy od szablonu strony."""
    html = _renderuj(aplikacja, partial, formula=FORMULA_BRAMKI)

    assert html.count("<script") == 1
    assert html.count("/static/css/wizualizacje.css") == 1
    assert "url_for" not in html, "adresy plików statycznych rozwiązuje url_for"


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
    assert "fetch(" in skrypt_bramek
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
def test_zbiory_biora_kroki_z_prawa(aplikacja, slug):
    """Kryterium PRZ-075: liczba kroków paska równa się liczbie wpisów ``kroki`` prawa."""
    prawo = next(law for law in all_laws() if law.slug == slug)

    html = _renderuj(aplikacja, "partials/_sets.html", formula=prawo.formula, prawo=prawo)

    assert html.count("<li data-opis=") == len(prawo.kroki), f"zła liczba kroków dla {slug}"
    assert prawo.kroki[0].opis in html, "partial gubi opisy kroków prawa"


@pytest.mark.parametrize("slug", PRAWA_ZBIOROW)
def test_zbiory_krok_pierwszy_to_lewa_strona_ostatni_prawa(slug):
    """Kryterium PRZ-075: krok 0 pokazuje obszar lewej strony, ostatni — prawej.

    ``sets.js`` rysuje na kroku ``i`` obszar formuły ``kroki[i].po``. Test pilnuje więc
    danych: pierwsza formuła kroków to lewa strona prawa, a ostatnia — prawa.
    """
    prawo = next(law for law in all_laws() if law.slug == slug)

    assert prawo.kroki[0].po == prawo.lewa
    assert prawo.kroki[-1].po == prawo.prawa


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


def test_zbiory_partial_mowi_o_limicie_zbiorow(aplikacja):
    """Kryterium PRZ-075: partial mówi po polsku, ile zbiorów zmieści rysunek."""
    html = _renderuj(aplikacja, "partials/_sets.html", formula=FORMULA_ZBIORY)

    assert "co najwyżej trzy zbiory" in html


def test_zbiory_escapuja_opis_kroku_w_atrybucie(aplikacja):
    """Opis kroku idzie do atrybutu, więc cudzysłów nie może wyjść z atrybutu."""
    kroki = [
        SimpleNamespace(opis='" onclick="alert(1)', przed="∼p", po="∼p", regula="założenie"),
    ]
    prawo = SimpleNamespace(lewa="∼p", prawa="∼p", kroki=kroki)

    html = _renderuj(aplikacja, "partials/_sets.html", formula="∼p", prawo=prawo)

    assert 'onclick="' not in html
    assert "&#34;" in html
    assert 'data-rola="diagramy-zbiorow">' in html, "znacznik kontenera musi się domykać"


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


def test_style_maja_klasy_uzywane_przez_skrypty(style):
    for klasa in (".wiz-svg", ".wiz-przewod", ".wiz-obszar", ".wiz-obrys", ".wiz-diagramy"):
        assert klasa in style, f"brak stylu {klasa}"


def test_style_maja_kroki_bramek(style):
    """Klasy kroków z PRZ-074: grot strzałki, wartości przewodów i przełączniki wejść."""
    for klasa in (
        ".wiz-grot",
        ".wiz-prawda",
        ".wiz-falsz",
        ".wiz-nieznane",
        ".wiz-biezaca",
        ".wiz-wartosc",
        ".wiz-przelacznik",
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


def _prawa(rodzaj: str):
    return [law for law in all_laws() if law.wizualizacja == rodzaj]


def test_strona_prawa_z_zbiorami_podaje_obie_strony(klient):
    prawa = _prawa("sets")
    assert prawa, "rejestr nie ma prawa z wizualizacją „sets”"

    for law in prawa:
        html = klient.get(f"/prawa/{law.slug}").get_data(as_text=True)

        assert 'class="sets-mount"' in html, f"brak diagramu na stronie {law.slug}"
        assert f'data-lewa="{escape(law.lewa)}"' in html, f"zła lewa strona dla {law.slug}"
        assert f'data-prawa="{escape(law.prawa)}"' in html, f"zła prawa strona dla {law.slug}"


def test_strona_prawa_z_bramkami_podaje_formule(klient):
    prawa = [law for law in all_laws() if law.wizualizacja in ("gates", "switch")]
    assert prawa, "rejestr nie ma prawa z wizualizacją „gates”"

    for law in prawa:
        html = klient.get(f"/prawa/{law.slug}").get_data(as_text=True)

        assert 'class="gates-mount"' in html, f"brak schematu na stronie {law.slug}"
        assert f'data-formula="{escape(law.formula)}"' in html
        assert "/static/js/gates.js" in html
