"""Testy stron informacyjnych: strona główna, „Jak czytać” i słowniczek."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import render_template
from jinja2 import ChoiceLoader, DictLoader

from app import create_app
from app.blueprints import home

STRONY = ["/", "/jak-czytac", "/slowniczek"]

MENU = ["/prawa", "/plac-zabaw", "/quiz", "/jak-czytac", "/slowniczek"]

#: Strony, na których notacja z wykładu jest pierwszą pokazywaną.
STRONY_Z_NOTACJA = ["/jak-czytac", "/slowniczek"]

#: Znaki z wykładu i ich popularne odpowiedniki (te drugie tylko jako uwaga).
ZNAKI_WYKLADOWE = ["∼", "≡"]
ZNAKI_POPULARNE = ["¬", "↔"]

#: Pary (kotwica w HTML, hasło widoczne dla czytelnika).
HASLA = [
    ("zdanie-logiczne", "zdanie logiczne"),
    ("zmienna-zdaniowa", "zmienna zdaniowa"),
    ("spojnik-logiczny", "spójnik logiczny"),
    ("negacja", "negacja"),
    ("koniunkcja", "koniunkcja"),
    ("alternatywa", "alternatywa"),
    ("implikacja", "implikacja"),
    ("rownowaznosc", "równoważność"),
    ("wartosciowanie", "wartościowanie"),
    ("tabela-prawdy", "tabela prawdy"),
    ("tautologia", "tautologia"),
    ("kontrtautologia", "kontrtautologia"),
    ("formula-spelnialna", "formuła spełnialna"),
    ("prawo-logiczne", "prawo logiczne"),
    ("przeksztalcenie-rownowaznosciowe", "przekształcenie równoważnościowe"),
    ("forma-normalna", "forma normalna"),
    ("kwantyfikator", "kwantyfikator"),
]

#: Szablon testowy nadpisujący każdy blok `base.html` własnym znacznikiem.
SZABLON_TESTU_BLOKOW = """{% extends "base.html" %}
{% block tytul %}TYTUL-TESTOWY{% endblock %}
{% block head %}<meta name="test-head" content="HEAD-TESTOWY" />{% endblock %}
{% block tresc %}<p id="akapit-testowy">TRESC-TESTOWA</p>{% endblock %}
{% block skrypty %}<script>window.SKRYPT_TESTOWY = "SKRYPT-TESTOWY";</script>{% endblock %}
"""

#: Wyrażenie wstawiane filtrem ``|safe``. Klasa ``[^}]`` zatrzymuje dopasowanie
#: w jednym wyrażeniu Jinja — z ``re.DOTALL`` wzorzec pochłaniał treść między
#: dwoma wyrażeniami i maskował zły ``|safe`` stojący obok poprawnego.
WZORZEC_SAFE = re.compile(r"\{\{(?P<wyrazenie>[^}]*?)\|\s*safe\s*\}\}")

WZORZEC_TABELI_SYMBOLI = re.compile(
    r'<table[^>]*class="[^"]*tablica-symboli[^"]*"[^>]*>(?P<tabela>.*?)</table>',
    re.DOTALL,
)

WZORZEC_WIERSZA = re.compile(r"<tr>")

WZORZEC_HASLA = re.compile(
    r'<dt id="(?P<kotwica>[^"]+)"[^>]*>.*?</dt>\s*<dd>(?P<tresc>.*?)</dd>',
    re.DOTALL,
)


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


def _uzycia_safe(tekst: str) -> list[str]:
    """Zwraca wyrażenia wstawiane do HTML przez filtr ``|safe``."""
    return [dopasowanie["wyrazenie"].strip() for dopasowanie in WZORZEC_SAFE.finditer(tekst)]


def _tabela_symboli(html: str) -> str:
    """Zwraca HTML tabeli symboli ze strony „Jak czytać”."""
    dopasowanie = WZORZEC_TABELI_SYMBOLI.search(html)
    assert dopasowanie, 'brak tabeli symboli (class="tablica-symboli")'
    return dopasowanie["tabela"]


def _wiersze_tabeli_symboli(html: str) -> list[str]:
    """Zwraca wiersze z sekcji ``tbody`` tabeli symboli."""
    cialo = re.search(r"<tbody>(?P<tresc>.*?)</tbody>", _tabela_symboli(html), re.DOTALL)
    assert cialo, "tabela symboli nie ma sekcji tbody"
    return WZORZEC_WIERSZA.findall(cialo["tresc"])


def _tresc_hasla(html: str, kotwica: str) -> str:
    """Zwraca treść hasła słowniczka o podanej kotwicy."""
    for dopasowanie in WZORZEC_HASLA.finditer(html):
        if dopasowanie["kotwica"] == kotwica:
            return dopasowanie["tresc"]
    raise AssertionError(f"brak hasła o kotwicy {kotwica}")


@pytest.mark.parametrize("adres", STRONY)
def test_strona_odpowiada_200_i_html_utf8(klient, adres):
    odpowiedz = klient.get(adres)
    assert odpowiedz.status_code == 200
    typ_tresci = odpowiedz.headers["Content-Type"]
    assert typ_tresci.startswith("text/html")
    assert "charset=utf-8" in typ_tresci.lower()


@pytest.mark.parametrize("adres", STRONY)
def test_strona_nie_zostawia_nieuzupelnionych_szablonow(klient, adres):
    tresc = klient.get(adres).get_data(as_text=True)
    assert "{{" not in tresc
    assert "{%" not in tresc


# --- base.html ---------------------------------------------------------------


@pytest.mark.parametrize(
    "znacznik",
    ["TYTUL-TESTOWY", "HEAD-TESTOWY", "TRESC-TESTOWA", "SKRYPT-TESTOWY"],
)
def test_kazdy_blok_mozna_nadpisac(aplikacja, znacznik):
    with aplikacja.test_request_context("/"):
        html = render_template("test_blokow.html")
    assert znacznik in html


def test_menu_uzywa_stalych_sciezek(klient):
    html = klient.get("/").get_data(as_text=True)
    for adres in MENU:
        assert f'href="{adres}"' in html, f"brak odnośnika {adres}"


def test_base_ma_jezyk_i_przejscie_do_tresci(klient):
    html = klient.get("/").get_data(as_text=True)
    assert 'lang="pl"' in html
    assert "Przejdź do treści" in html
    assert 'href="#tresc"' in html
    assert 'id="tresc"' in html


def test_menu_dziala_na_wasnym_ekranie(klient):
    html = klient.get("/").get_data(as_text=True)
    assert "navbar-toggler" in html
    assert 'data-bs-toggle="collapse"' in html
    assert 'data-bs-target="#menuGlowne"' in html


# --- strona główna -----------------------------------------------------------


def test_strona_glowna_liczy_prawa_z_rejestru(monkeypatch, klient):
    prawa = [
        SimpleNamespace(slug="wylaczony-srodek", nazwa="Wyłączony środek", kategoria="podstawowe"),
        SimpleNamespace(slug="de-morgan", nazwa="Prawo de Morgana", kategoria="de Morgan"),
    ]
    monkeypatch.setattr(home, "_all_laws", lambda: prawa)

    html = klient.get("/").get_data(as_text=True)

    assert "Praw w zestawie: 2" in html
    assert 'href="/prawa/wylaczony-srodek"' in html
    assert 'href="/prawa/de-morgan"' in html
    assert "Wyłączony środek" in html
    assert "de Morgan" in html


def _prawo(slug: str) -> SimpleNamespace:
    """Prawo zastępcze — testy adresu nie zależą od treści rejestru ``laws_data``."""
    return SimpleNamespace(slug=slug, nazwa="Prawo testowe", kategoria="podstawowe")


@pytest.mark.parametrize(
    ("slug", "adres"),
    [
        ("wylaczony-srodek", "/prawa/wylaczony-srodek"),
        ("de-morgan", "/prawa/de-morgan"),
    ],
)
def test_zwykly_slug_zostaje_bez_zmian(monkeypatch, klient, slug, adres):
    """Adres poprawnego sluga wygląda jak dotąd — kodowanie nic tu nie zmienia."""
    monkeypatch.setattr(home, "_all_laws", lambda: [_prawo(slug)])

    html = klient.get("/").get_data(as_text=True)

    assert f'href="{adres}"' in html, f"slug {slug!r} dał inny adres niż {adres!r}"


@pytest.mark.parametrize(
    ("slug", "zakodowany"),
    [
        ("dziwny/slug", "dziwny%2Fslug"),
        ("spacja w-slugu", "spacja%20w-slugu"),
        ("pytanie?znak", "pytanie%3Fznak"),
        ("krzyzyk#znak", "krzyzyk%23znak"),
    ],
)
def test_slug_ze_znakiem_specjalnym_jest_zakodowany(monkeypatch, klient, slug, zakodowany):
    """Znak spoza ``[a-z0-9-]`` nie rozjeżdża adresu prawa: trafia do niego zakodowany."""
    monkeypatch.setattr(home, "_all_laws", lambda: [_prawo(slug)])

    html = klient.get("/").get_data(as_text=True)

    assert f"/prawa/{slug}" not in html, f"adres prawa ma surowy slug {slug!r}"
    assert f'href="/prawa/{zakodowany}"' in html, f"brak zakodowanego adresu {zakodowany!r}"


def test_strona_glowna_bez_rejestru_nie_udaje_tresci(monkeypatch, klient):
    monkeypatch.setattr(home, "_all_laws", lambda: [])

    html = klient.get("/").get_data(as_text=True)

    assert "Praw w zestawie: 0" in html
    assert 'href="/prawa/' not in html


def test_rejestr_praw_zwraca_liste():
    assert isinstance(home._all_laws(), list)


# --- jak czytać --------------------------------------------------------------


def test_jak_czytac_objasnia_symbole_nawiasy_i_tablice(klient):
    html = klient.get("/jak-czytac").get_data(as_text=True)
    for symbol in ["∼", "∧", "∨", "→", "≡"]:
        assert symbol in html, f"brak symbolu {symbol}"
    assert "Nawiasy" in html
    assert "Jak czytać tablicę prawdy" in html


# --- notacja wykładowa -------------------------------------------------------


@pytest.mark.parametrize("adres", STRONY_Z_NOTACJA)
def test_strony_pokazuja_znaki_z_wykladu(klient, adres):
    html = klient.get(adres).get_data(as_text=True)
    for znak in ZNAKI_WYKLADOWE:
        assert znak in html, f"brak znaku wykładowego {znak} na {adres}"


@pytest.mark.parametrize("adres", STRONY_Z_NOTACJA)
def test_znaki_popularne_tylko_jako_uwaga(klient, adres):
    html = klient.get(adres).get_data(as_text=True)
    razem = sum(html.count(znak) for znak in ZNAKI_POPULARNE)
    assert razem <= 2, f"{adres}: {razem} wystąpień znaków ¬ i ↔, dozwolone najwyżej 2"


def test_tabela_symboli_ma_piec_wierszy_spojnikow(klient):
    html = klient.get("/jak-czytac").get_data(as_text=True)
    tabela = _tabela_symboli(html)

    wiersze = _wiersze_tabeli_symboli(html)
    assert len(wiersze) == 5, f"tabela symboli ma {len(wiersze)} wierszy, oczekiwano 5"

    for naglowek in [
        "Symbol z wykładu",
        "Jak czytamy",
        "Nazwa",
        "Na klawiaturze",
        "Przykład z życia",
    ]:
        assert naglowek in tabela, f"brak kolumny {naglowek}"

    for zapis in ["∼p", "p ∧ q", "p ∨ q", "p → q", "p ≡ q"]:
        assert zapis in tabela, f"brak wiersza {zapis} w tabeli symboli"


def test_jak_czytac_odsyla_inne_ksiazki_do_notacji_popularnej(klient):
    html = klient.get("/jak-czytac").get_data(as_text=True)
    assert "W innych książkach spotkasz" in html
    assert "¬p" in html
    assert "p ↔ q" in html


def test_slowniczek_tabela_prawdy_uzywa_wartosci_1_i_0(klient):
    html = klient.get("/slowniczek").get_data(as_text=True)
    tresc = _tresc_hasla(html, "tabela-prawdy")
    assert "1" in tresc, "hasło „tabela prawdy” nie pokazuje wartości 1"
    assert "0" in tresc, "hasło „tabela prawdy” nie pokazuje wartości 0"
    assert "PRAWDA" in tresc
    assert "FAŁSZ" in tresc


# --- słowniczek --------------------------------------------------------------


@pytest.mark.parametrize(("kotwica", "haslo"), HASLA)
def test_slowniczek_zawiera_haslo(klient, kotwica, haslo):
    html = klient.get("/slowniczek").get_data(as_text=True)
    assert f'id="{kotwica}"' in html, f"brak kotwicy {kotwica}"
    assert haslo in html, f"brak hasła {haslo}"


def test_slowniczek_odsyla_kwantyfikator_do_rachunku_predykatow(klient):
    html = klient.get("/slowniczek").get_data(as_text=True)
    assert "rachunku predykatów" in html


# --- bezpieczeństwo szablonów ------------------------------------------------


def test_wzorzec_safe_wykrywa_wstawienie_tekstu():
    assert _uzycia_safe("{{ tekst|safe }}") == ["tekst"]
    assert _uzycia_safe("{{ to_html(formula)|safe }}") == ["to_html(formula)"]


def _uzycia_safe_bez_to_html(tekst: str) -> list[str]:
    """Zwraca użycia ``|safe``, które nie pochodzą z ``formula.to_html``."""
    return [wyrazenie for wyrazenie in _uzycia_safe(tekst) if "to_html" not in wyrazenie]


def test_zly_szablon_z_safe_bez_to_html_jest_wykryty():
    assert _uzycia_safe_bez_to_html("{{ tytul|safe }}") == ["tytul"]
    # Strażnik musi też łapać zły `|safe` stojący tuż obok poprawnego wyrażenia.
    assert _uzycia_safe_bez_to_html("{{ formula_to_html(a) }}{{ tytul|safe }}") == ["tytul"]


def test_poprawne_uzycie_safe_przechodzi():
    # Nazwa funkcji jest taka jak w aplikacji (``app/blueprints/wstep.py``).
    assert _uzycia_safe_bez_to_html("{{ formula_to_html(a)|safe }}") == []


def test_dwa_wyrazenia_obok_siebie_nie_maskuja_zlego_safe():
    dobre = "{{ a }}\n{{ formula_to_html(b)|safe }}"
    assert _uzycia_safe_bez_to_html(dobre) == []

    zle = "{{ formula_to_html(a) }}\n{{ tytul|safe }}"
    assert _uzycia_safe_bez_to_html(zle) == ["tytul"]


def test_szablony_uzywaja_safe_tylko_na_wyniku_to_html():
    katalog = Path(__file__).resolve().parents[1] / "app" / "templates"
    szablony = sorted(katalog.rglob("*.html"))
    assert szablony, "nie znaleziono szablonów"
    for szablon in szablony:
        for wyrazenie in _uzycia_safe(szablon.read_text(encoding="utf-8")):
            assert "to_html" in wyrazenie, f"{szablon.name}: |safe na {wyrazenie!r}"
