"""Testy wspólnego komponentu kroków (PRZ-072, PRZ-124).

Projekt nie ma runnera JavaScriptu (żadnego Node ani npm — patrz ``AGENTS.md``),
więc zachowanie ``stepper.js`` sprawdzamy statycznie: czytamy treść pliku i pilnujemy
obecności eksportu, obsługi klawiszy, atrybutów ARIA i braku ``innerHTML``.
Renderowanie partialu sprawdzamy przez ``render_template`` bez przeglądarki.

Karta PRZ-124 zwęziła pasek do dwóch strzałek „‹” i „›” (bez odtwarzania, kropek
i licznika kroków), więc testy pilnują też braku usuniętych części interfejsu
— w samym komponencie i u jego konsumentów.
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

#: Skrypty, które korzystają z paska kroków i nie mogą polegać na usuniętych częściach.
KONSUMENCI = ["steps.js", "tautologie.js", "dowody.js", "rezolucja.js"]

#: Napisy przycisków usuniętych w karcie PRZ-124.
USUNIETE_NAPISY = ["Odtwórz", "Pauza", "Od nowa"]

#: Licznik kroków, który zniknął z widoku (numer zostaje najwyżej dla czytnika ekranu).
WZORZEC_LICZNIKA = re.compile(r"krok\s+\d+\s+z", re.IGNORECASE)

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


# --- Pasek: dwie strzałki i nic więcej (PRZ-124) ----------------------------


@pytest.mark.parametrize("napis", USUNIETE_NAPISY)
def test_skrypt_nie_ma_napisow_usunietych_przyciskow(skrypt, napis):
    """Znikają „Odtwórz”, „Pauza” i „Od nowa” — razem z odtwarzaniem."""
    assert napis not in skrypt


def test_skrypt_nie_tworzy_kropek_ani_licznika(skrypt):
    kod = _bez_komentarzy(skrypt)

    assert "stepper-kropka" not in kod
    assert "aria-current" not in kod
    assert WZORZEC_LICZNIKA.search(skrypt) is None


def test_skrypt_tworzy_dokladnie_dwa_przyciski(skrypt):
    """Pasek ma dokładnie dwa elementy interaktywne: „‹” i „›”."""
    kod = _bez_komentarzy(skrypt)

    assert kod.count('createElement("button"') == 2
    for usuniety in ("buttons.play", "buttons.reset", "togglePlay"):
        assert usuniety not in kod


def test_skrypt_rysuje_strzalki_z_aria_label(skrypt):
    kod = _bez_komentarzy(skrypt)

    assert '"‹"' in kod
    assert '"›"' in kod
    assert '"Poprzedni krok"' in kod
    assert '"Następny krok"' in kod
    assert kod.count('setAttribute("aria-label", LABELS.') == 2


def test_skrypt_wylacza_strzalki_na_krancach(skrypt):
    """Na pierwszym kroku „poprzedni”, na ostatnim „następny” jest wyłączony."""
    kod = _bez_komentarzy(skrypt)

    assert "previous.disabled = pierwszy" in kod
    assert "following.disabled = ostatni" in kod
    assert 'setAttribute("aria-disabled", String(pierwszy))' in kod
    assert 'setAttribute("aria-disabled", String(ostatni))' in kod


def test_skrypt_zachowuje_sterowanie_krokami(skrypt):
    """Zostają `go`, `next`, `prev` i `index` — bez odtwarzania i resetu."""
    for metoda in ("go", "next", "prev"):
        assert re.search(rf"function {metoda}\(", skrypt), f"brak funkcji {metoda}"
    for usunieta in ("play", "pause", "reset"):
        assert not re.search(rf"function {usunieta}\(", skrypt), f"została funkcja {usunieta}"


def test_skrypt_ma_wszystkie_akcje_w_zwracanym_obiekcie(skrypt):
    zwrot = skrypt.split("return {", 1)[1]
    for metoda in ("go,", "next,", "prev,", "destroy,"):
        assert metoda in zwrot, f"brak {metoda} w zwracanym obiekcie"
    for usunieta in ("play,", "pause,", "reset,", "playing,"):
        assert usunieta not in zwrot, f"w zwracanym obiekcie zostało {usunieta}"


def test_skrypt_obsluguje_klawisze(skrypt):
    assert "const key = event.key;" in skrypt
    for klawisz in ('"ArrowLeft"', '"ArrowRight"', '"Home"', '"End"'):
        assert f"key === {klawisz}" in skrypt, f"brak obsługi {klawisz}"


def test_skrypt_nie_obsluguje_spacji(skrypt):
    """Spacja włączała odtwarzanie — razem z nim znika."""
    kod = _bez_komentarzy(skrypt)

    assert "togglePlay" not in kod
    assert 'key === " "' not in kod


@pytest.mark.parametrize("atrybut", ['"aria-live"', '"polite"'])
def test_skrypt_ustawia_arie(skrypt, atrybut):
    assert atrybut in skrypt


def test_skrypt_ustawia_aria_live_na_tresci_kroku(skrypt):
    assert 'setAttribute("aria-live", "polite")' in skrypt


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


# --- Konsumenci paska -------------------------------------------------------


@pytest.fixture(scope="module")
def konsumenci():
    return {
        nazwa: (KATALOG_STATYCZNY / "js" / nazwa).read_text(encoding="utf-8")
        for nazwa in KONSUMENCI
    }


@pytest.mark.parametrize("nazwa", KONSUMENCI)
def test_konsument_nie_wola_usunietych_metod(konsumenci, nazwa):
    """Karta PRZ-124: żaden konsument nie woła `play()`, `pause()` ani `reset()`."""
    kod = _bez_komentarzy(konsumenci[nazwa])

    for metoda in ("play", "pause", "reset"):
        assert not re.search(rf"\b{metoda}\s*\(", kod), f"{nazwa} woła {metoda}()"


@pytest.mark.parametrize("nazwa", KONSUMENCI)
def test_konsument_nie_korzysta_z_usunietych_czesci_paska(konsumenci, nazwa):
    """Bez kropek, licznika i napisów przycisków, które zniknęły."""
    kod = _bez_komentarzy(konsumenci[nazwa])

    assert "stepper-kropka" not in kod
    assert "aria-current" not in kod
    assert WZORZEC_LICZNIKA.search(kod) is None
    for napis in USUNIETE_NAPISY:
        assert napis not in kod, f"{nazwa} wciąż mówi „{napis}”"


def test_konsument_steps_nie_odsyla_do_przycisku_od_nowa(konsumenci):
    """Komunikat o sieci w `steps.js` nie może kierować do nieistniejącego guzika."""
    assert "odśwież stronę" in konsumenci["steps.js"]


# ---------------------------------------------------------------------------
# Arkusz stylów
# ---------------------------------------------------------------------------


def test_arkusz_stylizuje_okragle_strzalki_i_fokus():
    css = ARKUSZ.read_text(encoding="utf-8")

    assert ".stepper-strzalka" in css
    assert "border-radius: 50%" in css
    assert ".stepper-strzalka:disabled" in css
    assert ":focus-visible" in css
    assert "prefers-reduced-motion" in css


def test_arkusz_nie_ma_stylow_usunietych_kropek():
    css = ARKUSZ.read_text(encoding="utf-8")

    assert "stepper-kropka" not in css
    assert "stepper-wskaznik" not in css


def test_arkusz_zwija_pasek_na_telefonie():
    """Na wąskim ekranie strzałki mają 44 px, a opis zawija się pod nimi."""
    css = ARKUSZ.read_text(encoding="utf-8")
    telefon = css.split("@media (max-width: 575.98px)", 1)[1]

    assert "44px" in telefon
    assert "flex-basis: 100%" in telefon
    assert "order: 3" in telefon
