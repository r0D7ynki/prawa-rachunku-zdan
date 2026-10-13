"""Testy strony ``/wstep`` — pierwszej lekcji kursu."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
from markupsafe import Markup

from app import create_app
from app.blueprints import wstep

ADRES = "/wstep"

#: Trzy części planu kursu (fragmenty widoczne na stronie).
CZESCI_KURSU = ["rachunek zdań", "rachunek predykatów", "teorii zbiorów"]

#: Cztery przykłady wnioskowania: (fragment treści, odpowiedź z wykładu).
PRZYKLADY_WNIOSKOWANIA = [
    ("Każdy kwadrat jest prostokątem", "poprawne"),
    ("Nie zdałem, więc się nie nauczyłem", "poprawne"),
    ("Nie nauczyłem się, więc nie zdam", "niepoprawne"),
    ("Każdy filozof jest mądry", "niepoprawne"),
]

#: Cztery przykłady zdań z wykładu.
PRZYKLADY_ZDAN = [
    "9 dzieli się przez 3",
    "Słońce krąży wokół Ziemi",
    "Która godzina?",
    "Ten samochód jest drogi",
]

#: Blok jednego przykładu wnioskowania wraz z odpowiedzią.
PRZYKLAD = re.compile(r'<article class="przyklad-wnioskowania">.*?</article>', re.DOTALL)

#: Wyrażenie wstawiane do HTML przez filtr ``|safe``.
WZORZEC_SAFE = re.compile(r"\{\{(?P<wyrazenie>.*?)\|\s*safe\s*\}\}", re.DOTALL)

MODUL_FORMULY = "app.logic.formula"


@pytest.fixture(scope="module")
def klient():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def html(klient):
    odpowiedz = klient.get(ADRES)
    assert odpowiedz.status_code == 200
    return odpowiedz.get_data(as_text=True)


def _policz_slowo(tekst: str, slowo: str) -> int:
    """Liczy całe słowa, więc „niepoprawne” nie liczy się jako „poprawne”."""
    return len(re.findall(rf"(?<!\w){re.escape(slowo)}(?!\w)", tekst))


# --- szkielet strony ---------------------------------------------------------


def test_strona_odpowiada_200_i_html_utf8(klient):
    odpowiedz = klient.get(ADRES)
    assert odpowiedz.status_code == 200
    typ_tresci = odpowiedz.headers["Content-Type"]
    assert typ_tresci.startswith("text/html")
    assert "charset=utf-8" in typ_tresci.lower()


def test_strona_ma_jezyk_polski_i_dokladnie_jeden_h1(html):
    assert 'lang="pl"' in html
    assert len(re.findall(r"<h1\b", html)) == 1


def test_strona_nie_zostawia_nieuzupelnionych_szablonow(html):
    assert "{{" not in html
    assert "{%" not in html


# --- treść z wykładu ---------------------------------------------------------


@pytest.mark.parametrize("czesc", CZESCI_KURSU)
def test_plan_kursu_wymienia_trzy_czesci(html, czesc):
    assert czesc in html, f"brak części kursu {czesc!r}"


def test_strona_ma_cztery_przyklady_wnioskowania(html):
    bloki = PRZYKLAD.findall(html)
    assert len(bloki) == len(PRZYKLADY_WNIOSKOWANIA) == 4


@pytest.mark.parametrize(("fragment", "odpowiedz"), PRZYKLADY_WNIOSKOWANIA)
def test_przyklad_ma_odpowiedz_i_wyjasnienie(html, fragment, odpowiedz):
    pasujace = [blok for blok in PRZYKLAD.findall(html) if fragment in blok]
    assert len(pasujace) == 1, f"nie znalazłem dokładnie jednego przykładu {fragment!r}"

    blok = pasujace[0]
    assert "<details" in blok, "odpowiedź nie jest w rozwijanym elemencie <details>"
    assert f"<strong>{odpowiedz}</strong>" in blok, f"brak odpowiedzi {odpowiedz!r}"
    assert "wyjasnienie" in blok, "brak jednozdaniowego wyjaśnienia"


def test_strona_uzywa_obu_slow_poprawne_i_niepoprawne(html):
    assert _policz_slowo(html, "poprawne") >= 2
    assert _policz_slowo(html, "niepoprawne") >= 2


def test_strona_podaje_definicje_zdania_logicznego(html):
    assert "Zdanie logiczne to stwierdzenie" in html
    assert "prawdę albo fałsz" in html


@pytest.mark.parametrize("przyklad", PRZYKLADY_ZDAN)
def test_strona_podaje_cztery_przyklady_zdan(html, przyklad):
    assert przyklad in html, f"brak przykładu zdania {przyklad!r}"


def test_strona_pokazuje_wiersz_falszujacy_odwrocenie_implikacji(html):
    blok = next(blok for blok in PRZYKLAD.findall(html) if "Nie nauczyłem się" in blok)
    assert "∼q" in blok
    assert 'class="falsz">0</td>' in blok, "brak wiersza tablicy z wynikiem 0"


# --- wzory -------------------------------------------------------------------


def test_wzory_na_stronie_pochodza_z_to_html_a_nie_z_surowego_tekstu(html):
    if importlib.util.find_spec(MODUL_FORMULY) is None:
        pytest.skip("moduł app.logic.formula jeszcze nie scalony (karta PRZ-001)")

    wzory = re.findall(r'<p class="formula">(.*?)</p>', html, re.DOTALL)
    assert len(wzory) == 2, "strona pokazuje dwa wzory"
    for wzor, tekst in zip(wzory, (wstep.KONTRAPOZYCJA, wstep.ODWROCENIE_IMPLIKACJI), strict=True):
        assert "<span" in wzor and "class=" in wzor, f"wzór nie jest HTML-em: {wzor!r}"
        assert wzor.strip() == str(wstep.formula_to_html(tekst))


def test_warianty_zapisu_zamieniaja_znaki_wykladowe():
    assert wstep._warianty_zapisu("((p → q) ∧ ∼q) → ∼p") == [
        "((p → q) ∧ ∼q) → ∼p",
        "((p → q) ∧ ¬q) → ¬p",
    ]
    assert wstep._warianty_zapisu("p ≡ q") == ["p ≡ q", "p ↔ q"]


def test_warianty_zapisu_bez_znakow_wykladowych_daja_jeden_zapis():
    assert wstep._warianty_zapisu("p → q") == ["p → q"]


def test_formula_to_html_bez_modulu_zwraca_tekst_bez_znacznikow(monkeypatch):
    monkeypatch.setattr(wstep, "FORMULA_MODULE", "app.logic.modul_ktorego_nie_ma")

    wynik = wstep.formula_to_html("<p>p → q</p>")

    assert isinstance(wynik, Markup)
    assert wynik == "&lt;p&gt;p → q&lt;/p&gt;"


@pytest.mark.parametrize("tekst", ["∼p", "((p → q) ∧ ∼q) → ∼p", "to nie jest formuła (("])
def test_formula_to_html_nigdy_nie_podnosi_bledu(tekst):
    wynik = wstep.formula_to_html(tekst)

    assert isinstance(wynik, Markup)
    assert wynik, "wzór nigdy nie jest pusty"


# --- nawigacja i bezpieczeństwo szablonu -------------------------------------


def test_strona_ma_odnosniki_poprzedniej_i_nastepnej_lekcji(html):
    assert 'href="/"' in html
    assert 'href="/formuly"' in html
    assert "Poprzednia lekcja" in html
    assert "Następna lekcja" in html


def test_szablon_uzywa_safe_tylko_na_wyniku_to_html():
    szablon = Path(__file__).resolve().parents[1] / "app" / "templates" / "wstep.html"
    wyrazenia = [d["wyrazenie"].strip() for d in WZORZEC_SAFE.finditer(szablon.read_text("utf-8"))]
    assert wyrazenia, "szablon nie wstawia wzorów przez |safe"
    for wyrazenie in wyrazenia:
        assert "to_html" in wyrazenie, f"|safe na {wyrazenie!r}"
