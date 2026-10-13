"""Testy API formuł: parsowanie, tablica prawdy i równoważność (karta PRZ-009).

Wszystkie sprawdzenia idą przez ``create_app({"TESTING": True}).test_client()`` —
bez przeglądarki i bez sieci.
"""

from __future__ import annotations

import pytest

from app import create_app

PARSE = "/api/formula/parse"
TABLE = "/api/formula/table"
EQUIVALENCE = "/api/equivalence"


@pytest.fixture(scope="module")
def klient():
    """Klient testowy aplikacji."""
    return create_app({"TESTING": True}).test_client()


def _post_json(klient, adres: str, dane) -> dict:
    """Wysyła JSON na endpoint i zwraca odczytaną odpowiedź (kod 200, typ JSON)."""
    odpowiedz = klient.post(adres, json=dane)
    assert odpowiedz.status_code == 200, f"{adres}: kod {odpowiedz.status_code}"
    assert odpowiedz.headers["Content-Type"].startswith("application/json")
    return odpowiedz.get_json()


def _blad(klient, adres: str, dane) -> dict:
    """Wysyła dane, które mają się nie udać, i zwraca odpowiedź błędu."""
    odpowiedz = klient.post(adres, json=dane)
    assert odpowiedz.status_code == 200, f"{adres}: kod {odpowiedz.status_code}, oczekiwano 200"
    assert odpowiedz.headers["Content-Type"].startswith("application/json")
    tresc = odpowiedz.get_json()
    assert tresc["ok"] is False
    assert isinstance(tresc["blad"], str) and tresc["blad"].strip(), "puste pole blad"
    return tresc


def _wszystkie_wartosci(znaki: list[dict]) -> list:
    """Wszystkie liczby z pola ``values`` wszystkich wierszy tablicy."""
    return [wartosc for wiersz in znaki for wartosc in wiersz["values"]]


# --- /api/formula/parse ------------------------------------------------------


def test_parse_zwraca_zapisy_ast_i_zmienne(klient):
    dane = _post_json(klient, PARSE, {"formula": "p -> q"})

    assert dane["ok"] is True
    assert dane["wyklad"] == "p → q"
    assert dane["unicode"] == "p → q"
    assert dane["ascii"] == "p -> q"
    assert "op-imp" in dane["html"], f"brak klasy operatora w HTML: {dane['html']!r}"
    assert dane["zmienne"] == ["p", "q"]


def test_parse_negacji_trzyma_sie_notacji_pola(klient):
    dane = _post_json(klient, PARSE, {"formula": "∼(p ∨ q)"})

    assert dane["wyklad"].startswith("∼")
    assert dane["unicode"].startswith("¬")


def test_ast_implikacji_ma_dokladnie_taka_strukture(klient):
    dane = _post_json(klient, PARSE, {"formula": "p -> q"})

    assert dane["ast"] == {
        "typ": "Imp",
        "lewy": {"typ": "Var", "nazwa": "p"},
        "prawy": {"typ": "Var", "nazwa": "q"},
    }


def test_ast_negacji_ma_dziecko_koniunkcje(klient):
    ast = _post_json(klient, PARSE, {"formula": "¬(p ∧ q)"})["ast"]

    assert ast["typ"] == "Not"
    assert ast["dziecko"]["typ"] == "And"
    assert ast["dziecko"]["lewy"] == {"typ": "Var", "nazwa": "p"}
    assert ast["dziecko"]["prawy"] == {"typ": "Var", "nazwa": "q"}


@pytest.mark.parametrize("zapis", ["p → q", "p -> q", "p implies q"])
def test_parse_przyjmuje_rozne_zapisy_implikacji(klient, zapis):
    dane = _post_json(klient, PARSE, {"formula": zapis})

    assert dane["ok"] is True
    assert dane["wyklad"] == "p → q"


# --- /api/formula/table ------------------------------------------------------


def test_tablica_koniunkcji_ma_cztery_wiersze(klient):
    dane = _post_json(klient, TABLE, {"formula": "p ∧ q"})

    assert dane["ok"] is True
    assert dane["klasyfikacja"] == "spełnialna"
    assert dane["tabela"]["variables"] == ["p", "q"]
    assert len(dane["tabela"]["rows"]) == 4
    assert dane["tabela"]["classification"] == "spełnialna"


@pytest.mark.parametrize(
    ("formula", "klasyfikacja"),
    [("p ∨ ¬p", "tautologia"), ("p ∧ ¬p", "kontrtautologia"), ("p ∨ q", "spełnialna")],
)
def test_tablica_nazywa_formule(klient, formula, klasyfikacja):
    dane = _post_json(klient, TABLE, {"formula": formula})

    assert dane["klasyfikacja"] == klasyfikacja


def test_znaki_podaja_wartosci_jako_zera_i_jedynki(klient):
    dane = _post_json(klient, TABLE, {"formula": "p ∧ q"})
    znaki = dane["znaki"]

    assert len(znaki) == 4
    assert set(znaki[0]) == {"p", "q", "values"}
    # Wynik koniunkcji: 1 tylko w pierwszym wierszu (p i q prawdziwe).
    assert [wiersz["values"][-1] for wiersz in znaki] == [1, 0, 0, 0]
    for wartosc in _wszystkie_wartosci(znaki):
        assert wartosc in (0, 1)
        assert not isinstance(wartosc, bool), "wartość ma być liczbą 1/0, nie true/false"


def test_tabela_bez_podformul_ma_jedna_kolumne(klient):
    dane = _post_json(klient, TABLE, {"formula": "p ∧ q", "podformuly": False})

    assert dane["tabela"]["columns"] == ["p ∧ q"]
    assert dane["tabela"]["rows"][0]["values"] == [True]


def test_tabela_odrzuca_za_duzo_zmiennych(klient):
    formula = " ∧ ".join(f"a{indeks}" for indeks in range(7))

    tresc = _blad(klient, TABLE, {"formula": formula})

    assert "6" in tresc["blad"], f"komunikat bez granicy zmiennych: {tresc['blad']!r}"


# --- /api/equivalence --------------------------------------------------------


def test_rownowazne_formuly(klient):
    dane = _post_json(klient, EQUIVALENCE, {"lewa": "p → q", "prawa": "¬p ∨ q"})

    assert dane["ok"] is True
    assert dane["rownowazne"] is True
    assert dane["kontrprzyklad"] is None


def test_nierownowazne_formuly_maja_kontrprzyklad(klient):
    dane = _post_json(klient, EQUIVALENCE, {"lewa": "p ∧ q", "prawa": "p ∨ q"})

    assert dane["rownowazne"] is False
    assert dane["kontrprzyklad"] == {"p": 1, "q": 0}


def test_equivalence_rozroznia_pola(klient):
    tresc = _blad(klient, EQUIVALENCE, {"lewa": "p ∧ q"})

    assert "prawa" in tresc["blad"]


# --- błędy danych i nagłówek -------------------------------------------------


@pytest.mark.parametrize(
    ("adres", "dane"),
    [
        (PARSE, {"formula": "p ∧"}),
        (PARSE, {}),
        (PARSE, {"formula": 7}),
        (PARSE, {"formula": "p" * 501}),
        (PARSE, {"formula": []}),
        (PARSE, ["p ∧ q"]),
        (TABLE, {"formula": "p ∨"}),
        (TABLE, {"formula": "p", "podformuly": "tak"}),
        (EQUIVALENCE, {"lewa": "p", "prawa": "q ≡"}),
        (EQUIVALENCE, {"prawa": "q"}),
    ],
)
def test_bledne_dane_daja_ok_false_i_kod_200(klient, adres, dane):
    _blad(klient, adres, dane)


def test_brak_tresci_zadania_jest_bledem_danych(klient):
    odpowiedz = klient.post(PARSE)

    assert odpowiedz.status_code == 200
    assert odpowiedz.headers["Content-Type"].startswith("application/json")
    assert odpowiedz.get_json()["ok"] is False


def test_formula_pusta_jest_bledem_danych(klient):
    tresc = _blad(klient, PARSE, {"formula": "   "})

    assert "pusta" in tresc["blad"].lower()


def test_bardzo_glebokie_zagniezdzenie_jest_bledem_danych(klient):
    """499 znaków mieści się w limicie długości, ale wyczerpuje stos parsera."""
    formula = "(" * 249 + "p" + ")" * 249

    tresc = _blad(klient, PARSE, {"formula": formula})

    assert "zagnieżdżona" in tresc["blad"]


def test_granica_dlugosci_przechodzi_dokladnie_500_znakow(klient):
    dane = _post_json(klient, PARSE, {"formula": "p" * 500})

    assert dane["ok"] is True
    assert dane["zmienne"] == ["p" * 500]


def test_odpowiedz_jest_jsonem_z_kodem_200(klient):
    for adres, dane in [
        (PARSE, {"formula": "p"}),
        (TABLE, {"formula": "p"}),
        (EQUIVALENCE, {"lewa": "p", "prawa": "p"}),
    ]:
        odpowiedz = klient.post(adres, json=dane)

        assert odpowiedz.status_code == 200
        assert odpowiedz.headers["Content-Type"].startswith("application/json")
        assert odpowiedz.get_json()["ok"] is True


def test_blueprint_jest_zarejestrowany():
    app = create_app({"TESTING": True})

    assert "api_formula" in app.config["BLUEPRINTS"]
