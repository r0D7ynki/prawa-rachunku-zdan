"""Test dostępności i notacji wszystkich stron (karta PRZ-016).

Karta wymienia dwanaście adresów. Dla każdego sprawdzamy to, co da się ocenić
bez przeglądarki (projekt nie ma runnera JS — patrz ``AGENTS.md``):

* kod 200 i ``lang="pl"``,
* dokładnie jeden ``<h1>``,
* każdy ``<img>`` i ``<svg>`` ma opis słowny (``aria-label``, ``aria-hidden``,
  ``alt`` albo ``<title>``),
* każdy odnośnik ma tekst albo ``aria-label``,
* odnośnik „Przejdź do treści” i każdy odnośnik ``#…`` prowadzą do istniejącego ``id``,
* wynik „PRAWDA”/„FAŁSZ” niesie słowo albo liczbę ``1``/``0`` — kolor nigdy nie
  jest jedynym nośnikiem informacji,
* komponent interaktywnej tablicy prawdy nazywa wartości słowami ``PRAWDA``/``FAŁSZ``.

Druga funkcja pilnuje notacji: strony treści nie pokazują formuł w notacji
popularnej (``¬``, ``↔``) bez zdania, które ją zapowiada („spotkasz też zapis
``¬p``”). Poza stronami treści zostają narzędzia: ``/plac-zabaw`` przyjmuje obie
notacje na wejściu, a ``/quiz`` i strona główna nie uczą notacji.
"""

from __future__ import annotations

import re
from html import unescape
from pathlib import Path

import pytest

from app import create_app
from app.logic.laws import all_laws

KATALOG_APP = Path(__file__).resolve().parents[1] / "app"
KATALOG_JS = KATALOG_APP / "static" / "js"
SKRYPT_TABLICY = KATALOG_APP / "static" / "js" / "truth-table.js"

#: Dwanaście adresów z karty PRZ-016. ``<slug>`` rozwija się do każdej strony
#: prawa z rejestru, żeby objąć też prawa dodatkowe.
ADRESY_Z_KARTY = [
    "/",
    "/wstep",
    "/formuly",
    "/tautologie",
    "/przeksztalcanie",
    "/kpn",
    "/prawa",
    "/prawa/<slug>",
    "/jak-czytac",
    "/slowniczek",
    "/plac-zabaw",
    "/quiz",
]

#: Adresy, na których uczymy notacji wykładowej.
STRONY_TRESCI = [
    "/wstep",
    "/formuly",
    "/tautologie",
    "/przeksztalcanie",
    "/kpn",
    "/prawa",
    "/prawa/<slug>",
    "/jak-czytac",
    "/slowniczek",
]

#: Znaki notacji popularnej, które mogą stać tylko w zdaniu zapowiadającym.
ZNAKI_POPULARNE = ("¬", "↔")

#: Zwroty, które zapowiadają notację popularną (porównanie bez wielkości liter).
ZAPOWIEDZI = (
    "spotkasz",
    "innych książkach",
    "innego podręcznika",
    "popularn",
    "innym zapisie",
)

#: Blok tekstu, w którym szukamy zapowiedzi (akapit, hasło słownika, pozycja listy).
BLOK_TEKSTU = re.compile(
    r"<(p|dd|li|dt|figcaption)\b[^>]*>(?P<tresc>.*?)</\1>",
    re.DOTALL | re.IGNORECASE,
)

#: Element, w którym mieści się wartość logiczna: komórka albo odznaka.
WARTOSC_PRAWDY = re.compile(
    r'<(?P<znacznik>td|span)\b[^>]*class="[^"]*\b(?P<klasa>prawda|falsz)\b[^"]*"[^>]*>'
    r"(?P<tresc>.*?)</(?P=znacznik)>",
    re.DOTALL,
)

#: Co wolno pokazać w elemencie ``.prawda`` / ``.falsz`` — słowo albo liczbę z wykładu.
DOZWOLONE_WARTOSCI = {
    "prawda": {"1", "Prawda", "PRAWDA"},
    "falsz": {"0", "Fałsz", "FAŁSZ"},
}

#: Atrybuty, które dają obrazowi albo rysunkowi opis słowny.
ATRYBUTY_OPISU = ("aria-label", "aria-hidden", "title=", "alt=")

OBRAZ = re.compile(r"<(img|svg)\b[^>]*>", re.IGNORECASE)
ODNOSNIK = re.compile(r"<a\b(?P<atrybuty>[^>]*)>(?P<tresc>.*?)</a>", re.DOTALL | re.IGNORECASE)
ZNACZNIK = re.compile(r"<[^>]+>")


def _rozwin(adresy: list[str]) -> list[str]:
    """Zamienia ``/prawa/<slug>`` na adres każdej strony prawa z rejestru."""
    rozwinięte: list[str] = []
    for adres in adresy:
        if adres.endswith("<slug>"):
            rozwinięte.extend(f"/prawa/{prawo.slug}" for prawo in all_laws())
        else:
            rozwinięte.append(adres)
    return rozwinięte


ADRESY = _rozwin(ADRESY_Z_KARTY)


def _tekst(fragment: str) -> str:
    """Widoczny tekst fragmentu HTML — bez znaczników, ze odmienionymi encjami."""
    return unescape(ZNACZNIK.sub(" ", fragment)).strip()


def _zakresy_zapowiedzi(html: str) -> list[tuple[int, int]]:
    """Pozycje tych bloków tekstu, które zapowiadają notację popularną."""
    return [
        dopasowanie.span()
        for dopasowanie in BLOK_TEKSTU.finditer(html)
        if any(zapowiedz in _tekst(dopasowanie["tresc"]).lower() for zapowiedz in ZAPOWIEDZI)
    ]


def _niezapowiedziane(html: str) -> list[str]:
    """Fragmenty z ``¬`` albo ``↔``, których nie zapowiada zdanie w tym samym bloku."""
    zakresy = _zakresy_zapowiedzi(html)
    znalezione: list[str] = []
    for pozycja, znak in enumerate(html):
        if znak not in ZNAKI_POPULARNE:
            continue
        if any(poczatek <= pozycja < koniec for poczatek, koniec in zakresy):
            continue
        fragment = _tekst(html[max(0, pozycja - 60) : pozycja + 20])
        znalezione.append(f"{znak} w: …{fragment}")
    return znalezione


def _adresy_tresci() -> list[str]:
    """Rozwinięte adresy stron treści."""
    return _rozwin(STRONY_TRESCI)


@pytest.fixture(scope="module")
def klient():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def strony(klient) -> dict[str, str]:
    """HTML każdego sprawdzanego adresu — jedno pobranie na cały moduł."""
    return {adres: klient.get(adres).get_data(as_text=True) for adres in ADRESY}


# ---------------------------------------------------------------------------
# Podstawy: kod, język, nagłówek
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("adres", ADRESY, ids=ADRESY)
def test_strona_odpowiada_200(klient, adres):
    assert klient.get(adres).status_code == 200, f"{adres} nie odpowiada kodem 200"


@pytest.mark.parametrize("adres", ADRESY, ids=ADRESY)
def test_strona_ma_polski_jezyk_i_dokladnie_jeden_h1(strony, adres):
    html = strony[adres]

    assert 'lang="pl"' in html
    assert len(re.findall(r"<h1\b", html)) == 1, f"{adres}: ma nie dokładnie jeden <h1>"


# ---------------------------------------------------------------------------
# Obrazy, odnośniki i kotwice
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("adres", ADRESY, ids=ADRESY)
def test_obrazy_i_svg_maja_opis_slowny(strony, adres):
    html = strony[adres]

    for dopasowanie in OBRAZ.finditer(html):
        znacznik = dopasowanie.group(0)
        if any(atrybut in znacznik for atrybut in ATRYBUTY_OPISU):
            continue
        nazwa = dopasowanie.group(1).lower()
        wnetrze = html[dopasowanie.end() :].split("</svg>", 1)[0] if nazwa == "svg" else ""
        assert "<title" in wnetrze, f"{adres}: <{nazwa}> bez opisu słownego ({znacznik[:60]}…)"


@pytest.mark.parametrize("adres", ADRESY, ids=ADRESY)
def test_kazdy_odnosnik_ma_tekst_albo_aria_label(strony, adres):
    html = strony[adres]

    for dopasowanie in ODNOSNIK.finditer(html):
        atrybuty = dopasowanie["atrybuty"]
        ma_tekst = bool(_tekst(dopasowanie["tresc"]))
        ma_nazwe = "aria-label" in atrybuty or "title=" in atrybuty
        assert ma_tekst or ma_nazwe, (
            f"{adres}: odnośnik bez tekstu i bez aria-label: {dopasowanie.group(0)[:80]!r}"
        )


@pytest.mark.parametrize("adres", ADRESY, ids=ADRESY)
def test_odnosnik_przejdz_do_tresci_prowadzi_do_istniejacego_id(strony, adres):
    html = strony[adres]
    odnosnik = re.search(r'<a[^>]*class="[^"]*skip-link[^"]*"[^>]*href="#([^"]+)"', html)

    assert odnosnik, f"{adres}: brak odnośnika „Przejdź do treści”"
    assert "Przejdź do treści" in html
    assert re.search(rf'id="{re.escape(odnosnik.group(1))}"', html), (
        f"{adres}: „Przejdź do treści” prowadzi do #{odnosnik.group(1)}, którego nie ma"
    )


@pytest.mark.parametrize("adres", ADRESY, ids=ADRESY)
def test_wewnetrzne_odnosniki_prowadza_do_istniejacych_id(strony, adres):
    html = strony[adres]
    identyfikatory = set(re.findall(r'\bid="([^"]+)"', html))

    for cel in re.findall(r'href="#([^"]+)"', html):
        assert cel in identyfikatory, f'{adres}: href="#{cel}" bez elementu o takim id'


# ---------------------------------------------------------------------------
# Wynik „PRAWDA”/„FAŁSZ” nie może być tylko kolorem
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("adres", ADRESY, ids=ADRESY)
def test_wartosci_prawdy_maja_tekst_a_nie_tylko_kolor(strony, adres):
    html = strony[adres]

    for dopasowanie in WARTOSC_PRAWDY.finditer(html):
        klasa = dopasowanie["klasa"]
        tresc = _tekst(dopasowanie["tresc"])
        dozwolone = sorted(DOZWOLONE_WARTOSCI[klasa])

        assert tresc, f"{adres}: element .{klasa} nie ma tekstu — kolor byłby jedynym nośnikiem"
        assert tresc in DOZWOLONE_WARTOSCI[klasa], (
            f"{adres}: .{klasa} pokazuje {tresc!r}, a wolno tylko {dozwolone}"
        )


def test_strony_faktycznie_pokazuja_wartosci_prawdy(strony):
    razem = sum(len(WARTOSC_PRAWDY.findall(html)) for html in strony.values())

    assert razem > 0, "żadna strona nie pokazuje wartości prawdy — test byłby pusty"


def test_tablica_prawdy_nazywa_wartosci_slowem(strony):
    strony_z_tablica = [adres for adres, html in strony.items() if "truth-table-mount" in html]
    zrodlo = SKRYPT_TABLICY.read_text(encoding="utf-8")

    assert strony_z_tablica, "żadna strona nie montuje interaktywnej tablicy prawdy"
    assert "PRAWDA" in zrodlo and "FAŁSZ" in zrodlo, (
        "komponent tablicy prawdy nie nazywa wartości słowami PRAWDA/FAŁSZ"
    )
    for adres in strony_z_tablica:
        assert "js/truth-table.js" in strony[adres], f"{adres} nie ładuje komponentu tablicy"


# ---------------------------------------------------------------------------
# Notacja: popularna tylko w zdaniu, które ją zapowiada
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("adres", _adresy_tresci(), ids=_adresy_tresci())
def test_notacja_popularna_tylko_w_zdaniu_zapowiadajacym(strony, adres):
    niezapowiedziane = _niezapowiedziane(strony[adres])

    assert not niezapowiedziane, f"{adres}: notacja popularna bez zapowiedzi — {niezapowiedziane}"


def test_notacja_popularna_jest_zawsze_zapowiedziana(strony):
    """Kontrola sensu: strony treści wspominają notację popularną — i zawsze z zapowiedzią."""
    z_znakiem = [
        adres for adres in _adresy_tresci() if any(z in strony[adres] for z in ZNAKI_POPULARNE)
    ]

    assert z_znakiem, "żadna strona treści nie wspomina ¬ ani ↔ — test notacji byłby pusty"
    for adres in z_znakiem:
        assert _zakresy_zapowiedzi(strony[adres]), f"{adres}: ¬/↔ bez zdania zapowiadającego"
