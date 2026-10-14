"""Testy wspólnego klienta API i jego użycia w komponentach (karta PRZ-174).

Projekt nie ma runnera JavaScriptu (AGENTS.md, zasada 6), więc zachowanie `api.js`
sprawdzamy statycznie: czytamy treść plików i pilnujemy obecności identyfikatorów,
komunikatów i wywołań — tak samo jak pozostałe testy komponentów w `tests/`.

Karta wymienia dziewięć komponentów, ale trzy z nich — `tautologie.js`, `dowody.js`
i `rezolucja.js` — nie wykonują żadnego wywołania sieci: kroki przychodzą z serwera
w atrybucie `data-kroki`, a strony nie mają endpointu API. Import `pobierzJson` byłby
tam martwym kodem, więc te pliki zostają bez zmian; pilnujemy tylko, żeby nie pojawiło
się w nich własne `fetch(` (komunikat błędu zawsze daje wspólny klient).
"""

from __future__ import annotations

from pathlib import Path

import pytest

KATALOG_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "js"

#: Komponenty, które rozmawiają z API — każde żądanie idzie przez `pobierzJson`.
KOMPONENTY_SIECIOWE = [
    "truth-table.js",
    "gates.js",
    "sets.js",
    "playground.js",
    "quiz.js",
    "wynikanie.js",
]

#: Komponenty krokowe: kroki rysuje serwer, więc do API nie zaglądają.
KOMPONENTY_BEZ_SIECI = ["tautologie.js", "dowody.js", "rezolucja.js"]

IMPORT_API = 'import { pobierzJson } from "/static/js/api.js"'

#: Komunikaty wspólnego klienta — po jednym na każdy rodzaj awarii (kontrakt karty).
KOMUNIKATY = (
    "Nie udało się połączyć z serwerem. Sprawdź połączenie i spróbuj ponownie.",
    "Serwer zwrócił błąd (kod ",
    "Spróbuj ponownie.",
    "Serwer zwrócił nieprawidłową odpowiedź.",
    "Serwer nie odpowiedział w porę.",
)


@pytest.fixture(scope="module")
def api() -> str:
    """Treść wspólnego klienta `app/static/js/api.js`."""
    return (KATALOG_JS / "api.js").read_text(encoding="utf-8")


def _komponent(nazwa: str) -> str:
    """Treść pliku komponentu z `app/static/js/`."""
    return (KATALOG_JS / nazwa).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Wspólny klient `api.js`
# ---------------------------------------------------------------------------


def test_klient_eksportuje_pobierz_json(api):
    """Kryterium PRZ-174: jeden eksport dla wszystkich komponentów."""
    assert "export async function pobierzJson(adres, dane" in api
    assert "{ ok: true, dane:" in api
    assert "{ ok: false, blad:" in api


def test_klient_sprawdza_kod_odpowiedzi(api):
    """Kryterium PRZ-174: `!response.ok` to komunikat z kodem błędu HTTP."""
    assert "odpowiedz.ok" in api
    assert "komunikatKodu(odpowiedz.status)" in api
    assert "Serwer zwrócił błąd" in api


def test_klient_ma_limit_czasu_przez_abortcontroller(api):
    """Kryterium PRZ-174: po 15 s żądanie jest przerywane, a nie wisi bez końca."""
    assert "new AbortController()" in api
    assert "LIMIT_CZASU_MS = 15000" in api
    assert "sterownik.abort()" in api
    assert "signal: sterownik.signal" in api
    assert "AbortError" in api


def test_klient_rozroznia_brak_sieci_od_zlego_jsonu(api):
    """Kryterium PRZ-174: zerwane połączenie i nieparsowalna treść to dwa komunikaty."""
    assert "await odpowiedz.json()" in api
    assert "catch (blad)" in api
    assert "przekroczonyCzas(blad) ? TEKSTY.brakOdpowiedzi : TEKSTY.zlaOdpowiedz" in api
    assert "przekroczonyCzas(blad) ? TEKSTY.brakOdpowiedzi : TEKSTY.siec" in api


def test_klient_przekazuje_blad_z_api(api):
    """Kryterium PRZ-174: `ok: false` z API oddaje komunikat z pola `blad`."""
    assert "tresc.ok === false" in api
    assert "tresc.blad ||" in api


def test_klient_ma_polskie_komunikaty(api):
    for napis in KOMUNIKATY:
        assert napis in api, f"brak komunikatu „{napis}”"


def test_klient_nie_wstawia_tresci_przez_innerhtml(api):
    """Komunikaty wstawia komponent przez `textContent`; klient nic nie rysuje."""
    assert ".innerHTML" not in api
    assert "insertAdjacentHTML" not in api
    assert "document.write" not in api


# ---------------------------------------------------------------------------
# Komponenty sieciowe
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nazwa", KOMPONENTY_SIECIOWE)
def test_komponent_importuje_wspolnego_klienta(nazwa):
    """Kryterium PRZ-174: komponent korzysta z `api.js`, a nie z własnego `fetch`."""
    kod = _komponent(nazwa)

    assert IMPORT_API in kod, f"{nazwa} nie importuje pobierzJson"
    assert "pobierzJson(" in kod, f"{nazwa} nie woła pobierzJson"


@pytest.mark.parametrize("nazwa", KOMPONENTY_SIECIOWE)
def test_komponent_nie_wola_fetch_bezposrednio(nazwa):
    """Kryterium PRZ-174: transport obsługuje wyłącznie wspólny klient.

    Sprawdzamy całą treść pliku — także komentarze — żeby żaden `fetch(` nie wrócił
    do komponentu tylnymi drzwiami.
    """
    assert "fetch(" not in _komponent(nazwa)


@pytest.mark.parametrize("nazwa", KOMPONENTY_SIECIOWE)
def test_komponent_obsluguje_blad_z_klienta(nazwa):
    """Kryterium PRZ-174: wynik klienta jest sprawdzany, a `blad` trafia na stronę."""
    kod = _komponent(nazwa)

    assert ".ok" in kod, f"{nazwa} nie sprawdza pola ok"
    assert ".blad" in kod, f"{nazwa} nie pokazuje pola blad"


@pytest.mark.parametrize("nazwa", KOMPONENTY_SIECIOWE)
def test_komponent_oglosza_blad_przez_role_alert(nazwa):
    """Kryterium PRZ-174: komunikat jest tekstem w kontenerze z `role="alert"`."""
    kod = _komponent(nazwa)

    assert 'setAttribute("role", "alert")' in kod, f"{nazwa} nie ustawia role=alert"
    assert "textContent" in kod, f"{nazwa} nie wstawia komunikatu przez textContent"
    assert ".innerHTML" not in kod, f"{nazwa} wstawia treść przez innerHTML"


# ---------------------------------------------------------------------------
# Komponenty krokowe (bez wywołań sieci)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nazwa", KOMPONENTY_BEZ_SIECI)
def test_komponent_krokowy_nie_wola_api(nazwa):
    """Kroki przychodzą z serwera w `data-kroki`; komponent nie ma czego pobierać."""
    assert "fetch(" not in _komponent(nazwa)
    assert "pobierzJson(" not in _komponent(nazwa)
