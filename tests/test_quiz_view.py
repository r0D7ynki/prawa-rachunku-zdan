"""Testy widoku quizu ``/quiz`` i jego API (karta PRZ-015).

Sprawdzamy widok HTML, oba endpointy quizu i pliki statyczne — czytaniem, bez
przeglądarki i bez sieci. Poprawną odpowiedź na potrzeby testu bierzemy z generatora
``app.logic.quiz``: serwer ją zna, ale API jej nie wysyła, i to też jest tu sprawdzone.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import create_app
from app.logic.quiz import generate

STRONA = "/quiz"

#: Ziarno zestawu używane w testach — ten sam zestaw w każdym wywołaniu.
SEED = 1

#: Adres, pod którym endpoint zwraca błąd danych z kodem HTTP 200.
GENERUJ = "/api/quiz/generate"
SPRAWDZ = "/api/quiz/check"

#: Prawo z rejestru, którego używamy w testach zakresu.
PRAWO = "de-morgan-1"

#: Slug, którego nie ma w rejestrze.
NIEZNANE_PRAWO = "nie-ma-takiego-prawa"

#: Identyfikator pytania, którego na pewno nie ma w żadnym zestawie.
NIEZNANE_ID = "nie-ma-takiego-pytania-0-1"

#: Wartość wstrzykiwana jako parametr adresu.
WSTRZYKNIECIE = "<script>alert(1)</script>"

#: Liczby pytań, które musi oferować formularz startowy (kolejność z karty).
LICZBY_PYTAN = ["3", "5", "10"]

KATALOG_GLOWNY = Path(__file__).resolve().parents[1]
JS = KATALOG_GLOWNY / "app" / "static" / "js" / "quiz.js"
CSS = KATALOG_GLOWNY / "app" / "static" / "css" / "quiz.css"
SZABLON = KATALOG_GLOWNY / "app" / "templates" / "quiz.html"


@pytest.fixture(scope="module")
def klient():
    """Klient testowy aplikacji."""
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def html(klient):
    """Treść strony ``/quiz`` bez parametrów."""
    return klient.get(STRONA).get_data(as_text=True)


def _zrodlo(sciezka: Path) -> str:
    """Czyta plik projektu jako UTF-8."""
    assert sciezka.is_file(), f"brak pliku {sciezka}"
    return sciezka.read_text(encoding="utf-8")


def _pytania(klient, **dane: object) -> list[dict]:
    """Pyta API o zestaw pytań i zwraca listę pytań."""
    odpowiedz = klient.post(GENERUJ, json=dane)
    assert odpowiedz.status_code == 200
    wynik = odpowiedz.get_json()
    assert wynik["ok"] is True, wynik
    return wynik["pytania"]


def _poprawny_indeks(pytanie_id: str, seed: int, prawo: str | None = None) -> int:
    """Numer poprawnej odpowiedzi — liczony tym samym generatorem co serwer."""
    for pytanie in generate(prawo=prawo, ile=10_000, seed=seed):
        if pytanie.id == pytanie_id:
            return pytanie.poprawna
    raise AssertionError(f"generator nie zna pytania {pytanie_id}")


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


def test_jest_wybor_zakresu_z_wszystkimi_prawami(html):
    assert re.search(r'<select[^>]*id="pole-zakres"', html), "brak wyboru zakresu"
    assert re.search(r'<option value=""[^>]*>\s*Wszystkie prawa', html)
    assert re.search(rf'<option value="{re.escape(PRAWO)}"', html), "brak prawa na liście"


def test_jest_wybor_liczby_pytan_3_5_10(html):
    dopasowanie = re.search(r'<select[^>]*id="pole-ile".*?</select>', html, re.S)
    assert dopasowanie, "brak wyboru liczby pytań"
    opcje = re.findall(r'<option value="([^"]*)"', dopasowanie.group(0))

    assert opcje == LICZBY_PYTAN, f"opcje liczby pytań: {opcje}"


def test_jest_kontener_pytan_i_przycisk_startu(html):
    assert 'id="kontener-pytan"' in html, "brak kontenera pytań"
    assert 'id="przycisk-start"' in html, "brak przycisku startu"


def test_strona_ma_podpowiedz_bez_javascriptu(html):
    """Bez skryptów zostaje komunikat i odnośnik do listy praw."""
    assert "<noscript>" in html
    assert "/prawa" in html


# --- parametr adresu ---------------------------------------------------------


def test_parametr_ustawia_zakres_na_jedno_prawo(klient):
    html = klient.get(STRONA, query_string={"prawo": PRAWO}).get_data(as_text=True)

    assert re.search(rf'<option value="{re.escape(PRAWO)}"[^>]*selected', html), (
        "prawo z adresu nie jest zaznaczone na liście"
    )


def test_nieznany_slug_daje_komunikat_i_proponuje_liste_praw(klient):
    odpowiedz = klient.get(STRONA, query_string={"prawo": NIEZNANE_PRAWO})
    html = odpowiedz.get_data(as_text=True)

    assert odpowiedz.status_code == 200
    assert "Nie mamy prawa" in html
    assert NIEZNANE_PRAWO in html
    assert 'href="/prawa"' in html, "brak odnośnika do listy praw"


def test_parametr_prawo_jest_escapowany(klient):
    html = klient.get(STRONA, query_string={"prawo": WSTRZYKNIECIE}).get_data(as_text=True)

    assert WSTRZYKNIECIE not in html, "parametr utworzył znacznik script"
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_szablon_nie_uzywa_filtra_safe():
    assert "|safe" not in _zrodlo(SZABLON), "szablon nie powinien używać |safe"


# --- API: generowanie pytań --------------------------------------------------


def test_generate_zwraca_zadana_liczbe_pytan(klient):
    odpowiedz = klient.post(GENERUJ, json={"ile": 3, "seed": SEED})
    wynik = odpowiedz.get_json()

    assert odpowiedz.status_code == 200
    assert wynik["ok"] is True
    assert wynik["seed"] == SEED
    assert len(wynik["pytania"]) == 3


def test_generate_nie_wysyla_poprawnej_odpowiedzi_ani_wyjasnienia(klient):
    for pytanie in _pytania(klient, ile=3, seed=SEED):
        assert "poprawna" not in pytanie, f"pytanie {pytanie['id']} zdradza odpowiedź"
        assert "wyjasnienie" not in pytanie, f"pytanie {pytanie['id']} zdradza wyjaśnienie"
        assert pytanie["opcje"], "pytanie bez odpowiedzi"
        assert pytanie["podpowiedz"], "pytanie bez podpowiedzi"


def test_generate_ogranicza_sie_do_jednego_prawa(klient):
    pytania = _pytania(klient, prawo=PRAWO, ile=3, seed=SEED)

    assert pytania
    assert {pytanie["prawo"] for pytanie in pytania} == {PRAWO}


def test_generate_odrzuca_nieznane_prawo(klient):
    odpowiedz = klient.post(GENERUJ, json={"prawo": NIEZNANE_PRAWO, "ile": 3, "seed": SEED})
    wynik = odpowiedz.get_json()

    assert odpowiedz.status_code == 200
    assert wynik["ok"] is False
    assert NIEZNANE_PRAWO in wynik["blad"]


# --- API: sprawdzanie odpowiedzi ---------------------------------------------


def test_check_przyjmuje_poprawna_odpowiedz_i_daje_wyjasnienie(klient):
    pytanie = _pytania(klient, ile=3, seed=SEED)[0]
    indeks = _poprawny_indeks(pytanie["id"], SEED)

    odpowiedz = klient.post(
        SPRAWDZ,
        json={"seed": SEED, "id": pytanie["id"], "odpowiedz": indeks},
    )
    wynik = odpowiedz.get_json()

    assert odpowiedz.status_code == 200
    assert wynik["ok"] is True
    assert wynik["poprawna"] is True
    assert wynik["wyjasnienie"].strip(), "pusta odpowiedź wyjaśnienia"


def test_check_odrzuca_bledna_odpowiedz(klient):
    pytanie = _pytania(klient, ile=3, seed=SEED)[0]
    indeks = _poprawny_indeks(pytanie["id"], SEED)
    inny = (indeks + 1) % len(pytanie["opcje"])

    odpowiedz = klient.post(
        SPRAWDZ,
        json={"seed": SEED, "id": pytanie["id"], "odpowiedz": inny},
    )
    wynik = odpowiedz.get_json()

    assert odpowiedz.status_code == 200
    assert wynik["ok"] is True
    assert wynik["poprawna"] is False
    assert wynik["wyjasnienie"].strip(), "wyjaśnienie ma być także przy błędzie"


def test_check_z_nieznanym_id_zwraca_ok_false_i_kod_200(klient):
    odpowiedz = klient.post(
        SPRAWDZ,
        json={"seed": SEED, "id": NIEZNANE_ID, "odpowiedz": 0},
    )
    wynik = odpowiedz.get_json()

    assert odpowiedz.status_code == 200
    assert wynik["ok"] is False
    assert "Nie znam pytania" in wynik["blad"]
    assert "poprawna" not in wynik


def test_check_bez_ziarna_to_blad_danych(klient):
    odpowiedz = klient.post(SPRAWDZ, json={"id": NIEZNANE_ID, "odpowiedz": 0})
    wynik = odpowiedz.get_json()

    assert odpowiedz.status_code == 200
    assert wynik["ok"] is False
    assert "seed" in wynik["blad"]


def test_cialo_ktore_nie_jest_obiektem_json_to_blad_danych(klient):
    odpowiedz = klient.post(GENERUJ, json=[1, 2, 3])
    wynik = odpowiedz.get_json()

    assert odpowiedz.status_code == 200
    assert wynik["ok"] is False
    assert wynik["blad"]


# --- pliki statyczne ---------------------------------------------------------


def test_skrypt_i_styl_istnieja_i_nie_sa_puste():
    for plik in (JS, CSS):
        assert plik.is_file(), f"brak pliku {plik}"
        assert plik.stat().st_size > 0, f"plik {plik} jest pusty"


def test_skrypt_wola_oba_endpointy():
    zrodlo = _zrodlo(JS)

    assert GENERUJ in zrodlo, "brak wywołania generowania pytań"
    assert SPRAWDZ in zrodlo, "brak wywołania sprawdzania odpowiedzi"
    assert "fetch(" in zrodlo, "skrypt nie używa fetch"


def test_skrypt_czyta_zakres_z_adresu():
    zrodlo = _zrodlo(JS)

    assert "URLSearchParams" in zrodlo, "skrypt nie czyta parametrów adresu"
    assert "location.search" in zrodlo, "brak odczytu adresu"
    assert "prawo" in zrodlo, "skrypt nie obsługuje parametru prawo"


def test_skrypt_obsluguje_klawisze_1_4_i_enter():
    zrodlo = _zrodlo(JS)

    assert "keydown" in zrodlo, "brak obsługi klawiatury"
    for cyfra in ("1", "2", "3", "4"):
        assert f'"{cyfra}"' in zrodlo, f"brak klawisza {cyfra}"
    assert "Enter" in zrodlo, "brak obsługi klawisza Enter"


def test_skrypt_ma_podpowiedz_i_podsumowanie():
    zrodlo = _zrodlo(JS)

    assert "Podpowiedź" in zrodlo, "brak przycisku podpowiedzi"
    assert "Poprawne odpowiedzi" in zrodlo, "podsumowanie bez liczby poprawnych"
    assert "Do powtórki" in zrodlo, "podsumowanie bez listy błędów"
    assert "/prawa/" in zrodlo, "brak odnośników do praw w podsumowaniu"


def test_skrypt_obsluguje_blad_ok_false():
    zrodlo = _zrodlo(JS)

    assert ".ok" in zrodlo, "skrypt nie sprawdza pola ok"
    assert ".blad" in zrodlo, "skrypt nie pokazuje pola blad"
    assert "Nie udało się" in zrodlo, "brak komunikatu po polsku"


def test_skrypt_nie_wstawia_tresci_przez_innerhtml():
    zrodlo = _zrodlo(JS)

    assert ".innerHTML" not in zrodlo, "treść z API ma trafiać przez textContent"


# --- rejestracja widoku ------------------------------------------------------


def test_blueprinty_sa_zarejestrowane():
    app = create_app({"TESTING": True})

    assert "quiz" in app.config["BLUEPRINTS"]
    assert "api_quiz" in app.config["BLUEPRINTS"]
