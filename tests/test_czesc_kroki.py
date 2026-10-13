"""Testy komponentu krokowego przekształcania: API, partial i pliki statyczne (PRZ-013)."""

from __future__ import annotations

from pathlib import Path

import pytest
from flask import render_template

from app import create_app

ADRES = "/api/formula/simplify"
KATALOG_STATYCZNY = Path(__file__).resolve().parents[1] / "app" / "static"
POLA_SLADU = ("reguła", "nazwa", "przed", "po", "wyjaśnienie", "pozycja")


@pytest.fixture
def aplikacja():
    return create_app({"TESTING": True})


@pytest.fixture
def klient(aplikacja):
    return aplikacja.test_client()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


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


def test_skrypt_ma_cztery_przyciski(skrypt):
    for napis in ("Następny krok", "Poprzedni krok", "Pokaż wszystkie", "Od nowa"):
        assert napis in skrypt


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
    assert "Nie udało się połączyć z serwerem" in skrypt
    assert "aria-expanded" in skrypt
    assert "aria-live" in skrypt


def test_skrypt_podpowiada_o_rozwinieciu_kroku(skrypt):
    """Bez podpowiedzi początkujący nie zgadnie, że krok da się rozwinąć."""
    assert "Kliknij nagłówek kroku" in skrypt
