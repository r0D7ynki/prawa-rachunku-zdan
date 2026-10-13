"""Testy wizualizacji: schemat bramek i diagramy zbiorów (karta PRZ-012).

Rysunki powstają w przeglądarce z drzewa ``ast``, więc testy nie mogą narysować SVG.
Sprawdzają więc dwie rzeczy, które da się sprawdzić bez przeglądarki:

* co partial oddaje serwerowi (atrybuty kontenera, pliki statyczne, ``<noscript>``),
* jak zbudowany jest skrypt — czy drzewo z API trafia do DOM wyłącznie przez
  ``textContent`` i ``document.createElementNS``, czy każdy element dostaje ``<title>``
  i czy każdy błąd ma komunikat po polsku.

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


def test_zbiory_rysuja_zamalowanie_bez_schodkow(skrypt_zbiorow):
    assert "clipPath" in skrypt_zbiorow
    assert 'nowyElement("mask",' in skrypt_zbiorow
    assert "userSpaceOnUse" in skrypt_zbiorow


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
