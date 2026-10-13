"""Testy nawigacji: menu wykładami, okruszki, boczny spis lekcji, sąsiedzi lekcji.

Karta PRZ-023 wystawiła pierwszy pasek menu i ścieżkę nauki na stronie głównej.
Karta PRZ-069 przebudowała nawigację: menu dzieli się na „Wykłady” i „Narzędzia”,
pod menu są okruszki, po lewej boczny spis lekcji, a nad i pod treścią odnośniki
„poprzednia / następna lekcja”. Wszystko powstaje w ``base.html`` z rejestru ``NAV``
(``app/lessons.py``) — szablony lekcji nie wiedzą o tych elementach.

Odnośniki w menu to zwykłe ``href`` (decyzja D5), więc testy czytają HTML, a nie
tablicę routingu. Regiony nawigacji rozpoznajemy po klasach z ``base.html``:
``#nawigacja-glowna`` (menu), ``.okruszki``, ``.spis-lekcji``,
``.nawigacja-lekcji-gora`` i ``.nawigacja-lekcji-dol``.

Uwaga o zakresie: szablony lekcji mają własne odnośniki na dole treści (np. ``/wstep``
odsyła do „strona główna” jako poprzedniej lekcji). Karta PRZ-069 zabrania ich zmiany,
więc kryteria „brak poprzedniej na ``/wstep``” i „brak następnej na ostatniej lekcji”
sprawdzamy w regionach nowej nawigacji z ``base.html``.

Karta PRZ-093 dołożyła do rejestru wykład 2 (cztery lekcje). Od tego czasu testy czytają
wykłady i lekcje z ``app/lessons.py``, a nie z list wpisanych ręcznie: okruszki pokazują
wykład bieżącej lekcji, boczny spis lekcji — lekcje tego wykładu, a „wkrótce” widzą tylko
wykłady z ``gotowy=False``.
"""

from __future__ import annotations

import re
from html import unescape
from pathlib import Path

import pytest
from flask import render_template
from jinja2 import ChoiceLoader, DictLoader

from app import create_app
from app.lessons import lecture, lectures, lesson, lessons, previous
from app.lessons import next as nastepna

KATALOG = Path(__file__).resolve().parents[1]
SZABLON_BAZY = KATALOG / "app" / "templates" / "base.html"
KATALOG_SZABLONOW = KATALOG / "app" / "templates"
CSS_NAWIGACJI = KATALOG / "app" / "static" / "css" / "nawigacja.css"

#: Osiem kroków ścieżki nauki w kolejności wykładu: (adres, nazwa kroku na stronie głównej).
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

#: Wszystkie wykłady rejestru (gotowe i zapowiedzi) — kolejność numerów.
NAV_LECTURES = lectures()

#: Wszystkie ścieżki z rejestru lekcji (kolejność z `app/lessons.py`).
ADRESY_LEKCJI = [lekcja.sciezka for lekcja in lessons()]

#: Pozycje menu sprzed karty PRZ-023 — nie mogą zniknąć.
MENU_WCZEŚNIEJSZE = ["/prawa", "/plac-zabaw", "/quiz", "/jak-czytac", "/slowniczek"]

#: Odnośniki lekcji w rozwijanej pozycji **Wykłady** — wszystkie lekcje rejestru.
MENU_LEKCJE = ADRESY_LEKCJI

#: Narzędzia z rejestru — rozwijana pozycja **Narzędzia**.
NARZEDZIA = ["/prawa", "/plac-zabaw", "/quiz", "/slowniczek", "/jak-czytac"]

#: Tytuły wykładów-zapowiedzi (``gotowy=False``) — nieklikalne pozycje menu.
ZAPOWIEDZI = [wyklad.tytul for wyklad in NAV_LECTURES if not wyklad.gotowy]

#: Bloki, które ``base.html`` musi nadal wystawiać.
BLOKI = ["tytul", "head", "tresc", "skrypty"]

#: Klasy, które muszą mieć regułę w ``nawigacja.css`` — inaczej plik byłby martwy.
KLASY_CSS = [
    "okruszki",
    "nawigacja-lekcji-gora",
    "nawigacja-lekcji-dol",
    "nawigacja-lekcji-odnosnik",
    "spis-lekcji",
    "karta-lekcji",
    "spis-tresci-lekcje",
]

#: Szablony, które wolno zmieniać karcie PRZ-069. Reszta nie może znać nawigacji.
SZABLONY_NAWIGACJI = {"base.html", "spis_tresci.html"}

#: Znaczniki, które w szablonie lekcji znaczyłyby budowanie nawigacji obok ``base.html``.
ZAKAZANE_W_LEKCJACH = ["NAV", "aria-current", "okruszki", "spis-lekcji", "karta-lekcji"]

WZORZEC_NAV = re.compile(r'<nav\b[^>]*id="nawigacja-glowna".*?</nav>', re.DOTALL)
WZORZEC_MAIN = re.compile(r"<main\b.*?</main>", re.DOTALL)
WZORZEC_WYKLADU = re.compile(
    r'<section[^>]*id="wyklad-(?P<numer>\d+)"[^>]*>(?P<tresc>.*?)</section>', re.DOTALL
)
WZORZEC_ODNOSNIKA = re.compile(r'<a[^>]+href="(?P<adres>[^"]+)"')
WZORZEC_ZNACZNIKA = re.compile(r"<[^>]+>")
WZORZEC_STOPKI = re.compile(r"<footer\b.*?</footer>", re.DOTALL)
WZORZEC_SCIEZKI = re.compile(r'<ol class="lista-sciezki"[^>]*>(?P<tresc>.*?)</ol>', re.DOTALL)
WZORZEC_PUNKTU = re.compile(r"<li>(?P<tresc>.*?)</li>", re.DOTALL)

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


def _html(klient, adres: str) -> str:
    """Zwraca HTML strony; kod inny niż 200 to błąd testu."""
    odpowiedz = klient.get(adres)
    assert odpowiedz.status_code == 200, f"{adres} → kod {odpowiedz.status_code}"
    return odpowiedz.get_data(as_text=True)


def _tekst(fragment: str) -> str:
    """Widoczny tekst fragmentu HTML — bez znaczników, ze odmienionymi encjami."""
    return unescape(WZORZEC_ZNACZNIKA.sub(" ", fragment)).strip()


def _menu(html: str) -> str:
    """Zwraca HTML paska menu (bez okruszków, spisu lekcji i stopki)."""
    dopasowanie = WZORZEC_NAV.search(html)
    assert dopasowanie, "strona nie ma paska menu (#nawigacja-glowna)"
    return dopasowanie.group()


def _tresc(html: str) -> str:
    """Zwraca HTML elementu ``<main>`` — treść strony bez menu i stopki."""
    dopasowanie = WZORZEC_MAIN.search(html)
    assert dopasowanie, "strona nie ma elementu <main>"
    return dopasowanie.group()


def _region(html: str, klasa: str) -> str:
    """Zwraca HTML elementu, którego atrybut ``class`` zawiera podaną klasę."""
    wzorzec = re.compile(
        rf'<(?P<znacznik>nav|aside|div)\b[^>]*class="[^"]*\b{re.escape(klasa)}\b[^"]*"[^>]*>'
        r"(?P<tresc>.*?)</(?P=znacznik)>",
        re.DOTALL,
    )
    dopasowanie = wzorzec.search(html)
    assert dopasowanie, f"brak elementu .{klasa} na stronie"
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


def _odnosniki(fragment: str) -> list[str]:
    """Zwraca adresy wszystkich odnośników w podanym fragmencie HTML."""
    return WZORZEC_ODNOSNIKA.findall(fragment)


# --- strony odpowiadają i mają poprawny szkielet ------------------------------


@pytest.mark.parametrize("adres", ADRESY_LEKCJI + ["/spis-tresci"])
def test_kazda_strona_odpowiada_200(klient, adres):
    odpowiedz = klient.get(adres)
    assert odpowiedz.status_code == 200, f"{adres} → kod {odpowiedz.status_code}"
    assert odpowiedz.headers["Content-Type"].startswith("text/html")


@pytest.mark.parametrize("adres", ADRESY_LEKCJI + ["/spis-tresci"])
def test_strona_ma_polski_jezyk_i_dokladnie_jeden_h1(klient, adres):
    html = _html(klient, adres)
    assert 'lang="pl"' in html
    assert len(re.findall(r"<h1\b", html)) == 1, f"{adres}: ma nie dokładnie jeden <h1>"


def test_spis_tresci_jest_w_rejestrze_menu(strona_glowna):
    assert 'href="/spis-tresci"' in _menu(strona_glowna)
    assert "Spis treści" in _menu(strona_glowna)


# --- menu z rejestru wykładów --------------------------------------------------


@pytest.mark.parametrize("adres", MENU_LEKCJE + MENU_WCZEŚNIEJSZE)
def test_menu_zawiera_odnosnik(strona_glowna, adres):
    assert f'href="{adres}"' in _menu(strona_glowna), f"brak odnośnika {adres} w menu"


def test_base_buduje_nawigacje_z_rejestru():
    """Karta PRZ-069: adresy w nawigacji pochodzą z ``NAV``, nie są wpisane na sztywno.

    Stopka i skróty w bocznym spisie lekcji zostają jak w kartach PRZ-023/PRZ-069 —
    tu sprawdzamy menu, okruszki i sąsiadów lekcji.
    """
    zrodlo = SZABLON_BAZY.read_text(encoding="utf-8")
    menu = WZORZEC_NAV.search(zrodlo)
    assert menu, "base.html nie ma paska menu"
    menu = menu.group()

    for adres in ADRESY_LEKCJI:
        assert f'href="{adres}"' not in menu, f"{adres} wpisany na sztywno w menu"

    for wyrazenie in (
        'href="{{ lekcja.sciezka }}"',
        'href="{{ narzedzie.sciezka }}"',
        'href="{{ NAV.previous.sciezka }}"',
        'href="{{ NAV.next.sciezka }}"',
    ):
        assert wyrazenie in zrodlo, f"base.html nie buduje odnośnika: {wyrazenie}"


def test_menu_zawiera_wszystkie_lekcje_poza_strona_glowna(strona_glowna):
    menu = _menu(strona_glowna)
    brakujace = [adres for adres in ADRESY_LEKCJI if f'href="{adres}"' not in menu]
    assert not brakujace, f"lekcje poza menu: {brakujace}"


@pytest.mark.parametrize("adres", ADRESY_LEKCJI)
def test_menu_pokazuje_biezaca_lekcje_bez_klikania(klient, adres):
    """Każda lekcja ma w menu własny odnośnik — na bieżącej stronie oznaczony."""
    menu = _menu(_html(klient, adres))
    assert f'href="{adres}"' in menu, f"{adres}: brak odnośnika do bieżącej lekcji"


@pytest.mark.parametrize("adres", ADRESY_LEKCJI)
def test_menu_ma_dokladnie_jeden_aria_current(klient, adres):
    """Dokładnie jeden odnośnik menu jest bieżącą stroną."""
    menu = _menu(_html(klient, adres))
    oznaczone = re.findall(r'<a\b[^>]*aria-current="page"[^>]*>', menu)
    assert len(oznaczone) == 1, f"{adres}: {len(oznaczone)} oznaczeń aria-current w menu"
    assert f'href="{adres}"' in oznaczone[0], f"{adres}: oznaczony jest inny odnośnik"


@pytest.mark.parametrize("adres", ["/", "/slowniczek", "/spis-tresci"])
def test_menu_nie_oznacza_lekcji_poza_kursem(klient, adres):
    menu = _menu(_html(klient, adres))
    assert 'aria-current="page"' not in menu, f"{adres}: menu oznacza lekcję poza kursem"


def test_menu_ma_rozwijane_wyklady_i_narzedzia(strona_glowna):
    menu = _menu(strona_glowna)
    assert "Wykłady" in menu, "brak rozwijanej pozycji „Wykłady”"
    assert "Narzędzia" in menu, "brak rozwijanej pozycji „Narzędzia”"
    assert menu.count("nav-link dropdown-toggle") == 2, "menu ma nie dwie listy rozwijane"
    assert menu.count('data-bs-toggle="dropdown"') == 2, "Bootstrap nie otworzy obu list"
    assert menu.count('role="button"') == 2, "brak stanu przycisku dla czytnika"
    # Trzy stany rozwinięcia: przycisk zwijania menu oraz dwie listy rozwijane.
    assert menu.count('aria-expanded="false"') == 3, "brak stanu rozwinięcia dla czytnika"


def test_menu_wyklady_pokazuja_zapowiedzi(strona_glowna):
    """Wykłady-zapowiedzi są widoczne, ale nieklikalne (dopisek „wkrótce”)."""
    menu = _menu(strona_glowna)
    for tytul in ZAPOWIEDZI:
        assert tytul in menu, f"brak zapowiedzi {tytul!r} w menu"

    assert menu.count("wkrótce") == len(ZAPOWIEDZI)
    assert menu.count('<span class="dropdown-item disabled" aria-disabled="true">') == len(
        ZAPOWIEDZI
    ), "zapowiedź wykładu jest klikalna"
    # Wszystkie lekcje rejestru i pięć narzędzi — tylko one są odnośnikami.
    odnosniki = re.findall(r'<a\b[^>]*class="dropdown-item', menu)
    assert len(odnosniki) == len(ADRESY_LEKCJI) + len(NARZEDZIA), (
        f"lista rozwijana ma {len(odnosniki)} odnośników"
    )


def test_lista_rozwijana_jest_w_zwijanym_menu(strona_glowna):
    menu = _menu(strona_glowna)
    assert 'data-bs-target="#menuGlowne"' in menu, "brak przycisku zwijania na wąskim ekranie"
    assert 'id="menuGlowne"' in menu, "lista rozwijana poza zwijanym menu"


def test_bootstrap_jest_zaladowany(strona_glowna):
    # Rozwijanie listy i zwijanie menu robi Bootstrap, więc jego skrypt musi być na stronie.
    assert "bootstrap.bundle.min.js" in strona_glowna


def test_menu_nie_dolozyl_wlasnego_javascriptu(strona_glowna):
    """Karta PRZ-138: jedyny własny skrypt ``base.html`` to przełącznik motywu.

    Do karty PRZ-138 ``base.html`` nie mógł ładować żadnego pliku z ``/static/js/``.
    Przełącznik motywu wymaga skryptu (zapis wyboru i reakcja na ustawienie systemu),
    więc pilnujemy teraz tego, że jest to **jedyny** lokalny skrypt: inline w ``<head>``
    (bez mignięcia), Bootstrap z CDN i ``motyw.js``.
    """
    zrodlo = SZABLON_BAZY.read_text(encoding="utf-8")
    wlasne = re.findall(r"""filename=['"]js/(?P<plik>[\w.-]+)['"]""", zrodlo)
    assert wlasne == ["motyw.js"], f"base.html ładuje lokalne skrypty: {wlasne}"
    assert zrodlo.count("<script") == 3, "skrypt inline motywu + Bootstrap + motyw.js"
    assert "/static/js/motyw.js" in strona_glowna, "strona nie ładuje skryptu motywu"
    assert "<script" not in _menu(strona_glowna), "menu nie potrzebuje własnego skryptu"


def test_base_podlacza_css_nawigacji(strona_glowna):
    assert "/static/css/nawigacja.css" in strona_glowna


@pytest.mark.parametrize("klasa", KLASY_CSS)
def test_css_nawigacji_ma_regule(klasa):
    css = CSS_NAWIGACJI.read_text(encoding="utf-8")
    assert re.search(rf"\.{re.escape(klasa)}(?![\w-])", css), f"brak reguły .{klasa} w CSS"


# --- okruszki ------------------------------------------------------------------


@pytest.mark.parametrize("adres", ADRESY_LEKCJI)
def test_okruszki_sa_na_kazdej_lekcji(klient, adres):
    html = _html(klient, adres)
    okruszki = _region(html, "okruszki")
    wyklad = lecture(lesson(adres).wyklad)

    assert 'aria-label="Ścieżka nawigacji"' in okruszki
    assert 'class="breadcrumb"' in okruszki
    assert len(re.findall(r'aria-current="page"', okruszki)) == 1, "okruszki bez znacznika strony"
    assert f"Wykład {wyklad.numer}" in _tekst(okruszki), f"{adres}: okruszki nie mówią o wykładzie"
    assert wyklad.tytul in _tekst(okruszki), f"{adres}: okruszki bez tytułu wykładu"


def test_okruszki_formuly_pokazuja_wyklad_i_lekcje(klient):
    tekst = _tekst(_region(_html(klient, "/formuly"), "okruszki"))
    assert "Wykłady" in tekst
    assert "Wykład 1: Klasyczny rachunek zdań" in tekst
    assert "Formuły i wartościowanie" in tekst


@pytest.mark.parametrize("adres", ["/", "/slowniczek", "/spis-tresci"])
def test_okruszki_poza_lekcjami_sa_ukryte(klient, adres):
    assert "okruszki" not in _html(klient, adres), f"{adres}: okruszki poza kursem"


# --- boczny spis lekcji --------------------------------------------------------


@pytest.mark.parametrize("adres", ADRESY_LEKCJI)
def test_boczny_spis_lekcji_pokazuje_lekcje_biezacego_wykladu(klient, adres):
    html = _html(klient, adres)
    spis = _region(html, "spis-lekcji")
    wyklad = lecture(lesson(adres).wyklad)

    assert 'aria-label="Lekcje wykładu"' in spis
    assert f"Lekcje wykładu {wyklad.numer}" in _tekst(spis)
    for lekcja in wyklad.lekcje:
        assert f'href="{lekcja.sciezka}"' in spis, f"{adres}: spis lekcji bez {lekcja.sciezka}"

    oznaczone = re.findall(r'<a\b[^>]*aria-current="page"[^>]*>', spis)
    assert len(oznaczone) == 1, f"{adres}: {len(oznaczone)} oznaczeń bieżącej lekcji w spisie"
    assert f'href="{adres}"' in oznaczone[0], f"{adres}: spis wyróżnia inną lekcję"

    # Spis pokazuje lekcje jednego wykładu i dwa skróty poza ścieżką lekcji.
    assert len(_odnosniki(spis)) == len(wyklad.lekcje) + 2
    assert "Prawa rachunku zdań" in _tekst(spis)
    assert "Plac zabaw" in _tekst(spis)


@pytest.mark.parametrize("adres", ["/", "/slowniczek", "/spis-tresci"])
def test_boczny_spis_lekcji_poza_lekcjami_sa_ukryte(klient, adres):
    assert "spis-lekcji" not in _html(klient, adres), f"{adres}: spis lekcji poza kursem"


# --- poprzednia / następna lekcja ----------------------------------------------


def test_formuly_maja_sasiadow_na_gorze_i_na_dole(klient):
    html = _html(klient, "/formuly")
    gora = _region(html, "nawigacja-lekcji-gora")
    dol = _region(html, "nawigacja-lekcji-dol")

    for region in (gora, dol):
        assert 'href="/wstep"' in region, "brak poprzedniej lekcji"
        assert 'href="/tautologie"' in region, "brak następnej lekcji"

    # Górny pasek jest przed treścią, dolne karty — po treści.
    assert html.index("nawigacja-lekcji-gora") < html.index("<h1")
    assert html.index("nawigacja-lekcji-dol") > html.index("<h1")


@pytest.mark.parametrize("adres", ADRESY_LEKCJI)
def test_sasiedzi_zgadzaja_sie_z_rejestrem(klient, adres):
    html = _html(klient, adres)
    oczekiwane = sorted(
        lekcja.sciezka for lekcja in (previous(adres), nastepna(adres)) if lekcja is not None
    )

    for klasa in ("nawigacja-lekcji-gora", "nawigacja-lekcji-dol"):
        adresy = sorted(_odnosniki(_region(html, klasa)))
        assert adresy == oczekiwane, f"{adres}: {klasa} prowadzi do {adresy}, a ma do {oczekiwane}"


@pytest.mark.parametrize("adres", ADRESY_LEKCJI)
def test_karty_sasiadow_maja_tytul_i_opis(klient, adres):
    tekst = _tekst(_region(_html(klient, adres), "nawigacja-lekcji-dol"))
    for sasiad in (previous(adres), nastepna(adres)):
        if sasiad is None:
            continue
        assert sasiad.tytul in tekst, f"{adres}: karta bez tytułu {sasiad.tytul!r}"
        assert sasiad.opis in tekst, f"{adres}: karta bez opisu {sasiad.tytul!r}"


def test_wstep_nie_ma_poprzedniej_lekcji(klient):
    html = _html(klient, "/wstep")
    for klasa in ("nawigacja-lekcji-gora", "nawigacja-lekcji-dol"):
        tekst = _tekst(_region(html, klasa))
        assert "Poprzednia" not in tekst, f"/wstep: {klasa} pokazuje poprzednią lekcję"
        assert "Następna" in tekst, f"/wstep: {klasa} bez następnej lekcji"


def test_ostatnia_lekcja_nie_ma_nastepnej(klient):
    """Ostatnia lekcja rejestru kończy kurs — nie ma odnośnika „następna”."""
    ostatnia = lessons()[-1]
    assert nastepna(ostatnia.sciezka) is None

    html = _html(klient, ostatnia.sciezka)
    for klasa in ("nawigacja-lekcji-gora", "nawigacja-lekcji-dol"):
        tekst = _tekst(_region(html, klasa))
        assert "Poprzednia" in tekst, f"{ostatnia.sciezka}: {klasa} bez poprzedniej lekcji"
        assert "Następna" not in tekst, f"{ostatnia.sciezka}: {klasa} pokazuje następną lekcję"


def test_quiz_prowadzi_do_pierwszej_lekcji_wykladu_2(klient):
    """Koniec wykładu 1 prowadzi do początku wykładu 2 (karta PRZ-093)."""
    karty = _region(_html(klient, "/quiz"), "nawigacja-lekcji-dol")

    assert 'href="/konsekwencja"' in karty, "/quiz nie prowadzi do /konsekwencja"
    assert "Wynikanie logiczne" in _tekst(karty), "/quiz nie pokazuje tytułu następnej lekcji"


@pytest.mark.parametrize("adres", ["/", "/slowniczek", "/spis-tresci"])
def test_nawigacja_sasiadow_poza_kursem_sa_ukryte(klient, adres):
    html = _html(klient, adres)
    assert "nawigacja-lekcji-gora" not in html
    assert "nawigacja-lekcji-dol" not in html


# --- strona /spis-tresci -------------------------------------------------------


def test_spis_tresci_wymienia_wyklady_i_lekcje(klient):
    html = _html(klient, "/spis-tresci")
    sekcje = {int(d["numer"]): d["tresc"] for d in WZORZEC_WYKLADU.finditer(_tresc(html))}

    assert sorted(sekcje) == [wyklad.numer for wyklad in NAV_LECTURES]

    for wyklad in NAV_LECTURES:
        sekcja = sekcje[wyklad.numer]
        for lekcja in wyklad.lekcje:
            assert f'href="{lekcja.sciezka}"' in sekcja, (
                f"wykład {wyklad.numer} bez lekcji {lekcja.sciezka}"
            )

        if wyklad.gotowy:
            assert "wkrótce" not in sekcja, "gotowy wykład nie może być zapowiedzią"
            assert len(_odnosniki(sekcja)) == len(wyklad.lekcje)
        else:
            assert "wkrótce" in sekcja, f"wykład {wyklad.numer} bez dopisku „wkrótce”"
            assert _odnosniki(sekcja) == [], f"wykład {wyklad.numer} ma odnośniki do lekcji"


def test_spis_tresci_pokazuje_tytuly_zapowiedzi(klient):
    tresc = _tekst(_tresc(_html(klient, "/spis-tresci")))
    for tytul in ZAPOWIEDZI:
        assert tytul in tresc, f"spis treści bez zapowiedzi {tytul!r}"


def test_spis_tresci_odsyla_do_narzedzi(klient):
    tresc = _tresc(_html(klient, "/spis-tresci"))
    for adres in NARZEDZIA:
        assert f'href="{adres}"' in tresc, f"spis treści bez odnośnika do {adres}"


# --- endpoint techniczny -------------------------------------------------------


def test_zdrowie_bez_nawigacji_i_bez_bledu(klient):
    odpowiedz = klient.get("/zdrowie")

    assert odpowiedz.status_code == 200
    assert odpowiedz.get_json() == {"status": "ok", "aplikacja": "prawa-rachunku-zdan"}
    for znacznik in ("okruszki", "spis-lekcji", "nawigacja-lekcji", "breadcrumb", "<html"):
        assert znacznik not in odpowiedz.get_data(as_text=True)


# --- szablony lekcji nie budują nawigacji --------------------------------------


@pytest.mark.parametrize(
    "szablon",
    sorted(
        szablon
        for szablon in KATALOG_SZABLONOW.rglob("*.html")
        if szablon.name not in SZABLONY_NAWIGACJI
    ),
    ids=lambda szablon: szablon.name,
)
def test_szablon_lekcji_nie_zna_nawigacji(szablon):
    zrodlo = szablon.read_text(encoding="utf-8")
    znalezione = [znacznik for znacznik in ZAKAZANE_W_LEKCJACH if znacznik in zrodlo]
    assert not znalezione, f"{szablon.name}: szablon lekcji buduje nawigację ({znalezione})"


# --- ścieżka nauki na stronie głównej (karta PRZ-023) --------------------------


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


# --- stopka --------------------------------------------------------------------


def test_stopka_ma_odnosnik_do_wstepu(strona_glowna):
    stopka = _stopka(strona_glowna)
    assert 'href="/wstep"' in stopka, "stopka nie odsyła do /wstep"
    assert "Wstęp" in stopka


# --- bloki base.html -----------------------------------------------------------


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
