"""Testy huba wykładu ``/wyklad/<numer>`` (karta PRZ-071).

Hub jest wejściem do wykładu: tytuł i opis, ponumerowana lista lekcji
z odnośnikami oraz karty sąsiednich wykładów. Wszystkie dane czytamy z rejestru
``app.lessons`` (karta PRZ-070), więc testy porównują HTML z tym samym rejestrem,
a nie z listą wpisaną ręcznie do szablonu.

Regiony strony rozpoznajemy po identyfikatorach i klasach z szablonu:
``#lekcje-wykladu`` (lista lekcji albo komunikat „Wykład w przygotowaniu”)
i ``nav[aria-label="Sąsiednie wykłady"]`` (karty „Poprzedni/Następny wykład”).
Dzięki temu odnośniki ze stopki i z menu nie mieszają się z treścią huba.
"""

from __future__ import annotations

import re
from html import escape

import pytest
from flask import render_template

from app import create_app
from app.lessons import Lecture, Lesson, lecture, lectures, lesson

#: Sekcja z lekcjami wykładu — wspólna dla obu stanów (gotowy i w przygotowaniu).
SEKCJA_LEKCJI = re.compile(
    r'<section[^>]*\bid="lekcje-wykladu"[^>]*>(?P<tresc>.*?)</section>', re.DOTALL
)

#: Karty sąsiednich wykładów pod treścią.
SEKCJA_SASIADOW = re.compile(
    r'<nav[^>]*aria-label="Sąsiednie wykłady"[^>]*>(?P<tresc>.*?)</nav>', re.DOTALL
)

#: Ponumerowana lista lekcji gotowego wykładu.
LISTA_LEKCJI = re.compile(r'<ol class="spis-tresci-lekcje">', re.DOTALL)

#: Adres każdego odnośnika w podanym fragmencie HTML.
ODNOSNIK = re.compile(r'<a\b[^>]*href="(?P<adres>[^"]+)"', re.IGNORECASE)

#: Adresy, które nie są wykładem: spoza zakresu numerów albo nie liczba.
ADRESY_BEZ_WYJATKU = ["/wyklad/9", "/wyklad/abc", "/wyklad/0", "/wyklad/-1", "/wyklad/9999"]


@pytest.fixture(scope="module")
def app():
    return create_app({"TESTING": True})


@pytest.fixture(scope="module")
def klient(app):
    return app.test_client()


def _html(klient, adres: str) -> str:
    """HTML strony — jedno pobranie na wywołanie, z kontrolą kodu odpowiedzi."""
    odpowiedz = klient.get(adres)
    assert odpowiedz.status_code == 200, f"{adres} nie odpowiada kodem 200"
    return odpowiedz.get_data(as_text=True)


def _sekcja_lekcji(html: str) -> str:
    """Fragment HTML z sekcją lekcji wykładu."""
    dopasowanie = SEKCJA_LEKCJI.search(html)
    assert dopasowanie, "strona nie ma sekcji o identyfikatorze „lekcje-wykladu”"
    return dopasowanie["tresc"]


def _sekcja_sasiadow(html: str) -> str:
    """Fragment HTML z kartami sąsiednich wykładów."""
    dopasowanie = SEKCJA_SASIADOW.search(html)
    assert dopasowanie, "strona nie ma sekcji „Sąsiednie wykłady”"
    return dopasowanie["tresc"]


def _adresy(fragment: str) -> list[str]:
    """Adresy odnośników w kolejności występowania."""
    return ODNOSNIK.findall(fragment)


# ---------------------------------------------------------------------------
# Podstawy: kod odpowiedzi i nagłówek
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("numer", [1, 2])
def test_wyklad_odpowiada_200(klient, numer):
    assert klient.get(f"/wyklad/{numer}").status_code == 200


@pytest.mark.parametrize("numer", [1, 2])
def test_wyklad_ma_dokladnie_jeden_h1(klient, numer):
    html = _html(klient, f"/wyklad/{numer}")

    assert len(re.findall(r"<h1\b", html)) == 1, f"/wyklad/{numer}: nie dokładnie jeden <h1>"


@pytest.mark.parametrize("numer", [1, 2, 3])
def test_naglowek_i_opis_pochodza_z_rejestru(klient, numer):
    wyklad = lecture(numer)
    html = _html(klient, f"/wyklad/{numer}")

    assert f"Wykład {numer}: {escape(wyklad.tytul)}" in html
    assert escape(wyklad.opis) in html


# ---------------------------------------------------------------------------
# Wykład gotowy: lista lekcji z odnośnikami
# ---------------------------------------------------------------------------


def test_wyklad_1_wymienia_osiem_lekcji(klient):
    wyklad = lecture(1)
    html = _html(klient, "/wyklad/1")
    sekcja = _sekcja_lekcji(html)

    assert wyklad.gotowy
    assert len(wyklad.lekcje) == 8
    for lekcja in wyklad.lekcje:
        assert escape(lekcja.tytul) in sekcja, f"brak tytułu lekcji {lekcja.slug}"
        assert escape(lekcja.opis) in sekcja, f"brak opisu lekcji {lekcja.slug}"


def test_lista_lekcji_ma_odnosnik_do_kazdej_lekcji_w_kolejkosci(klient):
    wyklad = lecture(1)
    sekcja = _sekcja_lekcji(_html(klient, "/wyklad/1"))
    poczatek = LISTA_LEKCJI.search(sekcja)

    assert poczatek, "gotowy wykład nie ma ponumerowanej listy lekcji"

    lista = sekcja[poczatek.start() :]
    lista = lista[: lista.index("</ol>") + len("</ol>")]

    assert _adresy(lista) == [lekcja.sciezka for lekcja in wyklad.lekcje]

    # Numer lekcji wykładu widać obok jej tytułu.
    for numer, lekcja in enumerate(wyklad.lekcje, start=1):
        assert escape(lekcja.tytul) in lista
        assert f"1.{numer}" in lista


@pytest.mark.parametrize(
    "adres", [lekcja.sciezka for lekcja in lecture(1).lekcje], ids=lambda adres: adres
)
def test_kazdy_odnosnik_z_listy_odpowiada_200(klient, adres):
    """Test przechodzi po wszystkich odnośnikach z listy lekcji wykładu 1."""
    assert adres in {lekcja.sciezka for lekcja in lecture(1).lekcje}
    assert klient.get(adres).status_code == 200, f"{adres} nie odpowiada kodem 200"


# ---------------------------------------------------------------------------
# Wykład w przygotowaniu: komunikat i plan tematów bez odnośników
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("numer", [wyklad.numer for wyklad in lectures() if not wyklad.gotowy])
def test_wyklad_w_przygotowaniu_ma_komunikat(klient, numer):
    sekcja = _sekcja_lekcji(_html(klient, f"/wyklad/{numer}"))

    assert "Wykład w przygotowaniu" in sekcja
    assert not LISTA_LEKCJI.search(sekcja), "niegotowy wykład nie może mieć listy lekcji"


def test_plan_tematow_niegotowego_wykladu_jest_bez_odnosnikow(app):
    """Plan tematów pokazuje tytuły i opisy, ale nie prowadzi do nieistniejących lekcji."""
    planowany = Lecture(
        numer=7,
        tytul="Logika modalna",
        opis="Możliwości i konieczność w zapisie formalnym. Materiał w przygotowaniu.",
        lekcje=(
            Lesson(
                slug="mozliwosci",
                sciezka="/mozliwosci",
                tytul="Możliwości i konieczność",
                opis="Operator możliwości i konieczności na przykładach.",
                wyklad=7,
                ikona="◇",
            ),
        ),
        gotowy=False,
    )

    with app.test_request_context("/wyklad/7"):
        html = render_template("wyklad.html", wyklad=planowany, poprzedni=None, nastepny=None)

    sekcja = _sekcja_lekcji(html)

    assert "Wykład w przygotowaniu" in sekcja
    assert escape(planowany.lekcje[0].tytul) in sekcja
    assert escape(planowany.lekcje[0].opis) in sekcja
    assert "<a" not in sekcja, "plan tematów nie może zawierać odnośników"


# ---------------------------------------------------------------------------
# Numer spoza zakresu: 404 z odnośnikiem do spisu treści
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("adres", ADRESY_BEZ_WYJATKU)
def test_numer_spoza_zakresu_daje_404_po_polsku(klient, adres):
    odpowiedz = klient.get(adres)
    html = odpowiedz.get_data(as_text=True)

    assert odpowiedz.status_code == 404
    assert "Nie ma takiego wykładu" in html
    assert '/spis-tresci"' in html
    assert len(re.findall(r"<h1\b", html)) == 1


def test_numer_ze_znacznikami_nie_trafia_do_html(klient):
    odpowiedz = klient.get("/wyklad/%3Cscript%3Ealert(1)")
    html = odpowiedz.get_data(as_text=True)

    assert odpowiedz.status_code == 404
    assert "<script>alert" not in html


# ---------------------------------------------------------------------------
# Sąsiednie wykłady
# ---------------------------------------------------------------------------


def _numery_sasiadow(numer: int) -> tuple[int | None, int | None]:
    """(poprzedni, następny) numer wykładu wg rejestru — ``None`` na końcach."""
    numery = [wyklad.numer for wyklad in lectures()]
    indeks = numery.index(numer)
    poprzedni = numery[indeks - 1] if indeks > 0 else None
    nastepny = numery[indeks + 1] if indeks + 1 < len(numery) else None
    return poprzedni, nastepny


@pytest.mark.parametrize("wyklad", lectures(), ids=lambda w: f"wyklad-{w.numer}")
def test_strona_pokazuje_dokladnie_sasiadow_z_rejestru(klient, wyklad):
    poprzedni, nastepny = _numery_sasiadow(wyklad.numer)
    sekcja = _sekcja_sasiadow(_html(klient, f"/wyklad/{wyklad.numer}"))

    oczekiwane = [f"/wyklad/{numer}" for numer in (poprzedni, nastepny) if numer is not None]

    assert _adresy(sekcja) == oczekiwane


def test_wyklad_1_ma_odnosnik_do_nastepnego_wykladu(klient):
    sekcja = _sekcja_sasiadow(_html(klient, "/wyklad/1"))

    assert "/wyklad/2" in _adresy(sekcja)
    assert "Następny wykład" in sekcja
    assert "Poprzedni wykład" not in sekcja


def test_ostatni_wyklad_ma_odnosnik_do_poprzedniego(klient):
    ostatni = lectures()[-1]
    sekcja = _sekcja_sasiadow(_html(klient, f"/wyklad/{ostatni.numer}"))

    assert "Poprzedni wykład" in sekcja
    assert "Następny wykład" not in sekcja


def test_hub_wykladu_nie_ma_wlasnej_lekcji_w_rejestrze(klient):
    """Hub nie jest lekcją, więc nie dostaje bocznego spisu ani okruszków z `NAV`."""
    html = _html(klient, "/wyklad/1")

    assert lesson("/wyklad/1") is None
    assert 'class="spis-lekcji' not in html
