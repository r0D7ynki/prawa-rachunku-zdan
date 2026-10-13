"""Jeden przełącznik motywu: suwak jasny/ciemny (karta PRZ-155).

Projekt nie ma runnera JavaScript (``AGENTS.md``, zasada 6), więc zachowanie skryptu
sprawdzamy statycznie: czytamy ``base.html``, ``motyw.js`` i ``motyw.css`` i pilnujemy
umowy między nimi. Stronę renderujemy przez ``flask.test_client()``.

Przełącznik ma **jeden** stan do wyboru — jasny albo ciemny. Opcji „Auto” nie ma
w widoku: brak zapisanego wyboru znaczy „jak w systemie”, a pierwsze przełączenie
zapisuje wybór i od tej chwili system nie zmienia już motywu.

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

#: Etykiety starego przełącznika (trzy przyciski) — nie może ich już być w menu.
STARE_ETYKIETY = ["Auto", "Jasny", "Ciemny"]

WZORZEC_INLINE = re.compile(r"<script>(?P<tresc>.*?)</script>", re.DOTALL)
WZORZEC_MENU = re.compile(r'<nav\b[^>]*id="nawigacja-glowna".*?</nav>', re.DOTALL)
WZORZEC_SUWAKA = re.compile(r'<input\b[^>]*role="switch"[^>]*>', re.DOTALL)
WZORZEC_POLA = re.compile(r'<div class="przelacznik-motywu-pole".*?</div>', re.DOTALL)
WZORZEC_DEKLARACJI = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")
WZORZEC_ZNACZNIKA = re.compile(r"<[^>]+>")


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


def _strona() -> str:
    return _klient().get("/").get_data(as_text=True)


def _suwak() -> str:
    """Znacznik ``<input role="switch">`` z wyrenderowanej strony głównej."""
    dopasowanie = WZORZEC_SUWAKA.search(_strona())
    assert dopasowanie, "strona nie ma suwaka motywu (input z role=switch)"
    return dopasowanie.group()


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
# Suwak w menu
# ---------------------------------------------------------------------------


def test_strona_ma_jeden_suwak_motywu():
    suwaki = WZORZEC_SUWAKA.findall(_strona())

    assert len(suwaki) == 1, f"strona ma {len(suwaki)} elementów role=switch, a ma być jeden"
    suwak = suwaki[0]
    assert 'type="checkbox"' in suwak, "suwak motywu nie jest checkboxem"
    assert 'class="form-check-input przelacznik-motywu"' in suwak, (
        "suwak bez klasy Bootstrapa i własnej klasy przelacznik-motywu"
    )


def test_suwak_nie_ma_starych_przyciskow_ani_opcji_auto():
    html = _strona()
    menu = WZORZEC_MENU.search(html)

    assert menu, "strona nie ma paska menu"
    assert "data-motyw" not in html, "została obsługa trzech przycisków (data-motyw)"
    assert "motyw-przycisk" not in html, "zostały stare przyciski motywu"
    assert "Motyw strony" not in menu.group(), "została grupa przycisków motywu"
    assert "aria-pressed" not in menu.group(), "suwak nie ma już stanu `aria-pressed`"

    # Etykiety czytamy z tekstu menu (bez znaczników), żeby nie złapać atrybutów.
    tekst_menu = WZORZEC_ZNACZNIKA.sub(" ", menu.group())
    for etykieta in STARE_ETYKIETY:
        assert etykieta not in tekst_menu, f"w menu została etykieta {etykieta!r}"


def test_ikony_sa_po_bokach_suwaka():
    pole = WZORZEC_POLA.search(_strona())

    assert pole, "brak pola przełącznika motywu"
    zawartosc = pole.group()
    assert zawartosc.index("☀") < zawartosc.index("<input") < zawartosc.index("☾"), (
        "ikony mają stać w kolejności: ☀ z lewej, suwak w środku, ☾ z prawej"
    )
    assert zawartosc.count('aria-hidden="true"') == 2, "ikony to dekoracja dla czytnika"


def test_przelacznik_motywu_jest_w_menu():
    menu = WZORZEC_MENU.search(_strona())

    assert menu, "base.html nie ma paska menu"
    assert "przelacznik-motywu" in menu.group(), "przełącznik motywu poza menu"


def test_suwak_jest_dostepny_z_klawiatury():
    suwak = _suwak()

    assert 'aria-label="Tryb ciemny"' in suwak, "suwak bez nazwy dla czytnika ekranu"
    for atrybut in ("tabindex", "disabled", "hidden"):
        assert atrybut not in suwak, f"suwak nie może mieć {atrybut!r}"


def test_strona_ma_arkusz_i_skrypt_motywu():
    html = _strona()

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
    # Bez opcji „Auto” klucz nigdy nie znika — nie ma do czego wracać.
    assert "removeItem" not in tekst, "suwak nie ma stanu „jak w systemie” do wyboru"


def test_skrypt_reaguje_na_przelaczenie_suwaka():
    tekst = _zrodlo(SKRYPT_MOTYWU)

    assert 'document.querySelector(".przelacznik-motywu")' in tekst, "skrypt nie szuka suwaka"
    assert 'SUWAK.addEventListener("change"' in tekst, "skrypt nie słucha przełączenia suwaka"
    assert "SUWAK.checked" in tekst, "skrypt nie czyta stanu suwaka"


def test_bez_zapisanego_wyboru_motyw_idzie_za_systemem():
    tekst = _zrodlo(SKRYPT_MOTYWU)

    assert 'matchMedia("(prefers-color-scheme: dark)")' in tekst, (
        "brak pytania o ustawienie systemu"
    )
    assert 'SYSTEM_CIEMNY.matches ? "dark" : "light"' in tekst, "brak motywu z ustawienia systemu"
    assert "const motyw = wybor ?? motywSystemu();" in tekst, (
        "bez zapisanego wyboru motyw ma brać ustawienie systemu"
    )
    assert "let wybor = zapisanyWybor()" in tekst, "skrypt nie czyta wyboru przy wczytaniu"
    assert "wybor === null" in tekst, "system ma zmieniać motyw tylko bez zapisanego wyboru"


def test_skrypt_ustawia_atrybuty_na_stronie():
    tekst = _zrodlo(SKRYPT_MOTYWU)

    assert 'setAttribute("data-theme", motyw)' in tekst, "skrypt nie ustawia data-theme"
    assert 'setAttribute("data-bs-theme", motyw)' in tekst, "skrypt nie ustawia data-bs-theme"
    assert "innerHTML" not in tekst, "skrypt motywu nie potrzebuje innerHTML"
    assert "eval" not in tekst, "skrypt motywu nie używa eval"


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

    assert re.search(r"\.bez-js\s+\.przelacznik-motywu-pole\s*\{[^}]*display:\s*none", css), (
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


# ---------------------------------------------------------------------------
# Wygląd suwaka
# ---------------------------------------------------------------------------


def test_suwak_motywu_ma_cel_dotyku():
    blok = _blok(_zrodlo(ARKUSZ_MOTYWU), r'\.przelacznik-motywu\[type="checkbox"\]')

    assert blok, "motyw.css nie ma reguły .przelacznik-motywu"
    assert "min-height: var(--min-dotyk)" in blok, "suwak niższy niż cel dotyku 44px"
    assert "background-color: var(--tlo-panel-2)" in blok, "tor suwaka nie bierze tokenu motywu"


def test_suwak_pokazuje_stan_takze_bez_koloru():
    """Stan niesie pozycja gałki, nie sam kolor (zasada dostępności 5)."""
    css = _zrodlo(ARKUSZ_MOTYWU)
    zaznaczony = _blok(css, r'\.przelacznik-motywu\[type="checkbox"\]:checked')
    galka = _blok(css, r'\.przelacznik-motywu\[type="checkbox"\]:checked::before')

    assert zaznaczony, "brak reguły stanu zaznaczonego suwaka"
    assert "background-color: var(--akcent)" in zaznaczony, "zaznaczony tor poza paletą motywu"
    assert "left: calc(100%" in galka, "gałka nie przechodzi na drugą stronę po włączeniu"
    assert "background-color: var(--akcent-tekst)" in galka, "gałka poza paletą motywu"


def test_suwak_ma_obwodke_fokusu():
    css = _zrodlo(ARKUSZ_MOTYWU)

    assert re.search(
        r'\.przelacznik-motywu\[type="checkbox"\]:focus-visible\s*\{'
        r"[^}]*outline:\s*var\(--ramka-focus\)\s+solid\s+var\(--akcent\)",
        css,
    ), "suwak bez widocznej obwódki fokusu z tokenów motywu"
