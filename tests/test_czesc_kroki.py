"""Testy komponentu krokowego przekształcania: API, partial i pliki statyczne.

Karty PRZ-013 (sam komponent) i PRZ-077 (strzałka, wyróżnienie zmienianego fragmentu
i prowadzenie krok po kroku przez wspólny `stepper.js`).

Projekt nie ma runnera JavaScriptu (AGENTS.md, zasada 6), więc zachowanie `steps.js`
sprawdzamy statycznie: czytamy treść pliku i pilnujemy obecności identyfikatorów, klas
i wywołań oraz braku `innerHTML` z danymi z API.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from flask import render_template

from app import create_app

ADRES = "/api/formula/simplify"
KATALOG_STATYCZNY = Path(__file__).resolve().parents[1] / "app" / "static"
POLA_SLADU = ("reguła", "nazwa", "przed", "po", "wyjaśnienie", "pozycja")

#: Napis, którym `steps.js` opisuje wyróżniony fragment (kryterium PRZ-077).
TEKST_FRAGMENTU = "ten fragment zastępujemy"


@pytest.fixture
def aplikacja():
    return create_app({"TESTING": True})


@pytest.fixture
def klient(aplikacja):
    return aplikacja.test_client()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def _kroki(klient, formula: str, cel: str = "auto") -> list[dict]:
    """Kroki śladu z API dla poprawnej formuły."""
    dane = klient.post(ADRES, json={"formula": formula, "cel": cel}).get_json()

    assert dane["ok"] is True, dane.get("blad")
    return dane["slad"]["kroki"]


def test_api_simplify_dla_implikacji(klient):
    odpowiedz = klient.post(ADRES, json={"formula": "p -> q", "cel": "nnf"})

    assert odpowiedz.status_code == 200
    dane = odpowiedz.get_json()
    assert dane["ok"] is True
    assert len(dane["slad"]["kroki"]) >= 1
    assert any(krok["reguła"] == "definiowanie-implikacji" for krok in dane["slad"]["kroki"])


def test_api_simplify_bledna_formula(klient):
    odpowiedz = klient.post(ADRES, json={"formula": "p ∧", "cel": "auto"})

    assert odpowiedz.status_code == 200
    dane = odpowiedz.get_json()
    assert dane["ok"] is False
    assert dane["blad"].strip()


def test_api_simplify_nieznany_cel(klient):
    odpowiedz = klient.post(ADRES, json={"formula": "p", "cel": "xyz"})

    assert odpowiedz.status_code == 200
    dane = odpowiedz.get_json()
    assert dane["ok"] is False
    assert "xyz" in dane["blad"]


def test_api_simplify_odrzuca_cialo_nie_obiekt_json(klient):
    """Lista zamiast obiektu to błąd danych, nie awaria serwera (kontrakt API)."""
    odpowiedz = klient.post(ADRES, json=["p"])

    assert odpowiedz.status_code == 200
    dane = odpowiedz.get_json()
    assert dane["ok"] is False
    assert dane["blad"].strip()


def test_api_simplify_bez_tresci_zadania_to_blad_danych(klient):
    odpowiedz = klient.post(ADRES)

    assert odpowiedz.status_code == 200
    dane = odpowiedz.get_json()
    assert dane["ok"] is False
    assert dane["blad"].strip()


def test_api_simplify_glebokie_zagniezdzenie_to_blad_danych(klient):
    """Formuła, która wyczerpuje stos parsera, daje ``ok: false``, a nie kod 500."""
    odpowiedz = klient.post(ADRES, json={"formula": "(" * 249 + "p" + ")" * 249, "cel": "auto"})

    assert odpowiedz.status_code == 200
    dane = odpowiedz.get_json()
    assert dane["ok"] is False
    assert "zagnieżdżona" in dane["blad"]


def test_api_simplify_domyslny_cel_to_auto(klient):
    dane = klient.post(ADRES, json={"formula": "p ∧ (q ∨ r)"}).get_json()

    assert dane["ok"] is True
    assert dane["slad"]["forma"] == "DNF"


def test_api_simplify_pusta_formula_to_blad(klient):
    odpowiedz = klient.post(ADRES, json={"formula": "   "})

    assert odpowiedz.status_code == 200
    dane = odpowiedz.get_json()
    assert dane["ok"] is False
    assert dane["blad"].strip()


def test_api_simplify_slad_ma_wymagane_pola(klient):
    dane = klient.post(ADRES, json={"formula": "p → q", "cel": "nnf"}).get_json()["slad"]

    assert set(dane) == {"start", "kroki", "koniec", "forma"}
    assert dane["start"].strip()
    assert dane["koniec"].strip()
    assert dane["forma"] in {"NNF", "DNF", "CNF", "uproszczona"}
    assert dane["kroki"]
    for krok in dane["kroki"]:
        for pole in POLA_SLADU:
            assert krok[pole].strip()


def test_api_simplify_kazdy_krok_ma_pole_fragment(klient):
    """Kryterium PRZ-077: pole ``fragment`` jest w każdym kroku (może być puste)."""
    kroki = _kroki(klient, "p → q", "nnf")

    assert kroki
    for krok in kroki:
        assert isinstance(krok["fragment"], str)


def test_api_simplify_fragment_wskazuje_zmieniana_podformule(klient):
    """Dla wejścia negacji pod koniunkcję zmienia się dokładnie ``p ∧ q``."""
    kroki = _kroki(klient, "∼(p ∧ q)", "nnf")

    assert kroki[0]["fragment"] == "p ∧ q"


def test_api_simplify_fragment_przy_porzadkowaniu_to_cala_formula(klient):
    """Krok, który tylko przestawia argumenty, zmienia całą formułę."""
    kroki = _kroki(klient, "p → q", "nnf")
    krok = kroki[-1]

    assert krok["reguła"] == "przemiennosc-alternatywy"
    assert krok["fragment"] == krok["przed"]


@pytest.mark.parametrize(
    ("formula", "cel"),
    [
        ("p → q", "nnf"),
        ("∼(p ∧ q)", "nnf"),
        ("p ≡ q", "nnf"),
        ("p ∧ (q ∨ r)", "auto"),
    ],
)
def test_api_simplify_fragment_wystepuje_w_formule_kroku(klient, formula, cel):
    """Fragment musi dać się znaleźć w formule kroku — inaczej strona nie ma co wyróżnić."""
    kroki = _kroki(klient, formula, cel)

    assert kroki
    for krok in kroki:
        fragment = krok["fragment"]
        assert fragment == "" or fragment in krok["przed"] or fragment in krok["po"]


def test_api_simplify_formula_w_docelowej_postaci_nie_ma_krokow(klient):
    """Brak kroków to ``kroki: []`` — strona pokazuje wtedy sam komunikat."""
    kroki = _kroki(klient, "p ∨ ∼p", "nnf")

    assert kroki == []


def test_api_simplify_jest_zarejestrowany(aplikacja):
    assert "api_simplify" in aplikacja.config["BLUEPRINTS"]


# ---------------------------------------------------------------------------
# Partial
# ---------------------------------------------------------------------------


def _renderuj(aplikacja, **zmienne):
    with aplikacja.test_request_context():
        return render_template("partials/_steps.html", **zmienne)


def test_partial_renderuje_montaz_z_danymi(aplikacja):
    html = _renderuj(aplikacja, formula="p ∧ q", cel="nnf")

    assert 'class="steps-mount"' in html
    assert 'data-formula="p ∧ q"' in html
    assert 'data-cel="nnf"' in html


def test_partial_bez_celu_daje_auto(aplikacja):
    html = _renderuj(aplikacja, formula="p")

    assert 'data-cel="auto"' in html


def test_partial_dolacza_pliki_statyczne(aplikacja):
    html = _renderuj(aplikacja, formula="p")

    assert "/static/js/steps.js" in html
    assert "/static/css/steps.css" in html


def test_partial_dolacza_arkusz_paska_krokow(aplikacja):
    """Pasek prowadzenia rysuje komponent, więc partial musi dać jego arkusz."""
    html = _renderuj(aplikacja, formula="p")

    assert "/static/css/stepper.css" in html


def test_partial_ma_noscript(aplikacja):
    html = _renderuj(aplikacja, formula="p")

    assert "<noscript>" in html
    assert "JavaScript" in html


# ---------------------------------------------------------------------------
# Pliki statyczne
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sciezka", ["js/steps.js", "css/steps.css"])
def test_pliki_komponentu_istnieja_i_nie_sa_puste(sciezka):
    plik = KATALOG_STATYCZNY / sciezka

    assert plik.is_file()
    assert plik.stat().st_size > 0


@pytest.fixture(scope="module")
def skrypt():
    return (KATALOG_STATYCZNY / "js" / "steps.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def arkusz():
    return (KATALOG_STATYCZNY / "css" / "steps.css").read_text(encoding="utf-8")


def _bez_komentarzy(kod: str) -> str:
    """Usuwa komentarze, żeby sprawdzać kod, a nie przykłady w opisie."""
    kod = re.sub(r"/\*.*?\*/", "", kod, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", kod)


def test_skrypt_uzywa_wspolnego_komponentu_krokow(skrypt):
    """Kryterium PRZ-077: kroki prowadzi ``createStepper``, a nie własny pasek."""
    kod = _bez_komentarzy(skrypt)

    assert 'import { createStepper } from "/static/js/stepper.js"' in kod
    assert "createStepper({" in kod
    assert "onStep" in kod


def test_skrypt_pokazuje_strzalke_i_plakietke_prawa(skrypt):
    """Kryterium PRZ-077: każdy krok ma strzałkę i nazwę prawa."""
    kod = _bez_komentarzy(skrypt)

    assert "⇒" in kod
    assert "krok-plakietka" in kod
    assert "badge" in kod
    assert "krok.nazwa" in kod


def test_skrypt_wyroznia_fragment_przez_mark(skrypt):
    """Kryterium PRZ-077: wyróżnienie to ``<mark>`` z opisem zmiany."""
    kod = _bez_komentarzy(skrypt)

    assert 'element("mark"' in kod
    assert "krok-fragment" in kod
    assert TEKST_FRAGMENTU in kod
    assert 'setAttribute("aria-label"' in kod


def test_skrypt_pomija_pusty_fragment_bez_bledu(skrypt):
    """Kryterium PRZ-077: brak fragmentu w formule to krok bez wyróżnienia, nie błąd."""
    kod = _bez_komentarzy(skrypt)

    assert 'typeof fragment === "string"' in kod
    assert "!szukany || !formula.includes(szukany)" in kod
    assert "opakowanie.textContent = formula" in kod


def test_skrypt_zwija_poprzednie_kroki_i_rozwija_biezacy(skrypt):
    """Kryterium PRZ-077: bieżący krok z opisem, poprzednie zwinięte do jednej linii."""
    kod = _bez_komentarzy(skrypt)

    assert "tresc.hidden = !biezacy" in kod
    assert "krok-zwiniety" in kod
    assert "krok-aktywny" in kod


def test_skrypt_pokazuje_forme_wynikowa_i_liczbe_krokow(skrypt):
    """Kryterium PRZ-077: podsumowanie na końcu ma formę wynikową i liczbę kroków."""
    kod = _bez_komentarzy(skrypt)

    assert "Forma wynikowa:" in kod
    assert "Liczba kroków:" in kod


def test_skrypt_wola_api_i_pokazuje_liczbe_krokow(skrypt):
    assert ADRES in skrypt
    assert "fetch(" in skrypt
    assert "Liczba kroków" in skrypt


def test_skrypt_nie_wstawia_tresci_przez_innerhtml(skrypt):
    # W komentarzu słowo może wystąpić, ale w kodzie nie ma prawa.
    assert ".innerHTML" not in skrypt
    assert "insertAdjacentHTML" not in skrypt
    assert "document.write" not in skrypt


def test_skrypt_ma_polskie_komunikaty_i_arie(skrypt):
    kod = _bez_komentarzy(skrypt)

    assert "Nie udało się połączyć z serwerem" in kod
    assert 'status.setAttribute("role", "status")' in kod
    assert 'status.setAttribute("aria-live", "polite")' in kod


def test_skrypt_bez_krokow_pokazuje_sam_komunikat(skrypt):
    """Kryterium PRZ-077: formuła bez kroków daje komunikat, a nie pusty pasek."""
    kod = _bez_komentarzy(skrypt)

    assert "kroki.length === 0" in kod
    assert "brakKrokow" in kod


def test_skrypt_prowadzi_sekcje_krokow_rysowana_przez_serwer(skrypt):
    """Kryterium PRZ-143: te same kroki na stronie prawa prowadzi wspólny stepper."""
    kod = _bez_komentarzy(skrypt)

    assert "[data-kroki-prawa]" in kod
    assert "[data-stepper]" in kod
    assert "li.krok" in kod
    assert "createStepper({" in kod


def test_skrypt_pokazuje_na_stronie_prawa_jeden_krok_naraz(skrypt):
    """Kryterium PRZ-143: kroki czekają ukryte, a komponent pokazuje jeden.

    Bez JavaScriptu lista zostaje widoczna w całości, więc czytelnik nie traci
    treści — dlatego ukrywanie robi skrypt, a nie arkusz.
    """
    kod = _bez_komentarzy(skrypt)

    assert "pozycja.hidden = indeks !== numer" in kod
    assert '".krok-plakietka"' in kod
    assert "textContent.trim()" in kod


def test_arkusz_styluje_wyrozniony_fragment(arkusz):
    """Wyróżnienie fragmentu to tło **i** podkreślenie — kolor nie jest jedynym nośnikiem."""
    assert ".krok-fragment" in arkusz
    assert "background-color" in arkusz
    assert "border-bottom" in arkusz


def test_arkusz_ukrywa_kroki_poza_biezacym(arkusz):
    """Kroki czekające na wejście muszą zniknąć niezależnie od stylu listy."""
    assert ".krok[hidden]" in arkusz
    assert "display: none" in arkusz
