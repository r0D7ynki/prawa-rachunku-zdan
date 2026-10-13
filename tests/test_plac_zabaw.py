"""Testy placu zabaw ``/plac-zabaw`` (karta PRZ-014).

Sprawdzamy widok HTML i pliki statyczne czytaniem — bez przeglądarki i bez sieci.
Testy JavaScriptu patrzą na treść pliku, bo logika siedzi po stronie serwera:
skrypt tylko wysyła formułę i pokazuje odpowiedź.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import create_app

STRONA = "/plac-zabaw"

#: Pięć symboli, które musi mieć klawiatura (kolejność z karty).
SYMBOLE_OPERATOROW = ["¬", "∧", "∨", "→", "↔"]

#: Cztery przykłady na start — klikane formuły z karty.
PRZYKLADY = ["p → q", "¬(p ∧ q)", "p ∨ ¬p", "(p → q) ∧ p"]

#: Adresy czterech endpointów, które woła ``playground.js``.
ENDPOINTY = [
    "/api/formula/parse",
    "/api/formula/table",
    "/api/formula/simplify",
    "/api/equivalence",
]

#: Formuła, którą wstrzykujemy jako parametr adresu.
WSTRZYKNIECIE = "<script>alert(1)</script>"

KATALOG_GLOWNY = Path(__file__).resolve().parents[1]
JS = KATALOG_GLOWNY / "app" / "static" / "js" / "playground.js"
CSS = KATALOG_GLOWNY / "app" / "static" / "css" / "playground.css"
SZABLON = KATALOG_GLOWNY / "app" / "templates" / "plac_zabaw.html"

WZORZEC_POLA = re.compile(r'<input[^>]*id="pole-formula"[^>]*>')
WZORZEC_WARTOSCI = re.compile(r'value="(?P<wartosc>[^"]*)"')


@pytest.fixture(scope="module")
def klient():
    """Klient testowy aplikacji."""
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def html(klient):
    """Treść strony ``/plac-zabaw`` bez parametrów."""
    return klient.get(STRONA).get_data(as_text=True)


def _zrodlo(sciezka: Path) -> str:
    """Czyta plik projektu jako UTF-8."""
    assert sciezka.is_file(), f"brak pliku {sciezka}"
    return sciezka.read_text(encoding="utf-8")


def _pole_formuly(tekst: str) -> str:
    """Zwraca znacznik ``<input>`` pola formuły albo podnosi błąd."""
    dopasowanie = WZORZEC_POLA.search(tekst)
    assert dopasowanie, 'brak pola formuły (input id="pole-formula")'
    return dopasowanie.group(0)


def _wartosc_pola(tekst: str) -> str:
    """Zwraca wartość atrybutu ``value`` pola formuły."""
    dopasowanie = WZORZEC_WARTOSCI.search(_pole_formuly(tekst))
    assert dopasowanie, "pole formuły nie ma atrybutu value"
    return dopasowanie["wartosc"]


# --- widok HTML --------------------------------------------------------------


def test_strona_odpowiada_200_i_html_utf8(klient):
    odpowiedz = klient.get(STRONA)

    assert odpowiedz.status_code == 200
    typ = odpowiedz.headers["Content-Type"]
    assert typ.startswith("text/html")
    assert "charset=utf-8" in typ.lower()


def test_strona_nie_zostawia_nieuzupelnionych_szablonow(html):
    assert "{{" not in html
    assert "{%" not in html


def test_jest_pole_formuly_z_wartoscia_domyslna(html):
    assert "p → (q ∧ ¬r)" in _wartosc_pola(html)


def test_klawiatura_ma_piec_symboli(html):
    symbole = re.findall(r'data-symbol="([^"]*)"', html)

    for symbol in SYMBOLE_OPERATOROW:
        assert symbol in symbole, f"brak przycisku symbolu {symbol}"
    assert len(symbole) >= 5


def test_przyciski_klawiatury_maja_etykiety(html):
    symbole = re.findall(r'data-symbol="([^"]*)"', html)

    for symbol in symbole:
        assert re.search(rf'data-symbol="{re.escape(symbol)}"[^>]*aria-label=', html), (
            f"przycisk {symbol} bez aria-label"
        )


def test_jest_co_najmniej_cztery_przyklady(html):
    przyklady = re.findall(r'data-przyklad="([^"]*)"', html)

    assert len(przyklady) >= 4, f"przykładów jest {len(przyklady)}, oczekiwano co najmniej 4"
    for przykład in PRZYKLADY:
        assert przykład in przyklady, f"brak przykładu {przykład}"


def test_przyklady_dzialaja_takze_bez_javascriptu(html):
    """Odnośnik przykładu niesie formułę w adresie, więc działa bez skryptu."""
    if "p → q" in PRZYKLADY:
        assert 'href="/plac-zabaw?formula=p%20%E2%86%92%20q"' in html


def test_jest_druga_formula_i_przycisk_porownania(html):
    assert re.search(r'<input[^>]*id="pole-druga"', html), "brak drugiego pola"
    assert 'id="przycisk-porownaj"' in html


def test_przelacznik_celu_ma_cztery_opcje(html):
    opcje = re.findall(r'<option value="([^"]*)"', html)

    assert opcje == ["auto", "nnf", "dnf", "cnf"], f"opcje celu: {opcje}"


# --- parametr adresu ---------------------------------------------------------


def test_parametr_wstawia_formule_do_pola(klient):
    html = klient.get(f"{STRONA}?formula=p%20%E2%86%92%20q").get_data(as_text=True)

    assert _wartosc_pola(html) == "p → q"


def test_parametr_jest_escapowany(klient):
    html = klient.get(STRONA, query_string={"formula": WSTRZYKNIECIE}).get_data(as_text=True)

    assert WSTRZYKNIECIE not in html, "parametr utworzył znacznik script"
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_szablon_nie_uzywa_filtra_safe():
    assert "|safe" not in _zrodlo(SZABLON), "szablon nie powinien używać |safe"


# --- pliki statyczne ---------------------------------------------------------


def test_skrypt_i_styl_istnieja_i_nie_sa_puste():
    for plik in (JS, CSS):
        assert plik.is_file(), f"brak pliku {plik}"
        assert plik.stat().st_size > 0, f"plik {plik} jest pusty"


def test_skrypt_wola_cztery_endpointy():
    zrodlo = _zrodlo(JS)

    for endpoint in ENDPOINTY:
        assert endpoint in zrodlo, f"brak wywołania endpointu {endpoint}"
    assert "fetch(" in zrodlo, "skrypt nie używa fetch"


def test_skrypt_obsluguje_blad_ok_false():
    zrodlo = _zrodlo(JS)

    assert ".ok" in zrodlo, "skrypt nie sprawdza pola ok"
    assert ".blad" in zrodlo, "skrypt nie pokazuje pola blad"
    assert "Nie udało się" in zrodlo, "brak komunikatu po polsku"


def test_skrypt_pisze_kontrprzyklad_zdaniem():
    zrodlo = _zrodlo(JS)

    assert "PRAWDA" in zrodlo and "FAŁSZ" in zrodlo
    assert " = " in zrodlo, "brak zdania w postaci „p = PRAWDA”"


def test_skrypt_wstawia_symbol_w_miejscu_kursora():
    zrodlo = _zrodlo(JS)

    assert "selectionStart" in zrodlo
    assert "setSelectionRange" in zrodlo


def test_skrypt_nie_wstawia_tresci_przez_innerhtml():
    zrodlo = _zrodlo(JS)

    assert ".innerHTML" not in zrodlo, "treść z API ma trafiać przez textContent"


# --- rejestracja widoku ------------------------------------------------------


def test_blueprint_jest_zarejestrowany():
    app = create_app({"TESTING": True})

    assert "playground" in app.config["BLUEPRINTS"]
