"""Testy danych reguły rezolucji i strony ``/rezolucja`` (karta PRZ-092).

Testy nie wierzą danym na słowo:

* każdą rezolucję liczą od nowa — sklejają literały klauzul rodziców i porównują
  wynik z klauzulą, którą podają dane (``_rezolwuj``); test nie powtarza logiki
  z modułu, tylko sprawdza jej wynik,
* wiersze dowodów porównują z tabelami ``docs/TRESC-WYKLAD2.md`` (sekcja
  „7. Algorytm rezolucji”) — numer, klauzula i kolumna „Skąd”,
* tezę przykładu 1 i sprzeczność założeń przykładu 2 sprawdzają silnikiem
  (``app.logic.truth``),
* tabelę na stronie porównują z ``proofs()`` wiersz po wierszu.

Liczba kroków. Kryterium karty mówi „10 i 7 (bez wiersza sprzeczności licząc)”.
Wiersz sprzeczności jest krokiem dowodu (niesie ``rodzaj == "sprzecznosc"`` i jako
ostatni wiersz zamyka tabelę), więc ``len(kroki)`` to 10 i 7 — dokładnie tyle wierszy
mają tabele wykładu. Sklejeń (``rodzaj == "rezolucja"``) jest w nich 4 i 2; osobny
test pilnuje obu tych liczb.

Plik ``app/static/js/rezolucja.js`` sprawdzamy statycznie — projekt nie ma runnera JS
(``AGENTS.md``). Pilnujemy importu ``createStepper``, czytania ``data-kroki``, strzałki
od ``rodzice`` z literałem, podświetlenia sprzeczności i braku ``innerHTML``.
"""

from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path

import pytest

from app import create_app
from app.blueprints import rezolucja as widok
from app.logic import truth
from app.logic.formula import Not, Or, Var, parse, to_text
from app.logic.resolution import (
    RODZAJ_NEGACJA_TEZY,
    RODZAJ_REZOLUCJA,
    RODZAJ_SPRZECZNOSC,
    RODZAJ_ZALOZENIE,
    ResolutionProof,
    ResolutionStep,
    proofs,
)

ADRES = "/rezolucja"

#: Rodzaje kroków dopuszczone w danych.
RODZAJE = (RODZAJ_ZALOZENIE, RODZAJ_NEGACJA_TEZY, RODZAJ_REZOLUCJA, RODZAJ_SPRZECZNOSC)

KATALOG_GLOWNY = Path(__file__).resolve().parents[1]
JS = KATALOG_GLOWNY / "app" / "static" / "js" / "rezolucja.js"
ARKUSZ = KATALOG_GLOWNY / "app" / "static" / "css" / "rezolucja.css"
SZABLON = KATALOG_GLOWNY / "app" / "templates" / "rezolucja.html"
WYKLAD = KATALOG_GLOWNY / "docs" / "TRESC-WYKLAD2.md"

#: Wiersz tabeli wykładu: ``| 6 | `q ∨ r` | 1, 3 (na `p`) |``.
WIERSZ_WYKLADU = re.compile(
    r"^\|\s*(?P<nr>\d+)\s*\|\s*`(?P<klauzula>[^`]+)`\s*\|\s*(?P<skad>[^|]+?)\s*\|\s*$",
    re.MULTILINE,
)

#: Sekcja „7. Algorytm rezolucji” — dwie tabele przykładów.
SEKCJA_ALGORYTMU = re.compile(r"## 7\. Algorytm rezolucji(?P<tresc>.*)", re.DOTALL)

#: Kolumna „Skąd” wiersza rezolucji: ``1, 3 (na `p`)``.
REZOLUCJA_W_SKAD = re.compile(r"(?P<rodzice>\d+(?:,\s*\d+)*)\s*\(na\s*`(?P<literal>[^`]+)`\)")

TABELA = re.compile(
    r'<table class="table tablica-rezolucji align-middle" data-tabela-rezolucji>'
    r"(?P<tresc>.*?)</table>",
    re.DOTALL,
)
WIERSZ_TABELI = re.compile(
    r'<tr\s+data-nr="(?P<nr>\d+)"\s+data-rodzaj="(?P<rodzaj>[a-z-]+)"(?P<atrybuty>[^>]*)>'
    r"(?P<komorki>.*?)</tr>",
    re.DOTALL,
)
KOMORKA_KLAUZULI = re.compile(r'<td class="formula">(?P<tresc>.*?)</td>', re.DOTALL)
KOMORKA_SKAD = re.compile(r"<td>\s*(?P<tresc>.*?)</td>", re.DOTALL)
KOMORKA_LITERALU = re.compile(r'<td class="literal">(?P<tresc>.*?)</td>', re.DOTALL)
KRESKA = re.compile(r'<div class="kreska-rezolucji" aria-hidden="true"></div>')
KROKI_JSON = re.compile(r'data-kroki="(?P<dane>[^"]*)"')
UKRYTY_OPIS = re.compile(r'<span class="visually-hidden">(?P<tresc>.*?)</span>', re.DOTALL)
ZNACZNIK = re.compile(r"<[^>]+>")
SPACJE = re.compile(r"\s+")
H1 = re.compile(r"<h1\b")
LI = re.compile(r"<li>")


@pytest.fixture(scope="module")
def klient():
    """Klient testowy aplikacji."""
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def html(klient) -> str:
    """Treść strony ``/rezolucja``."""
    return klient.get(ADRES).get_data(as_text=True)


@pytest.fixture(scope="module")
def wyklad() -> str:
    """Treść źródła prawdy wykładu 2."""
    return WYKLAD.read_text(encoding="utf-8")


def _zrodlo(sciezka: Path) -> str:
    """Czyta plik projektu jako UTF-8."""
    assert sciezka.is_file(), f"brak pliku {sciezka}"
    return sciezka.read_text(encoding="utf-8")


def _tekst(fragment: str) -> str:
    """Widoczny tekst fragmentu HTML — bez znaczników, ze odmienionymi encjami."""
    return SPACJE.sub(" ", unescape(ZNACZNIK.sub("", fragment))).strip()


def _literaly(klauzula: str) -> set[tuple[str, bool]]:
    """Literały klauzuli jako zbiór par ``(nazwa zmiennej, czy bez negacji)``."""
    return _literaly_wezla(parse(klauzula))


def _literaly_wezla(wezel) -> set[tuple[str, bool]]:
    """Rozkłada drzewo klauzuli na literały."""
    if isinstance(wezel, Or):
        return _literaly_wezla(wezel.left) | _literaly_wezla(wezel.right)
    if isinstance(wezel, Var):
        return {(wezel.name, True)}
    if isinstance(wezel, Not) and isinstance(wezel.child, Var):
        return {(wezel.child.name, False)}
    raise AssertionError(f"to nie jest klauzula: {to_text(wezel)}")


def _rezolwuj(pierwsza: str, druga: str, literal: str) -> set[tuple[str, bool]]:
    """Skleja dwie klauzule na literale — liczone niezależnie od danych strony."""
    a, b = _literaly(pierwsza), _literaly(druga)
    dodatni, ujemny = (literal, True), (literal, False)
    assert (dodatni in a) != (dodatni in b), f"literał {literal} nie jest w obu klauzulach"
    assert ujemny in a or ujemny in b, f"brak negacji literału {literal}"
    return (a | b) - {dodatni, ujemny}


def _wiersze_wykladu() -> list[list[dict[str, str]]]:
    """Wiersze obu tabel z sekcji „7. Algorytm rezolucji”, w kolejności wykładu."""
    tresc = SEKCJA_ALGORYTMU.search(_zrodlo(WYKLAD)).group("tresc")
    dowody: list[list[dict[str, str]]] = []
    for dopasowanie in WIERSZ_WYKLADU.finditer(tresc):
        if int(dopasowanie["nr"]) == 1:
            dowody.append([])
        dowody[-1].append(dopasowanie.groupdict())
    return dowody


def _komorka(wzorzec: re.Pattern[str], wiersz: str) -> str:
    """Tekst komórki dopasowanej wzorcem."""
    dopasowanie = wzorzec.search(wiersz)
    assert dopasowanie, f"brak komórki {wzorzec.pattern!r} w wierszu {wiersz[:80]!r}"
    return _tekst(dopasowanie["tresc"])


def _skad(tabela: str, nr: int) -> str:
    """Widoczny tekst kolumny „Skąd” — bez opisu dla czytnika ekranu."""
    wiersz = _wiersz_tabeli(tabela, nr)
    tresc = KOMORKA_SKAD.search(wiersz)["tresc"]
    return _tekst(UKRYTY_OPIS.sub("", tresc))


def _wyklad_plain() -> str:
    """Treść wykładu bez znaczników markdown i z pojedynczymi spacjami."""
    return SPACJE.sub(" ", _zrodlo(WYKLAD).replace("`", "").replace("*", ""))


def _wiersz_tabeli(tabela: str, nr: int) -> str:
    """HTML wiersza o podanym numerze."""
    for dopasowanie in WIERSZ_TABELI.finditer(tabela):
        if int(dopasowanie["nr"]) == nr:
            return dopasowanie.group(0)
    raise AssertionError(f"brak wiersza o numerze {nr}")


def _kroki_z_atrybutu(sekcja: str) -> list[dict]:
    """Kroki z atrybutu ``data-kroki`` (encje wracają do znaków)."""
    dopasowanie = KROKI_JSON.search(sekcja)
    assert dopasowanie, "sekcja dowodu bez atrybutu data-kroki"
    return json.loads(unescape(dopasowanie["dane"]))


# ---------------------------------------------------------------------------
# Dane: ``app.logic.resolution``
# ---------------------------------------------------------------------------


def test_proofs_zwraca_dwa_dowody():
    dowody = proofs()

    assert [dowod.id for dowod in dowody] == ["przyklad-1", "przyklad-2"]
    for dowod in dowody:
        assert isinstance(dowod, ResolutionProof)
        assert dowod.tytul.strip() and dowod.opis.strip()
        assert dowod.kroki and all(isinstance(krok, ResolutionStep) for krok in dowod.kroki)


def test_liczba_krokow_i_sklejen_jest_jak_w_wykladzie():
    """Kroków jest 10 i 7 (z wierszem sprzeczności), a sklejeń — 4 i 2."""
    liczba = [len(dowod.kroki) for dowod in proofs()]
    sklejenia = [
        len([krok for krok in dowod.kroki if krok.rodzaj == RODZAJ_REZOLUCJA]) for dowod in proofs()
    ]

    assert liczba == [10, 7]
    assert sklejenia == [4, 2]


def test_proofs_zwraca_kopie_listy():
    """Wołający nie może przez przypadek zmienić rejestru."""
    pierwsza = proofs()
    pierwsza.clear()

    assert len(proofs()) == 2


def test_wiersze_maja_kolejne_numery():
    for dowod in proofs():
        assert [krok.nr for krok in dowod.kroki] == list(range(1, len(dowod.kroki) + 1))


def test_rodzaje_krokow_sa_z_ustalonego_zbioru():
    for dowod in proofs():
        for krok in dowod.kroki:
            assert krok.rodzaj in RODZAJE, f"nieznany rodzaj {krok.rodzaj!r}"


def test_kazda_rezolucja_ma_dwoch_rodzicow_i_literal():
    for dowod in proofs():
        for krok in dowod.kroki:
            if krok.rodzaj != RODZAJ_REZOLUCJA:
                continue
            assert len(krok.rodzice) == 2, f"wiersz {krok.nr}: rodziców ma być dwóch"
            assert krok.literal, f"wiersz {krok.nr}: brak literału sklejenia"
            assert krok.rodzice == sorted(krok.rodzice), "numery rodziców rosnąco"
            assert all(1 <= nr < krok.nr for nr in krok.rodzice), "rodzic musi być wyżej"


def test_wiersze_z_wykladu_nie_maja_rodzicow_ani_literalu():
    for dowod in proofs():
        for krok in dowod.kroki:
            if krok.rodzaj in (RODZAJ_ZALOZENIE, RODZAJ_NEGACJA_TEZY, RODZAJ_SPRZECZNOSC):
                assert krok.rodzice == [] or krok.rodzaj == RODZAJ_SPRZECZNOSC
                assert krok.literal == "", f"wiersz {krok.nr}: literał ma być pusty"


def test_ostatni_krok_kazdego_dowodu_to_sprzecznosc():
    for dowod in proofs():
        ostatni = dowod.kroki[-1]

        assert ostatni.rodzaj == RODZAJ_SPRZECZNOSC
        assert len(ostatni.rodzice) == 2
        assert ostatni.literal == ""
        assert [krok for krok in dowod.kroki if krok.rodzaj == RODZAJ_SPRZECZNOSC] == [ostatni]


def test_kazda_rezolucja_jest_poprawnym_sklejeniem():
    """Klauzula wiersza musi być dokładnie wynikiem sklejenia jego rodziców."""
    for dowod in proofs():
        wiersze = {krok.nr: krok for krok in dowod.kroki}
        for krok in dowod.kroki:
            if krok.rodzaj != RODZAJ_REZOLUCJA:
                continue
            pierwszy, drugi = (wiersze[nr] for nr in krok.rodzice)
            wynik = _rezolwuj(pierwszy.klauzula, drugi.klauzula, krok.literal)

            assert wynik == _literaly(krok.klauzula), f"wiersz {krok.nr} nie jest sklejeniem"


def test_wiersz_sprzecznosci_ma_pare_literalow():
    """Rodzice wiersza sprzeczności muszą tworzyć parę ``x`` i ``∼x``."""
    for dowod in proofs():
        ostatni = dowod.kroki[-1]
        pierwszy, drugi = (dowod.kroki[nr - 1] for nr in ostatni.rodzice)
        a, b = _literaly(pierwszy.klauzula), _literaly(drugi.klauzula)
        pary = [literal for literal in a if (literal[0], not literal[1]) in b]

        assert pary, f"{dowod.id}: sprzeczne wiersze nie mają pary x i ∼x"


def test_przyklad_1_teza_wynika_z_zalozen():
    """Zdanie ze strony liczy silnik, nie wykonawca."""
    assert truth.is_tautology(parse("((p → q) ∧ (r → s) ∧ (p ∨ r)) → (p ∨ s)"))


def test_przyklad_2_zalozenia_sa_sprzeczne():
    assert truth.is_contradiction(parse("(p ∨ q) ∧ (p → q) ∧ (∼q ∨ r) ∧ ∼r"))


def test_przyklad_reguly_z_wykladu_jest_poprawnym_sklejeniem():
    """Przykład ze sekcji „6. Reguła rezolucji”: sklejenie na literale ``q``."""
    wynik = _rezolwuj(widok.PRZYKLAD_PRZESLANKI[0], widok.PRZYKLAD_PRZESLANKI[1], "q")

    assert wynik == _literaly(widok.PRZYKLAD_WNIOSEK)


def test_dane_zgadzaja_sie_z_tabelami_wykladu():
    tabele = _wiersze_wykladu()

    assert len(tabele) == len(proofs()) == 2
    for dowod, tabela in zip(proofs(), tabele, strict=True):
        assert len(dowod.kroki) == len(tabela), f"{dowod.id}: inna liczba wierszy niż w wykładzie"
        for krok, wiersz in zip(dowod.kroki, tabela, strict=True):
            assert krok.nr == int(wiersz["nr"])
            assert krok.klauzula == wiersz["klauzula"], f"{dowod.id}, wiersz {krok.nr}"


def test_rodzice_i_literal_zgadzaja_sie_z_kolumna_skad():
    """Kolumna „Skąd” wykładu mówi, z których wierszy i na czym sklejono."""
    for dowod, tabela in zip(proofs(), _wiersze_wykladu(), strict=True):
        for krok, wiersz in zip(dowod.kroki, tabela, strict=True):
            skad = wiersz["skad"]
            if krok.rodzaj == RODZAJ_REZOLUCJA:
                dopasowanie = REZOLUCJA_W_SKAD.fullmatch(skad)
                assert dopasowanie, f"{dowod.id}, wiersz {krok.nr}: {skad!r}"
                numery = [int(nr) for nr in dopasowanie["rodzice"].split(",")]
                assert numery == krok.rodzice
                assert dopasowanie["literal"] == krok.literal
            elif krok.rodzaj == RODZAJ_SPRZECZNOSC:
                assert skad == "—"
            elif krok.rodzaj == RODZAJ_NEGACJA_TEZY:
                assert skad == "negacja tezy"
            else:
                assert skad.startswith("założenie")


def test_teksty_zalozen_pochodza_z_wykladu():
    for dowod in proofs():
        zrodla = widok.ZRODLA_ZALOZEN.get(dowod.id, {})
        for krok in dowod.kroki:
            if krok.rodzaj != RODZAJ_ZALOZENIE or krok.nr not in zrodla:
                continue
            assert f"`{zrodla[krok.nr]}`" in _zrodlo(WYKLAD), f"brak formuły {zrodla[krok.nr]!r}"


def test_algorytm_ma_cztery_kroki_z_wykladu():
    assert len(widok.ALGORYTM) == 4
    wyklad = _wyklad_plain()
    for krok in widok.ALGORYTM:
        assert krok in wyklad, f"kroku algorytmu {krok!r} nie ma w wykładzie"


# ---------------------------------------------------------------------------
# Strona: nagłówek, sekcje, schemat reguły
# ---------------------------------------------------------------------------


def test_strona_odpowiada_200_i_html_utf8(klient):
    odpowiedz = klient.get(ADRES)

    assert odpowiedz.status_code == 200
    typ = odpowiedz.headers["Content-Type"]
    assert typ.startswith("text/html")
    assert "charset=utf-8" in typ.lower()


def test_strona_ma_dokladnie_jeden_h1(html):
    assert len(H1.findall(html)) == 1
    assert 'lang="pl"' in html


def test_strona_nie_zostawia_nieuzupelnionych_szablonow(html):
    assert "{{" not in html
    assert "{%" not in html


def test_strona_pokazuje_regule_rezolucji(html):
    assert 'id="sekcja-regula"' in html
    assert "Reguła rezolucji" in html
    assert "Literał to zmienna zdaniowa albo jej negacja" in html

    for wzor in (*widok.SCHEMAT_PRZESLANKI, widok.SCHEMAT_WNIOSEK):
        assert wzor in html, f"brak schematu {wzor!r}"


def test_strona_pokazuje_przyklad_reguly_z_wykladu(html):
    for wzor in (*widok.PRZYKLAD_PRZESLANKI, widok.PRZYKLAD_WNIOSEK):
        assert _tekst(widok.formula_to_html(wzor)) in _tekst(html), f"brak wzoru {wzor!r}"


def test_schemat_ma_kreske_jako_element_html(html):
    """Kreska to ``div.kreska-rezolucji`` malowany w CSS, a nie znak „—”."""
    assert len(KRESKA.findall(html)) == 2, "schemat reguły i przykład mają własną kreskę"

    styl = _zrodlo(ARKUSZ)
    assert ".kreska-rezolucji" in styl
    assert "border-top" in styl


def test_strona_pokazuje_algorytm_w_czterech_krokach(html):
    blok = re.search(
        r'<ol class="lista-algorytmu" id="lista-algorytmu">(.*?)</ol>', html, re.DOTALL
    )

    assert blok, "brak listy algorytmu"
    assert len(LI.findall(blok.group(0))) == 4
    for krok in widok.ALGORYTM:
        assert krok in html


def test_strona_odsyla_do_kpn_z_wykladu_1(html):
    assert 'href="/kpn"' in html
    assert "wykładu 1" in html


def test_strona_uzywa_notacji_wykladu(html):
    assert "∼" in html and "∨" in html
    assert "¬" not in html, "strona treści nie pokazuje notacji popularnej"
    assert "↔" not in html


def test_strona_odsyla_do_regul_wnioskowania(html):
    assert 'href="/reguly"' in html


# ---------------------------------------------------------------------------
# Strona: dwie tabele dowodów
# ---------------------------------------------------------------------------


def test_strona_ma_dwie_tabele_dowodow(html):
    assert len(TABELA.findall(html)) == 2
    assert html.count("data-tabela-rezolucji") == 2
    assert html.count("data-stepper") == 2, "każdy dowód ma własny pasek kroków"


def test_tabele_maja_tyle_wierszy_ile_danych(html):
    tabele = TABELA.findall(html)

    for dowod, tabela in zip(proofs(), tabele, strict=True):
        assert len(WIERSZ_TABELI.findall(tabela)) == len(dowod.kroki)


def test_wiersze_tabeli_zgadzaja_sie_z_danymi(html):
    for dowod, tabela in zip(proofs(), TABELA.findall(html), strict=True):
        for krok in dowod.kroki:
            wiersz = _wiersz_tabeli(tabela, krok.nr)

            assert f'data-rodzaj="{krok.rodzaj}"' in wiersz
            oczekiwana = _tekst(widok.formula_to_html(krok.klauzula))
            assert _komorka(KOMORKA_KLAUZULI, wiersz) == oczekiwana, f"wiersz {krok.nr}"


def test_kolumna_literalu_pokazuje_literal_sklejenia(html):
    for dowod, tabela in zip(proofs(), TABELA.findall(html), strict=True):
        for krok in dowod.kroki:
            wiersz = _wiersz_tabeli(tabela, krok.nr)
            tresc = _komorka(KOMORKA_LITERALU, wiersz)

            if krok.rodzaj == RODZAJ_REZOLUCJA:
                assert tresc == krok.literal, f"wiersz {krok.nr}"
            else:
                assert tresc == "—"


def test_kolumna_skad_zalezy_od_rodzaju_kroku(html):
    for dowod, tabela in zip(proofs(), TABELA.findall(html), strict=True):
        zrodla = widok.ZRODLA_ZALOZEN.get(dowod.id, {})
        for krok in dowod.kroki:
            skad = _skad(tabela, krok.nr)

            if krok.rodzaj == RODZAJ_REZOLUCJA:
                assert skad == ", ".join(str(nr) for nr in krok.rodzice)
            elif krok.rodzaj == RODZAJ_NEGACJA_TEZY:
                assert skad == "negacja tezy"
            elif krok.rodzaj == RODZAJ_SPRZECZNOSC:
                assert skad == "—"
            else:
                assert skad == f"założenie {zrodla.get(krok.nr, '')}".strip()


def test_wiersze_sprzeczne_maja_klase_i_opis_slowny(html):
    for dowod, tabela in zip(proofs(), TABELA.findall(html), strict=True):
        ostatni = dowod.kroki[-1]
        oczekiwane = {ostatni.nr, *ostatni.rodzice}
        # Dokładny zapis atrybutu: ``class="&quot;wiersz-sprzecznosc&quot;"`` nie zadziała
        # w przeglądarce, więc test pilnuje klasy bez encji.
        z_klasa = {
            int(dopasowanie["nr"])
            for dopasowanie in WIERSZ_TABELI.finditer(tabela)
            if ' class="wiersz-sprzecznosc"' in dopasowanie["atrybuty"]
        }

        assert z_klasa == oczekiwane, f"{dowod.id}: wiersze sprzeczne to {oczekiwane}"
        assert f"Sprzeczność {ostatni.rodzice[0]}, {ostatni.rodzice[1]}" in unescape(tabela)
        assert "wiersz sprzeczny z wierszem" in unescape(tabela), "brak opisu słownego"


def test_strona_bez_javascriptu_pokazuje_cale_tabele(html):
    """Wiersze są w HTML — żaden atrybut ``hidden`` nie ukrywa ich po stronie serwera."""
    assert " hidden" not in html
    assert "Prowadzenie krok po kroku wymaga włączonego JavaScriptu" in html


# ---------------------------------------------------------------------------
# Strona: dane dla skryptu (``data-kroki``)
# ---------------------------------------------------------------------------


def test_kroki_dla_skryptu_zgadzaja_sie_z_danymi(html):
    sekcje = html.split("data-dowod-rezolucji=")[1:]

    assert len(sekcje) == 2
    for dowod, sekcja in zip(proofs(), sekcje, strict=True):
        kroki = _kroki_z_atrybutu(sekcja)
        assert len(kroki) == len(dowod.kroki)
        for krok, dane in zip(dowod.kroki, kroki, strict=True):
            assert dane["nr"] == krok.nr
            assert dane["rodzaj"] == krok.rodzaj
            assert dane["rodzice"] == krok.rodzice
            assert dane["literal"] == krok.literal
            assert dane["tytul"].startswith(f"{krok.nr}.")
            assert dane["opis"].strip(), f"krok {krok.nr} bez opisu"


def test_opis_kroku_rezolucji_mowi_o_rodzicach_i_literale():
    for dowod in proofs():
        for krok, dane in zip(dowod.kroki, widok.kroki_dowodu(dowod), strict=True):
            if krok.rodzaj != RODZAJ_REZOLUCJA:
                continue
            assert f"wiersze {krok.rodzice[0]} i {krok.rodzice[1]}" in dane["opis"]
            assert f"na literale {krok.literal}" in dane["opis"]


def test_strona_ma_kontener_na_strzalki(html):
    assert html.count("data-strzalki") == 2


def test_widok_jest_zarejestrowany():
    app = create_app({"TESTING": True})

    assert "rezolucja" in app.config["BLUEPRINTS"]


# ---------------------------------------------------------------------------
# Plik JavaScript
# ---------------------------------------------------------------------------


def test_skrypt_istnieje_i_nie_jest_pusty():
    assert JS.is_file(), f"brak pliku {JS}"
    assert JS.stat().st_size > 0, "plik JavaScript jest pusty"


def test_skrypt_korzysta_z_wspolnego_paska_krokow():
    zrodlo = _zrodlo(JS)

    assert 'from "/static/js/stepper.js"' in zrodlo, "brak importu stepper.js"
    assert "createStepper(" in zrodlo, "skrypt nie tworzy paska kroków"


def test_skrypt_czyta_kroki_z_atrybutu():
    zrodlo = _zrodlo(JS)

    assert "dataset.kroki" in zrodlo, "skrypt nie czyta atrybutu data-kroki"
    assert "JSON.parse" in zrodlo
    assert "data-dowod-rezolucji" in zrodlo, "skrypt nie szuka sekcji dowodów"


def test_skrypt_rysuje_strzalke_od_rodzicow_z_literalem():
    zrodlo = _zrodlo(JS)

    assert "krok.rodzice" in zrodlo, "strzałka nie bierze rodziców z kroku"
    assert '"→"' in zrodlo, "brak znaku strzałki"
    assert "strzalka-rezolucji" in zrodlo, "brak klasy strzałki"
    assert "na ${krok.literal}" in zrodlo, "etykieta strzałki bez literału"
    assert "aria-label" in zrodlo, "strzałka bez opisu słownego"


def test_skrypt_podswietla_sprzeczne_wiersze():
    zrodlo = _zrodlo(JS)

    assert "wiersz-podswietlony" in zrodlo
    assert "sprzecznosc" in zrodlo, "skrypt nie rozpoznaje ostatniego kroku"
    assert "wiersz-biezacy" in zrodlo and "wiersz-rodzic" in zrodlo


def test_skrypt_dodaje_wiersze_krok_po_kroku():
    zrodlo = _zrodlo(JS)

    assert "hidden" in zrodlo, "skrypt nie ukrywa jeszcze nieodkrytych wierszy"
    assert "data-nr" in zrodlo or "dataset.nr" in zrodlo, "skrypt nie szuka wiersza po numerze"


def test_skrypt_nie_wstawia_tresci_przez_innerhtml():
    assert ".innerHTML" not in _zrodlo(JS), "treść ma trafiać przez textContent"


def test_skrypt_nie_uzywa_eval():
    assert "eval(" not in _zrodlo(JS)


# ---------------------------------------------------------------------------
# Arkusz stylów i szablon
# ---------------------------------------------------------------------------


def test_arkusz_stylow_ma_klasy_stanu_tabeli():
    styl = _zrodlo(ARKUSZ)

    for klasa in (
        "wiersz-sprzecznosc",
        "wiersz-podswietlony",
        "wiersz-biezacy",
        "wiersz-rodzic",
        "strzalka-rezolucji",
    ):
        assert f".{klasa}" in styl, f"brak stylu dla .{klasa}"
    assert "[hidden]" in styl, "ukryte wiersze muszą znikać z tabeli"


def test_szablon_siega_po_dane_z_widoku():
    """Szablon nie wpisuje klauzul ręcznie — dostaje je z ``proofs()``."""
    zrodlo = _zrodlo(SZABLON)

    assert "dowod.wiersze" in zrodlo
    assert "dowod.kroki_json" in zrodlo
    assert "partials/_stepper.html" in zrodlo
    dluzsze = [krok.klauzula for dowod in proofs() for krok in dowod.kroki if "∨" in krok.klauzula]
    assert dluzsze, "dane nie mają klauzul z alternatywą"
    for klauzula in dluzsze:
        assert klauzula not in zrodlo, f"klauzula {klauzula!r} wpisana do szablonu"
