"""Testy rejestru wykładów i lekcji (``app/lessons.py``).

Rejestr (karta PRZ-070) jest jednym źródłem prawdy dla nawigacji: kolejności
lekcji, sąsiadów „poprzednia/następna” i pozycji narzędziowych. Testy sprawdzają
same dane rejestru, to, że każda ścieżka z rejestru ma istniejącą trasę, oraz to,
że każdy szablon widzi słownik ``NAV``. Karta PRZ-093 dołożyła do rejestru
wykład 2 „Konsekwencja logiczna i dowody” z czterema lekcjami.
"""

from __future__ import annotations

import re

import pytest
from flask import render_template
from jinja2 import ChoiceLoader, DictLoader

from app import create_app
from app.lessons import lecture, lectures, lesson, lessons, previous, tool_links
from app.lessons import next as nastepna

#: Osiem lekcji wykładu 1 w kolejności z sekcji ``Context`` karty.
SCIEZKI_WYKLADU_1 = [
    "/wstep",
    "/formuly",
    "/tautologie",
    "/przeksztalcanie",
    "/kpn",
    "/prawa",
    "/plac-zabaw",
    "/quiz",
]

#: Slug tych samych lekcji — bez ukośnika i bez polskich znaków.
SLUGI_WYKLADU_1 = [
    "wstep",
    "formuly",
    "tautologie",
    "przeksztalcanie",
    "kpn",
    "prawa",
    "plac-zabaw",
    "quiz",
]

#: Cztery lekcje wykładu 2 w kolejności z sekcji ``Context`` karty.
SCIEZKI_WYKLADU_2 = ["/konsekwencja", "/reguly", "/dowody", "/rezolucja"]

#: Slug tych samych lekcji wykładu 2.
SLUGI_WYKLADU_2 = ["konsekwencja", "reguly", "dowody", "rezolucja"]

#: Wszystkie lekcje rejestru: najpierw wykład 1, potem wykład 2.
SCIEZKI_LEKCJI = SCIEZKI_WYKLADU_1 + SCIEZKI_WYKLADU_2

#: Tytuł wykładu 2 po dołożeniu lekcji (karta PRZ-093).
TYTUL_WYKLADU_2 = "Konsekwencja logiczna i dowody"

#: Pasek menu i boczny spis lekcji — regiony nawigacji z ``base.html``.
WZORZEC_MENU = re.compile(r'<nav\b[^>]*id="nawigacja-glowna".*?</nav>', re.DOTALL)
WZORZEC_SEKCJI_LEKCJI = re.compile(
    r'<section[^>]*\bid="lekcje-wykladu"[^>]*>(?P<tresc>.*?)</section>', re.DOTALL
)

#: Ścieżki narzędziowe w kolejności z karty.
SCIEZKI_NARZEDZI = ["/prawa", "/plac-zabaw", "/quiz", "/slowniczek", "/jak-czytac"]

#: Klucze, które ``NAV`` musi mieć w każdym szablonie.
KLUCZE_NAV = {"lectures", "lesson", "previous", "next", "tools"}

#: Szablon wypisujący to, co widzi zwykły szablon: klucze ``NAV`` i sąsiadów lekcji.
SZABLON_NAV = (
    "KLUCZE:{{ NAV|list|sort|join(',') }}"
    "|LEKCJA:{{ NAV.lesson.sciezka if NAV.lesson else 'brak' }}"
    "|POPRZEDNIA:{{ NAV.previous.sciezka if NAV.previous else 'brak' }}"
    "|NASTEPNA:{{ NAV.next.sciezka if NAV.next else 'brak' }}"
    "|WYKLADY:{{ NAV.lectures|length }}"
    "|NARZEDZIA:{{ NAV.tools|length }}"
)


@pytest.fixture(scope="module")
def aplikacja():
    """Aplikacja z dodatkowym szablonem, który pokazuje zawartość ``NAV``."""
    app = create_app({"TESTING": True})
    app.jinja_env.loader = ChoiceLoader(
        [DictLoader({"nav_test.html": SZABLON_NAV}), app.jinja_env.loader]
    )
    return app


@pytest.fixture(scope="module")
def klient(aplikacja):
    """Klient testowy do stron, które sprawdzają nawigację."""
    return aplikacja.test_client()


def _html(klient, adres: str) -> str:
    """HTML strony; kod inny niż 200 to błąd testu."""
    odpowiedz = klient.get(adres)
    assert odpowiedz.status_code == 200, f"{adres} → kod {odpowiedz.status_code}"
    return odpowiedz.get_data(as_text=True)


def _menu(html: str) -> str:
    """HTML paska menu (``#nawigacja-glowna``) z odnośnikami wykładów."""
    dopasowanie = WZORZEC_MENU.search(html)
    assert dopasowanie, "strona nie ma paska menu (#nawigacja-glowna)"
    return dopasowanie.group()


def _region(html: str, klasa: str) -> str:
    """HTML elementu, którego atrybut ``class`` zawiera podaną klasę."""
    wzorzec = re.compile(
        rf'<(?P<znacznik>nav|aside|div)\b[^>]*class="[^"]*\b{re.escape(klasa)}\b[^"]*"[^>]*>'
        r"(?P<tresc>.*?)</(?P=znacznik)>",
        re.DOTALL,
    )
    dopasowanie = wzorzec.search(html)
    assert dopasowanie, f"brak elementu .{klasa} na stronie"
    return dopasowanie.group()


def _nav(aplikacja, sciezka: str) -> dict[str, str]:
    """Renderuje ``SZABLON_NAV`` pod podaną ścieżką i zwraca pola jako słownik."""
    with aplikacja.test_request_context(sciezka):
        html = render_template("nav_test.html")
    return dict(czesc.split(":", 1) for czesc in html.split("|"))


# --- wykłady ------------------------------------------------------------------


def test_lectures_zwraca_trzy_wyklady():
    assert [wyklad.numer for wyklad in lectures()] == [1, 2, 3]


def test_tylko_wyklad_3_jest_zapowiedzia():
    zapowiedzi = [wyklad for wyklad in lectures() if not wyklad.gotowy]
    assert [wyklad.numer for wyklad in zapowiedzi] == [3]
    for wyklad in zapowiedzi:
        assert wyklad.lekcje == (), f"wykład {wyklad.numer} ma już lekcje"
        assert wyklad.tytul and wyklad.opis, f"wykład {wyklad.numer} bez tytułu lub opisu"


def test_pierwszy_wyklad_jest_gotowy():
    wyklad = lectures()[0]
    assert wyklad.gotowy is True
    assert len(wyklad.lekcje) == 8


def test_wyklad_2_jest_gotowy_i_ma_cztery_lekcje_w_kolejnosci():
    wyklad = lecture(2)

    assert wyklad.gotowy is True
    assert wyklad.tytul == TYTUL_WYKLADU_2
    assert [lekcja.slug for lekcja in wyklad.lekcje] == SLUGI_WYKLADU_2
    assert [lekcja.sciezka for lekcja in wyklad.lekcje] == SCIEZKI_WYKLADU_2
    assert {lekcja.wyklad for lekcja in wyklad.lekcje} == {2}


@pytest.mark.parametrize(
    ("numer", "tytul"),
    [
        (1, "Klasyczny rachunek zdań"),
        (2, TYTUL_WYKLADU_2),
        (3, "Elementy teorii zbiorów i relacji"),
    ],
)
def test_lecture_po_numerze(numer, tytul):
    assert lecture(numer) is not None
    assert lecture(numer).tytul == tytul


def test_lecture_nieznany_numer_daje_none():
    assert lecture(99) is None


# --- lekcje -------------------------------------------------------------------


def test_lessons_zwraca_lekcje_wykladu_1_a_potem_wykladu_2():
    assert [lekcja.sciezka for lekcja in lessons()] == SCIEZKI_LEKCJI
    assert [lekcja.slug for lekcja in lessons()] == SLUGI_WYKLADU_1 + SLUGI_WYKLADU_2
    assert [lekcja.wyklad for lekcja in lessons()] == [1] * 8 + [2] * 4


def test_lessons_to_plaska_lista_lekcji_wykladow():
    z_wykladow = [lekcja for wyklad in lectures() for lekcja in wyklad.lekcje]
    assert lessons() == z_wykladow


@pytest.mark.parametrize("lekcja", lessons(), ids=lambda lekcja: lekcja.slug)
def test_lekcja_ma_tytul_opis_i_ikone(lekcja):
    assert lekcja.tytul
    assert lekcja.ikona
    assert len(lekcja.opis.split()) <= 20, f"opis lekcji {lekcja.slug} jest za długi"


@pytest.mark.parametrize(
    ("sciezka", "slug", "wyklad"),
    [("/formuly", "formuly", 1), ("/reguly", "reguly", 2)],
)
def test_lesson_po_sciezce(sciezka, slug, wyklad):
    lekcja = lesson(sciezka)
    assert lekcja is not None
    assert lekcja.slug == slug
    assert lekcja.sciezka == sciezka
    assert lekcja.wyklad == wyklad


def test_lesson_nieznana_sciezka_daje_none():
    assert lesson("/nie-ma") is None


# --- sąsiedzi w nawigacji ------------------------------------------------------


@pytest.mark.parametrize(
    ("sciezka", "poprzednia"),
    [
        ("/formuly", "/wstep"),
        ("/wstep", None),
        ("/quiz", "/plac-zabaw"),
        ("/konsekwencja", "/quiz"),
        ("/reguly", "/konsekwencja"),
        ("/nie-ma", None),
    ],
)
def test_previous(sciezka, poprzednia):
    wynik = previous(sciezka)
    assert (wynik.sciezka if wynik else None) == poprzednia


@pytest.mark.parametrize(
    ("sciezka", "nastepna_lekcja"),
    [
        ("/formuly", "/tautologie"),
        ("/quiz", "/konsekwencja"),
        ("/wstep", "/formuly"),
        ("/rezolucja", None),
        ("/nie-ma", None),
    ],
)
def test_next(sciezka, nastepna_lekcja):
    wynik = nastepna(sciezka)
    assert (wynik.sciezka if wynik else None) == nastepna_lekcja


def test_koniec_wykladu_1_prowadzi_do_poczatku_wykladu_2():
    assert nastepna("/quiz").sciezka == "/konsekwencja"
    assert previous("/konsekwencja").sciezka == "/quiz"


def test_sasiedzi_pokrywaja_cala_sciezke():
    """Każda lekcja poza pierwszą i ostatnią ma oba odnośniki."""
    for indeks, lekcja in enumerate(lessons()):
        poprzednia = previous(lekcja.sciezka)
        nastepna_lekcja = nastepna(lekcja.sciezka)
        oczekiwana_poprzednia = None if indeks == 0 else SCIEZKI_LEKCJI[indeks - 1]
        oczekiwana_nastepna = (
            None if indeks == len(SCIEZKI_LEKCJI) - 1 else SCIEZKI_LEKCJI[indeks + 1]
        )
        assert (poprzednia.sciezka if poprzednia else None) == oczekiwana_poprzednia
        assert (nastepna_lekcja.sciezka if nastepna_lekcja else None) == oczekiwana_nastepna


# --- narzędzia -----------------------------------------------------------------


def test_tool_links_w_kolejnosci_z_karty():
    assert [pozycja["sciezka"] for pozycja in tool_links()] == SCIEZKI_NARZEDZI


def test_tool_links_maja_tytul_i_ikone():
    for pozycja in tool_links():
        assert set(pozycja) == {"sciezka", "tytul", "ikona"}
        assert pozycja["tytul"] and pozycja["ikona"]


def test_tool_links_nie_zmieniaja_wspoldzielonej_listy():
    """Modyfikacja zwróconej listy nie psuje następnego wywołania."""
    pozycje = tool_links()
    pozycje[0]["tytul"] = "zmienione"
    assert tool_links()[0]["tytul"] != "zmienione"


# --- trasy ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "sciezka",
    [lekcja.sciezka for lekcja in lessons()] + SCIEZKI_NARZEDZI,
)
def test_kazda_sciezka_z_rejestru_ma_trase(aplikacja, sciezka):
    trasy = {reguła.rule for reguła in aplikacja.url_map.iter_rules()}
    assert sciezka in trasy, f"brak trasy dla {sciezka}"


# --- NAV w szablonach ----------------------------------------------------------


@pytest.mark.parametrize("sciezka", SCIEZKI_LEKCJI)
def test_szablon_widzi_nav_z_lekcja(aplikacja, sciezka):
    nav = _nav(aplikacja, sciezka)
    assert set(nav["KLUCZE"].split(",")) == KLUCZE_NAV
    assert nav["LEKCJA"] == sciezka
    assert nav["WYKLADY"] == "3"
    assert nav["NARZEDZIA"] == str(len(SCIEZKI_NARZEDZI))


@pytest.mark.parametrize(
    ("sciezka", "poprzednia", "nastepna_lekcja"),
    [
        ("/formuly", "/wstep", "/tautologie"),
        ("/wstep", "brak", "/formuly"),
        ("/quiz", "/plac-zabaw", "/konsekwencja"),
        ("/konsekwencja", "/quiz", "/reguly"),
        ("/rezolucja", "/dowody", "brak"),
    ],
)
def test_nav_ma_sasiadow_lekcji(aplikacja, sciezka, poprzednia, nastepna_lekcja):
    nav = _nav(aplikacja, sciezka)
    assert nav["POPRZEDNIA"] == poprzednia
    assert nav["NASTEPNA"] == nastepna_lekcja


def test_nav_bez_lekcji_dla_strony_spoza_rejestru(aplikacja):
    """Strona spoza kursu (np. słowniczek) widzi ``NAV``, ale bez lekcji."""
    nav = _nav(aplikacja, "/slowniczek")
    assert set(nav["KLUCZE"].split(",")) == KLUCZE_NAV
    assert nav["LEKCJA"] == "brak"
    assert nav["POPRZEDNIA"] == "brak"
    assert nav["NASTEPNA"] == "brak"


# --- wykład 2 w nawigacji -------------------------------------------------------


def test_hub_wykladu_2_wymienia_cztery_lekcje(klient):
    html = _html(klient, "/wyklad/2")
    dopasowanie = WZORZEC_SEKCJI_LEKCJI.search(html)
    assert dopasowanie, "/wyklad/2 nie ma sekcji z lekcjami (id „lekcje-wykladu”)"

    sekcja = dopasowanie["tresc"]
    assert TYTUL_WYKLADU_2 in html
    for lekcja in lecture(2).lekcje:
        assert f'href="{lekcja.sciezka}"' in sekcja, f"brak odnośnika do {lekcja.sciezka}"
        assert lekcja.tytul in sekcja, f"brak tytułu lekcji {lekcja.slug}"


def test_menu_pokazuje_lekcje_wykladu_2(klient):
    """Menu na lekcji wykładu 2 prowadzi do pozostałych lekcji tego wykładu."""
    menu = _menu(_html(klient, "/konsekwencja"))

    assert 'href="/reguly"' in menu, "menu nie pokazuje lekcji /reguly"
    for sciezka in SCIEZKI_WYKLADU_2:
        assert f'href="{sciezka}"' in menu, f"menu bez odnośnika {sciezka}"
    for sciezka in SCIEZKI_WYKLADU_1:
        assert f'href="{sciezka}"' in menu, f"menu zgubiło lekcję wykładu 1: {sciezka}"


def test_boczny_spis_lekcji_pokazuje_cztery_lekcje_wykladu_2(klient):
    spis = _region(_html(klient, "/konsekwencja"), "spis-lekcji")

    assert "Lekcje wykładu 2" in spis
    for sciezka in SCIEZKI_WYKLADU_2:
        assert f'href="{sciezka}"' in spis, f"spis lekcji bez {sciezka}"
    assert 'aria-current="page"' in spis, "spis nie oznacza bieżącej lekcji"
