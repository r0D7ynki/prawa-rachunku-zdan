"""Testy rysunków liczonych na serwerze (karta PRZ-123).

Rysunek bramek i diagram zbiorów powstają w :mod:`app.logic.diagrams`, więc bramka QA
sprawdza je bez przeglądarki. Testy pilnują trzech rzeczy: samego rysunku (kształt
i opis słowny), kroków rysunku (kolejność i opisy po polsku) oraz tego, że **każda**
strona prawa pokazuje oba diagramy i nie wraca do rysowania w przeglądarce.
"""

from __future__ import annotations

import re
from dataclasses import replace
from html.parser import HTMLParser

import pytest
from flask import render_template

from app import create_app
from app.blueprints import laws as widoki
from app.logic.diagrams import MAX_ZBIOROW, gates_svg, kroki_gates, kroki_sets, sets_svg
from app.logic.formula import FormulaError, parse, to_text
from app.logic.laws import all_laws

FORMULA_ZBIOROW = "∼(p ∨ q)"
FORMULA_BRAMKI = "p → q"
FORMULA_DRZEWA = "(p ∧ q) → r"

#: Prostokąt próbki razem z jej położeniem na siatce — po tym poznajemy obszar.
PROBKA = re.compile(r'<rect class="wiz-probka" x="(\d+)" y="(\d+)" width="(\d+)"')

#: Rysunek bramek ma prostokąty i przewody; kryterium liczy je razem.
KSZTALT = re.compile(r"<rect\b|<path\b")


def _probki(svg: str) -> set[tuple[str, str, str]]:
    """Zamalowane próbki rysunku zbiorów."""
    return set(PROBKA.findall(svg))


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


def test_sets_svg_ma_dwie_warstwy_w_kroku():
    """Krok operacji dwuargumentowej pokazuje oba operandy (kryterium PRZ-123)."""
    node = parse(FORMULA_ZBIOROW)
    numer = next(index for index, krok in enumerate(kroki_sets(node)) if krok["operacja"] == "suma")

    svg = str(sets_svg(node, krok=numer))

    assert 'class="obszar-1"' in svg
    assert 'class="obszar-2"' in svg


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
    """Kryterium PRZ-123: co najmniej dwa kroki, w opisach „suma” i „dopełnienie”."""
    kroki = kroki_sets(parse(FORMULA_ZBIOROW))

    assert len(kroki) >= 2
    opis = " ".join(krok["opis"] for krok in kroki).lower()
    assert "suma" in opis
    assert "dopełnienie" in opis
    assert kroki[0]["operacja"] == "zbiór"
    assert kroki[-1]["operacja"] == "dopełnienie"
    for krok in kroki:
        assert krok["opis"].endswith("."), "opis kroku to zdanie"


def test_kroki_sets_ida_od_najmniejszej_podformuly():
    kroki = kroki_sets(parse(FORMULA_ZBIOROW))

    assert [krok["opis"] for krok in kroki] == [
        "Zaznaczamy zbiór p.",
        "Zaznaczamy zbiór q.",
        "Suma zbiorów p i q.",
        "Dopełnienie: bierzemy wszystko poza zbiorem p ∨ q.",
    ]


def test_kroki_sets_roznia_sie_miedzy_krokami():
    """Kryterium PRZ-123: kolejne kroki rysują różne obszary."""
    node = parse(FORMULA_ZBIOROW)
    obszary = {
        frozenset(_probki(str(sets_svg(node, krok=numer))))
        for numer in range(len(kroki_sets(node)))
    }

    assert len(obszary) == len(kroki_sets(node)), "każdy krok musi pokazać inny obszar"


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
        kroki = rysunki[rodzaj]["kroki"]
        assert kroki, f"brak kroków rysunku {rodzaj}"
        assert all("<svg" in str(krok["svg"]) for krok in kroki)
        assert all(krok["wzor"] for krok in kroki), "krok bez wzoru"


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
