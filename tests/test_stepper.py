"""Testy wspólnego komponentu kroków (PRZ-072).

Projekt nie ma runnera JavaScriptu (żadnego Node ani npm — patrz ``AGENTS.md``),
więc zachowanie ``stepper.js`` sprawdzamy statycznie: czytamy treść pliku i pilnujemy
obecności eksportu, obsługi klawiszy, atrybutów ARIA i braku ``innerHTML``.
Renderowanie partialu sprawdzamy przez ``render_template`` bez przeglądarki.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from flask import render_template

from app import create_app

KATALOG_STATYCZNY = Path(__file__).resolve().parents[1] / "app" / "static"
SKRYPT = KATALOG_STATYCZNY / "js" / "stepper.js"
ARKUSZ = KATALOG_STATYCZNY / "css" / "stepper.css"
PARTIAL = "partials/_stepper.html"

KROKI = [
    {"tytul": "Założenie", "opis": "Zapisujemy wzór wyjściowy."},
    {"tytul": "Rozdzielność", "opis": "Wynosimy wspólny czynnik przed nawias."},
    {"tytul": "Wniosek", "opis": "Otrzymujemy postać końcową."},
]


@pytest.fixture
def aplikacja():
    return create_app({"TESTING": True})


@pytest.fixture(scope="module")
def skrypt():
    return SKRYPT.read_text(encoding="utf-8")


def _renderuj(aplikacja, **zmienne):
    with aplikacja.test_request_context():
        return render_template(PARTIAL, **zmienne)


def _bez_komentarzy(kod: str) -> str:
    """Usuwa komentarze, żeby sprawdzać sam kod, a nie przykłady w opisie."""
    kod = re.sub(r"/\*.*?\*/", "", kod, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", kod)


# ---------------------------------------------------------------------------
# Partial
# ---------------------------------------------------------------------------


def test_partial_renderuje_kontener_steppera(aplikacja):
    html = _renderuj(aplikacja)

    assert "data-stepper" in html
    assert 'data-rola="kroki"' in html


def test_partial_dolacza_pliki_statyczne(aplikacja):
    html = _renderuj(aplikacja)

    assert "/static/js/stepper.js" in html
    assert "/static/css/stepper.css" in html
    assert 'type="module"' in html


def test_partial_uzywa_url_for_dla_plikow_statycznych(aplikacja):
    """Ścieżki plików mają iść przez `url_for`, a nie być wpisane na sztywno."""
    zrodlo = (Path(__file__).resolve().parents[1] / "app" / "templates" / PARTIAL).read_text(
        encoding="utf-8"
    )

    assert "url_for('static'" in zrodlo
    assert zrodlo.count("url_for('static'") == 2  # skrypt i arkusz


def test_partial_ma_noscript_bez_krokow_z_komunikatem(aplikacja):
    html = _renderuj(aplikacja)

    assert "<noscript>" in html
    assert "JavaScript" in html
    assert "<ol" not in html


def test_partial_ma_noscript_z_lista_krokow(aplikacja):
    html = _renderuj(aplikacja, steps=KROKI)

    assert "<noscript>" in html
    lista = html.split("<noscript>", 1)[1].split("</noscript>", 1)[0]
    assert "<ol" in lista
    for krok in KROKI:
        assert krok["tytul"] in lista
        assert krok["opis"] in lista


def test_partial_bez_krokow_nie_wyswietla_pustej_listy(aplikacja):
    html = _renderuj(aplikacja, steps=[])

    assert "JavaScript" in html
    assert "<ol" not in html


def test_partial_ucieka_tresc_krokow(aplikacja):
    """Tytuł kroku trafia do HTML jako tekst, nie jako kod."""
    html = _renderuj(aplikacja, steps=[{"tytul": "<script>alert(1)</script>", "opis": ""}])

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# Pliki komponentu
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sciezka", ["js/stepper.js", "css/stepper.css"])
def test_pliki_komponentu_istnieja_i_nie_sa_puste(sciezka):
    plik = KATALOG_STATYCZNY / sciezka

    assert plik.is_file()
    assert plik.stat().st_size > 0


def test_skrypt_jest_modulem_es(skrypt):
    assert re.search(r"^export function createStepper", skrypt, re.MULTILINE)


def test_skrypt_eksportuje_createStepper(skrypt):
    assert "export function createStepper" in skrypt
    # Strona importuje komponent po nazwie pliku z `url_for`.
    assert "createStepper(options = {})" in skrypt


def test_skrypt_obsluguje_sterowanie(skrypt):
    for metoda in ("go", "next", "prev", "play", "pause", "reset"):
        assert re.search(rf"function {metoda}\(", skrypt), f"brak funkcji {metoda}"


def test_skrypt_ma_wszystkie_akcje_w_zwracanym_obiekcie(skrypt):
    zwrot = skrypt.split("return {", 1)[1]
    for metoda in ("go,", "next,", "prev,", "play,", "pause,", "reset,", "destroy,"):
        assert metoda in zwrot, f"brak {metoda} w zwracanym obiekcie"


def test_skrypt_obsluguje_klawisze(skrypt):
    assert "const key = event.key;" in skrypt
    for klawisz in ('"ArrowLeft"', '"ArrowRight"', '"Home"', '"End"'):
        assert f"key === {klawisz}" in skrypt, f"brak obsługi {klawisz}"
    # Spacja: klawisz zapisujemy jako `" "`.
    assert 'key === " "' in skrypt


def test_skrypt_ma_cztery_przyciski_z_polskimi_napisami(skrypt):
    for napis in ("Wstecz", "Dalej", "Odtwórz", "Pauza", "Od nowa"):
        assert napis in skrypt


@pytest.mark.parametrize("atrybut", ['"aria-current"', '"step"', '"aria-live"', '"polite"'])
def test_skrypt_ustawia_arie(skrypt, atrybut):
    assert atrybut in skrypt


def test_skrypt_ustawia_aria_current_na_biezacej_kropce(skrypt):
    assert 'setAttribute("aria-current", "step")' in skrypt


def test_skrypt_ustawia_aria_live_na_tresci_kroku(skrypt):
    assert 'setAttribute("aria-live", "polite")' in skrypt


def test_skrypt_pokazuje_wskaźnik_kroku(skrypt):
    """Wskaźnik „Krok 3 z 7” — użytkownik wie, na którym kroku jest."""
    assert "} z ${steps.length}" in skrypt


def test_skrypt_nie_wstawia_tresci_przez_innerhtml(skrypt):
    """Teksty kroków trafiają do DOM przez `textContent`, nigdy jako kod."""
    assert ".innerHTML" not in skrypt
    assert "insertAdjacentHTML" not in skrypt
    assert "document.write" not in skrypt
    assert "eval(" not in skrypt


def test_skrypt_nie_rzuca_bez_krokow(skrypt):
    """Brak kontenera albo brak kroków to komunikat po polsku, a nie wyjątek."""
    assert "inertStepper" in skrypt
    assert "nie ma jeszcze kroków" in skrypt
    assert "if (!mount)" in skrypt
    assert "list.length === 0" in skrypt


def test_skrypt_domyslnie_nie_pisze_poza_paskiem_i_opisem(skrypt):
    """Komponent podmienia tylko własny kontener, nie dotyka reszty dokumentu."""
    kod = _bez_komentarzy(skrypt)

    assert "mount.replaceChildren(" in kod
    for zabronione in ("document.body", "document.querySelector(", "document.getElementById("):
        assert zabronione not in kod


def test_arkusz_styluje_biezacy_krok_i_fokus():
    css = ARKUSZ.read_text(encoding="utf-8")

    assert '[aria-current="step"]' in css
    assert ":focus-visible" in css
    assert "prefers-reduced-motion" in css
