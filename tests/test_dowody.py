"""Testy danych dowodów założeniowych i strony ``/dowody`` (karta PRZ-091).

Testy nie wierzą danym na słowo:

* wiersze każdego dowodu porównują z tabelami ``docs/TRESC-WYKLAD2.md`` (sekcje
  „3. Dowód założeniowy wprost” i „4. Dowód założeniowy nie wprost”) — numer, formuła
  i uzasadnienie. Dokument jest źródłem prawdy, więc ten test pilnuje, że nic nie
  zostało przepisane po swojemu,
* każdą tezę liczą od nowa przez ``truth.is_tautology`` — dowód ma sens tylko wtedy,
  gdy teza naprawdę jest tautologią,
* numery z pola ``z`` sprawdzają wobec numerów wierszy tego samego dowodu, a kody
  reguł z uzasadnień — wobec rejestru ``app.logic.rules``,
* tabelę na stronie porównują z ``proofs()`` wiersz po wierszu (osobno liczby wierszy
  i wiersze sprzeczności).

Plik ``app/static/js/dowody.js`` sprawdzamy statycznie — projekt nie ma runnera JS
(``AGENTS.md``). Pilnujemy importu ``createStepper``, czytania ``data-kroki``,
strzałki od wierszy z listy ``z``, podświetlenia pary sprzecznej i braku ``innerHTML``.
"""

from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path

import pytest

from app import create_app
from app.blueprints import dowody as widok
from app.logic import rules as rejestr_regul
from app.logic import truth
from app.logic.formula import FormulaError, parse, to_html
from app.logic.proofs import (
    DODATKOWE_ZALOZENIE,
    RODZAJ_NIE_WPROST,
    RODZAJ_WIELOKROTNE,
    RODZAJ_WPROST,
    UZASADNIENIA_BEZ_Z,
    Proof,
    get,
    is_contradiction,
    proofs,
)

ADRES = "/dowody"

#: Dowody w kolejności z wykładu.
ID_DOWODOW = ["A", "B", "C", "D", "E", "F"]

#: Rodzaje dowodów dopuszczone w danych.
RODZAJE = (RODZAJ_WPROST, RODZAJ_NIE_WPROST, RODZAJ_WIELOKROTNE)

KATALOG_GLOWNY = Path(__file__).resolve().parents[1]
JS = KATALOG_GLOWNY / "app" / "static" / "js" / "dowody.js"
ARKUSZ = KATALOG_GLOWNY / "app" / "static" / "css" / "dowody.css"
SZABLON = KATALOG_GLOWNY / "app" / "templates" / "dowody.html"
WYKLAD = KATALOG_GLOWNY / "docs" / "TRESC-WYKLAD2.md"

#: Nagłówek dowodu w wykładzie: ``### Dowód A — `((p → q) ∧ (q → r)) → (p → r)```.
#: Dowód F ma przed wzorem jeszcze słowa („wielokrotne założenia: …”), więc wzór
#: wyciągamy z reszty nagłówka, a nie z całego ogona.
NAGLOWEK_DOWODU = re.compile(r"^### Dowód (?P<id>[A-F]) — (?P<reszta>.+)$", re.MULTILINE)

#: Wzór w nagłówku dowodu — pierwszy napis w odwrotnych apostrofach.
TEZA_NAGLOWKA = re.compile(r"`(?P<teza>[^`]+)`")

#: Początek następnej sekcji wykładu — koniec tabeli danego dowodu.
NASTEPNA_SEKCJA = re.compile(r"^#{2,3} ", re.MULTILINE)

#: Wiersz tabeli wykładu: ``| 5 | `q` | RO 2, 3 |``.
WIERSZ_WYKLADU = re.compile(
    r"^\|\s*(?P<nr>\d+(?:\.\d+)?)\s*\|\s*`(?P<formula>[^`]+)`\s*"
    r"\|\s*(?P<uzasadnienie>[^|]+?)\s*\|\s*$",
    re.MULTILINE,
)

#: Jeden dowód na stronie — od znacznika sekcji do jej zamknięcia.
SEKCJA_DOWODU = re.compile(
    r'<section\s+class="sekcja dowod"\s+id="dowod-(?P<id>[a-f])".*?</section>',
    re.DOTALL,
)
WIERSZ_TABELI = re.compile(
    r'<tr\s+class="(?P<klasy>[^"]*)"\s+data-nr="(?P<nr>[^"]+)"(?P<atrybuty>[^>]*)>'
    r"(?P<komorki>.*?)</tr>",
    re.DOTALL,
)
KOMORKA_FORMULY = re.compile(r'<td class="wiersz-formula formula">(?P<tresc>.*?)</td>', re.DOTALL)
KROKI_JSON = re.compile(r'data-kroki="(?P<dane>[^"]*)"')
ZNACZNIK = re.compile(r"<[^>]+>")
SPACJE = re.compile(r"\s+")
H1 = re.compile(r"<h1\b")
KOD_REGULY = re.compile(r"^[A-Z][A-Z0-9]+$")


@pytest.fixture(scope="module")
def klient():
    """Klient testowy aplikacji."""
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def html(klient) -> str:
    """Treść strony ``/dowody``."""
    return klient.get(ADRES).get_data(as_text=True)


@pytest.fixture(scope="module")
def wyklad() -> str:
    """Treść źródła prawdy wykładu 2."""
    return WYKLAD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tabele_wykladu(wyklad) -> dict[str, tuple[str, list[tuple[str, str, str]]]]:
    """Tabele dowodów A–F z wykładu: identyfikator → ``(teza, wiersze)``."""
    return _tabele_wykladu(wyklad)


def _zrodlo(sciezka: Path) -> str:
    """Czyta plik projektu jako UTF-8."""
    assert sciezka.is_file(), f"brak pliku {sciezka}"
    return sciezka.read_text(encoding="utf-8")


def _tekst(fragment: str) -> str:
    """Widoczny tekst fragmentu HTML — bez znaczników, ze odmienionymi encjami."""
    return SPACJE.sub(" ", unescape(ZNACZNIK.sub("", fragment))).strip()


def _tabele_wykladu(wyklad: str) -> dict[str, tuple[str, list[tuple[str, str, str]]]]:
    """Czyta z wykładu tabele dowodów: identyfikator → ``(teza, wiersze)``.

    Fragment dowodu kończy się na nagłówku następnej sekcji, żeby tabela dowodu F nie
    połknęła tabel rezolucji z sekcji 7.
    """
    tabele: dict[str, tuple[str, list[tuple[str, str, str]]]] = {}
    for naglowek in NAGLOWEK_DOWODU.finditer(wyklad):
        nastepna = NASTEPNA_SEKCJA.search(wyklad, naglowek.end())
        fragment = wyklad[naglowek.end() : nastepna.start() if nastepna else len(wyklad)]
        teza = TEZA_NAGLOWKA.search(naglowek["reszta"])
        assert teza is not None, f"nagłówek dowodu {naglowek['id']} bez wzoru"
        wiersze = [
            (wiersz["nr"], wiersz["formula"], wiersz["uzasadnienie"])
            for wiersz in WIERSZ_WYKLADU.finditer(fragment)
        ]
        tabele[naglowek["id"]] = (teza["teza"], wiersze)
    return tabele


def _sekcje(html: str) -> dict[str, str]:
    """Sekcje dowodów ze strony: identyfikator → fragment HTML."""
    return {sekcja["id"].upper(): sekcja.group(0) for sekcja in SEKCJA_DOWODU.finditer(html)}


def _wiersze_html(sekcja: str) -> list[re.Match]:
    """Wiersze tabeli dowodu w HTML."""
    return list(WIERSZ_TABELI.finditer(sekcja))


def _kroki_json(sekcja: str) -> list[dict]:
    """Kroki jednego dowodu z atrybutu ``data-kroki``."""
    dopasowanie = KROKI_JSON.search(sekcja)
    assert dopasowanie is not None, "brak atrybutu data-kroki"
    return json.loads(unescape(dopasowanie["dane"]))


def _dowod(proof_id: str) -> Proof:
    """Dowód z rejestru — testy nie zakładają kolejności listy."""
    dowod = get(proof_id)
    assert dowod is not None
    return dowod


# ---------------------------------------------------------------------------
# Dane dowodów
# ---------------------------------------------------------------------------


def test_rejestr_ma_szesc_dowodow_w_kolejnosci_wykladu():
    assert [dowod.id for dowod in proofs()] == ID_DOWODOW


def test_rejestr_oddaje_kopie_listy():
    """Wołający nie może zmienić rejestru przez przypadek."""
    pierwsza = proofs()
    pierwsza.clear()

    assert len(proofs()) == len(ID_DOWODOW)


def test_get_zna_wielkosc_liter_i_spacje():
    assert get("A") is not None
    assert get(" a ") is get("A")
    assert get("f") is get("F")
    assert get("Z") is None


def test_wiersze_zgodne_z_wykladem(tabele_wykladu):
    """Criterion karty: wiersze dokładnie jak w ``docs/TRESC-WYKLAD2.md``."""
    assert sorted(tabele_wykladu) == ID_DOWODOW

    for dowod in proofs():
        teza, wiersze = tabele_wykladu[dowod.id]

        assert dowod.teza == teza, f"dowód {dowod.id}: inna teza niż w wykładzie"
        assert [(w.nr, w.formula, w.uzasadnienie) for w in dowod.wiersze] == wiersze, (
            f"dowód {dowod.id}: wiersze inne niż w wykładzie"
        )


def test_kazdy_dowod_ma_rodzaj_z_listy():
    for dowod in proofs():
        assert dowod.rodzaj in RODZAJE, f"dowód {dowod.id}: nieznany rodzaj {dowod.rodzaj}"


def test_rodzaje_dowodow_sa_zgodne_z_wykladem():
    """A i B są wprost (sekcja 3), C–E nie wprost (sekcja 4), F ma dodatkowe założenia."""
    rodzaje = {dowod.id: dowod.rodzaj for dowod in proofs()}

    assert rodzaje == {
        "A": RODZAJ_WPROST,
        "B": RODZAJ_WPROST,
        "C": RODZAJ_NIE_WPROST,
        "D": RODZAJ_NIE_WPROST,
        "E": RODZAJ_NIE_WPROST,
        "F": RODZAJ_WIELOKROTNE,
    }


def test_tytul_i_opis_nie_sa_puste():
    for dowod in proofs():
        assert dowod.tytul.strip()
        assert dowod.opis.strip().endswith("."), f"dowód {dowod.id}: opis to nie zdanie"


def test_kazda_teza_jest_tautologia():
    """Dowód ma sens tylko wtedy, gdy teza naprawdę jest tautologią."""
    for dowod in proofs():
        drzewo = parse(dowod.teza)

        assert truth.is_tautology(drzewo), f"dowód {dowod.id}: teza nie jest tautologią"


def test_kazdy_wiersz_poza_zalozeniem_wskazuje_zrodla():
    """Criterion karty: każdy wiersz poza założeniami ma niepustą listę ``z``."""
    for dowod in proofs():
        for wiersz in dowod.wiersze:
            if wiersz.uzasadnienie in UZASADNIENIA_BEZ_Z:
                assert wiersz.z == [], f"{dowod.id}/{wiersz.nr}: założenie nie ma źródeł"
            else:
                assert wiersz.z, f"{dowod.id}/{wiersz.nr}: brak źródeł wiersza"


def test_z_wskazuje_istniejace_wiersze_tego_samego_dowodu():
    for dowod in proofs():
        numery = {wiersz.nr for wiersz in dowod.wiersze}

        for wiersz in dowod.wiersze:
            for zrodlo in wiersz.z:
                assert zrodlo in numery, f"{dowod.id}/{wiersz.nr}: nie ma wiersza {zrodlo}"
            assert wiersz.nr not in wiersz.z, f"{dowod.id}/{wiersz.nr}: wiersz z siebie"


def test_formuly_wierszy_sie_parsuja():
    """Criterion karty: każda formuła poza wierszem sprzeczności parsuje się."""
    for dowod in proofs():
        for wiersz in dowod.wiersze:
            if is_contradiction(wiersz):
                with pytest.raises(FormulaError):
                    parse(wiersz.formula)
                continue

            parse(wiersz.formula)  # brak wyjątku = formuła poprawna


def test_z_zgadza_sie_z_uzasadnieniem():
    """Numery wypisane w uzasadnieniu („RO 2, 3”) to dokładnie lista ``z`` wiersza."""
    for dowod in proofs():
        for wiersz in dowod.wiersze:
            if wiersz.uzasadnienie in UZASADNIENIA_BEZ_Z or is_contradiction(wiersz):
                continue

            wymienione = re.findall(r"\d+(?:\.\d+)?", wiersz.uzasadnienie.split(maxsplit=1)[1])

            assert wymienione == wiersz.z, f"{dowod.id}/{wiersz.nr}: „{wiersz.uzasadnienie}”"


def test_wiersz_sprzecznosci_wymienia_swoje_zrodla():
    """„Sprzeczność 5, 7” wskazuje dokładnie wiersze 5 i 7 — i żadne inne."""
    for dowod in proofs():
        for wiersz in dowod.wiersze:
            if not is_contradiction(wiersz):
                continue

            wymienione = re.findall(r"\d+(?:\.\d+)?", wiersz.formula)
            assert wymienione == wiersz.z, f"{dowod.id}/{wiersz.nr}: numery ≠ lista z"


def test_wiersz_sprzecznosci_zamyka_dowod_nie_wprost():
    """Dowód wprost kończy teza, dowód nie wprost — sprzeczność w ostatnim wierszu."""
    for dowod in proofs():
        ostatni = dowod.wiersze[-1]
        sprzecznosci = [w for w in dowod.wiersze if is_contradiction(w)]

        if dowod.rodzaj == RODZAJ_WPROST:
            assert sprzecznosci == []
            continue

        # Dowód z wielokrotnymi założeniami zamyka każdy przypadek osobną sprzecznością.
        assert is_contradiction(ostatni), f"dowód {dowod.id}: sprzeczność nie zamyka dowodu"
        if dowod.rodzaj == RODZAJ_NIE_WPROST:
            assert sprzecznosci == [ostatni]


def test_wielokrotne_zalozenia_maja_wciete_wiersze():
    """Dowód F rozbija się na dwa przypadki: 4.1–4.4 oraz 5.1–5.4."""
    numery = [wiersz.nr for wiersz in _dowod("F").wiersze]
    wciete = [nr for nr in numery if "." in nr]

    assert wciete == ["4.1", "4.2", "4.3", "4.4", "5.1", "5.2", "5.3", "5.4"]

    # Każdy przypadek otwiera dodatkowe założenie: nie ma źródeł, bo niczego nie wyprowadza.
    for nr in ("4.1", "5.1"):
        podzalozenie = [wiersz for wiersz in _dowod("F").wiersze if wiersz.nr == nr][0]
        assert podzalozenie.uzasadnienie == DODATKOWE_ZALOZENIE
        assert podzalozenie.z == []


def test_kody_regul_istnieja_w_rejestrze_regul():
    """Uzasadnienia powołują się tylko na reguły, które są na stronie ``/reguly``."""
    for dowod in proofs():
        for wiersz in dowod.wiersze:
            kod = widok._kod_reguly(wiersz)
            if kod:
                assert rejestr_regul.get(kod) is not None, f"{dowod.id}: nieznany kod {kod}"
            elif wiersz.uzasadnienie not in UZASADNIENIA_BEZ_Z:
                assert is_contradiction(wiersz), f"{dowod.id}/{wiersz.nr}: brak kodu reguły"


def test_zalozenia_nie_maja_kodu_reguly():
    for dowod in proofs():
        for wiersz in dowod.wiersze:
            if wiersz.uzasadnienie in UZASADNIENIA_BEZ_Z:
                assert widok._kod_reguly(wiersz) == ""
                assert widok._nazwa_reguly(wiersz) == ""


def test_nazwa_reguly_zgadza_sie_z_rejestrem():
    """Kod z uzasadnienia prowadzi do pełnej nazwy z ``/reguly``."""
    for dowod in proofs():
        for wiersz in dowod.wiersze:
            kod = widok._kod_reguly(wiersz)
            if not kod:
                continue

            regula = rejestr_regul.get(kod)
            assert regula is not None
            assert widok._nazwa_reguly(wiersz) == regula.nazwa


def test_wymien_odmienia_polskie_listy():
    assert widok._wymien([]) == ""
    assert widok._wymien(["2"]) == "2"
    assert widok._wymien(["2", "3"]) == "2 i 3"
    assert widok._wymien(["1", "2", "3"]) == "1, 2 i 3"


# ---------------------------------------------------------------------------
# Widok /dowody
# ---------------------------------------------------------------------------


def test_strona_zwraca_200(klient):
    odpowiedz = klient.get(ADRES)

    assert odpowiedz.status_code == 200


def test_strona_ma_jeden_h1(html):
    assert len(H1.findall(html)) == 1
    assert "<h1>Dowody założeniowe</h1>" in html


def test_strona_ma_szesc_sekcji_dowodow(html):
    sekcje = _sekcje(html)

    assert sorted(sekcje) == ID_DOWODOW
    for identyfikator, sekcja in sekcje.items():
        assert f'<h2 id="naglowek-dowod-{identyfikator.lower()}">' in sekcja


def test_strona_pokazuje_teze_kazdego_dowodu(html):
    for dowod in proofs():
        assert to_html(parse(dowod.teza)) in html, f"dowód {dowod.id}: brak tezy w HTML"


def test_strona_ma_tyle_wierszy_ile_w_danych(html):
    """Criterion karty: w HTML jest łącznie tyle wierszy, ile w danych."""
    sekcje = _sekcje(html)

    for dowod in proofs():
        wiersze = _wiersze_html(sekcje[dowod.id])

        assert len(wiersze) == len(dowod.wiersze), f"dowód {dowod.id}: inna liczba wierszy"
        assert [w["nr"] for w in wiersze] == [w.nr for w in dowod.wiersze]


def test_wiersze_niosa_tylko_swoje_klasy(html):
    """Klasy wcięcia i sprzeczności stoją tylko przy wierszach, które ich potrzebują."""
    sekcje = _sekcje(html)

    for dowod in proofs():
        for wiersz_html, wiersz in zip(_wiersze_html(sekcje[dowod.id]), dowod.wiersze, strict=True):
            klasy = wiersz_html["klasy"].split()

            assert "wiersz-dowodu" in klasy
            assert ("wiersz-wciety" in klasy) is ("." in wiersz.nr)
            assert ("wiersz-sprzecznosc" in klasy) is is_contradiction(wiersz)


def test_wiersz_sprzecznosci_ma_arie_po_polsku(html):
    """Criterion karty: wiersz sprzeczności ma klasę i polski ``aria-label``."""
    sekcje = _sekcje(html)
    znalezione = 0

    for dowod in proofs():
        for wiersz_html, wiersz in zip(_wiersze_html(sekcje[dowod.id]), dowod.wiersze, strict=True):
            if not is_contradiction(wiersz):
                continue

            znalezione += 1
            opis = unescape(re.search(r'aria-label="([^"]*)"', wiersz_html["atrybuty"])[1])
            assert f"Wiersz {wiersz.nr}" in opis
            assert "sprzeczność wierszy" in opis
            assert "Koniec dowodu" in opis
            for numer in wiersz.z:
                assert numer in opis

    oczekiwane = sum(
        1 for dowod in proofs() for wiersz in dowod.wiersze if is_contradiction(wiersz)
    )
    assert znalezione == oczekiwane == 5


def test_strona_pokazuje_wzory_z_formula_to_html(html):
    """Wzory rysuje ten sam kod co na pozostałych stronach, nie wpisany ręcznie napis."""
    for dowod in proofs():
        for wiersz in dowod.wiersze:
            if is_contradiction(wiersz):
                continue
            assert to_html(parse(wiersz.formula)) in html, f"{dowod.id}/{wiersz.nr}"


def test_strona_pokazuje_pelne_nazwy_regul(html):
    """Kod z uzasadnienia prowadzi do pełnej nazwy reguły także na stronie."""
    nazwy = {
        wiersz["nazwa_reguly"]
        for dowod in proofs()
        for wiersz in widok._dowod_widoku(dowod)["wiersze"]
    }
    nazwy.discard("")

    assert nazwy, "żadna reguła nie ma pełnej nazwy w tabelach"
    for nazwa in nazwy:
        assert nazwa in html


def test_wiersze_poddowodu_sa_podpisane(html):
    """Wiersze 4.1 i 5.1 mają uzasadnienie „Dodatkowe założenie”."""
    sekcja = _sekcje(html)["F"]
    wiersze = _wiersze_html(sekcja)

    assert sum(1 for w in wiersze if "Dodatkowe założenie" in w["komorki"]) == 2
    assert len([w for w in wiersze if "wiersz-wciety" in w["klasy"]]) == 8


def test_strona_podaje_kroki_dla_kazdego_dowodu(html):
    sekcje = _sekcje(html)

    for dowod in proofs():
        kroki = _kroki_json(sekcje[dowod.id])

        assert len(kroki) == len(dowod.wiersze)
        assert [krok["nr"] for krok in kroki] == [wiersz.nr for wiersz in dowod.wiersze]
        for krok, wiersz in zip(kroki, dowod.wiersze, strict=True):
            assert krok["tytul"] == f"Wiersz {wiersz.nr}"
            assert krok["opis"]
            assert krok["z"] == wiersz.z
            assert krok["sprzecznosc"] is is_contradiction(wiersz)


def test_kroki_niosa_kod_i_nazwe_reguly(html):
    """Skrypt rysuje „RO (Reguła odrywania)” — dane kroku muszą mieć oba napisy."""
    kroki = _kroki_json(_sekcje(html)["D"])
    wiersz_9 = [krok for krok in kroki if krok["nr"] == "9"][0]

    assert wiersz_9["regula"] == "RO"
    assert wiersz_9["regula_nazwa"] == "Reguła odrywania"
    assert wiersz_9["z"] == ["5", "7"]


def test_bez_javascriptu_wszystkie_wiersze_sa_widoczne(html):
    """Tabela w HTML nie ma ukrytych wierszy — bez skryptu widać cały dowód."""
    sekcje = _sekcje(html)

    for dowod in proofs():
        assert "hidden" not in "".join(w.group(0) for w in _wiersze_html(sekcje[dowod.id]))


def test_strona_ma_sekcje_o_kontrprzykladzie(html):
    """Criterion karty: sekcja o kontrprzykładzie z dwoma przykładami."""
    assert 'id="skad-kontrprzyklad"' in html
    assert "Skąd kontrprzykład" in html

    tabela = html.split('id="skad-kontrprzyklad"', 1)[1]
    for przyklad in widok.PRZYKLADY_KONTRPRZYKLADU:
        assert przyklad["rozumowanie"].split(",")[0] in tabela
        assert przyklad["kontrprzyklad"] in tabela


def test_wzory_kontrprzykladow_sie_parsuja(html):
    fragment = html.split('id="skad-kontrprzyklad"', 1)[1]

    for przyklad in widok.PRZYKLADY_KONTRPRZYKLADU:
        for wzor in przyklad["wiersze"]:
            assert to_html(parse(wzor)) in fragment, f"brak wzoru {wzor} w sekcji"


def test_wszedl_partial_steppera_dla_kazdego_dowodu(html):
    assert html.count("data-stepper") == len(ID_DOWODOW)
    assert html.count('data-rola="kroki"') == len(ID_DOWODOW)
    assert html.count("Kroki pojawią się tutaj") == len(ID_DOWODOW)


def test_strona_dolacza_skrypt_i_arkusz(html):
    assert 'src="/static/js/dowody.js"' in html
    assert 'href="/static/css/dowody.css"' in html
    assert html.count('type="module"') > 0


def test_wstep_opisuje_trzy_rodzaje_dowodu(html):
    """Criterion karty: 2–3 zdania na każdy rodzaj dowodu."""
    for rodzaj in widok.RODZAJE:
        assert f'id="rodzaj-{rodzaj["kod"]}"' in html
        assert rodzaj["tytul"] in html
        zdania = [zdanie for zdanie in re.split(r"(?<=\.)\s+", rodzaj["opis"]) if zdanie.strip()]
        assert 2 <= len(zdania) <= 3, f"{rodzaj['tytul']}: {len(zdania)} zdań"


def test_spis_dowodow_prowadzi_do_sekcji(html):
    for identyfikator in ID_DOWODOW:
        assert f'href="#dowod-{identyfikator.lower()}"' in html
        assert f'id="dowod-{identyfikator.lower()}"' in html


def test_formula_to_html_oddaje_tekst_gdy_wzor_sie_nie_parsuje():
    """Literówka w treści pokazuje napis, a nie stronę z błędem 500."""
    assert str(widok.formula_to_html("Sprzeczność 5, 7")) == "Sprzeczność 5, 7"


# ---------------------------------------------------------------------------
# Skrypt i arkusz
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def skrypt() -> str:
    return _zrodlo(JS)


def test_skrypt_korzysta_ze_steppera(skrypt):
    """Criterion karty: ``dowody.js`` importuje ``createStepper``."""
    assert 'import { createStepper } from "/static/js/stepper.js";' in skrypt
    assert "createStepper({" in skrypt
    assert "steps: kroki" in skrypt


def test_skrypt_czyta_kroki_i_wiersze_z_dom(skrypt):
    assert "data-kroki" in skrypt
    assert "dataset.kroki" in skrypt
    assert "dataset.nr" in skrypt
    assert 'querySelectorAll("[data-dowod]")' in skrypt


def test_skrypt_rysuje_strzalki_dla_wierszy_z_lista_z(skrypt):
    """Criterion karty: strzałka rusza z wierszy z listy ``z`` do nowego wiersza."""
    assert "krok.z" in skrypt
    assert "opisZrodel" in skrypt
    assert "wiersz ${numery[0]}" in skrypt
    assert "wiersze ${wymien(numery)}" in skrypt
    assert "zbudujStrzalke" in skrypt
    assert "replaceChildren" in skrypt
    assert 'setAttribute("aria-label"' in skrypt


def test_skrypt_ukrywa_wiersze_do_biezacego_kroku(skrypt):
    assert "ustawWiersze" in skrypt
    assert "wiersz.hidden = !widoczne.has(wiersz.dataset.nr)" in skrypt


def test_skrypt_podswietla_pare_sprzeczna_z_podpisem(skrypt):
    """Kolor nie jest jedynym nośnikiem: wiersz sprzeczny dostaje napis „sprzeczny”."""
    assert 'const KLASA_SPRZECZNY = "wiersz-sprzeczny";' in skrypt
    assert 'const TEKST_SPRZECZNY = "sprzeczny";' in skrypt
    assert 'nowyElement("span", KLASA_ODZNAKA, TEKST_SPRZECZNY)' in skrypt


def test_skrypt_nie_wstawia_tresci_przez_innerhtml(skrypt):
    assert ".innerHTML" not in skrypt
    assert "insertAdjacentHTML" not in skrypt
    assert "document.write" not in skrypt
    assert "eval(" not in skrypt


def test_skrypt_nie_wysadza_strony_bez_krokow(skrypt):
    """Bez kroków albo bez tabeli skrypt zostawia pełną tabelę z HTML-a."""
    assert "if (!tabela || kroki.length === 0)" in skrypt
    assert "return;" in skrypt


def test_arkusz_styluje_wiersze_dowodu():
    css = _zrodlo(ARKUSZ)

    assert ".tablica-dowodu [hidden]" in css
    assert ".wiersz-biezacy" in css
    assert ".wiersz-zrodlo" in css
    assert ".wiersz-sprzecznosc" in css
    assert ".wiersz-sprzeczny" in css
    assert ".wiersz-wciety" in css
    assert ".strzalka-dowodu" in css
    assert "prefers-reduced-motion" in css


def test_szablon_uzywa_partialu_steppera():
    szablon = _zrodlo(SZABLON)

    assert szablon.count('{% include "partials/_stepper.html" %}') == 1
    assert "{% for dowod in dowody %}" in szablon
    assert "url_for('static'" in szablon
