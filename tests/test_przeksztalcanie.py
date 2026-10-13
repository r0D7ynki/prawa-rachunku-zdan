"""Testy strony ``/przeksztalcanie`` — nawiasy, kolejność i reguła podstawiania.

Testy nie wierzą stronie na słowo. Wzory porównują z wynikiem ``formula.to_html``,
wartości w tabelach liczą od nowa przez ``formula.evaluate``, a nazwy praw biorą
z rejestru ``app.logic.laws``. Dzięki temu test nie zakłada konkretnego znaku
operatora i nie rozjedzie się z treścią praw.

Test pilnuje też, że lekcja mówi prawdę: kolejne kroki upraszczania są naprawdę
równoważne, a obie formuły z implikacją naprawdę się różnią (``truth.equivalent``).
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from html import unescape
from itertools import pairwise, product
from pathlib import Path

import pytest
from markupsafe import Markup

from app import create_app
from app.blueprints import przeksztalcanie
from app.logic import truth
from app.logic.formula import Node, evaluate, parse, to_html
from app.logic.laws import get

ADRES = "/przeksztalcanie"

#: Podpisy (``<caption>``), po których znajdujemy tabele na stronie.
PODPIS_IMPLIKACJI = "Porównanie obu wzorów"
PODPIS_UPROSZCZENIA = "Pięć kroków upraszczania"
PODPIS_SPRAWDZENIA = "Porównanie wzoru wyjściowego"

#: Slug praw, które lekcja przywołuje. Test sprawdza, że wszystkie są w rejestrze.
OCZEKIWANE_SLUGI = {
    "definiowanie-implikacji",
    "podstawianie",
    "lacznosc-alternatywy",
    "przemiennosc-alternatywy",
    "de-morgan-1",
    "podwojne-przeczenie",
    "idempotencja-alternatywy",
    "zastepowanie-rownych",
}

TABELA = re.compile(r"<table\b[^>]*>(?P<tresc>.*?)</table>", re.DOTALL)
WIERSZ = re.compile(r"<tr[^>]*>(?P<tresc>.*?)</tr>", re.DOTALL)
KOMORKA = re.compile(r"<t[dh][^>]*>(?P<tresc>.*?)</t[dh]>", re.DOTALL)
SEKCJA_TABELI = re.compile(r"<tbody>(?P<tresc>.*?)</tbody>", re.DOTALL)
SEKCJA_NAGLOWKOW = re.compile(r"<thead>(?P<tresc>.*?)</thead>", re.DOTALL)
LANCUCH = re.compile(r'<div class="lancuch-formul"[^>]*>(?P<tresc>.*?)</div>', re.DOTALL)
KROKI_PODSTAWIANIA = re.compile(r'<ol class="kroki-podstawiania">(?P<tresc>.*?)</ol>', re.DOTALL)
PODSTAWY = re.compile(r'<ul class="lista-podstawien">(?P<tresc>.*?)</ul>', re.DOTALL)

#: Wyrażenie wstawiane do HTML przez filtr ``|safe``.
WZORZEC_SAFE = re.compile(r"\{\{(?P<wyrazenie>.*?)\|\s*safe\s*\}\}", re.DOTALL)

SZABLON = Path(__file__).resolve().parents[1] / "app" / "templates" / "przeksztalcanie.html"

#: Wzory, które strona musi pokazać jako HTML z ``to_html`` (nigdy jako zwykły tekst).
WZORY_STRONY: list[str] = [
    *[ogniwo.formula for ogniwo in przeksztalcanie.LANCUCH],
    przeksztalcanie.IMPLIKACJA_LEWA,
    przeksztalcanie.IMPLIKACJA_PRAWA,
    przeksztalcanie.PODSTAWIENIE_BAZA,
    przeksztalcanie.PODSTAWIENIE_P,
    przeksztalcanie.PODSTAWIENIE_Q,
    przeksztalcanie.PODSTAWIENIE_WYNIK,
    *[krok.formula for krok in przeksztalcanie.KROKI_UPROSZCZENIA],
    *[krok.wzor_prawa for krok in przeksztalcanie.KROKI_UPROSZCZENIA if krok.wzor_prawa],
    przeksztalcanie.UPROSZCZENIE_START,
    przeksztalcanie.UPROSZCZENIE_KONIEC,
]


@pytest.fixture(scope="module")
def klient():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def html(klient):
    odpowiedz = klient.get(ADRES)
    assert odpowiedz.status_code == 200
    return odpowiedz.get_data(as_text=True)


@pytest.fixture(scope="module")
def tekst(html):
    """Cała strona jako tekst: bez znaczników, z pojedynczymi spacjami."""
    return _tekst(html)


# --- narzędzia ---------------------------------------------------------------


def _tekst(fragment: str) -> str:
    """Zamienia fragment HTML na tekst: usuwa znaczniki, odmienia encje i skleja spacje."""
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment))).strip()


def _znak(wartosc: bool) -> str:
    """Wartość logiczna tak, jak na stronie: ``1`` albo ``0``."""
    return "1" if wartosc else "0"


def _wzor_html(wzor: str) -> str:
    """Wzór jako HTML z ``formula.to_html`` — to samo, co wstawia strona."""
    return str(przeksztalcanie.formula_to_html(wzor))


def _wzor_tekstem(wzor: str | Node) -> str:
    """Tekst wzoru tak, jak przeczyta go człowiek: bez znaczników HTML."""
    drzewo = parse(wzor) if isinstance(wzor, str) else wzor
    return _tekst(str(to_html(drzewo)))


def _nazwy(slugi: Sequence[str], dzialania: Sequence[str] = ()) -> list[str]:
    """Nazwy praw i działań tak, jak pokaże je strona."""
    return [wpis["nazwa"] for wpis in przeksztalcanie.prawa_kroku(slugi, dzialania)]


def _tabela(html: str, podpis: str) -> str:
    """Treść tablicy, której podpis (``<caption>``) zawiera dany fragment."""
    pasujace = [tresc for tresc in TABELA.findall(html) if podpis in tresc]
    assert len(pasujace) == 1, f"nie znalazłem dokładnie jednej tablicy z {podpis!r}"
    return pasujace[0]


def _naglowki(tabela: str) -> list[str]:
    """Teksty nagłówków kolumn tablicy, w kolejności ze strony."""
    tresc = SEKCJA_NAGLOWKOW.search(tabela).group("tresc")
    return [_tekst(komorka) for komorka in KOMORKA.findall(tresc)]


def _wiersze(tabela: str) -> list[list[str]]:
    """Teksty komórek kolejnych wierszy tablicy."""
    tresc = SEKCJA_TABELI.search(tabela).group("tresc")
    return [
        [_tekst(komorka) for komorka in KOMORKA.findall(wiersz)] for wiersz in WIERSZ.findall(tresc)
    ]


def _lancuch(html: str) -> str:
    """Surowy HTML łańcucha równoważności z punktu 1."""
    dopasowanie = LANCUCH.search(html)
    assert dopasowanie is not None, "brak łańcucha równoważności na stronie"
    return dopasowanie.group("tresc")


def _oczekiwane(wzor: str, zmienne: str, uklad: tuple[int, ...]) -> str:
    """Liczy wartość wzoru dla układu zapisanego jako ``(1, 0, …)``."""
    wartosci = dict(zip(zmienne, (bool(int(znak)) for znak in uklad), strict=True))
    return _znak(evaluate(parse(wzor), wartosci))


def _uklady(zmienne: str) -> Iterator[tuple[int, ...]]:
    """Wszystkie układy wartości zmiennych jako krotki zer i jedynek."""
    yield from product((1, 0), repeat=len(zmienne))


def _w_kolejnosci(tekst: str, fragmenty: Sequence[str]) -> None:
    """Sprawdza, że fragmenty występują w tekście w podanej kolejności, bez powtórzeń."""
    od = 0
    for fragment in fragmenty:
        pozycja = tekst.find(fragment, od)
        assert pozycja >= 0, f"brak {fragment!r} po pozycji {od} w: {tekst!r}"
        od = pozycja + len(fragment)


# --- szkielet strony ---------------------------------------------------------


def test_strona_odpowiada_200_i_html_utf8(klient):
    odpowiedz = klient.get(ADRES)
    assert odpowiedz.status_code == 200
    typ_tresci = odpowiedz.headers["Content-Type"]
    assert typ_tresci.startswith("text/html")
    assert "charset=utf-8" in typ_tresci.lower()


def test_strona_ma_jezyk_polski_i_dokladnie_jeden_h1(html):
    assert 'lang="pl"' in html
    assert len(re.findall(r"<h1\b", html)) == 1


def test_strona_nie_zostawia_nieuzupelnionych_szablonow(html):
    assert "{{" not in html
    assert "{%" not in html


# --- punkt 1: łańcuch czterech formuł ----------------------------------------


def test_lancuch_ma_cztery_formuly_w_kolejnosci_z_wykladu(html):
    _w_kolejnosci(
        _tekst(_lancuch(html)),
        [_wzor_tekstem(ogniwo.formula) for ogniwo in przeksztalcanie.LANCUCH],
    )


def test_lancuch_ma_cztery_ogniwa():
    assert len(przeksztalcanie.LANCUCH) == 4, "wykład pokazuje cztery formuły"


def test_lancuch_podaje_prawo_przy_kazdym_przejściu(html):
    """Przy każdym ``≡`` stoi nazwa prawa: łączność, opuszczanie nawiasów, przemienność."""
    oczekiwane: list[str] = []
    for ogniwo in przeksztalcanie.LANCUCH:
        if ogniwo.slugi or ogniwo.dzialania:
            oczekiwane.append(przeksztalcanie.SPOJNIK_ROWNAWAZANIA)
            oczekiwane.extend(_nazwy(ogniwo.slugi, ogniwo.dzialania))
        oczekiwane.append(_wzor_tekstem(ogniwo.formula))

    tresc = _tekst(_lancuch(html))
    _w_kolejnosci(tresc, oczekiwane)
    assert tresc.count(przeksztalcanie.SPOJNIK_ROWNAWAZANIA) == 3, "trzy przejścia"


def test_lancuch_pokazuje_prawo_lacznosci_i_przemiennosci(html):
    tresc = _tekst(_lancuch(html))

    assert _nazwy(["lacznosc-alternatywy"])[0] in tresc
    assert _nazwy(["przemiennosc-alternatywy"])[0] in tresc
    assert "opuszczanie nawiasów" in tresc


def test_strona_pokazuje_formuly_lancucha_przez_to_html(html):
    tresc = _lancuch(html)
    for ogniwo in przeksztalcanie.LANCUCH:
        assert _wzor_html(ogniwo.formula) in tresc


def test_strona_tlumaczy_ze_nawias_zewnetrzny_nic_nie_zmienia(tekst):
    assert "Nawias zewnętrzny" in tekst
    assert "nic nie zmienia" in tekst


def test_spojnik_lancucha_to_ten_sam_znak_co_w_to_html():
    """Spójnik ``≡`` na stronie ma ten sam znak i klasę, co operator z ``to_html``."""
    spojnik = f'<span class="op-iff">{przeksztalcanie.SPOJNIK_ROWNAWAZANIA}</span>'

    assert spojnik in to_html(parse("p ≡ q"))


# --- punkt 2: ostrzeżenie o implikacji ---------------------------------------


def test_strona_pokazuje_obie_formuly_implikacji_przez_to_html(html):
    assert _wzor_html(przeksztalcanie.IMPLIKACJA_LEWA) in html
    assert _wzor_html(przeksztalcanie.IMPLIKACJA_PRAWA) in html


def test_implikacje_nie_sa_rownowazne():
    """Sedno ostrzeżenia: obie formuły różnią się wynikiem przy którymś wartościowaniu."""
    lewa = parse(przeksztalcanie.IMPLIKACJA_LEWA)
    prawa = parse(przeksztalcanie.IMPLIKACJA_PRAWA)

    assert truth.equivalent(lewa, prawa) is False
    assert truth.counterexample(lewa, prawa) is not None
    assert not truth.is_tautology(
        parse(f"{przeksztalcanie.IMPLIKACJA_LEWA} ≡ {przeksztalcanie.IMPLIKACJA_PRAWA}")
    )


def test_tabela_implikacji_ma_osiem_wierszy_i_kolumne_roznicy(html):
    tabela = _tabela(html, PODPIS_IMPLIKACJI)
    naglowki = _naglowki(tabela)

    assert naglowki[:3] == ["p", "q", "r"]
    assert naglowki[3] == _wzor_tekstem(przeksztalcanie.IMPLIKACJA_LEWA)
    assert naglowki[4] == _wzor_tekstem(przeksztalcanie.IMPLIKACJA_PRAWA)
    assert naglowki[5] == "różnica"
    assert len(_wiersze(tabela)) == 8, "trzy zmienne to osiem wartościowań"


def test_tabela_implikacji_pokazuje_kontrprzyklad(html):
    """Kontrprzykład jest realny: wiersz, w którym wzory mają różne wartości."""
    wiersze = _wiersze(_tabela(html, PODPIS_IMPLIKACJI))
    rozne = [wiersz for wiersz in wiersze if wiersz[5] == "tak"]
    niezgodne = [wiersz for wiersz in wiersze if (wiersz[3] != wiersz[4]) != (wiersz[5] == "tak")]

    assert niezgodne == [], "kolumna „różnica” musi zgadzać się z wartościami w wierszu"
    assert rozne, "bez kontrprzykładu ostrzeżenie o implikacji nie ma pokrycia"
    for wiersz in rozne:
        uklad = (int(wiersz[0]), int(wiersz[1]), int(wiersz[2]))
        assert wiersz[3] != wiersz[4], "kontrprzykład musi mieć różne wartości"
        assert wiersz[3] == _oczekiwane(przeksztalcanie.IMPLIKACJA_LEWA, "pqr", uklad)
        assert wiersz[4] == _oczekiwane(przeksztalcanie.IMPLIKACJA_PRAWA, "pqr", uklad)


def test_tabela_implikacji_liczy_sie_z_evaluate(html):
    """Wszystkie wartości w tabeli muszą zgadzać się z tym, co liczy ``evaluate``."""
    wzory = [przeksztalcanie.IMPLIKACJA_LEWA, przeksztalcanie.IMPLIKACJA_PRAWA]

    for wiersz in _wiersze(_tabela(html, PODPIS_IMPLIKACJI)):
        uklad = (int(wiersz[0]), int(wiersz[1]), int(wiersz[2]))
        assert wiersz[3:5] == [_oczekiwane(wzor, "pqr", uklad) for wzor in wzory]
        assert wiersz[5] == ("tak" if wiersz[3] != wiersz[4] else "nie")


def test_wniosek_o_implikacji_mowi_o_roznicy(tekst):
    dane = przeksztalcanie.porownanie(
        przeksztalcanie.IMPLIKACJA_LEWA, przeksztalcanie.IMPLIKACJA_PRAWA
    )

    assert "już jeden taki wiersz wystarczy" in tekst
    assert "nie są równoważne" in tekst
    assert f"różnią się w {dane['roznich']} z {dane['wszystkich']} wierszy" in tekst


def test_strona_wstawia_partial_tablicy_prawdy(html):
    """Punkt 2 wykładu: tablica dla ``(p → q) → r`` przez partial (PRZ-011)."""
    assert 'class="truth-table-mount"' in html
    assert f'data-formula="{przeksztalcanie.IMPLIKACJA_LEWA}"' in html
    assert "partials/_truth_table.html" in SZABLON.read_text("utf-8")


# --- punkt 3: reguła podstawiania --------------------------------------------


def test_podstawianie_ma_trzy_kroki(html):
    dopasowanie = KROKI_PODSTAWIANIA.search(html)
    assert dopasowanie is not None, "brak listy kroków podstawiania"

    tresc = dopasowanie.group("tresc")
    assert tresc.count("<h3>") == 3, "podstawianie pokazujemy w trzech krokach"
    _w_kolejnosci(_tekst(tresc), [krok.tytul for krok in przeksztalcanie.KROKI_PODSTAWIENIA])


def test_kroki_podstawiania_pokazuja_formuly_przez_to_html(html):
    dopasowanie = KROKI_PODSTAWIANIA.search(html)
    tresc = dopasowanie.group("tresc")

    for wzor in [
        przeksztalcanie.PODSTAWIENIE_BAZA,
        przeksztalcanie.PODSTAWIENIE_P,
        przeksztalcanie.PODSTAWIENIE_Q,
    ]:
        assert _wzor_html(wzor) in tresc, f"krok bez wyniku to_html dla {wzor!r}"


def test_podstawianie_pokazuje_co_wchodzi_pod_jaka_zmienna(html):
    """Krok 2 mówi wprost: pod ``p`` wchodzi jedna formuła, pod ``q`` druga."""
    dopasowanie = PODSTAWY.search(html)
    assert dopasowanie is not None, "brak listy podstawień"

    tresc = _tekst(dopasowanie.group("tresc"))
    _w_kolejnosci(
        tresc,
        [
            f"pod {_wzor_tekstem('p')} wstawiamy {_wzor_tekstem(przeksztalcanie.PODSTAWIENIE_P)}",
            f"pod {_wzor_tekstem('q')} wstawiamy {_wzor_tekstem(przeksztalcanie.PODSTAWIENIE_Q)}",
        ],
    )


def test_strona_pokazuje_wynik_podstawienia(html):
    assert _wzor_html(przeksztalcanie.PODSTAWIENIE_WYNIK) in html


def test_wynik_podstawienia_jest_tautologia(tekst):
    """Podstawienie do tautologii musi dać tautologię — sprawdzamy to i pokazujemy."""
    wynik = przeksztalcanie.PODSTAWIENIE_WYNIK
    wierszy = len(truth.build(parse(wynik), with_subformulas=False).rows)

    assert truth.is_tautology(parse(wynik)) is True
    assert "Sprawdzone tablicą prawdy" in tekst
    assert f"same jedynki w {wierszy} wierszach" in tekst
    assert "też jest tautologią" in tekst


def test_strona_odroznia_podstawianie_od_zastepowania_rownych(html, tekst):
    prawo = get(przeksztalcanie.ZASTEPOWANIE_ROWNYCH)
    assert prawo is not None

    assert "To nie to samo co prawo zastępowania równych" in tekst
    assert f'href="/prawa/{prawo.slug}"' in html
    assert _wzor_html(prawo.formula) in html


# --- punkt 4: upraszczanie krok po kroku -------------------------------------


def test_tabela_uproszczenia_ma_piec_krokow_i_cztery_kolumny(html):
    tabela = _tabela(html, PODPIS_UPROSZCZENIA)

    assert _naglowki(tabela) == ["krok", "formuła", "prawa", "wyjaśnienie"]
    wiersze = _wiersze(tabela)
    assert len(wiersze) == 5, "wykład pokazuje pięć kroków, od kroku 0"
    assert [int(wiersz[0]) for wiersz in wiersze] == [0, 1, 2, 3, 4]


def test_kazdy_krok_uproszczenia_pokazuje_formule_i_wyjasnienie(html):
    wiersze = _wiersze(_tabela(html, PODPIS_UPROSZCZENIA))

    for wiersz, krok in zip(wiersze, przeksztalcanie.KROKI_UPROSZCZENIA, strict=True):
        assert wiersz[1] == _wzor_tekstem(krok.formula)
        assert wiersz[3] == krok.wyjasnienie


def test_kazdy_krok_uproszczenia_podaje_prawa(html):
    tabela = _tabela(html, PODPIS_UPROSZCZENIA)
    wiersze = _wiersze(tabela)

    for wiersz, krok in zip(wiersze, przeksztalcanie.KROKI_UPROSZCZENIA, strict=True):
        prawa = przeksztalcanie.prawa_kroku(krok.slugi, krok.dzialania)
        if not prawa:
            assert wiersz[2] == "—", "krok startowy nie powołuje się na żadne prawo"
            continue
        for wpis in prawa:
            assert wpis["nazwa"] in wiersz[2]
            if wpis["slug"]:
                assert f'href="/prawa/{wpis["slug"]}"' in tabela
        if krok.wzor_prawa:
            assert _wzor_tekstem(krok.wzor_prawa) in wiersz[2]


def test_kolejne_kroki_uproszczenia_sa_rownowazne():
    """Każdy krok wolno zrobić, bo po nim formuła znaczy to samo."""
    for przed, po in pairwise(przeksztalcanie.KROKI_UPROSZCZENIA):
        assert truth.equivalent(parse(przed.formula), parse(po.formula)), (
            f"krok {przed.formula!r} → {po.formula!r} nie jest równoważnością"
        )


def test_upraszczanie_konczy_sie_formula_z_wykladu():
    assert _wzor_tekstem(przeksztalcanie.UPROSZCZENIE_KONIEC) == _wzor_tekstem("∼p ∨ r ∨ q")
    assert truth.is_tautology(
        parse(f"({przeksztalcanie.UPROSZCZENIE_START}) ≡ ({przeksztalcanie.UPROSZCZENIE_KONIEC})")
    )


def test_strona_pisze_o_prawie_dodatkowym(tekst):
    assert "prawo dodatkowe" in tekst
    assert "nie nadaje mu numeru T" in tekst


# --- punkt 5: sprawdzenie wyniku ---------------------------------------------


def test_tabela_sprawdzenia_nie_ma_zadnej_roznicy(html):
    tabela = _tabela(html, PODPIS_SPRAWDZENIA)
    naglowki = _naglowki(tabela)

    assert naglowki[3] == _wzor_tekstem(przeksztalcanie.UPROSZCZENIE_START)
    assert naglowki[4] == _wzor_tekstem(przeksztalcanie.UPROSZCZENIE_KONIEC)
    wiersze = _wiersze(tabela)
    assert len(wiersze) == 8
    assert {wiersz[5] for wiersz in wiersze} == {"nie"}, "wzory są równoważne w każdym wierszu"
    for wiersz in wiersze:
        assert wiersz[3] == wiersz[4]


def test_wynik_uproszczenia_jest_rownowazny_z_formula_wejściowa():
    assert (
        truth.equivalent(
            parse(przeksztalcanie.UPROSZCZENIE_START),
            parse(przeksztalcanie.UPROSZCZENIE_KONIEC),
        )
        is True
    )


def test_wniosek_sprawdzenia_mowi_o_rownowaznosci(tekst):
    dane = przeksztalcanie.porownanie(
        przeksztalcanie.UPROSZCZENIE_START, przeksztalcanie.UPROSZCZENIE_KONIEC
    )

    assert f"tę samą wartość w każdym z {dane['wszystkich']} wierszy" in tekst
    assert "więc są równoważne" in tekst


def test_strona_odsyla_do_placu_zabaw(html, tekst):
    assert 'href="/plac-zabaw"' in html
    assert "plac zabaw" in tekst


# --- nawigacja i bezpieczeństwo szablonu -------------------------------------


def test_strona_ma_odnosniki_poprzedniej_i_nastepnej_lekcji(html, tekst):
    assert 'href="/tautologie"' in html
    assert 'href="/kpn"' in html
    assert "Poprzednia lekcja" in tekst
    assert "Następna lekcja" in tekst


def test_wzory_na_stronie_sa_html_em_z_to_html(html):
    """Każdy wzór lekcji musi być w HTML, a nie cofnięty do zwykłego tekstu."""
    for wzor in WZORY_STRONY:
        oczekiwany = _wzor_html(wzor)
        assert '<span class="op-' in oczekiwany, f"to_html zwrócił tekst dla {wzor!r}"
        assert oczekiwany in html, f"brak wyniku to_html dla {wzor!r}"


def test_szablon_uzywa_safe_tylko_na_wyniku_to_html():
    wyrazenia = [
        dopasowanie["wyrazenie"].strip()
        for dopasowanie in WZORZEC_SAFE.finditer(SZABLON.read_text("utf-8"))
    ]

    assert wyrazenia, "szablon nie wstawia wzorów przez |safe"
    for wyrazenie in wyrazenia:
        assert "formula_to_html" in wyrazenie, f"|safe na {wyrazenie!r}"


# --- funkcje pomocnicze modułu -----------------------------------------------


def test_formula_to_html_zamienia_zwykly_tekst_bez_bledu():
    wynik = przeksztalcanie.formula_to_html("podstawienie (bez wzoru")

    assert isinstance(wynik, Markup)
    assert wynik == "podstawienie (bez wzoru"


def test_formula_to_html_zwraca_html_dla_wzoru():
    assert str(przeksztalcanie.formula_to_html("∼p")) == str(to_html(parse("∼p")))


def test_slugi_uzyte_przez_strone_istnieja_w_rejestrze():
    slugi = {slug for ogniwo in przeksztalcanie.LANCUCH for slug in ogniwo.slugi}
    slugi |= {slug for krok in przeksztalcanie.KROKI_PODSTAWIENIA for slug in krok.slugi}
    slugi |= {slug for krok in przeksztalcanie.KROKI_UPROSZCZENIA for slug in krok.slugi}
    slugi.add(przeksztalcanie.ZASTEPOWANIE_ROWNYCH)

    assert slugi == OCZEKIWANE_SLUGI
    for slug in slugi:
        assert get(slug) is not None, f"nie ma prawa {slug!r} w rejestrze"


def test_opis_prawa_zwraca_nazwe_i_odnosnik():
    opis = przeksztalcanie.opis_prawa("de-morgan-1")
    prawo = get("de-morgan-1")

    assert opis["nazwa"] == prawo.nazwa
    assert opis["slug"] == "de-morgan-1"
    assert opis["formula"] == prawo.formula


def test_opis_prawa_nie_zna_sluga_bez_odnosnika():
    """Nieznany slug nie może dać odnośnika do strony, której nie ma."""
    opis = przeksztalcanie.opis_prawa("nie-ma-takiego-prawa")

    assert opis["slug"] is None
    assert opis["nazwa"] == "nie-ma-takiego-prawa"


def test_prawa_kroku_dokłada_dzialania_bez_prawa():
    prawa = przeksztalcanie.prawa_kroku([], ["opuszczanie nawiasów"])

    assert prawa == [{"nazwa": "opuszczanie nawiasów", "slug": None, "formula": ""}]


def test_porownanie_liczy_wiersze_i_roznice():
    dane = przeksztalcanie.porownanie("p → q", "q → p")

    assert dane["zmienne"] == ["p", "q"]
    assert dane["wszystkich"] == 4
    assert dane["roznich"] == 2, "implikacja nie jest przemienna"
    assert dane["wiersze"][0] == {
        "zmienne": ["1", "1"],
        "lewa": "1",
        "prawa": "1",
        "rozny": False,
    }


def test_porownanie_znajduje_rownowaznosc():
    dane = przeksztalcanie.porownanie("p → q", "∼q → ∼p")

    assert dane["roznich"] == 0
    assert {wiersz["rozny"] for wiersz in dane["wiersze"]} == {False}


def test_wniosek_porownania_mowi_o_rownowaznosci_i_roznicy():
    rownowazne = przeksztalcanie.porownanie("p", "p")
    rozne = przeksztalcanie.porownanie("p", "∼p")

    assert "więc są równoważne" in przeksztalcanie.wniosek_porownania(rownowazne)
    assert "nie są równoważne" in przeksztalcanie.wniosek_porownania(rozne)


def test_wniosek_podstawienia_ostrzega_gdy_wynik_nie_jest_tautologia():
    """Gdyby ktoś podmienił wzór wyniku, wniosek na stronie też to pokaże."""
    wniosek = przeksztalcanie.wniosek_podstawienia("p ∧ ∼p")

    assert "nie ma samych jedynek" in wniosek


def test_uklady_zwracaja_wszystkie_wartosciowania():
    assert set(_uklady("pq")) == {(1, 1), (1, 0), (0, 1), (0, 0)}
