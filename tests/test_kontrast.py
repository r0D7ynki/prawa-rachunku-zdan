"""Kontrast kolorów motywu (karta PRZ-139).

Arkusz ``app.css`` trzyma paletę w tokenach: motyw jasny w bloku ``:root``,
ciemny w ``:root[data-theme="dark"]`` (wybór użytkownika) i — żeby działał
również bez JavaScriptu — w kopii pod ``@media (prefers-color-scheme: dark)``.
Test czyta te bloki i liczy współczynnik kontrastu WCAG 2.1 dla par
„tekst na tle”, którymi malują się komórki, wzory, alerty i plakietki.

Projekt nie ma przeglądarki w bramce (``AGENTS.md``, zasada 6), więc kolory
czytamy ze źródła arkusza, a nie z wyrenderowanej strony. Wzór na kontrast jest
ze specyfikacji WCAG: luminancja względna ``(0,2126 R + 0,7152 G + 0,0722 B)``
po przejściu składowej przez odwrotną kompresję sRGB, a wynik
``(jaśniejsza + 0,05) / (ciemniejsza + 0,05)``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

KATALOG = Path(__file__).resolve().parents[1]
KATALOG_CSS = KATALOG / "app" / "static" / "css"
ARKUSZ_APP = KATALOG_CSS / "app.css"
ARKUSZ_TABLICY = KATALOG_CSS / "truth-table.css"

#: Arkusze komponentów — kolory biorą wyłącznie z tokenów motywu.
ARKUSZE_KOMPONENTOW = [
    "truth-table.css",
    "wizualizacje.css",
    "playground.css",
    "quiz.css",
    "steps.css",
    "stepper.css",
    "reguly.css",
    "dowody.css",
    "rezolucja.css",
    "nawigacja.css",
]

#: Komplet tokenów motywu — te same nazwy w obu motywach (karta PRZ-139).
TOKENY = [
    "--tlo",
    "--tlo-panel",
    "--tlo-panel-2",
    "--tekst",
    "--tekst-muted",
    "--ramka",
    "--akcent",
    "--akcent-tekst",
    "--prawda",
    "--prawda-tlo",
    "--falsz",
    "--falsz-tlo",
    "--formula-tlo",
    "--komorka-tlo",
    "--komorka-obramowanie",
    "--cien",
]

#: Pary „tekst na tle”, o które prosi karta: (kolor tekstu, kolor tła).
PARY = [
    ("--tekst", "--tlo"),
    ("--tekst", "--tlo-panel"),
    ("--tekst-muted", "--tlo-panel"),
    ("--prawda", "--prawda-tlo"),
    ("--falsz", "--falsz-tlo"),
    ("--akcent-tekst", "--akcent"),
]

#: Te same pary w miejscach, które nie są tablicą prawdy: akcent na tle wzoru
#: (alert informacyjny, plakietka kroku) i tekst na drugiej powierzchni.
PARY_DODATKOWE = [
    ("--akcent", "--formula-tlo"),
    ("--tekst", "--tlo-panel-2"),
    ("--akcent", "--komorka-tlo"),
]

#: Minimalny kontrast tekstu dla rozmiaru zwykłego — poziom AA WCAG 2.1.
MINIMALNY = 4.5

WZORZEC_DEKLARACJI = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")
WZORZEC_HEKSA = re.compile(r"^#[0-9a-fA-F]{6}$")
WZORZEC_KOLORU_WPROST = re.compile(r"#[0-9a-fA-F]{3,8}\b")
#: ``white`` i ``black`` jako kolor — z pominięciem właściwości ``white-space``.
WZORZEC_BIALY_CZARNY = re.compile(
    r"(?<![\w-])(?:white|black)(?![\w-])|#fff\b|#ffffff\b|#000\b", re.IGNORECASE
)


def _zrodlo(sciezka: Path) -> str:
    return sciezka.read_text(encoding="utf-8")


def _blok(css: str, naglowek: str) -> str:
    """Zwraca treść pierwszego bloku ``{…}``, którego nagłówek pasuje do wyrażenia.

    Liczymy klamry, więc blok ``@media`` zwraca się razem z zagnieżdżonym ``:root``.
    """
    wzorzec = re.compile(naglowek + r"[^{]*\{")
    dopasowanie = wzorzec.search(css)
    if not dopasowanie:
        return ""

    glebokosc = 1
    indeks = dopasowanie.end()
    while indeks < len(css) and glebokosc:
        if css[indeks] == "{":
            glebokosc += 1
        elif css[indeks] == "}":
            glebokosc -= 1
        indeks += 1
    return css[dopasowanie.end() : indeks - 1]


def _deklaracje(blok: str) -> dict[str, str]:
    """Zmienne z bloku jako słownik ``nazwa → wartość`` (bez zbędnych spacji)."""
    return {nazwa: " ".join(wartosc.split()) for nazwa, wartosc in WZORZEC_DEKLARACJI.findall(blok)}


def _motyw_jasny(css: str) -> dict[str, str]:
    """Tokeny motywu jasnego — pierwszy blok ``:root`` arkusza."""
    return _deklaracje(_blok(css, r":root\b"))


def _motyw_ciemny(css: str) -> dict[str, str]:
    """Tokeny wybrane przez użytkownika (``data-theme="dark"``)."""
    return _deklaracje(_blok(css, r':root\[data-theme="dark"\]'))


def _motyw_ciemny_systemowy(css: str) -> dict[str, str]:
    """Tokeny trybu systemowego bez JavaScriptu (``@media``)."""
    return _deklaracje(_blok(css, r":root:not\(\[data-theme\]\)"))


def _kanal(skladowa: int) -> float:
    """Składowa koloru po odwrotnej kompresji sRGB (wzór WCAG 2.1)."""
    wartosc = skladowa / 255
    if wartosc <= 0.03928:
        return wartosc / 12.92
    return ((wartosc + 0.055) / 1.055) ** 2.4


def _jasnosc(kolor: str) -> float:
    """Luminancja względna koloru ``#rrggbb``."""
    skladowe = [int(kolor[i : i + 2], 16) for i in (1, 3, 5)]
    czerwony, zielony, niebieski = (_kanal(skladowa) for skladowa in skladowe)
    return 0.2126 * czerwony + 0.7152 * zielony + 0.0722 * niebieski


def _kontrast(tekst: str, tlo: str) -> float:
    """Współczynnik kontrastu dwóch kolorów ``#rrggbb`` (1–21)."""
    jasny, ciemny = _jasnosc(tekst), _jasnosc(tlo)
    if jasny < ciemny:
        jasny, ciemny = ciemny, jasny
    return (jasny + 0.05) / (ciemny + 0.05)


def _kolor(motyw: dict[str, str], nazwa: str, etykieta: str) -> str:
    """Wartość tokenu jako kolor ``#rrggbb``; inna postać to błąd testu."""
    wartosc = motyw.get(nazwa, "")
    assert WZORZEC_HEKSA.match(wartosc), (
        f"{etykieta}: token {nazwa} nie jest kolorem „#rrggbb” (jest {wartosc!r}) — "
        "kontrastu nie da się policzyć"
    )
    return wartosc


def _motywy() -> dict[str, dict[str, str]]:
    css = _zrodlo(ARKUSZ_APP)
    return {"jasny": _motyw_jasny(css), "ciemny": _motyw_ciemny(css)}


# ---------------------------------------------------------------------------
# Tokeny w obu motywach
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("motyw", ["jasny", "ciemny"])
@pytest.mark.parametrize("token", TOKENY)
def test_motyw_ma_kazdy_token(token, motyw):
    """Komplet tokenów musi stać i w ``:root``, i w bloku ciemnym."""
    wartosc = _motywy()[motyw].get(token)

    assert wartosc, f"motyw {motyw}: brak tokenu {token} w app.css"


def test_tryb_systemowy_ma_te_same_tokeny_co_wybor_uzytkownika():
    """Kopia w ``@media`` musi co do wartości zgadzać się z blokiem ciemnym.

    Bez JavaScriptu serwer nie wpisuje ``data-theme``, więc o motywie decyduje
    samo zapytanie o media. Gdyby oba zestawy się rozjechały, ten sam motyw
    wyglądałby inaczej u jednego i drugiego czytelnika.
    """
    css = _zrodlo(ARKUSZ_APP)
    wybrany = _motyw_ciemny(css)
    systemowy = _motyw_ciemny_systemowy(css)

    assert systemowy, "app.css nie ma bloku tokenów dla trybu systemowego"
    rozjazdy = sorted(nazwa for nazwa in TOKENY if wybrany.get(nazwa) != systemowy.get(nazwa))
    assert not rozjazdy, f"tokeny rozjechały się z blokiem data-theme: {rozjazdy}"


# ---------------------------------------------------------------------------
# Kontrast par „tekst na tle”
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("motyw", ["jasny", "ciemny"])
@pytest.mark.parametrize(("tekst", "tlo"), PARY, ids=[f"{t}-na-{b}" for t, b in PARY])
def test_kontrast_pary_tekst_na_tle(tekst, tlo, motyw):
    """Każda para z karty ma w obu motywach co najmniej 4,5:1."""
    kolory = _motywy()[motyw]
    wartosc = _kontrast(
        _kolor(kolory, tekst, f"motyw {motyw}"), _kolor(kolory, tlo, f"motyw {motyw}")
    )

    assert wartosc >= MINIMALNY, (
        f"motyw {motyw}: para {tekst}/{tlo} ma kontrast {wartosc:.2f}:1, "
        f"a wymagane jest {MINIMALNY}:1"
    )


@pytest.mark.parametrize("motyw", ["jasny", "ciemny"])
@pytest.mark.parametrize(
    ("tekst", "tlo"), PARY_DODATKOWE, ids=[f"{t}-na-{b}" for t, b in PARY_DODATKOWE]
)
def test_kontrast_alertow_i_wyroznien(tekst, tlo, motyw):
    """Alerty, plakietki i wyróżnienia kroków malują się tymi samymi tokenami."""
    kolory = _motywy()[motyw]
    wartosc = _kontrast(
        _kolor(kolory, tekst, f"motyw {motyw}"), _kolor(kolory, tlo, f"motyw {motyw}")
    )

    assert wartosc >= MINIMALNY, (
        f"motyw {motyw}: para {tekst}/{tlo} ma kontrast {wartosc:.2f}:1, "
        f"a wymagane jest {MINIMALNY}:1"
    )


# ---------------------------------------------------------------------------
# Komponenty biorą kolory z tokenów
# ---------------------------------------------------------------------------


def test_komorki_oceny_biora_kolory_z_tokenow():
    """Kryterium karty: ocena wpisu to ``--prawda``/``--falsz`` na swoich tłach."""
    styl = _zrodlo(ARKUSZ_TABLICY)
    dobrze = _blok(styl, r"\.tt-komorka-wyniku\.komorka-dobrze\b")
    zle = _blok(styl, r"\.tt-komorka-wyniku\.komorka-zle\b")

    assert "background-color: var(--prawda-tlo);" in dobrze, "dobra ocena bez tła z tokenu"
    assert "color: var(--prawda);" in dobrze, "dobra ocena bez tekstu z tokenu"
    assert "background-color: var(--falsz-tlo);" in zle, "zła ocena bez tła z tokenu"
    assert "color: var(--falsz);" in zle, "zła ocena bez tekstu z tokenu"


def test_arkusze_komponentow_nie_maja_bialego_ani_czarnego():
    """Kryterium karty: żadnego ``#fff``, ``white``, ``#000`` ani ``black``.

    ``white-space`` to właściwość układu, nie kolor — wzorzec ją pomija.
    """
    znalezione: dict[str, list[str]] = {}
    for nazwa in ARKUSZE_KOMPONENTOW:
        trafienia = [
            numer
            for numer, linia in enumerate(_zrodlo(KATALOG_CSS / nazwa).splitlines(), start=1)
            if WZORZEC_BIALY_CZARNY.search(linia)
        ]
        if trafienia:
            znalezione[nazwa] = trafienia

    assert not znalezione, f"arkusze wpisują biel albo czerń wprost: {znalezione}"


def test_arkusze_komponentow_nie_maja_kolorow_wprost():
    """Kolory bierzemy wyłącznie z tokenów — inaczej tryb ciemny ich nie zmieni."""
    znalezione: dict[str, list[str]] = {}
    for nazwa in ARKUSZE_KOMPONENTOW:
        trafienia = sorted(set(WZORZEC_KOLORU_WPROST.findall(_zrodlo(KATALOG_CSS / nazwa))))
        if trafienia:
            znalezione[nazwa] = trafienia

    assert not znalezione, f"arkusze wpisują kolory wprost: {znalezione}"


def test_alerty_i_plakietki_biora_kolory_z_tokenow():
    """Alerty i plakietki Bootstrapa dostają kolory motywu, nie Bootstrapa."""
    css = _zrodlo(ARKUSZ_APP)

    for klasa, tekst, tlo in (
        ("alert-info", "--akcent", "--formula-tlo"),
        ("alert-success", "--prawda", "--prawda-tlo"),
        ("alert-danger", "--falsz", "--falsz-tlo"),
    ):
        blok = _blok(css, rf"\.{klasa}\b")

        assert f"--bs-alert-color: var({tekst});" in blok, f"{klasa}: tekst nie z tokenu"
        assert f"--bs-alert-bg: var({tlo});" in blok, f"{klasa}: tło nie z tokenu"

    plakietka = _blok(css, r"\.badge\.text-bg-secondary\b")

    assert "color: var(--tekst) !important;" in plakietka, "plakietka bez tekstu z tokenu"
    assert "background-color: var(--tlo-panel-2) !important;" in plakietka, (
        "plakietka bez tła z tokenu"
    )
