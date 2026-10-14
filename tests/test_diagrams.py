"""Testy rysunków liczonych na serwerze (karty PRZ-123 i PRZ-141).

Rysunek bramek i diagram zbiorów powstają w :mod:`app.logic.diagrams`, więc bramka QA
sprawdza je bez przeglądarki. Testy pilnują trzech rzeczy: samego rysunku (kształt
i opis słowny), kroków rysunku (kolejność i opisy po polsku) oraz tego, że **każda**
strona prawa pokazuje oba diagramy i nie wraca do rysowania w przeglądarce.

Karta PRZ-141 dokłada drugi warunek: **każdy krok musi być widocznie inny** od
poprzedniego. Dlatego testy porównują zamalowane komórki kolejnych kroków, liczą
bramki policzone i zapalone oraz sprawdzają numer kroku z adresu (``?krok=N``).

Karta PRZ-172 dokłada trzeci: rysunek zbiorów to **dwie** figury — lewa i prawa
strona prawa — a lista kroków pod nimi nazywa operację każdego kroku. Krok zbiorów
liczy się wtedy po operacjach, a nie po samych podformułach: zbiór ``p`` nie jest
operacją, tylko punktem wyjścia.
"""

from __future__ import annotations

import re
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path

import pytest
from flask import render_template

from app import create_app
from app.blueprints import laws as widoki
from app.logic.diagrams import MAX_ZBIOROW, gates_svg, kroki_gates, kroki_sets, sets_svg
from app.logic.formula import FormulaError, parse, subformulas, to_text
from app.logic.laws import all_laws

ARKUSZ = Path(__file__).resolve().parents[1] / "app" / "static" / "css" / "wizualizacje.css"

FORMULA_ZBIOROW = "∼(p ∨ q)"
FORMULA_BRAMKI = "p → q"
FORMULA_DRZEWA = "(p ∧ q) → r"
FORMULA_DE_MORGANA = "∼(p ∨ q) ≡ (∼p ∧ ∼q)"

#: Wzór, w którym dwie operacje jednej strony zachodzą na siebie — na nim obie
#: warstwy obszaru są niepuste (karta PRZ-141).
FORMULA_WARSTW = "∼p ∨ q"

#: Slugi praw, dla których karty PRZ-172 i PRZ-123 pokazują diagram zbiorów.
PRAWA_ZBIOROW = ("de-morgan-1", "rozdzielnosc-1")

#: Nazwy operacji, które karta PRZ-172 wymaga w punkcie listy kroków.
NAZWY_OPERACJI = ("suma", "część wspólna", "dopełnienie")

#: Prostokąt próbki razem z jej położeniem na siatce — po tym poznajemy obszar.
PROBKA = re.compile(r'<rect class="wiz-probka" x="(\d+)" y="(\d+)" width="(\d+)"')

#: Rysunek bramek ma prostokąty i przewody; kryterium liczy je razem.
KSZTALT = re.compile(r"<rect\b|<path\b")

#: Nazwy klas warstw obszaru z karty PRZ-141: nowy obszar i ten z poprzedniego kroku.
NOWY = "obszar-nowy"
POPRZEDNI = "obszar-poprzedni"

#: Etykieta operacji nad rysunkiem zbiorów.
ETYKIETA = re.compile(r'class="wiz-etykieta-kroku"[^>]*>([^<]+)</text>')

#: Wartość logiczna w ``<title>`` kształtu rysunku bramek.
WARTOSC_SLOWAMI = re.compile(r"PRAWDA|FAŁSZ|nieznana")


def _probki(svg: str) -> set[tuple[str, str, str]]:
    """Zamalowane próbki rysunku zbiorów."""
    return set(PROBKA.findall(svg))


class _WarstwyParser(HTMLParser):
    """Zbiera zamalowane komórki razem z warstwą, w której leżą.

    Prostokąty próbek są dziećmi grupy ``<g class="obszar-…">``, więc o tym, czy
    komórka należy do obszaru nowego, czy do poprzedniego, mówi klasa grupy —
    a nie klasa prostokąta. Bez tego porównanie kroków widziałoby same prostokąty.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.warstwy: dict[str, set[tuple[str, str, str]]] = {}
        self.biezaca: str | None = None

    def handle_starttag(self, tag, atrybuty):
        atrybuty = dict(atrybuty)
        klasy = atrybuty.get("class", "").split()
        if tag == "g":
            warstwa = next((klasa for klasa in klasy if klasa in (NOWY, POPRZEDNI)), None)
            self.biezaca = warstwa
            if warstwa is not None:
                self.warstwy.setdefault(warstwa, set())
        elif tag == "rect" and self.biezaca and "wiz-probka" in klasy:
            self.warstwy[self.biezaca].add((atrybuty["x"], atrybuty["y"], atrybuty["width"]))

    def handle_endtag(self, tag):
        if tag == "g":
            self.biezaca = None


def _warstwy(svg: str) -> dict[str, set[tuple[str, str, str]]]:
    """Warstwy obszaru jednego kroku: ``{klasa: komórki}``."""
    parser = _WarstwyParser()
    parser.feed(svg)
    return parser.warstwy


def _rysunek(html: str, rola: str) -> str:
    """Fragment strony od początku rysunku do jego ``</svg>`` — bez szablonów kroków."""
    poczatek = html.index(f'data-rola="{rola}"')
    koniec = html.index("</svg>", poczatek)
    return html[poczatek:koniec]


@pytest.fixture(scope="module")
def klient():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def strony(klient) -> dict[str, str]:
    """HTML każdej strony prawa — jedno pobranie na cały moduł."""
    return {law.slug: klient.get(f"/prawa/{law.slug}").get_data(as_text=True) for law in all_laws()}


# ---------------------------------------------------------------------------
# Diagram zbiorów
# ---------------------------------------------------------------------------


def test_sets_svg_rysuje_obszar_z_probek():
    """Kryterium PRZ-123: ``sets_svg`` zwraca ``<svg>`` z co najmniej 20 kształtami."""
    svg = str(sets_svg(parse(FORMULA_ZBIOROW)))

    assert "<svg" in svg
    assert len(KSZTALT.findall(svg)) >= 20, "obszar to wiele prostokątów próbek"


def test_sets_svg_rozni_zbior_i_jego_dopelnienie():
    """Kryterium PRZ-123: ``p`` i ``∼p`` zamalowują różne komórki siatki."""
    zbior = _probki(str(sets_svg(parse("p"))))
    dopelnienie = _probki(str(sets_svg(parse("∼p"))))

    assert zbior and dopelnienie
    assert zbior != dopelnienie
    assert not (zbior & dopelnienie), "próbka nie może być zamalowana i pusta naraz"


def test_sets_svg_pokazuje_przestrzen_i_kola():
    svg = str(sets_svg(parse(FORMULA_ZBIOROW)))

    assert 'class="wiz-przestrzen"' in svg, "prostokąt to cała przestrzeń"
    assert svg.count("<circle") == 2, "dwie zmienne to dwa koła"
    assert svg.count("<title") >= 3, "przestrzeń i koła mają opisy słowne"


def test_sets_svg_rozroznia_obszar_nowy_i_poprzedni():
    """Kryterium PRZ-141: krok ma obie warstwy i różne klasy obszaru.

    Krok „suma ∼p ∨ q” rysuje część wspólną z krokiem „dopełnienie ∼p” (słabym
    akcentem) i to, co dokłada (mocnym), więc obie warstwy są niepuste.
    """
    node = parse(FORMULA_WARSTW)

    svg = str(sets_svg(node, krok=1))

    assert 'class="obszar-1 obszar-nowy"' in svg
    assert 'class="obszar-2 obszar-poprzedni"' in svg
    warstwy = _warstwy(svg)
    assert warstwy[NOWY], "obszar nowy bez zamalowanych komórek"
    assert warstwy[POPRZEDNI], "obszar z poprzedniego kroku bez zamalowanych komórek"


def test_sets_svg_ma_obie_warstwy_w_kazdym_kroku():
    """Kryterium PRZ-141: żaden krok nie gubi warstwy obszaru."""
    node = parse(FORMULA_ZBIOROW)

    for numer in range(len(kroki_sets(node))):
        svg = str(sets_svg(node, krok=numer))

        assert NOWY in svg, f"krok {numer} bez obszaru nowego"
        assert POPRZEDNI in svg, f"krok {numer} bez obszaru z poprzedniego kroku"


def test_kazdy_krok_ma_etykiete_operacji():
    """Kryterium PRZ-141: nad rysunkiem stoi nazwa operacji po polsku."""
    node = parse(FORMULA_ZBIOROW)

    for numer, krok in enumerate(kroki_sets(node)):
        etykieta = ETYKIETA.search(str(sets_svg(node, krok=numer)))

        assert etykieta, f"krok {numer} bez etykiety operacji nad rysunkiem"
        assert krok["operacja"] in etykieta.group(1).lower(), (
            f"etykieta {etykieta.group(1)!r} nie nazywa operacji {krok['operacja']!r}"
        )


def test_kolor_obszaru_dochodzi_do_prostokatow_probki():
    """Regresja PRZ-141: własne ``fill`` na próbce gasi kolor warstwy obszaru.

    Prostokąty próbek są dziećmi warstwy (``<g class="obszar-…">``), a SVG dziedziczy
    kolor z grupy. Gdy prostokąt ustawia własne ``fill``, dziedziczenie przestaje
    działać i diagram wychodzi bez zamalowanego obszaru — choć SVG jest poprawny,
    więc żaden test czytający sam HTML tego nie złapie.
    """
    styl = ARKUSZ.read_text(encoding="utf-8")
    warstwa = re.search(r"\.obszar-nowy\s*\{([^}]*)\}", styl)
    probka = re.search(r"\.wiz-probka\s*\{([^}]*)\}", styl)

    assert warstwa and "fill:" in warstwa.group(1), "warstwa obszaru bez koloru"
    assert probka is None or "fill" not in probka.group(1), (
        "`fill` na prostokącie próbki przesłania kolor warstwy — obszar zniknie"
    )


def test_etykieta_stoi_nad_rysunkiem_bez_numeru_kroku():
    """Etykieta jest nad obszarem i nie pokazuje numerka kroku (karta PRZ-141)."""
    node = parse(FORMULA_ZBIOROW)

    svg = str(sets_svg(node, krok=2))
    etykieta = ETYKIETA.search(svg)

    assert etykieta, "brak etykiety kroku"
    assert svg.index("wiz-etykieta-kroku") < svg.index("wiz-przestrzen"), (
        "etykieta operacji musi stać nad rysunkiem"
    )
    assert not re.search(r"krok\s*\d", etykieta.group(1), re.IGNORECASE), (
        "numer kroku należy do ``aria-label``, nie do widocznej etykiety"
    )


def test_sets_svg_odmawia_przy_czterech_zbiorach():
    """Ponad trzy zmienne to komunikat po polsku, a nie rysunek."""
    wynik = str(sets_svg(parse("p ∧ q ∧ r ∧ s")))

    assert MAX_ZBIOROW == 3
    assert "<svg" not in wynik
    assert "co najwyżej trzy zbiory" in wynik
    assert "4 zmiennych" in wynik, "komunikat mówi, ile zmiennych ma wzór"


def test_sets_svg_nie_podnosi_bledu_przy_trzech_zbiorach():
    assert "<svg" in str(sets_svg(parse("(p ∧ q) ∨ r")))
    assert "<circle" in str(sets_svg(parse("(p ∧ q) ∨ r")))


# ---------------------------------------------------------------------------
# Schemat bramek
# ---------------------------------------------------------------------------


def test_gates_svg_rysuje_bramki_groty_i_wartosci():
    """Kryterium PRZ-123: ``<svg>``, prostokąty bramek, groty i wartości słowami."""
    svg = str(gates_svg(parse(FORMULA_BRAMKI), {"p": True, "q": False}))

    assert "<svg" in svg
    assert 'class="wiz-ksztalt"' in svg, "bramka to prostokąt"
    assert "<marker" in svg, "przewody kończą się grotem strzałki"
    assert "→" in svg, "w prostokącie stoi symbol operatora"
    assert "PRAWDA" in svg, "wartość przewodu słowami"
    assert "FAŁSZ" in svg, "wartość przewodu słowami"


def test_gates_svg_liczy_wartosci_podformul():
    """Wartości pochodzą z ``formula.evaluate``, a nie z przeglądarki."""
    svg = str(gates_svg(parse(FORMULA_BRAMKI), {"p": True, "q": False}))

    assert "Przewód z p: PRAWDA (1)." in svg
    assert "Przewód z q: FAŁSZ (0)." in svg


def test_gates_svg_przed_krokiem_zostawia_pytajnik():
    """Bramki policzone później pokazują ``?`` — wynik jeszcze nie zapadł."""
    svg = str(gates_svg(parse(FORMULA_BRAMKI), {"p": True, "q": False}, krok=0))

    assert "?" in svg
    assert "wartość jeszcze nieznana" in svg


def test_gates_svg_rysuje_kazdy_operator():
    for tekst, symbol in (
        ("∼p", "∼"),
        ("p ∧ q", "∧"),
        ("p ∨ q", "∨"),
        ("p → q", "→"),
        ("p ≡ q", "≡"),
    ):
        svg = str(gates_svg(parse(tekst), {"p": True, "q": True}))

        assert f">{symbol}</text>" in svg, f"brak symbolu {symbol} w bramce"


def test_gates_svg_wymaga_wartosci_kazdej_zmiennej():
    with pytest.raises(FormulaError):
        gates_svg(parse(FORMULA_BRAMKI), {"p": True})


def test_gates_svg_zapala_jedna_bramke_na_krok():
    """Kryterium PRZ-141: krok zapala dokładnie jedną bramkę."""
    node = parse(FORMULA_DRZEWA)
    wartosci = {"p": True, "q": True, "r": True}

    for numer in range(len(kroki_gates(node))):
        svg = str(gates_svg(node, wartosci, krok=numer))

        assert svg.count("bramka-aktywna") == 1, f"krok {numer} nie zapala jednej bramki"


def test_gates_svg_bramki_policzone_rosna_z_krokiem():
    """Kryterium PRZ-141: każdy krok ma więcej bramek policzonych niż poprzedni."""
    node = parse(FORMULA_DRZEWA)
    wartosci = {"p": True, "q": True, "r": True}

    liczby = [
        str(gates_svg(node, wartosci, krok=numer)).count("bramka-policzona")
        for numer in range(len(kroki_gates(node)))
    ]

    assert liczby == sorted(liczby), f"bramki policzone nie rosną: {liczby}"
    assert len(set(liczby)) == len(liczby), f"dwa kroki mają tyle samo policzonych: {liczby}"


def test_gates_svg_przewody_biezacej_bramki_niosa_slowa():
    """Kryterium PRZ-141: przewody wejściowe bieżącej bramki mają wartość słowami."""
    node = parse(FORMULA_DRZEWA)
    wartosci = {"p": True, "q": True, "r": True}
    numer = subformulas(node).index(parse("p ∧ q"))

    svg = str(gates_svg(node, wartosci, krok=numer))

    assert svg.count("przewod-aktywny") == 2, "koniunkcja ma dwa przewody wejściowe"
    assert ">PRAWDA</text>" in svg, "wartość przewodu bieżącej bramki słowami, nie cyfrą"


def test_gates_svg_kazdy_ksztalt_ma_wartosc_slowami():
    """Kryterium PRZ-141: każdy prostokąt bramki i każdy przewód ma ``<title>``."""
    node = parse(FORMULA_DRZEWA)

    svg = str(gates_svg(node, {"p": True, "q": True, "r": True}, krok=1))
    tytuly = re.findall(r"<title>([^<]*)</title>", svg)

    ksztalty = svg.count('class="wiz-ksztalt"') + svg.count('class="wiz-przewod')
    assert len(tytuly) == ksztalty + 1, "kształt bez <title> (1 to tytuł całego rysunku)"
    for tytul in tytuly[1:]:
        assert WARTOSC_SLOWAMI.search(tytul), f"opis kształtu bez wartości słowami: {tytul!r}"


def test_gates_svg_przycina_numer_kroku():
    """Numer spoza listy nie przewraca rysunku — przycinamy go do końców."""
    node = parse(FORMULA_DRZEWA)
    ostatni = len(kroki_gates(node)) - 1

    assert str(gates_svg(node, {"p": True, "q": True, "r": True}, krok=99)) == str(
        gates_svg(node, {"p": True, "q": True, "r": True}, krok=ostatni)
    )


# ---------------------------------------------------------------------------
# Kroki rysunków
# ---------------------------------------------------------------------------


def test_kroki_sets_nazywaja_operacje():
    """Kryterium PRZ-172: krok zbiorów to operacja, a nie samo zaznaczenie zbioru."""
    kroki = kroki_sets(parse(FORMULA_ZBIOROW))

    assert [krok["operacja"] for krok in kroki] == ["suma", "dopełnienie"]
    assert [krok["wzor"] for krok in kroki] == ["p ∨ q", "∼(p ∨ q)"]
    assert kroki[0]["opis"] == "obszar, który pokrywa p albo q."
    assert all(krok["strona"] == "lewa" for krok in kroki), "wzór bez ≡ to jedna strona"
    for krok in kroki:
        assert krok["opis"].endswith("."), "opis kroku to zdanie"


def test_kroki_sets_ida_po_operacjach_stron():
    """Kryterium PRZ-172: najpierw operacje lewej strony prawa, potem prawej."""
    kroki = kroki_sets(parse(FORMULA_DE_MORGANA))

    assert [(krok["strona"], krok["operacja"]) for krok in kroki] == [
        ("lewa", "suma"),
        ("lewa", "dopełnienie"),
        ("prawa", "dopełnienie"),
        ("prawa", "dopełnienie"),
        ("prawa", "część wspólna"),
    ]
    lewe = [krok for krok in kroki if krok["strona"] == "lewa"]
    assert len(lewe) == len(kroki_sets(parse("∼(p ∨ q)"))), "lista zaczyna się od lewej strony"


def test_kroki_sets_roznia_sie_miedzy_krokami():
    """Kryterium PRZ-141: każdy kolejny krok maluje inny zbiór komórek.

    Porównujemy liczbę i położenie komórek obu warstw („nowej” i „poprzedniej”)
    kroku z krokiem następnym — gdyby operacja nie zmieniała rysunku, użytkownik
    nie zobaczyłby, co się właśnie stało.
    """
    node = parse(FORMULA_ZBIOROW)
    kroki = kroki_sets(node)
    warstwy = [_warstwy(str(sets_svg(node, krok=numer))) for numer in range(len(kroki))]

    assert all(warstwy), "krok bez warstw obszaru"
    for numer, (krok, nastepny) in enumerate(zip(warstwy, warstwy[1:], strict=False)):
        assert krok != nastepny, (
            f"kroki {numer} i {numer + 1} malują te same komórki — różnicy nie widać"
        )


def test_kroki_gates_ida_od_zmiennych_do_calej_formuly():
    """Kryterium PRZ-123: ``(p ∧ q) → r`` ma co najmniej trzy kroki."""
    kroki = kroki_gates(parse(FORMULA_DRZEWA))

    assert len(kroki) >= 3
    assert [krok["bramka"] for krok in kroki] == list(range(1, len(kroki) + 1))
    assert kroki[0]["opis"] == "Zapisujemy wartość zmiennej p."
    assert to_text(parse(FORMULA_DRZEWA)) in kroki[-1]["opis"], "ostatni krok opisuje cały wzór"


def test_kroki_rozpoznaja_kazda_operacje():
    for tekst, slowo in (
        ("p ∧ q", "koniunkcja"),
        ("p ∨ q", "alternatywa"),
        ("p → q", "implikacja"),
        ("p ≡ q", "równoważność"),
        ("∼p", "negacja"),
    ):
        opis = kroki_gates(parse(tekst))[-1]["opis"].lower()

        assert slowo in opis, f"brak nazwy operacji {slowo}"


# ---------------------------------------------------------------------------
# Rysunki na stronie prawa
# ---------------------------------------------------------------------------


def test_diagramy_prawa_maja_oba_rysunki_i_kroki():
    """Widok przygotowuje dla szablonu oba diagramy razem z krokami."""
    prawo = next(law for law in all_laws() if law.slug == "de-morgan-1")

    rysunki = widoki.diagramy(prawo)

    for rodzaj in ("bramki", "zbiory"):
        assert rysunki[rodzaj]["kroki"], f"brak kroków rysunku {rodzaj}"
    for krok in rysunki["bramki"]["kroki"]:
        assert "<svg" in str(krok["svg"])
        assert krok["wzor"], "krok bramek bez wzoru"
    for krok in rysunki["zbiory"]["kroki"]:
        assert str(krok["svg"]).count("wiz-svg-zbiory") == 2, "krok zbiorów to dwa diagramy"
        assert krok["opis"], "krok zbiorów bez napisu punktu listy"


def test_diagramy_prawa_z_blednym_wzorem_daja_puste_kroki():
    """Literówka w treści prawa daje komunikat na stronie, a nie błąd 500."""
    prawo = replace(all_laws()[0], formula="p ∧")

    rysunki = widoki.diagramy(prawo)

    assert rysunki["bramki"]["kroki"] == []
    assert rysunki["zbiory"]["kroki"] == []


@pytest.mark.parametrize("law", all_laws(), ids=lambda law: law.slug)
def test_strona_prawa_pokazuje_oba_diagramy(strony, law):
    """Kryterium PRZ-123: każda strona prawa ma schemat bramek i diagram zbiorów."""
    html = strony[law.slug]

    assert "<svg" in _rysunek(html, "rysunek-bramek"), f"brak schematu bramek dla {law.slug}"
    assert "<svg" in _rysunek(html, "rysunek-zbiorow"), f"brak diagramu zbiorów dla {law.slug}"
    assert html.count("<svg") >= 2


@pytest.mark.parametrize("law", all_laws(), ids=lambda law: law.slug)
def test_strona_prawa_bez_licznika_i_guzikow_krokow(strony, law):
    """Kryterium PRZ-123: żadnego „krok 3 z 7”, żadnego „Odtwórz”, „Pauza”, „Od nowa”."""
    html = strony[law.slug]

    assert not re.search(r"krok\s+\d+\s+z\s+\d+", html, re.IGNORECASE), "licznik kroków"
    for napis in ("Odtwórz", "Pauza", "Od nowa"):
        assert napis not in html, f"przycisk {napis!r} nie może wrócić na stronę prawa"


@pytest.mark.parametrize("law", all_laws(), ids=lambda law: law.slug)
def test_rysunki_na_stronie_maja_tytul_po_polsku(strony, law):
    """Kryterium PRZ-123: każdy rysunek ma ``<title>`` z opisem po polsku."""
    for rola, slowo in (
        ("rysunek-bramek", "Schemat bramek"),
        ("rysunek-zbiorow", "Diagram zbiorów"),
    ):
        rysunek = _rysunek(strony[law.slug], rola)
        tytul = re.search(r"<title>(?P<tekst>[^<]+)</title>", rysunek)

        assert tytul, f"brak <title> w rysunku {rola} prawa {law.slug}"
        assert slowo in tytul["tekst"], f"tytuł rysunku {rola} nie mówi, co to za rysunek"


@pytest.mark.parametrize("law", all_laws(), ids=lambda law: law.slug)
def test_strzalki_maja_polskie_etykiety(strony, law):
    """Dwie strzałki na każdym z dwóch rysunków, z etykietą dla czytnika ekranu."""
    html = strony[law.slug]

    assert html.count('aria-label="Poprzedni krok"') == 2
    assert html.count('aria-label="Następny krok"') == 2


# ---------------------------------------------------------------------------
# Dwie strony prawa na diagramie zbiorów (karta PRZ-172)
# ---------------------------------------------------------------------------


def _widoczny_rysunek_zbiorow(html: str) -> str:
    """Widoczna figura diagramu zbiorów — od kontenera do pierwszego ``<template>``.

    Gotowe kroki czekają w szablonach dalej, więc ten fragment to dokładnie to,
    co widać bez JavaScriptu.
    """
    poczatek = html.index('data-rola="rysunek-zbiorow"')
    return html[poczatek : html.index("<template", poczatek)]


def _punkty_listy(html: str) -> list[str]:
    """Punkty widocznej listy kroków — ``<li>`` z ``<ol class="wiz-opisy">``."""
    lista = re.search(r'<ol class="wiz-opisy">(.*?)</ol>', html, re.DOTALL)

    assert lista, "brak listy kroków pod rysunkiem"
    return re.findall(r"<li[^>]*>(.*?)</li>", lista.group(1), re.DOTALL)


def _bez_znacznikow(html: str) -> str:
    """Tekst bez znaczników — wzór w nagłówku i w punkcie listy jest opakowany w ``<span>``."""
    return re.sub(r"<[^>]+>", "", html)


def _warstwy_obu_stron(krok: dict) -> tuple[dict, dict]:
    """Warstwy obszaru obu diagramów jednego kroku: lewa strona i prawa."""
    diagramy = str(krok["svg"]).split('class="wiz-svg wiz-svg-zbiory"')[1:]

    assert len(diagramy) == 2, "krok zbiorów to dwa diagramy"
    return _warstwy(diagramy[0]), _warstwy(diagramy[1])


def _prawo(slug: str):
    """Prawo z rejestru po slugu — na nim liczymy kroki rysunku."""
    return next(law for law in all_laws() if law.slug == slug)


@pytest.mark.parametrize("slug", PRAWA_ZBIOROW)
def test_strona_prawa_ma_dwa_diagramy_zbiorow(strony, slug):
    """Kryterium PRZ-172: widoczna figura zbiorów pokazuje obie strony prawa."""
    rysunek = _widoczny_rysunek_zbiorow(strony[slug])

    assert rysunek.count('class="wiz-svg wiz-svg-zbiory"') == 2, "dwa diagramy zbiorów"


@pytest.mark.parametrize("slug", PRAWA_ZBIOROW)
def test_naglowki_stron_stoja_nad_diagramami(strony, slug):
    """Kryterium PRZ-172: nad każdym diagramem stoi wzór jego strony prawa."""
    prawo = _prawo(slug)
    rysunek = _widoczny_rysunek_zbiorow(strony[slug])
    naglowki = re.findall(r'<p class="wiz-strona-tytul">(.*?)</p>', rysunek, re.DOTALL)

    assert [_bez_znacznikow(naglowek) for naglowek in naglowki] == [
        f"Lewa strona: {to_text(parse(prawo.lewa))}",
        f"Prawa strona: {to_text(parse(prawo.prawa))}",
    ]
    assert rysunek.index(naglowki[0]) < rysunek.index("<svg"), "nagłówek nad diagramem"
    assert rysunek.index(naglowki[1]) < rysunek.rindex("<svg"), "nagłówek nad diagramem"


@pytest.mark.parametrize("slug", PRAWA_ZBIOROW)
def test_lista_krokow_nazywa_operacje_i_wzor(strony, slug):
    """Kryterium PRZ-172: punkt mówi, jaką operację robi krok i jaki ma wzór."""
    kroki = kroki_sets(parse(_prawo(slug).formula))
    punkty = _punkty_listy(_widoczny_rysunek_zbiorow(strony[slug]))

    assert len(punkty) == len(kroki), "tyle punktów, ile kroków zwraca ``kroki_sets``"
    for punkt, krok in zip(punkty, kroki, strict=True):
        assert krok["operacja"] in punkt.lower(), f"punkt bez nazwy operacji: {punkt!r}"
        assert krok["wzor"] in _bez_znacznikow(punkt), f"punkt bez wzoru: {punkt!r}"
        assert any(nazwa in punkt.lower() for nazwa in NAZWY_OPERACJI), (
            f"punkt bez nazwy operacji z karty: {punkt!r}"
        )


@pytest.mark.parametrize("slug", PRAWA_ZBIOROW)
def test_kazdy_krok_zbiorow_ma_obie_warstwy_i_rozni_sie_od_poprzedniego(slug):
    """Kryterium PRZ-172: krok ma oba obszary i maluje inne komórki niż poprzedni."""
    kroki = widoki.diagramy(_prawo(slug))["zbiory"]["kroki"]
    stany = [_warstwy_obu_stron(krok) for krok in kroki]

    for numer, stan in enumerate(stany):
        for diagram in stan:
            assert NOWY in diagram and POPRZEDNI in diagram, f"krok {numer} bez warstwy"
    for numer, (stan, nastepny) in enumerate(zip(stany, stany[1:], strict=False)):
        assert stan != nastepny, f"kroki {numer} i {numer + 1} rysują to samo"


@pytest.mark.parametrize("law", all_laws(), ids=lambda law: law.slug)
def test_bez_javascriptu_widac_diagramy_i_cala_liste(strony, law):
    """Kryterium PRZ-172: pierwszy krok i cała lista kroków są na stronie bez skryptu."""
    rysunek = _widoczny_rysunek_zbiorow(strony[law.slug])

    assert "<svg" in rysunek, "bez JavaScriptu nie widać żadnego diagramu"
    assert len(_punkty_listy(rysunek)) == len(kroki_sets(parse(law.formula)))


# ---------------------------------------------------------------------------
# Numer kroku z adresu (karta PRZ-141)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def prawo_z_krokami():
    """Prawo o pięciu krokach rysunku — na nim sprawdzamy numer z adresu."""
    return next(law for law in all_laws() if law.slug == "de-morgan-1")


def _krok_z_adresu(klient, adres: str) -> str:
    """Widoczna figura diagramu zbiorów po otwarciu ``adres``."""
    odpowiedz = klient.get(adres)

    assert odpowiedz.status_code == 200
    return _widoczny_rysunek_zbiorow(odpowiedz.get_data(as_text=True))


def test_strona_prawa_otwiera_krok_z_adresu(klient, prawo_z_krokami):
    """Kryterium PRZ-141: ``?krok=2`` ustawia diagramy na krok 2.

    Sprawdzamy dwie rzeczy naraz: rysunek widoczny bez JavaScriptu to krok 2
    i pierwszy szablon kroków to też krok 2 — inaczej ``wizualizacje.js``
    przeskoczyłby na początek listy po wczytaniu strony.
    """
    odpowiedz = klient.get("/prawa/de-morgan-1?krok=2")

    assert odpowiedz.status_code == 200
    svg = str(widoki.diagramy(prawo_z_krokami)["zbiory"]["kroki"][2]["svg"])
    html = odpowiedz.get_data(as_text=True)
    szablony = re.findall(r"<template data-wiz-krok>(.*?)</template>", html, re.DOTALL)

    assert svg in _widoczny_rysunek_zbiorow(html), "widoczny rysunek to nie krok z adresu"
    assert szablony, "brak szablonów kroków"
    assert svg in szablony[0], "skrypt zacznie od innego kroku, niż pokazuje strona"


def test_strona_prawa_przycina_krok_spoza_zakresu(klient, prawo_z_krokami):
    """Kryterium PRZ-141: ``?krok=999`` pokazuje ostatni krok, a nie błąd."""
    ostatni = str(widoki.diagramy(prawo_z_krokami)["zbiory"]["kroki"][-1]["svg"])

    assert ostatni in _krok_z_adresu(klient, "/prawa/de-morgan-1?krok=999")


@pytest.mark.parametrize(
    "adres",
    ["/prawa/de-morgan-1", "/prawa/de-morgan-1?krok=abc", "/prawa/de-morgan-1?krok="],
)
def test_strona_prawa_bez_dobrego_numeru_zaczyna_od_pierwszego(klient, prawo_z_krokami, adres):
    """Brak numeru albo śmieć w adresie to „od początku”, a nie błąd 500."""
    pierwszy = str(widoki.diagramy(prawo_z_krokami)["zbiory"]["kroki"][0]["svg"])

    assert pierwszy in _krok_z_adresu(klient, adres)


class _PanelParser(HTMLParser):
    """Sprawdza, czy każdy ``template[data-wiz-krok]`` leży w panelu ``[data-wiz-kroki]``.

    ``wizualizacje.js`` szuka szablonów przez ``panel.querySelectorAll``, więc szablon
    postawiony obok panelu jest dla skryptu niewidoczny — strzałki nic wtedy nie robią.
    Żaden test czytający sam plik ``.js`` tego nie złapie, a przeglądarki w bramce nie ma.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stos: list[tuple[str, dict[str, str]]] = []
        self.w_panelu: list[bool] = []

    def handle_starttag(self, tag, atrybuty):
        atrybuty = dict(atrybuty)
        if tag == "template" and "data-wiz-krok" in atrybuty:
            self.w_panelu.append(any("data-wiz-kroki" in ramka for _, ramka in self.stos))
        self.stos.append((tag, atrybuty))

    def handle_endtag(self, tag):
        for pozycja in range(len(self.stos) - 1, -1, -1):
            if self.stos[pozycja][0] == tag:
                del self.stos[pozycja:]
                return


def _html_partialu(partial: str, prawo) -> str:
    with create_app({"TESTING": True}).test_request_context():
        return render_template(partial, formula=prawo.formula, **widoki.diagramy(prawo))


@pytest.mark.parametrize("partial", ["partials/_gates.html", "partials/_sets.html"])
def test_szablony_krokow_leza_w_panelu(partial):
    """Regresja: szablon kroku poza panelem czyni strzałki bezużytecznymi."""
    parser = _PanelParser()
    parser.feed(_html_partialu(partial, all_laws()[0]))

    assert parser.w_panelu, "partial nie wypisał szablonów kroków"
    assert all(parser.w_panelu), "szablon kroku leży poza panelem [data-wiz-kroki]"
