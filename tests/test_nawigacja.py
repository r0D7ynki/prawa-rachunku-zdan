"""Testy nawigacji: menu, ścieżka nauki na stronie głównej i stopka.

Karta PRZ-023. Menu i strona główna prowadzą studenta przez kurs w kolejności
wykładu. Odnośniki w menu to zwykłe ``href`` (decyzja D5), więc testy czytają
HTML, a nie tablicę routingu.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from flask import render_template
from jinja2 import ChoiceLoader, DictLoader

from app import create_app

KATALOG = Path(__file__).resolve().parents[1]
SZABLON_BAZY = KATALOG / "app" / "templates" / "base.html"

#: Osiem kroków ścieżki nauki w kolejności wykładu: (adres, nazwa kroku).
SCIEZKA = [
    ("/wstep", "Wstęp"),
    ("/formuly", "Formuły"),
    ("/tautologie", "Tautologie"),
    ("/przeksztalcanie", "Przekształcanie"),
    ("/kpn", "KPN"),
    ("/prawa", "Prawa"),
    ("/plac-zabaw", "Plac zabaw"),
    ("/quiz", "Quiz"),
]

ADRESY_SCIEZKI = [adres for adres, _ in SCIEZKA]

#: Pozycje menu sprzed tej karty — nie mogą zniknąć.
MENU_WCZEŚNIEJSZE = ["/prawa", "/plac-zabaw", "/quiz", "/jak-czytac", "/slowniczek"]

#: Nowe odnośniki lekcji w rozwijanej pozycji **Nauka**.
MENU_LEKCJE = ["/wstep", "/formuly", "/tautologie", "/przeksztalcanie", "/kpn"]

#: Bloki, które ``base.html`` musi nadal wystawiać.
BLOKI = ["tytul", "head", "tresc", "skrypty"]

WZORZEC_NAV = re.compile(r"<nav\b.*?</nav>", re.DOTALL)
WZORZEC_STOPKI = re.compile(r"<footer\b.*?</footer>", re.DOTALL)
WZORZEC_SCIEZKI = re.compile(r'<ol class="lista-sciezki"[^>]*>(?P<tresc>.*?)</ol>', re.DOTALL)
WZORZEC_PUNKTU = re.compile(r"<li>(?P<tresc>.*?)</li>", re.DOTALL)
WZORZEC_ODNOSNIKA = re.compile(r'<a[^>]+href="(?P<adres>[^"]+)"')

#: Szablon testowy nadpisujący każdy blok ``base.html`` własnym znacznikiem.
SZABLON_TESTU_BLOKOW = """{% extends "base.html" %}
{% block tytul %}TYTUL-TESTOWY{% endblock %}
{% block head %}<meta name="test-head" content="HEAD-TESTOWY" />{% endblock %}
{% block tresc %}<p id="akapit-testowy">TRESC-TESTOWA</p>{% endblock %}
{% block skrypty %}<script>window.SKRYPT_TESTOWY = "SKRYPT-TESTOWY";</script>{% endblock %}
"""


@pytest.fixture(scope="module")
def aplikacja():
    """Aplikacja z dodatkowym szablonem, który sprawdza nadpisywanie bloków."""
    app = create_app({"TESTING": True})
    app.jinja_env.loader = ChoiceLoader(
        [DictLoader({"test_blokow.html": SZABLON_TESTU_BLOKOW}), app.jinja_env.loader]
    )
    return app


@pytest.fixture(scope="module")
def klient(aplikacja):
    return aplikacja.test_client()


@pytest.fixture(scope="module")
def strona_glowna(klient):
    odpowiedz = klient.get("/")
    assert odpowiedz.status_code == 200
    return odpowiedz.get_data(as_text=True)


def _menu(html: str) -> str:
    """Zwraca HTML paska nawigacji (bez stopki, która ma te same odnośniki)."""
    dopasowanie = WZORZEC_NAV.search(html)
    assert dopasowanie, "strona nie ma elementu <nav>"
    return dopasowanie.group()


def _stopka(html: str) -> str:
    """Zwraca HTML stopki."""
    dopasowanie = WZORZEC_STOPKI.search(html)
    assert dopasowanie, "strona nie ma elementu <footer>"
    return dopasowanie.group()


def _punkty_sciezki(html: str) -> list[str]:
    """Zwraca punkty listy kroków ze strony głównej."""
    dopasowanie = WZORZEC_SCIEZKI.search(html)
    assert dopasowanie, 'brak listy kroków (class="lista-sciezki")'
    return WZORZEC_PUNKTU.findall(dopasowanie["tresc"])


# --- każdy adres ścieżki działa ----------------------------------------------


@pytest.mark.parametrize("adres", ADRESY_SCIEZKI)
def test_kazdy_adres_sciezki_odpowiada_200(klient, adres):
    odpowiedz = klient.get(adres)
    assert odpowiedz.status_code == 200, f"{adres} → kod {odpowiedz.status_code}"
    assert odpowiedz.headers["Content-Type"].startswith("text/html")


# --- menu --------------------------------------------------------------------


@pytest.mark.parametrize("adres", MENU_LEKCJE + MENU_WCZEŚNIEJSZE)
def test_menu_zawiera_odnosnik(strona_glowna, adres):
    assert f'href="{adres}"' in _menu(strona_glowna), f"brak odnośnika {adres} w menu"


@pytest.mark.parametrize("adres", MENU_LEKCJE + MENU_WCZEŚNIEJSZE)
def test_szablon_bazy_zawiera_odnosnik(adres):
    zrodlo = SZABLON_BAZY.read_text(encoding="utf-8")
    assert f'href="{adres}"' in _menu(zrodlo), f"brak odnośnika {adres} w base.html"


def test_menu_zawiera_wszystkie_osiem_lekcji_poza_strona_glowna(strona_glowna):
    menu = _menu(strona_glowna)
    brakujace = [adres for adres in ADRESY_SCIEZKI[1:] if f'href="{adres}"' not in menu]
    assert not brakujace, f"lekcje poza menu: {brakujace}"


def test_menu_ma_rozwijana_pozycje_nauka(strona_glowna):
    menu = _menu(strona_glowna)
    assert "nav-link dropdown-toggle" in menu, "pozycja Nauka nie jest listą rozwijaną"
    assert 'class="dropdown-menu"' in menu, "brak listy rozwijanej"
    assert 'data-bs-toggle="dropdown"' in menu, "Bootstrap nie otworzy listy"
    assert 'role="button"' in menu and 'aria-expanded="false"' in menu, "brak stanu dla czytnika"
    assert "Nauka" in menu


def test_lista_rozwijana_jest_w_zwijanym_menu(strona_glowna):
    menu = _menu(strona_glowna)
    assert 'data-bs-target="#menuGlowne"' in menu, "brak przycisku zwijania na wąskim ekranie"
    assert 'id="menuGlowne"' in menu, "lista rozwijana poza zwijanym menu"


def test_bootstrap_jest_zaladowany(strona_glowna):
    # Rozwijanie listy i zwijanie menu robi Bootstrap, więc jego skrypt musi być na stronie.
    assert "bootstrap.bundle.min.js" in strona_glowna


def test_menu_nie_dolozyl_wlasnego_javascriptu(strona_glowna):
    zrodlo = SZABLON_BAZY.read_text(encoding="utf-8")
    assert "/static/js/" not in zrodlo, "base.html nie może ładować lokalnego skryptu"
    assert zrodlo.count("<script") == 1, "base.html ładuje tylko Bootstrap z CDN"
    assert "<script" not in _menu(strona_glowna), "menu nie potrzebuje własnego skryptu"


# --- ścieżka nauki na stronie głównej ----------------------------------------


def test_sciezka_ma_osiem_krokow(strona_glowna):
    assert len(_punkty_sciezki(strona_glowna)) == len(SCIEZKA) == 8


def test_sciezka_jest_w_kolejnosci_wykladu(strona_glowna):
    adresy = []
    for punkt in _punkty_sciezki(strona_glowna):
        dopasowanie = WZORZEC_ODNOSNIKA.search(punkt)
        assert dopasowanie, f"krok bez odnośnika: {punkt.strip()!r}"
        adresy.append(dopasowanie["adres"])

    assert adresy == ADRESY_SCIEZKI, f"kolejność kroków: {adresy}"


@pytest.mark.parametrize(("adres", "nazwa"), SCIEZKA)
def test_krok_ma_nazwe_i_opis(strona_glowna, adres, nazwa):
    pasujace = [punkt for punkt in _punkty_sciezki(strona_glowna) if f'href="{adres}"' in punkt]
    assert len(pasujace) == 1, f"nie znalazłem dokładnie jednego kroku {adres}"

    punkt = pasujace[0]
    assert nazwa in punkt, f"krok {adres} nie pokazuje nazwy {nazwa!r}"

    opis = WZORZEC_ODNOSNIKA.sub("", punkt, count=1).strip(" —\t\n")
    assert len(opis.split()) >= 3, f"krok {adres} nie ma zdania opisu: {opis!r}"


def test_strona_glowna_nie_zostawia_nieuzupelnionych_szablonow(strona_glowna):
    assert "{{" not in strona_glowna
    assert "{%" not in strona_glowna


# --- stopka ------------------------------------------------------------------


def test_stopka_ma_odnosnik_do_wstepu(strona_glowna):
    stopka = _stopka(strona_glowna)
    assert 'href="/wstep"' in stopka, "stopka nie odsyła do /wstep"
    assert "Wstęp" in stopka


# --- bloki base.html ---------------------------------------------------------


@pytest.mark.parametrize("blok", BLOKI)
def test_base_definiuje_blok(blok):
    zrodlo = SZABLON_BAZY.read_text(encoding="utf-8")
    assert f"{{% block {blok} %}}" in zrodlo, f"base.html nie definiuje bloku {blok}"


@pytest.mark.parametrize(
    "znacznik",
    ["TYTUL-TESTOWY", "HEAD-TESTOWY", "TRESC-TESTOWA", "SKRYPT-TESTOWY"],
)
def test_kazdy_blok_mozna_nadpisac(aplikacja, znacznik):
    with aplikacja.test_request_context("/"):
        html = render_template("test_blokow.html")
    assert znacznik in html
