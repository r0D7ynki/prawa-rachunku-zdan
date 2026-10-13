"""Testy placu zabaw ``/plac-zabaw`` (karty PRZ-014 i PRZ-122).

Sprawdzamy widok HTML i pliki statyczne czytaniem — bez przeglądarki i bez sieci.
Testy JavaScriptu patrzą na treść pliku, bo logika siedzi po stronie serwera:
skrypt tylko wysyła formułę i pokazuje odpowiedź.

Karta PRZ-122 dokłada panel znaków przy **każdym** polu formuły. Testy poniżej
sprawdzają, że panel drugiego pola wstawia znaki do drugiego pola — czytając
atrybut ``data-pole`` panelu i sposób, w jaki skrypt wybiera pole.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import create_app

STRONA = "/plac-zabaw"

#: Znaki z notacji wykładowej — musi je mieć każdy panel (kryterium karty PRZ-122).
SYMBOLE_WYKLADU = ["∼", "∧", "∨", "→", "≡", "(", ")"]

#: Wszystkie znaki panelu: znaki wykładowe plus popularne odpowiedniki ``¬`` i ``↔``.
SYMBOLE_PANELU = ["∼", "¬", "∧", "∨", "→", "≡", "↔", "(", ")"]

#: Pary „znak wykładowy — popularny odpowiednik”. Notacja z wykładu idzie pierwsza (D15).
PARY_ZAPISU = [("∼", "¬"), ("≡", "↔")]

#: Etykiety paneli — panel mówi, przy którym polu stoi.
ETYKIETY_PANELI = ["Znaki do pierwszej formuły", "Znaki do drugiej formuły"]

#: Pola, do których panele wstawiają znaki (``data-pole`` panelu).
POLA_PANELI = ["pole-formula", "pole-druga"]

#: Cztery przykłady na start — klikane formuły z karty.
PRZYKLADY = ["p → q", "¬(p ∧ q)", "p ∨ ¬p", "(p → q) ∧ p"]

#: Adresy czterech endpointów, które woła ``playground.js``.
ENDPOINTY = [
    "/api/formula/parse",
    "/api/formula/table",
    "/api/formula/simplify",
    "/api/equivalence",
]

#: Formuła, którą wstrzykujemy jako parametr adresu.
WSTRZYKNIECIE = "<script>alert(1)</script>"

KATALOG_GLOWNY = Path(__file__).resolve().parents[1]
JS = KATALOG_GLOWNY / "app" / "static" / "js" / "playground.js"
CSS = KATALOG_GLOWNY / "app" / "static" / "css" / "playground.css"
SZABLON = KATALOG_GLOWNY / "app" / "templates" / "plac_zabaw.html"

WZORZEC_POLA = re.compile(r'<input[^>]*id="pole-formula"[^>]*>')
WZORZEC_WARTOSCI = re.compile(r'value="(?P<wartosc>[^"]*)"')

#: Panel znaków: znacznik ``<div class="klawiatura-symboli">`` z atrybutami i treścią.
#: Panel nie zawiera innych ``<div>``, więc treść kończy się na pierwszym ``</div>``.
WZORZEC_PANELU = re.compile(
    r'<div\b(?=[^>]*class="[^"]*klawiatura-symboli[^"]*")(?P<atrybuty>[^>]*)>(?P<tresc>.*?)</div>',
    re.DOTALL,
)

#: Znacznik przycisku razem z atrybutami (treść przycisku nas tu nie interesuje).
WZORZEC_PRZYCISKU = re.compile(r"<button[^>]*>")


def _cialo_funkcji(zrodlo: str, nazwa: str) -> str:
    """Zwraca ciało funkcji ``nazwa`` z pliku JavaScript."""
    dopasowanie = re.search(
        rf"function {nazwa}\([^)]*\)\s*\{{(?P<tresc>.*?)\n\}}", zrodlo, re.DOTALL
    )
    assert dopasowanie, f"brak funkcji {nazwa}() w {JS.name}"
    return dopasowanie["tresc"]


@pytest.fixture(scope="module")
def klient():
    """Klient testowy aplikacji."""
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def html(klient):
    """Treść strony ``/plac-zabaw`` bez parametrów."""
    return klient.get(STRONA).get_data(as_text=True)


def _zrodlo(sciezka: Path) -> str:
    """Czyta plik projektu jako UTF-8."""
    assert sciezka.is_file(), f"brak pliku {sciezka}"
    return sciezka.read_text(encoding="utf-8")


def _pole_formuly(tekst: str) -> str:
    """Zwraca znacznik ``<input>`` pola formuły albo podnosi błąd."""
    dopasowanie = WZORZEC_POLA.search(tekst)
    assert dopasowanie, 'brak pola formuły (input id="pole-formula")'
    return dopasowanie.group(0)


def _wartosc_pola(tekst: str) -> str:
    """Zwraca wartość atrybutu ``value`` pola formuły."""
    dopasowanie = WZORZEC_WARTOSCI.search(_pole_formuly(tekst))
    assert dopasowanie, "pole formuły nie ma atrybutu value"
    return dopasowanie["wartosc"]


def _panele(tekst: str) -> list[re.Match]:
    """Zwraca panele znaków w kolejności ze strony."""
    return list(WZORZEC_PANELU.finditer(tekst))


def _atrybut(znacznik: str, nazwa: str) -> str:
    """Zwraca wartość atrybutu z napisu ze znacznikiem HTML."""
    dopasowanie = re.search(rf'{nazwa}="([^"]*)"', znacznik)
    assert dopasowanie, f"brak atrybutu {nazwa} w {znacznik[:80]!r}"
    return dopasowanie.group(1)


# --- widok HTML --------------------------------------------------------------


def test_strona_odpowiada_200_i_html_utf8(klient):
    odpowiedz = klient.get(STRONA)

    assert odpowiedz.status_code == 200
    typ = odpowiedz.headers["Content-Type"]
    assert typ.startswith("text/html")
    assert "charset=utf-8" in typ.lower()


def test_strona_nie_zostawia_nieuzupelnionych_szablonow(html):
    assert "{{" not in html
    assert "{%" not in html


def test_jest_pole_formuly_z_wartoscia_domyslna(html):
    assert "p → (q ∧ ¬r)" in _wartosc_pola(html)


def test_panel_znakow_jest_przy_kazdym_polu_formuly(html):
    """Dwa pola formuły — dwa panele, każdy ze swoją etykietą i swoim polem."""
    panele = _panele(html)

    assert len(panele) == 2, f"paneli znaków jest {len(panele)}, oczekiwano dwóch"
    etykiety = [_atrybut(panel["atrybuty"], "aria-label") for panel in panele]
    pola = [_atrybut(panel["atrybuty"], "data-pole") for panel in panele]
    assert etykiety == ETYKIETY_PANELI, f"etykiety paneli: {etykiety}"
    assert pola == POLA_PANELI, f"panele wskazują pola: {pola}"


def test_panel_pierwszej_formuly_stoi_w_pierwszym_formularzu(html):
    panele = _panele(html)
    poczatek = html.index('id="formularz-formuly"')
    koniec = html.index('id="formularz-porownania"')

    assert poczatek < panele[0].start() < koniec, "panel pierwszej formuły jest nie przy niej"


def test_panel_drugiej_formuly_stoi_w_porownaniu_i_wstawia_do_drugiego_pola(html):
    """Kliknięcie ``∨`` w drugim panelu ma trafić do drugiego pola, nie do pierwszego."""
    panele = _panele(html)
    poczatek = html.index('id="formularz-porownania"')
    drugi = panele[1]

    assert drugi.start() > poczatek, "panel drugiej formuły stoi poza sekcją porównania"
    assert _atrybut(drugi["atrybuty"], "data-pole") == "pole-druga", (
        "panel drugiej formuły nie wskazuje drugiego pola"
    )
    assert 'data-symbol="∨"' in drugi["tresc"], "w panelu drugiej formuły brakuje znaku ∨"
    assert drugi["tresc"].count("<button") == len(SYMBOLE_PANELU) + 1, (
        "panel ma mieć znaki i przycisk czyszczenia"
    )


def test_kazdy_panel_ma_znaki_wykladu_i_przycisk_czyszczenia(html):
    """Panel ma wszystkie znaki z wykładu (∼, ∧, ∨, →, ≡, nawiasy) i „Wyczyść”."""
    for panel in _panele(html):
        symbole = re.findall(r'data-symbol="([^"]*)"', panel["tresc"])

        for symbol in SYMBOLE_WYKLADU:
            assert symbol in symbole, f"brak przycisku symbolu {symbol} w panelu"
        for symbol in SYMBOLE_PANELU:
            assert symbol in symbole, f"brak przycisku symbolu {symbol} w panelu"
        for wykładowy, popularny in PARY_ZAPISU:
            assert symbole.index(wykładowy) < symbole.index(popularny), (
                f"znak {popularny} stoi przed znakiem z wykładu {wykładowy}"
            )
        assert "data-czysc" in panel["tresc"], "panel nie ma przycisku czyszczenia"
        assert "Wyczyść" in panel["tresc"], "przycisk czyszczenia nie ma napisu po polsku"


def test_przyciski_paneli_sa_klawiszowe(html):
    """Panel obsługujemy z klawiatury: prawdziwe ``<button type="button">`` z etykietą."""
    for panel in _panele(html):
        przyciski = WZORZEC_PRZYCISKU.findall(panel["tresc"])

        assert len(przyciski) == len(SYMBOLE_PANELU) + 1, "zły zestaw przycisków w panelu"
        assert "<a " not in panel["tresc"], "przycisk panelu jest odnośnikiem, nie buttonem"
        for przycisk in przyciski:
            assert 'type="button"' in przycisk, f"przycisk bez type=button: {przycisk}"
            assert "aria-label=" in przycisk, f"przycisk bez aria-label: {przycisk}"


def test_jest_co_najmniej_cztery_przyklady(html):
    przyklady = re.findall(r'data-przyklad="([^"]*)"', html)

    assert len(przyklady) >= 4, f"przykładów jest {len(przyklady)}, oczekiwano co najmniej 4"
    for przykład in PRZYKLADY:
        assert przykład in przyklady, f"brak przykładu {przykład}"


def test_przyklady_dzialaja_takze_bez_javascriptu(html):
    """Odnośnik przykładu niesie formułę w adresie, więc działa bez skryptu."""
    if "p → q" in PRZYKLADY:
        assert 'href="/plac-zabaw?formula=p%20%E2%86%92%20q"' in html


def test_jest_druga_formula_i_przycisk_porownania(html):
    assert re.search(r'<input[^>]*id="pole-druga"', html), "brak drugiego pola"
    assert 'id="przycisk-porownaj"' in html


def test_przelacznik_celu_ma_cztery_opcje(html):
    opcje = re.findall(r'<option value="([^"]*)"', html)

    assert opcje == ["auto", "nnf", "dnf", "cnf"], f"opcje celu: {opcje}"


# --- parametr adresu ---------------------------------------------------------


def test_parametr_wstawia_formule_do_pola(klient):
    html = klient.get(f"{STRONA}?formula=p%20%E2%86%92%20q").get_data(as_text=True)

    assert _wartosc_pola(html) == "p → q"


def test_parametr_jest_escapowany(klient):
    html = klient.get(STRONA, query_string={"formula": WSTRZYKNIECIE}).get_data(as_text=True)

    assert WSTRZYKNIECIE not in html, "parametr utworzył znacznik script"
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_szablon_nie_uzywa_filtra_safe():
    assert "|safe" not in _zrodlo(SZABLON), "szablon nie powinien używać |safe"


# --- pliki statyczne ---------------------------------------------------------


def test_skrypt_i_styl_istnieja_i_nie_sa_puste():
    for plik in (JS, CSS):
        assert plik.is_file(), f"brak pliku {plik}"
        assert plik.stat().st_size > 0, f"plik {plik} jest pusty"


def test_skrypt_wola_cztery_endpointy():
    zrodlo = _zrodlo(JS)

    for endpoint in ENDPOINTY:
        assert endpoint in zrodlo, f"brak wywołania endpointu {endpoint}"
    assert "fetch(" in zrodlo, "skrypt nie używa fetch"


def test_skrypt_obsluguje_blad_ok_false():
    zrodlo = _zrodlo(JS)

    assert ".ok" in zrodlo, "skrypt nie sprawdza pola ok"
    assert ".blad" in zrodlo, "skrypt nie pokazuje pola blad"
    assert "Nie udało się" in zrodlo, "brak komunikatu po polsku"


def test_skrypt_pisze_kontrprzyklad_zdaniem():
    zrodlo = _zrodlo(JS)

    assert "PRAWDA" in zrodlo and "FAŁSZ" in zrodlo
    assert " = " in zrodlo, "brak zdania w postaci „p = PRAWDA”"


def test_skrypt_wstawia_symbol_w_miejscu_kursora():
    zrodlo = _zrodlo(JS)

    assert "selectionStart" in zrodlo
    assert "setSelectionRange" in zrodlo


def test_skrypt_wstawia_symbol_do_pola_wskazanego_przez_panel():
    """Panel mówi w ``data-pole``, do którego pola wstawia — nie ma pola na sztywno."""
    zrodlo = _zrodlo(JS)

    assert "dataset.pole" in zrodlo, "skrypt nie czyta pola z atrybutu data-pole panelu"
    assert "wstawSymbol(pole," in zrodlo, "znak nie trafia do pola wskazanego przez panel"
    assert "wstawSymbol(poleFormuly" not in zrodlo, "znak trafia na sztywno do pierwszego pola"


def test_skrypt_przywraca_fokus_do_pola_po_wstawieniu():
    """Po wstawieniu znaku kursor i fokus wracają do tego samego pola."""
    cialo = _cialo_funkcji(_zrodlo(JS), "wstawSymbol")

    assert "focus()" in cialo, "funkcja wstawiania nie przywraca fokusu do pola"


def test_skrypt_czysci_pole_z_panelu():
    zrodlo = _zrodlo(JS)

    assert "data-czysc" in zrodlo, "skrypt nie obsługuje przycisku czyszczenia"
    cialo = _cialo_funkcji(zrodlo, "wyczyscPole")
    assert "focus()" in cialo, "czyszczenie nie przywraca fokusu do pola"


def test_skrypt_nie_wstawia_tresci_przez_innerhtml():
    zrodlo = _zrodlo(JS)

    assert ".innerHTML" not in zrodlo, "treść z API ma trafiać przez textContent"


# --- rejestracja widoku ------------------------------------------------------


def test_blueprint_jest_zarejestrowany():
    app = create_app({"TESTING": True})

    assert "playground" in app.config["BLUEPRINTS"]
