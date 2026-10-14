"""Testy strony ``/konsekwencja`` i API ``/api/wynikanie`` (karta PRZ-083).

Sprawdzamy całą lekcję: definicję, dwa rozumowania o Azorze, założenia sprzeczne,
interaktywną tablicę równoważności i test wynikania. Testy nie wierzą stronie na słowo —
oceny rozumowań i wniosek pod tablicą liczą od nowa przez ``app.logic.truth``.

Dwie ścieżki testu wynikania muszą dawać ten sam wynik: ``POST /api/wynikanie``
(który woła ``wynikanie.js``) i zwykły ``POST`` na ``/konsekwencja`` (bez JavaScriptu).
Dlatego wynik porównujemy dla obu adresów.

Testy pliku ``app/static/js/wynikanie.js`` patrzą na jego treść — projekt nie ma
runnera JS (``AGENTS.md``), więc pilnujemy identyfikatorów, wywołania ``fetch``
i braku ``innerHTML`` z danymi z API.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import create_app
from app.blueprints import konsekwencja
from app.logic import truth
from app.logic.formula import parse, to_html

ADRES = "/konsekwencja"
API = "/api/wynikanie"

#: Rozumowanie poprawne z wykładu: założenia ``p → q`` i ``∼q``, teza ``∼p``.
ZALOZENIA_POPRAWNE = ["p → q", "∼q"]
TEZA_POPRAWNA = "∼p"

#: Rozumowanie niepoprawne z wykładu: założenia ``p → q`` i ``∼p``, teza ``∼q``.
ZALOZENIA_NIEPOPRAWNE = ["p → q", "∼p"]
TEZA_NIEPOPRAWNA = "∼q"

#: Kontrprzykład rozumowania niepoprawnego — Azor-kot.
KONTRPRZYKLAD_NIEPOPRAWNY = "p = 0, q = 1"

#: Tekst wstrzykiwany w pola formularza i do API.
WSTRZYKNIECIE = "<script>alert(1)</script>"

KATALOG_GLOWNY = Path(__file__).resolve().parents[1]
JS = KATALOG_GLOWNY / "app" / "static" / "js" / "wynikanie.js"
SZABLON = KATALOG_GLOWNY / "app" / "templates" / "konsekwencja.html"

H1 = re.compile(r"<h1\b")
WZORZEC_SAFE = re.compile(r"\{\{(?P<wyrazenie>.*?)\|\s*safe\s*\}\}", re.DOTALL)
WZORZEC_TEXTAREA = re.compile(
    r'<textarea[^>]*id="pole-zalozenia"[^>]*>(?P<tresc>.*?)</textarea>', re.DOTALL
)
WZORZEC_INPUTU = re.compile(r'<input[^>]*id="pole-teza"[^>]*>', re.DOTALL)
WZORZEC_WARTOSCI = re.compile(r'value="(?P<wartosc>[^"]*)"')


@pytest.fixture(scope="module")
def klient():
    """Klient testowy aplikacji."""
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def html(klient):
    """Treść strony ``/konsekwencja`` bez wysyłania formularza."""
    return klient.get(ADRES).get_data(as_text=True)


def _zrodlo(sciezka: Path) -> str:
    """Czyta plik projektu jako UTF-8."""
    assert sciezka.is_file(), f"brak pliku {sciezka}"
    return sciezka.read_text(encoding="utf-8")


def _post_json(klient, adres: str, dane) -> dict:
    """Wysyła JSON na endpoint i zwraca odpowiedź (kod 200, typ JSON)."""
    odpowiedz = klient.post(adres, json=dane)
    assert odpowiedz.status_code == 200, f"{adres}: kod {odpowiedz.status_code}"
    assert odpowiedz.headers["Content-Type"].startswith("application/json")
    return odpowiedz.get_json()


def _blad(klient, adres: str, dane) -> dict:
    """Wysyła dane, które mają się nie udać, i zwraca odpowiedź błędu."""
    tresc = _post_json(klient, adres, dane)
    assert tresc["ok"] is False
    assert isinstance(tresc["blad"], str) and tresc["blad"].strip(), "puste pole blad"
    return tresc


def _formularz(klient, zalozenia: str, teza: str) -> str:
    """Wysyła formularz zwykłym POST-em (ścieżka bez JavaScriptu)."""
    odpowiedz = klient.post(ADRES, data={"zalozenia": zalozenia, "teza": teza})
    assert odpowiedz.status_code == 200
    return odpowiedz.get_data(as_text=True)


def _pole_zalozen(html: str) -> str:
    """Zwraca zawartość pola z założeniami."""
    dopasowanie = WZORZEC_TEXTAREA.search(html)
    assert dopasowanie, 'brak pola założeń (textarea id="pole-zalozenia")'
    return dopasowanie["tresc"]


def _pole_tezy(html: str) -> str:
    """Zwraca wartość pola z tezą."""
    dopasowanie = WZORZEC_INPUTU.search(html)
    assert dopasowanie, 'brak pola tezy (input id="pole-teza")'
    wartosc = WZORZEC_WARTOSCI.search(dopasowanie.group(0))
    assert wartosc, "pole tezy nie ma atrybutu value"
    return wartosc["wartosc"]


# --- widok HTML ---------------------------------------------------------------


def test_strona_odpowiada_200_i_html_utf8(klient):
    odpowiedz = klient.get(ADRES)

    assert odpowiedz.status_code == 200
    typ = odpowiedz.headers["Content-Type"]
    assert typ.startswith("text/html")
    assert "charset=utf-8" in typ.lower()


def test_strona_ma_dokladnie_jeden_h1(html):
    assert len(H1.findall(html)) == 1, "strona ma mieć jeden nagłówek h1"


def test_strona_nie_zostawia_nieuzupelnionych_szablonow(html):
    assert "{{" not in html
    assert "{%" not in html


def test_strona_pokazuje_definicje_wynikania(html):
    assert "wynika logicznie" in html
    assert "tautologią" in html
    assert "założenia" in html and "teza" in html
    assert "nie istnieje wartościowanie" in html


def test_strona_pokazuje_oba_rozumowania_o_azorze(html):
    for formula in (konsekwencja.AZOR_POPRAWNE, konsekwencja.AZOR_NIEPOPRAWNE):
        assert to_html(parse(formula)) in html, f"brak wzoru {formula}"

    assert "poprawne" in html
    assert "niepoprawne" in html
    assert KONTRPRZYKLAD_NIEPOPRAWNY in html


def test_ocena_rozumowan_zgadza_sie_z_silnikiem(html):
    """Strona pisze o rozumowaniu poprawnym tylko wtedy, gdy wzór jest tautologią."""
    wiersze = {wiersz["formula"]: wiersz for wiersz in konsekwencja.rozumowania_azora()}

    assert wiersze[konsekwencja.AZOR_POPRAWNE]["poprawne"] is True
    assert wiersze[konsekwencja.AZOR_NIEPOPRAWNE]["poprawne"] is False
    assert truth.is_tautology(parse(konsekwencja.AZOR_POPRAWNE))
    assert not truth.is_tautology(parse(konsekwencja.AZOR_NIEPOPRAWNE))
    assert wiersze[konsekwencja.AZOR_NIEPOPRAWNE]["kontrprzyklad"] == KONTRPRZYKLAD_NIEPOPRAWNY


def test_strona_ma_sekcje_o_zalozeniach_sprzecznych(html):
    assert 'id="naglowek-sprzeczne"' in html
    assert "Założenia sprzeczne" in html
    assert to_html(parse(konsekwencja.ZALOZENIA_SPRZECZNE)) in html
    assert "Ziemia jest płaska" in html
    assert "formalną poprawność rozumowania, a nie jego sens" in html


def test_strona_pokazuje_tablice_rownowaznosci_przez_partial(html):
    assert 'data-rola="tablica-prawdy"' in html
    assert 'data-adres="/api/formula/table"' in html
    assert konsekwencja.ROWNOZNACZNOSC_PRZYKLADU in html, "brak formuły równoważności"


def test_rownowaznosc_z_przykladu_jest_tautologia(html):
    """Zdanie pod tablicą musi zgadzać się z tym, co naprawdę liczy silnik."""
    assert truth.is_tautology(parse(konsekwencja.ROWNOZNACZNOSC_PRZYKLADU))
    assert konsekwencja.wniosek_rownowaznosci()["tautologia"] is True
    assert "same jedynki" in html


def test_strona_uzywa_notacji_wykladu(html):
    assert "∼" in html and "≡" in html
    assert "¬" not in html, "strona treści nie pokazuje notacji popularnej"
    assert "↔" not in html


def test_strona_ma_formularz_testu(html):
    assert re.search(r'<form[^>]*id="formularz-wynikania"', html)
    assert 'method="post"' in html
    assert f'action="{ADRES}"' in html
    assert re.search(r'<textarea[^>]*name="zalozenia"', html)
    assert re.search(r'<input[^>]*name="teza"', html)
    assert 'id="przycisk-sprawdz"' in html


def test_pola_formularza_maja_etykiety(html):
    for identyfikator in ("pole-zalozenia", "pole-teza"):
        assert f'for="{identyfikator}"' in html, f"brak etykiety dla {identyfikator}"
    assert "aria-describedby" in html, "pola bez opisu dla czytnika ekranu"


def test_szablon_uzywa_safe_tylko_na_wyniku_to_html():
    """Tekst z formularza trafia do strony bez ``|safe`` — inaczej byłby wstrzyknięciem."""
    wyrazenia = WZORZEC_SAFE.findall(_zrodlo(SZABLON))

    assert wyrazenia, "szablon nie rysuje wzorów przez to_html"
    for wyrazenie in wyrazenia:
        assert "to_html" in wyrazenie, f"|safe na {wyrazenie!r}"


# --- formularz bez JavaScriptu -------------------------------------------------


def test_formularz_bez_javascriptu_pokazuje_ze_teza_wynika(klient):
    html = _formularz(klient, "\n".join(ZALOZENIA_POPRAWNE), TEZA_POPRAWNA)

    assert "Teza wynika z założeń." in html


def test_formularz_bez_javascriptu_pokazuje_kontrprzyklad(klient):
    html = _formularz(klient, "\n".join(ZALOZENIA_NIEPOPRAWNE), TEZA_NIEPOPRAWNA)

    assert "Teza nie wynika z założeń." in html
    assert KONTRPRZYKLAD_NIEPOPRAWNY in html
    assert 'href="/plac-zabaw"' in html, "brak odnośnika do placu zabaw"


def test_formularz_pokazuje_blad_dla_zlej_formuly(klient):
    html = _formularz(klient, "p ∧", "q")

    assert "Założenie 1" in html
    assert "Teza nie wynika" not in html and "Teza wynika" not in html


def test_formularz_odsyla_wpisane_wartosci(klient):
    html = _formularz(klient, "\n".join(ZALOZENIA_POPRAWNE), TEZA_POPRAWNA)

    assert _pole_zalozen(html).strip() == "\n".join(ZALOZENIA_POPRAWNE)
    assert _pole_tezy(html) == TEZA_POPRAWNA


def test_formularz_odrzuca_za_duzo_zalozen(klient):
    zalozenia = "\n".join(f"p{indeks}" for indeks in range(11))

    html = _formularz(klient, zalozenia, "q")

    assert "limit to 10" in html


def test_formularz_odrzuca_za_duzo_zmiennych(klient):
    html = _formularz(klient, "a ∧ b ∧ c ∧ d", "e ∨ f ∨ g")

    assert "limit to 6" in html


def test_formularz_bez_zalozen_prosi_o_zalozenie(klient):
    html = _formularz(klient, "   \n  ", "q")

    assert "co najmniej jedno założenie" in html


def test_formularz_escapuje_tresc_uzytkownika(klient):
    html = _formularz(klient, WSTRZYKNIECIE, WSTRZYKNIECIE)

    assert WSTRZYKNIECIE not in html, "treść pola utworzyła znacznik script"
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


# --- API /api/wynikanie -------------------------------------------------------


def test_api_zwraca_wynika_dla_poprawnego_rozumowania(klient):
    dane = _post_json(klient, API, {"zalozenia": ZALOZENIA_POPRAWNE, "teza": TEZA_POPRAWNA})

    assert dane["ok"] is True
    assert dane["wynika"] is True
    assert dane["kontrprzyklad"] is None
    assert dane["blad"] == ""


def test_api_zwraca_nie_wynika_i_kontrprzyklad(klient):
    dane = _post_json(klient, API, {"zalozenia": ZALOZENIA_NIEPOPRAWNE, "teza": TEZA_NIEPOPRAWNA})

    assert dane["ok"] is True
    assert dane["wynika"] is False
    assert dane["kontrprzyklad"] == {"p": 0, "q": 1}


def test_api_podaje_kontrprzyklad_liczbami_zero_jeden(klient):
    dane = _post_json(klient, API, {"zalozenia": ZALOZENIA_NIEPOPRAWNE, "teza": TEZA_NIEPOPRAWNA})

    for wartosc in dane["kontrprzyklad"].values():
        assert wartosc in (0, 1)
        assert not isinstance(wartosc, bool), "wartość ma być liczbą 1/0, nie true/false"


def test_api_dla_zalozen_sprzecznych_zawsze_wynika(klient):
    dane = _post_json(klient, API, {"zalozenia": ["p ∧ ∼p"], "teza": "q"})

    assert dane["ok"] is True
    assert dane["wynika"] is True
    assert dane["kontrprzyklad"] is None


@pytest.mark.parametrize(
    ("zalozenia", "teza", "wynika"),
    [
        (["p → q", "q → r"], "p → r", True),
        (["p ∨ q", "∼p"], "q", True),
        (["p → q"], "q → p", False),
        (["p ∧ q"], "p ∨ q", True),
        (["p"], "p", True),
    ],
)
def test_api_zgadza_sie_z_rachunkiem(klient, zalozenia, teza, wynika):
    dane = _post_json(klient, API, {"zalozenia": zalozenia, "teza": teza})

    assert dane["wynika"] is wynika


def test_api_zla_formula_daje_ok_false_i_kod_200(klient):
    tresc = _blad(klient, API, {"zalozenia": ["p ∧"], "teza": "q"})

    assert "Założenie 1" in tresc["blad"]
    assert "brakuje argumentu" in tresc["blad"]


def test_api_odrzuca_za_duzo_zalozen(klient):
    tresc = _blad(klient, API, {"zalozenia": ["p"] * 11, "teza": "q"})

    assert "10" in tresc["blad"]


def test_api_odrzuca_za_duzo_zmiennych(klient):
    tresc = _blad(klient, API, {"zalozenia": ["a ∧ b ∧ c ∧ d"], "teza": "e ∨ f ∨ g"})

    assert "6" in tresc["blad"]


def test_api_odrzuca_za_dluga_formule(klient):
    tresc = _blad(klient, API, {"zalozenia": ["p" * 501], "teza": "q"})

    assert "500" in tresc["blad"]


@pytest.mark.parametrize(
    ("zalozenia", "teza"),
    [
        (None, "q"),
        (["p → q"], None),
        ("p → q", "q"),
        ([7], "q"),
        (["p → q"], 7),
        ([], "q"),
        (["   "], "q"),
        (["p → q"], "   "),
    ],
)
def test_api_bledne_dane_daja_ok_false_i_kod_200(klient, zalozenia, teza):
    _blad(klient, API, {"zalozenia": zalozenia, "teza": teza})


def test_api_bez_tresci_zadania_jest_bledem_danych(klient):
    odpowiedz = klient.post(API)

    assert odpowiedz.status_code == 200
    assert odpowiedz.headers["Content-Type"].startswith("application/json")
    assert odpowiedz.get_json()["ok"] is False


def test_api_lapie_zbyt_glebokie_zagniezdzenie(klient):
    """499 znaków mieści się w limicie długości, ale wyczerpuje stos parsera."""
    formula = "(" * 249 + "p" + ")" * 249

    tresc = _blad(klient, API, {"zalozenia": [formula], "teza": "q"})

    assert "zagnieżdżona" in tresc["blad"]


def test_api_nie_zwraca_bledu_serwera_na_zadne_dane(klient):
    for dane in ({"zalozenia": ["p ∨"], "teza": "q"}, {"zalozenia": [], "teza": ""}, {}):
        odpowiedz = klient.post(API, json=dane)

        assert odpowiedz.status_code == 200


def test_api_i_formularz_daja_ten_sam_wynik(klient):
    for zalozenia, teza in (
        (ZALOZENIA_POPRAWNE, TEZA_POPRAWNA),
        (ZALOZENIA_NIEPOPRAWNE, TEZA_NIEPOPRAWNA),
    ):
        dane = _post_json(klient, API, {"zalozenia": zalozenia, "teza": teza})
        html = _formularz(klient, "\n".join(zalozenia), teza)

        if dane["wynika"]:
            assert "Teza wynika z założeń." in html
        else:
            assert "Teza nie wynika z założeń." in html


def test_widoki_sa_zarejestrowane():
    app = create_app({"TESTING": True})

    assert "konsekwencja" in app.config["BLUEPRINTS"]
    assert "api_wynikanie" in app.config["BLUEPRINTS"]


# --- plik JavaScript ----------------------------------------------------------


def test_skrypt_istnieje_i_nie_jest_pusty():
    assert JS.is_file(), f"brak pliku {JS}"
    assert JS.stat().st_size > 0, "plik JavaScript jest pusty"


def test_skrypt_wola_endpoint_wynikania():
    zrodlo = _zrodlo(JS)

    assert API in zrodlo, "brak wywołania /api/wynikanie"
    assert "pobierzJson(" in zrodlo, "skrypt nie korzysta ze wspólnego klienta API"


def test_skrypt_obsluguje_blad_ok_false():
    zrodlo = _zrodlo(JS)

    assert ".ok" in zrodlo, "skrypt nie sprawdza pola ok"
    assert ".blad" in zrodlo, "skrypt nie pokazuje pola blad"
    assert "Nie udało się" in zrodlo, "brak komunikatu po polsku"


def test_skrypt_pisze_kontrprzyklad_zdaniem():
    zrodlo = _zrodlo(JS)

    assert " = " in zrodlo, "brak zdania w postaci „p = 1”"
    assert "kontrprzyklad" in zrodlo
    assert "/plac-zabaw" in zrodlo, "brak odnośnika do placu zabaw"


def test_skrypt_bierze_zalozenia_z_wierszy():
    zrodlo = _zrodlo(JS)

    assert 'split("\\n")' in zrodlo, "skrypt nie dzieli założeń na wiersze"


def test_skrypt_nie_wstawia_tresci_przez_innerhtml():
    zrodlo = _zrodlo(JS)

    assert ".innerHTML" not in zrodlo, "treść z API ma trafiać przez textContent"


def test_skrypt_nie_uzywa_eval():
    assert "eval(" not in _zrodlo(JS)
