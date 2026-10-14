"""Testy rysunków liczonych na serwerze (karty PRZ-123, PRZ-141 i PRZ-182).

Rysunek bramek i diagram zbiorów powstają w :mod:`app.logic.diagrams`, więc bramka QA
sprawdza je bez przeglądarki. Testy pilnują trzech rzeczy: samego rysunku (kształt
i opis słowny), kroków rysunku (kolejność i opisy po polsku) oraz tego, że **każda**
strona prawa pokazuje oba diagramy i nie wraca do rysowania w przeglądarce.

Karta PRZ-141 dokłada drugi warunek: **każdy krok musi być widocznie inny** od
poprzedniego. Dlatego testy porównują kontury kolejnych kroków, liczą bramki
policzone i zapalone oraz sprawdzają numer kroku z adresu (``?krok=N``).

Karta PRZ-172 dokłada trzeci: rysunek zbiorów to **dwie** figury — lewa i prawa
strona prawa — a lista kroków pod nimi nazywa operację każdego kroku. Krok zbiorów
liczy się wtedy po operacjach, a nie po samych podformułach: zbiór ``p`` nie jest
operacją, tylko punktem wyjścia.

Karta PRZ-182 dokłada czwarty: obszar zbiorów to **gładki kontur** (jedna ścieżka
z krzywymi, a nie dziesiątki prostokątów próbek), schemat bramek jest schludny
(równe prostokąty, przewody z grotami, nic nie wychodzi z ``viewBox``), a **każdy
diagram ma własne strzałki** — diagramy zbiorów to dwa osobne panele kroków.
"""

from __future__ import annotations

import re
import time
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path

import pytest
from flask import render_template

from app import create_app
from app.blueprints import laws as widoki
from app.logic.diagrams import (
    KOLUMNY_SIATKI,
    LEWA,
    MAX_ZBIOROW,
    PRAWA,
    WIERSZE_SIATKI,
    gates_svg,
    kroki_gates,
    kroki_sets,
    sets_svg,
)
from app.logic.formula import FormulaError, parse, subformulas, to_text, variables
from app.logic.laws import all_laws

KATALOG = Path(__file__).resolve().parents[1] / "app" / "static"
ARKUSZ = KATALOG / "css" / "wizualizacje.css"
SKRYPT = KATALOG / "js" / "wizualizacje.js"

FORMULA_ZBIOROW = "∼(p ∨ q)"
FORMULA_BRAMKI = "p → q"
FORMULA_DRZEWA = "(p ∧ q) → r"
FORMULA_DE_MORGANA = "∼(p ∨ q) ≡ (∼p ∧ ∼q)"

#: Najdłuższy wzór w rejestrze praw — na nim sprawdzamy układ schematu bramek
#: i to, że napisy nie nachodzą na siebie (karta PRZ-182).
FORMULA_NAJDLUZSZA = "((p → q) → (p ∧ q)) ≡ (∼(p → q) ∨ (p ∧ q))"

#: Wzór, w którym ten sam fragment stoi w drzewie dwa razy — oba wystąpienia
#: muszą mieć własne miejsce na rysunku bramek (karta PRZ-182).
FORMULA_POWTORZONA = "p ∨ p"

#: Wzór, w którym dwie operacje jednej strony zachodzą na siebie — na nim obie
#: warstwy obszaru są niepuste (karta PRZ-141).
FORMULA_WARSTW = "∼p ∨ q"

#: Slugi praw, dla których karty PRZ-172 i PRZ-123 pokazują diagram zbiorów.
PRAWA_ZBIOROW = ("de-morgan-1", "rozdzielnosc-1")

#: Nazwy operacji, które karta PRZ-172 wymaga w punkcie listy kroków.
NAZWY_OPERACJI = ("suma", "część wspólna", "dopełnienie")

#: Kontur obszaru: jedna ścieżka z krzywymi Béziera (``C``), domknięta (``Z``).
KONTUR = re.compile(r'<path class="wiz-obszar" d="([^"]+)"')

#: Rysunek bramek ma prostokąty i przewody; kryterium liczy je razem.
KSZTALT = re.compile(r"<rect\b|<path\b")

#: Prostokąt bramki razem z rozmiarem — do sprawdzenia równego rozmiaru (PRZ-182).
BRAMKA = re.compile(
    r'<rect class="wiz-ksztalt" x="([-\d.]+)" y="([-\d.]+)" '
    r'width="([\d.]+)" height="([\d.]+)"'
)

#: Przewód bramki: ortogonalna łamana (``M``/``H``/``V``) z grotem na końcu.
PRZEWOD = re.compile(r'<path class="(wiz-przewod[^"]*)" d="([^"]+)" marker-end="url\(#([^)]+)\)"')

#: Napis wartości na przewodzie razem z położeniem — sprawdzamy, że nie wchodzi
#: w prostokąt bramki i nie nachodzi na inny napis (karta PRZ-182).
NAPOLIS = re.compile(
    r'<text class="wiz-wartosc[^"]*" x="([-\d.]+)" y="([-\d.]+)"[^>]*>([^<]*)</text>'
)

#: Polecenia ścieżki razem z ich współrzędnymi — z ``viewBox`` porównujemy skrajne.
POLECENIE = re.compile(r"([MHV])\s*([-\d.]+)(?:\s+([-\d.]+))?")

#: Nazwy klas warstw obszaru z karty PRZ-141: nowy obszar i ten z poprzedniego kroku.
NOWY = "obszar-nowy"
POPRZEDNI = "obszar-poprzedni"

#: Etykieta operacji nad rysunkiem zbiorów.
ETYKIETA = re.compile(r'class="wiz-etykieta-kroku"[^>]*>([^<]+)</text>')

#: Wartość logiczna w ``<title>`` kształtu rysunku bramek.
WARTOSC_SLOWAMI = re.compile(r"PRAWDA|FAŁSZ|nieznana")


def _probki(svg: str, klasa: str | None = None) -> set[str]:
    """Kontury rysunku zbiorów — cały rysunek albo jedna warstwa obszaru."""
    if klasa is None:
        return set(KONTUR.findall(svg))
    return _warstwy(svg).get(klasa, set())


class _WarstwyParser(HTMLParser):
    """Zbiera kontury razem z warstwą, w której leżą.

    Ścieżki konturu są dziećmi grupy ``<g class="obszar-…">``, więc o tym, czy
    obszar należy do bieżącego kroku, czy do poprzedniego, mówi klasa grupy —
    a nie klasa ścieżki. Bez tego porównanie kroków widziałoby same kontury.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.warstwy: dict[str, set[str]] = {}
        self.biezaca: str | None = None
        self.stos: list[str] = []

    def handle_starttag(self, tag, atrybuty):
        atrybuty = dict(atrybuty)
        klasy = atrybuty.get("class", "").split()
        if tag == "g":
            warstwa = next((klasa for klasa in klasy if klasa in (NOWY, POPRZEDNI)), None)
            self.stos.append(warstwa or "")
            if warstwa is not None:
                self.warstwy.setdefault(warstwa, set())
        elif tag == "path" and "wiz-obszar" in klasy:
            warstwa = self.stos[-1] if self.stos else ""
            if warstwa:
                self.warstwy[warstwa].add(atrybuty["d"])

    def handle_endtag(self, tag):
        if tag == "g" and self.stos:
            self.stos.pop()


def _warstwy(svg: str) -> dict[str, set[str]]:
    """Warstwy obszaru jednego kroku: ``{klasa: kontury}``."""
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


def test_sets_svg_rysuje_obszar_jednym_gladkim_konturem():
    """Kryterium PRZ-182: obszar to jedna ścieżka z krzywymi, a nie dziesiątki prostokątów."""
    svg = str(sets_svg(parse(FORMULA_ZBIOROW)))
    kontury = KONTUR.findall(svg)

    assert "<svg" in svg
    assert kontury, "obszar musi być ścieżką, a nie zbiorem prostokątów próbek"
    assert len(kontury) < 10, f"obszar rozbity na {len(kontury)} ścieżek"
    assert 'class="wiz-probka"' not in svg, "prostokąty próbek zniknęły z rysunku"
    for kontur in kontury:
        assert kontur.startswith("M "), "ścieżka zaczyna się w punkcie konturu"
        assert " C " in kontur, "krawędź obszaru wygładzają krzywe Béziera"
        assert kontur.endswith("Z"), "kontur obszaru jest domknięty"


def test_sets_svg_siatka_probki_jest_gesta():
    """Kryterium PRZ-182: gęsta siatka próbek trzyma kontur blisko granicy obszaru."""
    assert KOLUMNY_SIATKI >= 200, "zbyt rzadka siatka próbek — kontur wychodzi schodkowy"
    assert WIERSZE_SIATKI >= 160, "zbyt rzadka siatka próbek — kontur wychodzi schodkowy"


def test_sets_svg_rysuje_z_precyzja_geometryczna():
    """Kryterium PRZ-182: SVG prosi przeglądarkę o gładkie krawędzie obszaru."""
    svg = str(sets_svg(parse(FORMULA_ZBIOROW)))

    assert 'shape-rendering="geometricPrecision"' in svg
    assert 'stroke-linejoin="round"' in svg, "załamania konturu mają być zaokrąglone"


def test_sets_svg_rozni_zbior_i_jego_dopelnienie():
    """Kryterium PRZ-123: ``p`` i ``∼p`` zamalowują inne obszary."""
    zbior = _probki(str(sets_svg(parse("p"))), NOWY)
    dopelnienie = _probki(str(sets_svg(parse("∼p"))), NOWY)

    assert zbior and dopelnienie
    assert zbior != dopelnienie


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


def test_kolor_obszaru_dochodzi_do_konturu():
    """Regresja PRZ-141: własne ``fill`` na konturze gasi kolor warstwy obszaru.

    Ścieżki konturu są dziećmi warstwy (``<g class="obszar-…">``), a SVG dziedziczy
    kolor z grupy. Gdy ścieżka ustawia własne ``fill``, dziedziczenie przestaje
    działać i diagram wychodzi bez zamalowanego obszaru — choć SVG jest poprawny,
    więc żaden test czytający sam HTML tego nie złapie.
    """
    styl = ARKUSZ.read_text(encoding="utf-8")
    warstwa = re.search(r"\.obszar-nowy\s*\{([^}]*)\}", styl)
    kontur = re.search(r"\.wiz-obszar\s*\{([^}]*)\}", styl)

    assert warstwa and "fill:" in warstwa.group(1), "warstwa obszaru bez koloru"
    assert kontur is None or "fill" not in kontur.group(1), (
        "`fill` na konturze przesłania kolor warstwy — obszar zniknie"
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


def test_diagramy_prawa_maja_rysunki_i_kroki():
    """Widok przygotowuje dla szablonu oba diagramy razem z krokami."""
    prawo = next(law for law in all_laws() if law.slug == "de-morgan-1")

    rysunki = widoki.diagramy(prawo)

    assert rysunki["bramki"]["kroki"], "brak kroków schematu bramek"
    for krok in rysunki["bramki"]["kroki"]:
        assert "<svg" in str(krok["svg"])
        assert krok["wzor"], "krok bramek bez wzoru"
    for strona in ("lewa", "prawa"):
        assert rysunki["zbiory"][strona]["kroki"], f"brak kroków diagramu zbiorów: {strona}"
        assert rysunki["zbiory"][strona]["tytul"], f"diagram zbiorów bez tytułu: {strona}"
        for krok in rysunki["zbiory"][strona]["kroki"]:
            assert str(krok["svg"]).count("wiz-svg-zbiory") == 1, (
                f"krok strony {strona} to jeden diagram — drugą stronę rysuje osobny panel"
            )
            assert krok["opis"], "krok zbiorów bez napisu punktu listy"


def test_diagramy_prawa_z_blednym_wzorem_daja_puste_kroki():
    """Literówka w treści prawa daje komunikat na stronie, a nie błąd 500."""
    prawo = replace(all_laws()[0], formula="p ∧")

    rysunki = widoki.diagramy(prawo)

    assert rysunki["bramki"]["kroki"] == []
    assert rysunki["zbiory"]["lewa"]["kroki"] == []
    assert rysunki["zbiory"]["prawa"]["kroki"] == []


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
    """Kryterium PRZ-182: każdy z trzech diagramów ma własną parę strzałek.

    Trzy diagramy to schemat bramek, zbiory lewej strony i zbiory prawej strony.
    """
    html = strony[law.slug]

    assert html.count('aria-label="Poprzedni krok"') == 3
    assert html.count('aria-label="Następny krok"') == 3


# ---------------------------------------------------------------------------
# Dwie strony prawa na diagramie zbiorów (karty PRZ-172 i PRZ-182)
# ---------------------------------------------------------------------------


def _widoczny_rysunek_zbiorow(html: str, rola: str = "rysunek-zbiorow") -> str:
    """Widoczna figura jednego diagramu zbiorów — od kontenera do ``<template>``.

    Gotowe kroki czekają w szablonach dalej, więc ten fragment to dokładnie to,
    co widać bez JavaScriptu. ``rola`` wybiera stronę: ``rysunek-zbiorow`` to
    lewa strona prawa, ``rysunek-zbiorow-prawa`` — prawa (karta PRZ-182).
    """
    poczatek = html.index(f'data-rola="{rola}"')
    return html[poczatek : html.index("<template", poczatek)]


def _punkty_listy(html: str) -> list[str]:
    """Punkty widocznej listy kroków — ``<li>`` z ``<ol class="wiz-opisy">``."""
    lista = re.search(r'<ol class="wiz-opisy">(.*?)</ol>', html, re.DOTALL)

    assert lista, "brak listy kroków pod rysunkiem"
    return re.findall(r"<li[^>]*>(.*?)</li>", lista.group(1), re.DOTALL)


def _bez_znacznikow(html: str) -> str:
    """Tekst bez znaczników — wzór w nagłówku i w punkcie listy jest opakowany w ``<span>``."""
    return re.sub(r"<[^>]+>", "", html)


def _prawo(slug: str):
    """Prawo z rejestru po slugu — na nim liczymy kroki rysunku."""
    return next(law for law in all_laws() if law.slug == slug)


@pytest.mark.parametrize("slug", PRAWA_ZBIOROW)
def test_strona_prawa_ma_dwa_diagramy_zbiorow(strony, slug):
    """Kryterium PRZ-172: strona prawa pokazuje obie strony prawa.**

    Od PRZ-182 każda strona stoi w **własnym panelu** kroków, więc szukamy jej
    po roli rysunku, a nie w jednym kontenerze na oba diagramy.
    """
    html = strony[slug]

    assert html.count('<figure class="wiz-figura">') == 3, "trzy figury na stronie prawa"
    for rola in ("rysunek-zbiorow", "rysunek-zbiorow-prawa"):
        assert f'data-rola="{rola}"' in html, f"brak diagramu zbiorów: {rola}"
        assert "<svg" in _widoczny_rysunek_zbiorow(html, rola)


@pytest.mark.parametrize("slug", PRAWA_ZBIOROW)
def test_naglowki_stron_stoja_nad_diagramami(strony, slug):
    """Kryterium PRZ-172: nad każdym diagramem stoi wzór jego strony prawa."""
    prawo = _prawo(slug)
    html = strony[slug]
    naglowki = [
        _bez_znacznikow(naglowek).strip()
        for naglowek in re.findall(r'<figcaption class="wiz-figura-tytul">(.*?)</figcaption>', html)
    ]

    assert sorted(naglowki) == sorted(
        [
            "Schemat bramek",
            f"Lewa strona: {to_text(parse(prawo.lewa))}",
            f"Prawa strona: {to_text(parse(prawo.prawa))}",
        ]
    )
    for tytul, rola in (
        (f"Lewa strona: {to_text(parse(prawo.lewa))}", "rysunek-zbiorow"),
        (f"Prawa strona: {to_text(parse(prawo.prawa))}", "rysunek-zbiorow-prawa"),
    ):
        assert html.index(tytul) < html.index(f'data-rola="{rola}"'), "nagłówek nad diagramem"


@pytest.mark.parametrize("slug", PRAWA_ZBIOROW)
def test_lista_krokow_nazywa_operacje_i_wzor(strony, slug):
    """Kryterium PRZ-172: punkt mówi, jaką operację robi krok i jaki ma wzór.

    Od PRZ-182 każdy diagram przechodzi własne kroki, więc lista pod diagramem
    zbiorów to punkty jego strony prawa — razem dają całą listę kroków.
    """
    kroki = kroki_sets(parse(_prawo(slug).formula))
    html = strony[slug]
    punkty = [
        punkt
        for rola in ("rysunek-zbiorow", "rysunek-zbiorow-prawa")
        for punkt in _punkty_listy(_widoczny_rysunek_zbiorow(html, rola))
    ]

    assert len(punkty) == len(kroki), "tyle punktów, ile kroków zwraca ``kroki_sets``"
    for punkt, krok in zip(punkty, kroki, strict=True):
        assert krok["operacja"] in punkt.lower(), f"punkt bez nazwy operacji: {punkt!r}"
        assert krok["wzor"] in _bez_znacznikow(punkt), f"punkt bez wzoru: {punkt!r}"
        assert any(nazwa in punkt.lower() for nazwa in NAZWY_OPERACJI), (
            f"punkt bez nazwy operacji z karty: {punkt!r}"
        )


@pytest.mark.parametrize("slug", PRAWA_ZBIOROW)
def test_kazdy_krok_zbiorow_ma_obie_warstwy_i_rozni_sie_od_poprzedniego(slug):
    """Kryterium PRZ-172: krok ma oba obszary i maluje inne kontury niż poprzedni."""
    kroki = widoki.diagramy(_prawo(slug))["zbiory"]["prawa"]["kroki"]
    stany = [_warstwy(str(krok["svg"])) for krok in kroki]

    for numer, stan in enumerate(stany):
        assert NOWY in stan and POPRZEDNI in stan, f"krok {numer} bez warstwy"
    for numer, (stan, nastepny) in enumerate(zip(stany, stany[1:], strict=False)):
        assert stan != nastepny, f"kroki {numer} i {numer + 1} rysują to samo"


@pytest.mark.parametrize("law", all_laws(), ids=lambda law: law.slug)
def test_bez_javascriptu_widac_diagramy_i_cala_liste(strony, law):
    """Kryterium PRZ-172: pierwszy krok i cała lista kroków są na stronie bez skryptu."""
    html = strony[law.slug]
    punkty = []
    for rola in ("rysunek-zbiorow", "rysunek-zbiorow-prawa"):
        rysunek = _widoczny_rysunek_zbiorow(html, rola)

        assert "<svg" in rysunek, "bez JavaScriptu nie widać żadnego diagramu"
        assert _punkty_listy(rysunek), f"diagram {rola} bez listy kroków"
        punkty += _punkty_listy(rysunek)

    napisy = _bez_znacznikow(" ".join(punkty)).lower()
    for krok in kroki_sets(parse(law.formula)):
        assert krok["operacja"] in napisy, f"lista kroków bez operacji {krok['operacja']!r}"


# ---------------------------------------------------------------------------
# Numer kroku z adresu (karta PRZ-141)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def prawo_z_krokami():
    """Prawo o pięciu krokach rysunku — na nim sprawdzamy numer z adresu."""
    return next(law for law in all_laws() if law.slug == "de-morgan-1")


def _krok_z_adresu(klient, adres: str, rola: str = "rysunek-zbiorow") -> str:
    """Widoczna figura jednej strony diagramu zbiorów po otwarciu ``adres``."""
    odpowiedz = klient.get(adres)

    assert odpowiedz.status_code == 200
    return _widoczny_rysunek_zbiorow(odpowiedz.get_data(as_text=True), rola)


def _kroki_zbiorow(prawo) -> list[dict]:
    """Kroki obu stron diagramu zbiorów w kolejności nauki: najpierw lewa strona."""
    zbiory = widoki.diagramy(prawo)["zbiory"]
    return [*zbiory["lewa"]["kroki"], *zbiory["prawa"]["kroki"]]


def _szablony_panelu(html: str, rola: str) -> list[str]:
    """Szablony kroków panelu, w którym widać rysunek o tej roli.

    Panel kończy się tam, gdzie zaczyna się następny (``data-wiz-kroki``), więc
    wycinamy fragment od widocznego rysunku do początku kolejnego panelu.
    """
    poczatek = html.index(f'data-rola="{rola}"')
    nastepny = html.find("data-wiz-kroki=", poczatek)
    fragment = html[poczatek:nastepny] if nastepny != -1 else html[poczatek:]
    return re.findall(r"<template data-wiz-krok>(.*?)</template>", fragment, re.DOTALL)


def test_strona_prawa_otwiera_krok_z_adresu(klient, prawo_z_krokami):
    """Kryterium PRZ-141: ``?krok=2`` ustawia diagramy na krok 2.

    Sprawdzamy dwie rzeczy naraz: rysunek widoczny bez JavaScriptu to krok 2
    i pierwszy szablon kroków to też krok 2 — inaczej ``wizualizacje.js``
    przeskoczyłby na początek listy po wczytaniu strony. Od PRZ-182 numer kroku
    działa w **każdym panelu osobno**, więc oba diagramy zbiorów otwierają się
    na swoim kroku 2 (przyciętym do długości swojej listy).
    """
    odpowiedz = klient.get("/prawa/de-morgan-1?krok=2")

    assert odpowiedz.status_code == 200
    html = odpowiedz.get_data(as_text=True)
    zbiory = widoki.diagramy(prawo_z_krokami, krok=2)["zbiory"]

    for strona, rola in ((LEWA, "rysunek-zbiorow"), (PRAWA, "rysunek-zbiorow-prawa")):
        svg = str(zbiory[strona]["kroki"][0]["svg"])
        szablony = _szablony_panelu(html, rola)

        assert svg in _widoczny_rysunek_zbiorow(html, rola), (
            f"widoczny rysunek {strona} to nie krok z adresu"
        )
        assert szablony, f"panel {strona} bez szablonów kroków"
        assert svg in szablony[0], "skrypt zacznie od innego kroku, niż pokazuje strona"


def test_strona_prawa_przycina_krok_spoza_zakresu(klient, prawo_z_krokami):
    """Kryterium PRZ-141: ``?krok=999`` pokazuje ostatni krok każdego panelu."""
    kroki = widoki.diagramy(prawo_z_krokami)["zbiory"]

    assert str(kroki["lewa"]["kroki"][-1]["svg"]) in _krok_z_adresu(
        klient, "/prawa/de-morgan-1?krok=999"
    )
    assert str(kroki["prawa"]["kroki"][-1]["svg"]) in _krok_z_adresu(
        klient, "/prawa/de-morgan-1?krok=999", "rysunek-zbiorow-prawa"
    )


@pytest.mark.parametrize(
    "adres",
    ["/prawa/de-morgan-1", "/prawa/de-morgan-1?krok=abc", "/prawa/de-morgan-1?krok="],
)
def test_strona_prawa_bez_dobrego_numeru_zaczyna_od_pierwszego(klient, prawo_z_krokami, adres):
    """Brak numeru albo śmieć w adresie to „od początku”, a nie błąd 500."""
    kroki = widoki.diagramy(prawo_z_krokami)["zbiory"]

    assert str(kroki["lewa"]["kroki"][0]["svg"]) in _krok_z_adresu(klient, adres)
    assert str(kroki["prawa"]["kroki"][0]["svg"]) in _krok_z_adresu(
        klient, adres, "rysunek-zbiorow-prawa"
    )


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


# ---------------------------------------------------------------------------
# Trzy panele kroków — osobne strzałki dla każdego diagramu (karta PRZ-182)
# ---------------------------------------------------------------------------


def test_partial_ma_trzy_panele_z_wlasnymi_strzalkami():
    """Kryterium PRZ-182: bramki, zbiory-lewa i zbiory-prawa mają każdy swoją parę.

    Panel to ``[data-wiz-kroki]`` — ``wizualizacje.js`` szuka w nim szablonów
    kroków i strzałek, więc osobny panel znaczy „osobne strzałki”.
    """
    for partial in ("partials/_sets.html", "partials/_gates.html"):
        html = _html_partialu(partial, _prawo("de-morgan-1"))
        panele = re.findall(r'<div class="wiz-kroki" data-wiz-kroki="([^"]+)">', html)

        assert sorted(panele) == [
            "bramki-logiczne",
            "diagramy-zbiorow",
            "diagramy-zbiorow-prawa",
        ], f"{partial}: panele kroków to {panele}"
        assert html.count('aria-label="Poprzedni krok"') == 3
        assert html.count('aria-label="Następny krok"') == 3


def test_kazdy_diagram_ma_wlasna_liste_krokow():
    """Kryterium PRZ-182: krok zmienia dokładnie jeden panel, więc każdy ma swoją listę."""
    html = _html_partialu("partials/_sets.html", _prawo("de-morgan-1"))
    panele = re.findall(r'data-wiz-kroki="([^"]+)">(.*?)(?=data-wiz-kroki=|\Z)', html, re.DOTALL)

    liczby = {rola: tresc.count("</li>") for rola, tresc in panele}

    assert liczby["diagramy-zbiorow"] == 2, "lewa strona prawa ma dwie operacje"
    assert liczby["diagramy-zbiorow-prawa"] == 3, "prawa strona prawa ma trzy operacje"
    assert liczby["bramki-logiczne"] >= 3, "schemat bramek idzie po podformułach"


def test_skrypt_trzyma_numer_kroku_w_panelu():
    """Kryterium PRZ-182: numer kroku żyje w domknięciu panelu, nie w module.

    Gdyby numer stał w zmiennej modułu, kliknięcie ``›`` w jednym diagramie
    przestawiłoby wszystkie. Test czyta sam plik ``.js`` — projektu nie stać na
    runner JavaScriptu (``AGENTS.md``).
    """
    skrypt = SKRYPT.read_text(encoding="utf-8")
    deklaracje = re.findall(r"^(?:let|const|var)\s+([A-Za-z_$][\w$]*)", skrypt, re.MULTILINE)

    assert "indeks" not in deklaracje, "numer kroku nie może stać w zasięgu modułu"
    assert "krok" not in deklaracje, "numer kroku nie może stać w zasięgu modułu"
    assert re.search(r"function uruchomPanel\(panel\)\s*\{\s*let indeks = 0;", skrypt), (
        "każdy panel ma dostać własny numer kroku"
    )
    assert 'document.querySelectorAll("[data-wiz-kroki]").forEach(uruchomPanel)' in skrypt, (
        "skrypt musi uruchomić osobny panel dla każdego diagramu"
    )
    assert "idz(-1)" in skrypt and "idz(1)" in skrypt, "krok zmienia się dokładnie o jeden"


def test_wizualizacje_zmieniaja_krok_tylko_w_swoim_panelu():
    """Kryterium PRZ-182: skrypt szuka rysunku, opisu i strzałek **w panelu**."""
    skrypt = SKRYPT.read_text(encoding="utf-8")

    for wybor in ("panel.querySelector(RYSUNEK)", "panel.querySelector(OPIS)"):
        assert wybor in skrypt, f"zapytanie {wybor} musi być ograniczone do panelu"
    assert 'panel.querySelectorAll("template[data-wiz-krok]")' in skrypt
    assert "const przycisk = panel.querySelector(wybor);" in skrypt, (
        "strzałki szukamy w panelu, nie na całej stronie"
    )
    assert "przycisk.disabled = nieaktywny;" in skrypt, "na krańcach listy przycisk jest wyłączony"


# ---------------------------------------------------------------------------
# Schludny schemat bramek (karta PRZ-182)
# ---------------------------------------------------------------------------


def _wartosci(formula: str) -> dict[str, bool]:
    """Pierwszy wiersz tablicy prawdy: wszystkie zmienne prawdziwe."""
    return dict.fromkeys(variables(parse(formula)), True)


def _viewbox(svg: str) -> tuple[float, float]:
    """Szerokość i wysokość rysunku z ``viewBox``."""
    ramka = re.search(r'viewBox="([-\d. ]+)"', svg)

    assert ramka, "rysunek bez viewBox"
    czesci = [float(wartosc) for wartosc in ramka.group(1).split()]

    assert len(czesci) == 4, "viewBox bez czterech liczb"
    return czesci[2], czesci[3]


def _punkty_rysunku(svg: str) -> list[tuple[float, float]]:
    """Wszystkie punkty kształtów rysunku bramek: prostokąty, napisy i przewody."""
    punkty: list[tuple[float, float]] = []
    for x, y, szerokosc, wysokosc in BRAMKA.findall(svg):
        x, y, szerokosc, wysokosc = map(float, (x, y, szerokosc, wysokosc))
        punkty += [(x, y), (x + szerokosc, y + wysokosc)]
    for x, y, _ in NAPOLIS.findall(svg):
        punkty.append((float(x), float(y)))
    for _, sciezka, _ in PRZEWOD.findall(svg):
        x = y = 0.0
        for polecenie, pierwsza, druga in POLECENIE.findall(sciezka):
            if polecenie == "M":
                x, y = float(pierwsza), float(druga)
            elif polecenie == "H":
                x = float(pierwsza)
            else:
                y = float(pierwsza)
            punkty.append((x, y))
    return punkty


@pytest.mark.parametrize("formula", [FORMULA_DRZEWA, FORMULA_POWTORZONA, FORMULA_NAJDLUZSZA])
def test_bramki_maja_rowne_prostokaty(formula):
    """Kryterium PRZ-182: wszystkie prostokąty bramek są tego samego rozmiaru."""
    svg = str(gates_svg(parse(formula), _wartosci(formula)))
    rozmiary = {(szerokosc, wysokosc) for _, _, szerokosc, wysokosc in BRAMKA.findall(svg)}

    assert BRAMKA.findall(svg), "rysunek bez prostokątów bramek"
    assert len(rozmiary) == 1, f"prostokąty bramek różnią się rozmiarem: {rozmiary}"


@pytest.mark.parametrize("formula", [FORMULA_DRZEWA, FORMULA_POWTORZONA, FORMULA_NAJDLUZSZA])
def test_kazdy_przewod_jest_lamana_z_grotem(formula):
    """Kryterium PRZ-182: przewód to ortogonalna łamana z grotem na końcu."""
    svg = str(gates_svg(parse(formula), _wartosci(formula)))
    przewody = PRZEWOD.findall(svg)

    assert przewody, "rysunek bez przewodów"
    for _klasa, sciezka, grot in przewody:
        assert grot.startswith("wiz-grot"), "przewód bez grota"
        assert set(re.findall(r"[A-Za-z]", sciezka)) <= {"M", "H", "V"}, (
            f"przewód {sciezka!r} nie jest ortogonalną łamaną"
        )


@pytest.mark.parametrize("law", all_laws(), ids=lambda law: law.slug)
def test_viewbox_bramek_ma_marginesy(law):
    """Kryterium PRZ-182: żaden element nie wychodzi za ``viewBox``.

    Sprawdzamy **najdłuższy wzór z rejestru praw** i wszystkie pozostałe: rysunek
    z przyciętą bramką albo uciętym napisem jest nieczytelny.
    """
    svg = str(gates_svg(parse(law.formula), _wartosci(law.formula)))
    szerokosc, wysokosc = _viewbox(svg)
    punkty = _punkty_rysunku(svg)

    assert punkty, f"brak kształtów w rysunku bramek dla {law.slug}"
    skrajne_x = [x for x, _ in punkty]
    skrajne_y = [y for _, y in punkty]

    assert min(skrajne_x) > 0 and max(skrajne_x) < szerokosc, f"rysunek ucięty z boku: {law.slug}"
    assert min(skrajne_y) > 0 and max(skrajne_y) < wysokosc, f"rysunek ucięty z góry: {law.slug}"


def _pudelko_napisu(napis: str, x: float, y: float) -> tuple[float, float, float, float]:
    """Przybliżony prostokąt napisu wartości (font 9–10 px, kotwica na środku)."""
    szerokosc = len(napis) * 5.6
    return x - szerokosc / 2, y - 10, x + szerokosc / 2, y + 2


@pytest.mark.parametrize("law", all_laws(), ids=lambda law: law.slug)
def test_napisy_bramek_nie_nachodza_na_siebie(law):
    """Kryterium PRZ-182: wartości przewodów stoją między bramkami, nie na nich.

    Dwie rzeczy naraz: napis nie wchodzi w prostokąt bramki i nie nachodzi na inny
    napis. Sprawdzamy wszystkie prawa, bo długi przewód — od liścia do bramki
    o dwie kolumny dalej — wpadał w bramkę stojącą po drodze.
    """
    svg = str(gates_svg(parse(law.formula), _wartosci(law.formula)))
    bramki = [tuple(map(float, ramka)) for ramka in BRAMKA.findall(svg)]
    napisy = [(napis, float(x), float(y)) for x, y, napis in NAPOLIS.findall(svg)]

    assert napisy, f"brak napisów wartości dla {law.slug}"
    for napis, x, y in napisy:
        lewa, gora, prawa, dol = _pudelko_napisu(napis, x, y)
        for bx, by, bszerokosc, bwysokosc in bramki:
            nachodzi = lewa < bx + bszerokosc and prawa > bx and gora < by + bwysokosc and dol > by

            assert not nachodzi, f"{law.slug}: napis {napis!r} wchodzi w prostokąt bramki"
    for indeks, (napis, x, y) in enumerate(napisy):
        for drugi, x2, y2 in napisy[indeks + 1 :]:
            lewa, gora, prawa, dol = _pudelko_napisu(napis, x, y)
            lewa2, gora2, prawa2, dol2 = _pudelko_napisu(drugi, x2, y2)
            nachodza = lewa < prawa2 and prawa > lewa2 and gora < dol2 and dol > gora2

            assert not nachodza, f"{law.slug}: napisy {napis!r} i {drugi!r} nachodzą na siebie"


def test_bramki_powtorzonego_wzoru_maja_wlasne_miejsca():
    """Kryterium PRZ-182: ten sam wzór dwa razy w drzewie to dwie bramki.

    W „p ∨ p” oba zbiory ``p`` muszą mieć własny wiersz — inaczej napisy przewodów
    i prostokąty trafiają w to samo miejsce i rysunek jest nieczytelny.
    """
    svg = str(gates_svg(parse(FORMULA_POWTORZONA), {"p": True}))
    miejsca = [(x, y) for x, y, _szerokosc, _wysokosc in BRAMKA.findall(svg)]

    assert len(miejsca) == len(set(miejsca)), f"dwie bramki w tym samym miejscu: {miejsca}"


def test_rysunek_zbiorow_liczy_sie_szybko():
    """Kryterium PRZ-182: wszystkie kroki wzoru liczą się dużo krócej niż sekundę."""
    node = parse(FORMULA_DE_MORGANA)
    poczatek = time.perf_counter()
    for krok in range(len(kroki_sets(node))):
        sets_svg(node, krok=krok)
    czas = time.perf_counter() - poczatek

    assert czas < 1.0, f"rysowanie kroków wzoru trwa {czas:.2f} s"
