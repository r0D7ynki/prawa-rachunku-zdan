"""Test wyglądu i responsywności (karta PRZ-120).

Projekt nie ma przeglądarki w bramce ani runnera JS (``AGENTS.md``, zasada 6),
więc o arkusze pytamy statycznie: czytamy pliki CSS i HTML wyrenderowanych stron.

Sprawdzamy to, o co prosi karta:

* paleta w ``:root`` (``app.css``) — tło, akcent, prawda, fałsz, ramka, cień,
  tło wzoru i powierzchnia kart,
* co najmniej trzy zapytania ``@media``, w tym wąski ekran (576px) i tryb ciemny,
* każda tabela na stronach ``/prawa/<slug>``, ``/tautologie`` i ``/formuly``
  stoi w opakowaniu ``.table-responsive``,
* dotyk i klawiatura: ``min-height: 44px`` dla przycisków i ``:focus-visible``,
* struktura nagłówków bez zmian — jedna ``<h1>`` na stronę.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import create_app
from app.logic.laws import all_laws

KATALOG = Path(__file__).resolve().parents[1]
KATALOG_CSS = KATALOG / "app" / "static" / "css"
ARKUSZ_APP = KATALOG_CSS / "app.css"
ARKUSZ_NAWIGACJI = KATALOG_CSS / "nawigacja.css"
SZABLON_BAZY = KATALOG / "app" / "templates" / "base.html"

#: Strony, na których każda tabela musi mieć opakowanie ``.table-responsive``.
ADRESY_Z_TABELAMI = ["/formuly", "/tautologie", "/prawa/<slug>"]

#: Zmienne palety wymagane przez kartę — nazwy bez wiodących ``--``.
ZMIENNE_PALETY = [
    "kolor-tlo",
    "kolor-akcent",
    "kolor-prawda",
    "kolor-falsz",
    "kolor-ramka",
    "cien",
    "kolor-formula",
]

#: Najmniejszy sensowny cel dotyku (wytyczne WCAG 2.5.8 / praktyka mobilna).
MINIMALNY_DOTYK = 44

#: Sześciocyfrowy albo trzyliterowy kolor zapisany wprost (``#fff``, ``#f7f7fb``).
KOLOR_WPROST = re.compile(r"#[0-9a-fA-F]{3,8}\b")

WZORZEC_TABELI = re.compile(r"<table\b", re.IGNORECASE)
WZORZEC_OPAKOWANIA_TABELI = re.compile(
    r'<div\b[^>]*class="[^"]*\btable-responsive\b[^"]*"[^>]*>\s*$',
    re.IGNORECASE,
)


def _rozwin(adresy: list[str]) -> list[str]:
    """Zamienia ``/prawa/<slug>`` na adres każdej strony prawa z rejestru."""
    rozwinięte: list[str] = []
    for adres in adresy:
        if adres.endswith("<slug>"):
            rozwinięte.extend(f"/prawa/{prawo.slug}" for prawo in all_laws())
        else:
            rozwinięte.append(adres)
    return rozwinięte


ADRESY_Z_TABELAMI_ROZWINIETE = _rozwin(ADRESY_Z_TABELAMI)


def _arkusz(sciezka: Path) -> str:
    """Zwraca treść arkusza jako jeden napis."""
    return sciezka.read_text(encoding="utf-8")


def _blok(css: str, naglowek: str) -> str:
    """Zwraca treść pierwszego bloku, którego nagłówek pasuje do ``naglowek``.

    ``naglowek`` to wyrażenie regularne bez klamry otwierającej, np. ``r":root\\b"``
    albo ``r"@media[^{]*max-width:\\s*576px"``. Blok kończymy po klamrach, więc
    zagnieżdżone reguły (np. całe zapytanie ``@media``) liczą się razem.
    """
    wzorzec = re.compile(naglowek + r"[^{]*\{", re.IGNORECASE)
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


def _blok_palety(css: str) -> str:
    """Zwraca treść pierwszego bloku ``:root`` arkusza."""
    return _blok(css, r":root\b")


def _blok_ciemny(css: str) -> str:
    """Zwraca treść bloku ``@media (prefers-color-scheme: dark)``."""
    return _blok(css, r"@media[^{]*prefers-color-scheme:\s*dark")


def _tabele_bez_opakowania(html: str) -> list[str]:
    """Zwraca początkowe fragmenty tabel, które nie stoją w ``.table-responsive``."""
    bez_opakowania: list[str] = []
    poprzedni_koniec = 0
    for dopasowanie in WZORZEC_TABELI.finditer(html):
        poprzedzajacy = html[poprzedni_koniec : dopasowanie.start()]
        poprzedni_koniec = dopasowanie.start()
        if not WZORZEC_OPAKOWANIA_TABELI.search(poprzedzajacy):
            poczatek = max(0, dopasowanie.start() - 60)
            bez_opakowania.append(html[poczatek : dopasowanie.start() + 40])
    return bez_opakowania


@pytest.fixture(scope="module")
def strony():
    """HTML stron sprawdzanych pod kątem opakowania tabel."""
    klient = create_app({"TESTING": True}).test_client()
    return {
        adres: klient.get(adres).get_data(as_text=True) for adres in ADRESY_Z_TABELAMI_ROZWINIETE
    }


# ---------------------------------------------------------------------------
# Paleta i zmienne
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("zmienna", ZMIENNE_PALETY)
def test_paleta_ma_zmienna(zmienna):
    """Karta PRZ-120: ``:root`` w ``app.css`` trzyma całą paletę projektu."""
    paleta = _blok_palety(_arkusz(ARKUSZ_APP))

    assert paleta, "app.css nie ma bloku :root z paletą"
    assert re.search(rf"--{re.escape(zmienna)}\s*:", paleta), f"brak zmiennej --{zmienna}"


def test_paleta_zbiera_kolory_w_jednym_miejscu():
    """Zmienne palety mają wartości, a nie odesłania do innych zmiennych."""
    paleta = _blok_palety(_arkusz(ARKUSZ_APP))

    for zmienna in ZMIENNE_PALETY:
        dopasowanie = re.search(rf"--{re.escape(zmienna)}\s*:\s*(?P<wartosc>[^;]+);", paleta)
        assert dopasowanie, f"brak wartości zmiennej --{zmienna}"
        assert "var(" not in dopasowanie["wartosc"], f"--{zmienna} wskazuje na inną zmienną"


def test_nawigacja_bierze_kolory_ze_zmiennych():
    """``nawigacja.css`` nie wpisuje kolorów na sztywno — inaczej tryb ciemny nie działa."""
    css = _arkusz(ARKUSZ_NAWIGACJI)

    kolory = sorted({kolor for kolor in KOLOR_WPROST.findall(css)})
    assert not kolory, f"nawigacja.css wpisuje kolory wprost: {kolory}"
    assert "var(--" in css, "nawigacja.css nie korzysta ze zmiennych palety"


# ---------------------------------------------------------------------------
# Zapytania @media i tryb ciemny
# ---------------------------------------------------------------------------


def test_arkusz_ma_co_najmniej_trzy_zapytania_media():
    css = _arkusz(ARKUSZ_APP)

    zapytania = re.findall(r"@media[^{]*", css)
    assert len(zapytania) >= 3, f"app.css ma {len(zapytania)} zapytań @media zamiast trzech"


@pytest.mark.parametrize("warunek", ["max-width: 576px", "prefers-color-scheme: dark"])
def test_arkusz_ma_zapytanie_o_podanym_warunku(warunek):
    css = _arkusz(ARKUSZ_APP)

    assert re.search(rf"@media[^{{]*{re.escape(warunek)}", css), f"brak @media {warunek}"


def test_tryb_ciemny_zmienia_tlo_tekst_i_ramki():
    """Tryb ciemny musi przełączyć paletę, a nie tylko dodać jeden kolor."""
    blok = _blok_ciemny(_arkusz(ARKUSZ_APP))

    for zmienna in ("--kolor-tlo", "--kolor-tekst", "--kolor-ramka", "--kolor-formula"):
        assert zmienna in blok, f"tryb ciemny nie zmienia {zmienna}"
    # Bootstrap 5.3 nie zna trybu systemowego (tylko `light` i `dark`), więc
    # jego własne zmienne też trzeba przełączyć — inaczej menu zostaje jasne.
    assert "--bs-body-bg" in blok, "tryb ciemny nie przełącza zmiennych Bootstrapa"


def test_tryb_ciemny_nie_jest_jasniejszy_od_trybu_jasnego():
    """Kontrola sensu: tło trybu ciemnego jest naprawdę ciemniejsze."""
    css = _arkusz(ARKUSZ_APP)
    jasne = re.search(r"--kolor-tlo\s*:\s*(#[0-9a-fA-F]{6})", _blok_palety(css))
    ciemne = re.search(r"--kolor-tlo\s*:\s*(#[0-9a-fA-F]{6})", _blok_ciemny(css))

    assert jasne and ciemne, "brak kolorów tła dla obu trybów"
    assert _jasnosc(ciemne.group(1)) < _jasnosc(jasne.group(1)), (
        f"tło trybu ciemnego {ciemne.group(1)} nie jest ciemniejsze od {jasne.group(1)}"
    )


def _jasnosc(kolor: str) -> float:
    """Przybliżona jasność koloru ``#rrggbb`` — do porównania dwóch teł."""
    skladowe = [int(kolor[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    return sum(skladowe) / 3


# ---------------------------------------------------------------------------
# Typografia, tabele i dotyk
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("naglowek", ["h1", "h2", "h3"])
def test_naglowki_skaluja_sie_z_oknem(naglowek):
    """Reguła, której selektor kończy się na samym nagłówku, musi mieć ``clamp()``."""
    css = _arkusz(ARKUSZ_APP)
    reguly = re.findall(rf"(?:\A|[,{{}}])\s*{naglowek}\s*\{{(?P<tresc>[^}}]*)\}}", css)

    assert reguly, f"brak reguły dla {naglowek}"
    assert any("clamp(" in tresc for tresc in reguly), (
        f"{naglowek} bez clamp() — hierarchia nie skaluje się z szerokością okna"
    )


def test_akapity_maja_maksymalna_szerokosc():
    """Długi wiersz męczy — karta prosi o 70ch."""
    assert "70ch" in _arkusz(ARKUSZ_APP), "brak limitu szerokości 70ch dla tekstu"


def test_naglowki_tabel_sa_przyklejone():
    """Nagłówek tabeli zostaje na ekranie, gdy tabela jest dłuższa niż okno."""
    css = _arkusz(ARKUSZ_APP)

    assert re.search(r"th[^{]*\{[^}]*position:\s*sticky", css), "brak przyklejonych nagłówków"


def test_waski_ekran_zwez_jaskami_tabeli():
    """Na telefonie tabela ma mniejsze komórki — inaczej wychodzi za ekran."""
    blok = _blok(_arkusz(ARKUSZ_APP), r"@media[^{]*max-width:\s*576px")

    assert "padding" in blok, "brak zwężenia komórek tabeli na wąskim ekranie"


def test_przyciski_maja_minimalny_cel_dotyku():
    css = _arkusz(ARKUSZ_APP)
    zmienna = re.search(r"--min-dotyk\s*:\s*(\d+)px", css)

    assert zmienna, "brak zmiennej --min-dotyk w :root"
    assert int(zmienna.group(1)) >= MINIMALNY_DOTYK, (
        f"cel dotyku {zmienna.group(1)}px jest mniejszy niż {MINIMALNY_DOTYK}px"
    )
    assert re.search(r"\.btn[^{]*\{[^}]*min-height:\s*var\(--min-dotyk\)", css), (
        "przyciski .btn nie mają wysokości z --min-dotyk"
    )


def test_focus_visible_dla_odnosnikow_i_przyciskow():
    """Karta prosi o jawny stan fokusu: obwódka 2px, widoczna też spod klawiatury."""
    css = _arkusz(ARKUSZ_APP)

    assert re.search(r"--ramka-focus\s*:\s*2px", css), "brak zmiennej --ramka-focus: 2px"
    regula = re.search(r"a:focus-visible[^{]*\{(?P<tresc>[^}]*)\}", css)
    assert regula, "brak reguły dla a:focus-visible"
    assert "button:focus-visible" in regula.group(0), "przyciski bez stanu :focus-visible"
    assert "outline: var(--ramka-focus)" in regula["tresc"], "obwódka fokusu poza zmienną"


def test_odnosniki_w_tresci_nie_sa_stykowe():
    """Dwa odnośniki obok siebie muszą mieć odstęp — inaczej łatwo kliknąć zły."""
    css = _arkusz(ARKUSZ_APP)

    assert re.search(r"main (p|li) a[^{]*\{[^}]*margin-inline:\s*0\.125em", css), (
        "brak odstępu 0.25em między odnośnikami w treści"
    )


# ---------------------------------------------------------------------------
# Tabele w HTML i struktura nagłówków
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("adres", ADRESY_Z_TABELAMI_ROZWINIETE, ids=ADRESY_Z_TABELAMI_ROZWINIETE)
def test_kazda_tabela_ma_opakowanie(strony, adres):
    bez_opakowania = _tabele_bez_opakowania(strony[adres])

    assert not bez_opakowania, (
        f'{adres}: tabela bez <div class="table-responsive"> — {bez_opakowania}'
    )


def test_strony_z_tabelami_faktycznie_maja_tabele(strony):
    """Kontrola sensu: bez tabel test opakowań byłby pusty."""
    razem = sum(len(WZORZEC_TABELI.findall(html)) for html in strony.values())

    assert razem > 0, "żadna sprawdzana strona nie ma tabeli"


@pytest.mark.parametrize("adres", ADRESY_Z_TABELAMI_ROZWINIETE, ids=ADRESY_Z_TABELAMI_ROZWINIETE)
def test_strona_ma_dokladnie_jeden_h1(strony, adres):
    """Karta PRZ-120 nie zmienia struktury nagłówków — treść nadal ma jedną <h1>."""
    assert len(re.findall(r"<h1\b", strony[adres])) == 1, f"{adres}: ma nie dokładnie jeden <h1>"


def test_szkielet_nie_wstawia_wlasnego_h1():
    """Nagłówek strony pochodzi z treści, nie z ``base.html``."""
    assert "<h1" not in _arkusz(SZABLON_BAZY)
