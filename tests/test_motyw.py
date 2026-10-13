"""Przełącznik motywu: „Auto” (jak w systemie), „Jasny” i „Ciemny” (karta PRZ-138).

Projekt nie ma runnera JavaScript (``AGENTS.md``, zasada 6), więc zachowanie skryptu
sprawdzamy statycznie: czytamy ``base.html``, ``motyw.js`` i ``motyw.css`` i pilnujemy
umowy między nimi. Stronę renderujemy przez ``flask.test_client()``.

Druga część testu broni palety. Wybrany motyw to kopia palety z ``app.css`` (tam jest
źródło), więc gdyby oba zestawy się rozjechały, strona z wybranym motywem malowałaby
się inaczej niż ta sama strona z ustawień systemu.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import create_app

KATALOG = Path(__file__).resolve().parents[1]
SZABLON_BAZY = KATALOG / "app" / "templates" / "base.html"
SKRYPT_MOTYWU = KATALOG / "app" / "static" / "js" / "motyw.js"
ARKUSZ_MOTYWU = KATALOG / "app" / "static" / "css" / "motyw.css"
ARKUSZ_APP = KATALOG / "app" / "static" / "css" / "app.css"

#: Trzy stany przełącznika — wartość ``data-motyw`` przycisku.
WYBORY = ["auto", "light", "dark"]

#: Etykiety widoczne na przyciskach (obok ikony ukrytej przed czytnikiem).
ETYKIETY = ["Auto", "Jasny", "Ciemny"]

WZORZEC_INLINE = re.compile(r"<script>(?P<tresc>.*?)</script>", re.DOTALL)
WZORZEC_GRUPY = re.compile(r'<div class="motyw-przelacznik".*?</div>', re.DOTALL)
WZORZEC_MENU = re.compile(r'<nav\b[^>]*id="nawigacja-glowna".*?</nav>', re.DOTALL)
WZORZEC_PRZYCISKU = re.compile(r"<button\b[^>]*>")
WZORZEC_DEKLARACJI = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")


def _zrodlo(sciezka: Path) -> str:
    return sciezka.read_text(encoding="utf-8")


def _blok(tekst: str, naglowek: str) -> str:
    """Zwraca treść pierwszego bloku ``{…}``, którego nagłówek pasuje do wyrażenia.

    Liczymy klamry, więc blok ``@media`` zwraca się razem z zagnieżdżonym ``:root``.
    """
    wzorzec = re.compile(naglowek + r"[^{]*\{")
    dopasowanie = wzorzec.search(tekst)
    if not dopasowanie:
        return ""

    glebokosc = 1
    indeks = dopasowanie.end()
    while indeks < len(tekst) and glebokosc:
        if tekst[indeks] == "{":
            glebokosc += 1
        elif tekst[indeks] == "}":
            glebokosc -= 1
        indeks += 1
    return tekst[dopasowanie.end() : indeks - 1]


def _deklaracje(blok: str) -> dict[str, str]:
    """Zmienne z bloku jako słownik ``nazwa → wartość`` (bez zbędnych spacji)."""
    return {nazwa: " ".join(wartosc.split()) for nazwa, wartosc in WZORZEC_DEKLARACJI.findall(blok)}


def _paleta_app() -> tuple[dict[str, str], dict[str, str]]:
    """Paleta ``app.css``: (blok ``:root``, blok ciemny z ``@media``)."""
    css = _zrodlo(ARKUSZ_APP)
    ciemny = _blok(css, r"@media[^{]*prefers-color-scheme:\s*dark")
    return _deklaracje(_blok(css, r":root\b")), _deklaracje(_blok(ciemny, r":root\b"))


def _paleta_motywu() -> tuple[dict[str, str], dict[str, str]]:
    """Paleta ``motyw.css``: (blok jasny, blok ciemny)."""
    css = _zrodlo(ARKUSZ_MOTYWU)
    return (
        _deklaracje(_blok(css, r':root\[data-theme="light"\]')),
        _deklaracje(_blok(css, r':root\[data-theme="dark"\]')),
    )


def _klient():
    return create_app({"TESTING": True}).test_client()


# ---------------------------------------------------------------------------
# Ustawienie motywu przed pierwszym malowaniem
# ---------------------------------------------------------------------------


def test_skrypt_motywu_stoi_w_head_przed_arkuszami():
    zrodlo = _zrodlo(SZABLON_BAZY)
    skrypt = WZORZEC_INLINE.search(zrodlo)

    assert skrypt, "base.html nie ma skryptu inline ustawiającego motyw"
    assert skrypt.start() < zrodlo.index("<link"), "skrypt motywu musi stać przed arkuszami CSS"
    assert "<head>" in zrodlo[: skrypt.start()], "skrypt motywu musi stać w <head>"

    tresc = skrypt["tresc"]
    for fragment in (
        'setAttribute("data-theme"',
        'setAttribute("data-bs-theme"',
        'localStorage.getItem("motyw")',
        "prefers-color-scheme: dark",
    ):
        assert fragment in tresc, f"skrypt motywu bez {fragment!r}"


def test_motyw_nie_czeka_na_wczytanie_dokumentu():
    """Motyw ustawiamy od razu — inaczej strona mignęłaby jasnym tłem."""
    for sciezka in (SKRYPT_MOTYWU, SZABLON_BAZY):
        assert "DOMContentLoaded" not in _zrodlo(sciezka), f"{sciezka.name}: czekanie na dokument"


# ---------------------------------------------------------------------------
# Przełącznik w menu
# ---------------------------------------------------------------------------


def test_strona_ma_trzy_przyciski_motywu():
    html = _klient().get("/").get_data(as_text=True)
    grupa = WZORZEC_GRUPY.search(html)

    assert grupa, "brak grupy przycisków motywu"
    assert 'role="group"' in grupa.group(), "grupa przycisków bez roli dla czytnika"
    assert 'aria-label="Motyw strony"' in grupa.group(), "grupa przycisków bez nazwy"

    przyciski = WZORZEC_PRZYCISKU.findall(grupa.group())
    assert len(przyciski) == 3, f"przełącznik ma {len(przyciski)} przycisków, a nie trzy"
    assert sorted(re.findall(r'data-motyw="([^"]+)"', grupa.group())) == sorted(WYBORY)

    zaznaczone = [przycisk for przycisk in przyciski if 'aria-pressed="true"' in przycisk]
    assert len(zaznaczone) == 1, "dokładnie jeden przycisk ma być zaznaczony"
    assert 'data-motyw="auto"' in zaznaczone[0], "na start zaznaczony jest „Auto”"
    for przycisk in przyciski:
        assert "aria-pressed=" in przycisk, f"przycisk bez stanu: {przycisk}"
        assert 'type="button"' in przycisk, f"przycisk bez typu: {przycisk}"

    for etykieta in ETYKIETY:
        assert etykieta in grupa.group(), f"brak etykiety {etykieta!r} na przycisku"
    # Ikony są dekoracją — czytnik czyta samą etykietę.
    assert 'aria-hidden="true"' in grupa.group()


def test_przelacznik_motywu_jest_w_menu():
    menu = WZORZEC_MENU.search(_klient().get("/").get_data(as_text=True))

    assert menu, "base.html nie ma paska menu"
    assert "motyw-przelacznik" in menu.group(), "przełącznik motywu poza menu"


def test_strona_ma_arkusz_i_skrypt_motywu():
    html = _klient().get("/").get_data(as_text=True)

    assert "/static/css/motyw.css" in html, "strona bez arkusza motywu"
    assert "/static/js/motyw.js" in html, "strona bez skryptu motywu"


# ---------------------------------------------------------------------------
# Zachowanie skryptu (test statyczny: projekt nie ma runnera JS)
# ---------------------------------------------------------------------------


def test_skrypt_zapisuje_wybor_w_pamieci_przegladarki():
    tekst = _zrodlo(SKRYPT_MOTYWU)

    assert 'const KLUCZ = "motyw"' in tekst, "klucz wyboru to „motyw”"
    assert "localStorage.getItem(KLUCZ)" in tekst, "skrypt nie czyta zapisanego wyboru"
    assert "localStorage.setItem(KLUCZ, wybor)" in tekst, "skrypt nie zapisuje wyboru"
    assert "localStorage.removeItem(KLUCZ)" in tekst, "„Auto” ma usuwać klucz"


def test_skrypt_ustawia_atrybuty_na_stronie():
    tekst = _zrodlo(SKRYPT_MOTYWU)

    assert 'setAttribute("data-theme", motyw)' in tekst, "skrypt nie ustawia data-theme"
    assert 'setAttribute("data-bs-theme", motyw)' in tekst, "skrypt nie ustawia data-bs-theme"
    assert "innerHTML" not in tekst, "skrypt motywu nie potrzebuje innerHTML"


def test_skrypt_reaguje_na_zmiane_ustawienia_systemu():
    tekst = _zrodlo(SKRYPT_MOTYWU)

    assert 'matchMedia("(prefers-color-scheme: dark)")' in tekst, (
        "brak pytania o ustawienie systemu"
    )
    assert 'addEventListener("change"' in tekst, "skrypt nie słucha zmiany ustawienia systemu"
    assert "SYSTEM_CIEMNY" in tekst, "brak obsługi trybu systemowego"


# ---------------------------------------------------------------------------
# Warstwa bez JavaScriptu
# ---------------------------------------------------------------------------


def test_bez_javascriptu_zostaje_media_query():
    zrodlo = _zrodlo(SZABLON_BAZY)

    assert 'class="bez-js"' in zrodlo, "brak klasy, która ukrywa przełącznik bez JavaScriptu"
    assert re.search(r"@media[^{]*prefers-color-scheme:\s*dark", _zrodlo(ARKUSZ_APP)), (
        "app.css musi zostać warstwą bez JavaScriptu"
    )
    # Serwer nie wpisuje `data-theme`: bez JavaScriptu o motywie decyduje sam CSS.
    assert not re.search(r"<html[^>]*\sdata-theme=", zrodlo), "data-theme wpisany na sztywno"


def test_przelacznik_znika_bez_javascriptu():
    css = _zrodlo(ARKUSZ_MOTYWU)

    assert re.search(r"\.bez-js\s+\.motyw-przelacznik\s*\{[^}]*display:\s*none", css), (
        "motyw.css nie ukrywa przełącznika bez JavaScriptu"
    )
    assert 'classList.remove("bez-js")' in _zrodlo(SZABLON_BAZY), (
        "skrypt motywu nie zdejmuje klasy `bez-js`"
    )


# ---------------------------------------------------------------------------
# Paleta wybranego motywu
# ---------------------------------------------------------------------------


def test_arkusz_motywu_ma_oba_wybory():
    css = _zrodlo(ARKUSZ_MOTYWU)

    for wybor in ("light", "dark"):
        assert f':root[data-theme="{wybor}"]' in css, f"brak palety dla wyboru {wybor!r}"


def test_wybrany_motyw_ma_te_sama_palete_co_app_css():
    jasne_app, ciemne_app = _paleta_app()
    jasne_motyw, ciemne_motyw = _paleta_motywu()

    assert jasne_app and ciemne_app, "app.css bez palety w :root albo w bloku ciemnym"

    # Wybrany motyw ciemny to kopia bloku ciemnego app.css — inaczej ten sam motyw
    # wyglądałby inaczej niż wtedy, gdy idzie za ustawieniem systemu.
    assert ciemne_motyw == ciemne_app, "paleta ciemna rozjechała się z app.css"

    # Wybrany motyw jasny musi cofnąć każdą zmienną nadpisaną przez blok ciemny.
    brakujace = sorted(set(ciemne_app) - set(jasne_motyw))
    assert not brakujace, f"motyw jasny nie cofa zmiennych: {brakujace}"

    # Kolory palety projektu muszą być co do wartości te same, co w app.css.
    for nazwa in sorted(set(ciemne_app) & set(jasne_app)):
        assert jasne_motyw.get(nazwa) == jasne_app[nazwa], f"{nazwa} różni się od app.css"


def test_przyciski_motywu_maja_cel_dotyku():
    blok = _blok(_zrodlo(ARKUSZ_MOTYWU), r"\.motyw-przycisk\b")

    assert blok, "motyw.css nie ma reguły .motyw-przycisk"
    assert "min-height: var(--min-dotyk)" in blok, "przycisk niższy niż cel dotyku 44px"
    assert "min-width: var(--min-dotyk)" in blok, "przycisk węższy niż cel dotyku 44px"
