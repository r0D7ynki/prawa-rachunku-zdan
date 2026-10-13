"""Testy widoków praw: ``/prawa``, ``/prawa/<slug>`` i ``GET /api/prawa``.

Testy przechodzą po całym rejestrze (``all_laws()``) i **nie zakładają liczby praw** —
nowy plik treści w ``laws_data/`` ma je poszerzyć, a nie zepsuć. Dlatego każdy test
o treści jest parametryzowany prawem, a nie indeksem.

Oczekiwany wzór porównujemy zawsze z ``formula.to_html(formula.parse(...))``. To dowód
kryterium „każda formuła idzie przez ``to_html``”: gdyby szablon wstawiał surowy napis,
porównanie albo brak klas ``op-…`` by to pokazały.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from markupsafe import escape

from app import create_app
from app.blueprints import laws as widoki
from app.logic import formula, laws
from app.logic.law_model import Law
from app.logic.laws import all_laws, by_category

#: Prawa z rejestru — testy nie wpisują ich liczby na stałe.
PRAWA = all_laws()

KATALOG_APP = Path(__file__).resolve().parents[1] / "app"
SZABLON_PRAWA = KATALOG_APP / "templates" / "prawo.html"
SZABLON_LISTY = KATALOG_APP / "templates" / "prawa_lista.html"

#: Cztery partiale, których wymaga karta PRZ-010: tablica prawdy w sekcji „Tablica
#: prawdy”, a rysunek wybrany polem ``Law.wizualizacja`` (patrz ``widoki.RYSUNKI``).
PARTIAL_TABLICY = "partials/_truth_table.html"
PARTIALE_RYSUNKOW = {
    "partials/_gates.html",
    "partials/_sets.html",
    "partials/_steps.html",
}

#: Rysunek oczekiwany dla każdej wartości ``Law.wizualizacja``:
#: (klasa elementu-montażu, ``data-rola``).
OCZEKIWANY_RYSUNEK = {
    "gates": ("gates-mount", "bramki-logiczne"),
    "switch": ("gates-mount", "bramki-logiczne"),
    "sets": ("sets-mount", "diagramy-zbiorow"),
    "chain": ("steps-mount", "kroki-przeksztalcen"),
}

#: Kolejność sekcji strony prawa (identyfikatory ``<h2 id="…">``).
KOLEJNOSC_SEKCJI = [
    "naglowek-po-ludzku",
    "naglowek-przyklad",
    "naglowek-kroki",
    "naglowek-tablica-prawdy",
    "naglowek-rysunek",
    "naglowek-czeste-bledy",
    "naglowek-quiz",
]

WZORZEC_SAFE = re.compile(r"\{\{(?P<wyrazenie>.*?)\|\s*safe\s*\}\}", re.DOTALL)
WZORZEC_NAV = re.compile(r'aria-label="Nawigacja między prawami"(?P<tresc>.*?)</nav>', re.DOTALL)


def _slug(law: Law) -> str:
    """Identyfikator prawa w nazwie testu."""
    return law.slug


def _wzor_html(text: str, styl: str = "wyklad") -> str:
    """Oczekiwany HTML wzoru: dokładnie to, co zwraca ``formula.to_html``."""
    return formula.to_html(formula.parse(text), styl)


def _element(html: str, ident: str) -> str:
    """Zwraca wnętrze elementu o podanym ``id`` (bez otaczających znaczników)."""
    wzorzec = re.compile(rf'<dd id="{re.escape(ident)}"[^>]*>(?P<tresc>.*?)</dd>', re.DOTALL)
    dopasowanie = wzorzec.search(html)
    assert dopasowanie, f"brak elementu #{ident} na stronie"
    return dopasowanie["tresc"].strip()


def _nawigacja(html: str) -> str:
    """Zwraca HTML nawigacji „poprzednie / następne prawo”."""
    dopasowanie = WZORZEC_NAV.search(html)
    assert dopasowanie, "brak nawigacji między prawami (aria-label)"
    return dopasowanie["tresc"]


def _widac(html: str, tekst: str) -> bool:
    """Czy tekst widać na stronie — tak, jak zapisze go Jinja (z escapowaniem)."""
    return str(escape(tekst)) in html


@pytest.fixture(scope="module")
def klient():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def lista_html(klient) -> str:
    """HTML listy praw — jedno pobranie na cały moduł."""
    odpowiedz = klient.get("/prawa")
    assert odpowiedz.status_code == 200
    return odpowiedz.get_data(as_text=True)


@pytest.fixture(scope="module")
def strony(klient) -> dict[str, str]:
    """HTML strony każdego prawa, kluczowany po ``slug``."""
    wynik: dict[str, str] = {}
    for law in PRAWA:
        odpowiedz = klient.get(f"/prawa/{law.slug}")
        assert odpowiedz.status_code == 200, f"strona prawa {law.slug} nie odpowiada 200"
        wynik[law.slug] = odpowiedz.get_data(as_text=True)
    return wynik


# --- rejestracja widoków -----------------------------------------------------


def test_widoki_praw_sa_zarejestrowane():
    zarejestrowane = create_app({"TESTING": True}).config["BLUEPRINTS"]

    assert "laws" in zarejestrowane
    assert "api_laws" in zarejestrowane


def test_rejestr_ma_jakies_prawa():
    assert PRAWA, "rejestr praw jest pusty — nie ma czego testować"


# --- funkcje pomocnicze (bez przeglądarki) -----------------------------------


def test_formula_html_uzywa_to_html():
    wynik = widoki.formula_to_html("p ∨ ∼p")

    assert str(wynik) == _wzor_html("p ∨ ∼p")
    assert '<span class="op-or">' in str(wynik)
    assert '<span class="op-neg">' in str(wynik)


def test_formula_html_z_stylem_ascii_ma_te_same_klasy():
    wynik = str(widoki.formula_to_html("p | ~p", "ascii"))

    assert wynik == _wzor_html("p | ~p", "ascii")
    assert "|" in wynik and "~" in wynik
    assert '<span class="op-or">' in wynik
    assert '<span class="op-neg">' in wynik


@pytest.mark.parametrize("tekst", ["to nie jest formuła ((", "", "p ∧"])
def test_formula_html_nigdy_nie_podnosi_bledu(tekst):
    wynik = str(widoki.formula_to_html(tekst))

    assert wynik == str(escape(tekst)), "niepoprawny wzór pokazujemy jako tekst"


def test_rysunki_pokrywaja_wszystkie_dozwolone_wizualizacje():
    assert set(widoki.RYSUNKI) == set(laws.WIZUALIZACJE)
    assert {law.wizualizacja for law in PRAWA} <= set(widoki.RYSUNKI)


def test_kazdy_rysunek_wskazuje_istniejacy_partial():
    for partial in widoki.RYSUNKI.values():
        assert (KATALOG_APP / "templates" / partial).is_file(), f"brak {partial}"


def test_neighbours_pierwsze_prawo_nie_ma_poprzedniego():
    poprzednie, nastepne = widoki.neighbours(PRAWA[0])

    assert poprzednie is None
    assert nastepne is not None


def test_neighbours_ostatnie_prawo_nie_ma_nastepnego():
    poprzednie, nastepne = widoki.neighbours(PRAWA[-1])

    assert poprzednie is not None
    assert nastepne is None


def test_neighbours_srodkowe_prawo_ma_oba_sasiady():
    if len(PRAWA) < 3:
        pytest.skip("rejestr ma mniej niż trzy prawa")

    poprzednie, nastepne = widoki.neighbours(PRAWA[1])

    assert poprzednie is PRAWA[0]
    assert nastepne is PRAWA[2]


def test_neighbours_prawo_spoza_rejestru_nie_udaje_sasiadow():
    obce = Law(
        slug="spoza-rejestru",
        nazwa="Prawo spoza rejestru",
        kategoria="podstawowe",
        formula="p ∨ ∼p",
        formula_ascii="p | ~p",
        lewa="p ∨ ∼p",
        prawa="p ∨ ~p",
        po_ludzku="Treść.",
        przyklad="Przykład.",
        kroki=[],
        czeste_bledy=[],
        wizualizacja="chain",
        quiz=[],
    )

    assert widoki.neighbours(obce) == (None, None)


def test_neighbours_z_jednym_prawem_w_rejestrze(monkeypatch):
    monkeypatch.setattr(widoki, "all_laws", lambda: [PRAWA[0]])

    assert widoki.neighbours(PRAWA[0]) == (None, None)


# --- lista /prawa ------------------------------------------------------------


def test_lista_odpowiada_200_i_html_utf8(klient):
    odpowiedz = klient.get("/prawa")

    assert odpowiedz.status_code == 200
    typ_tresci = odpowiedz.headers["Content-Type"]
    assert typ_tresci.startswith("text/html")
    assert "charset=utf-8" in typ_tresci.lower()


def test_lista_ma_jezyk_polski_i_dokladnie_jeden_h1(lista_html):
    assert 'lang="pl"' in lista_html
    assert len(re.findall(r"<h1\b", lista_html)) == 1


def test_lista_nie_zostawia_nieuzupelnionych_szablonow(lista_html):
    assert "{{" not in lista_html
    assert "{%" not in lista_html


@pytest.mark.parametrize("law", PRAWA, ids=_slug)
def test_lista_ma_link_do_strony_kazdego_prawa(lista_html, law):
    assert f'href="/prawa/{law.slug}"' in lista_html, f"brak odnośnika do {law.slug}"


@pytest.mark.parametrize("law", PRAWA, ids=_slug)
def test_lista_pokazuje_nazwe_i_wzor_kazdego_prawa(lista_html, law):
    assert _widac(lista_html, law.nazwa), f"brak nazwy prawa {law.slug}"
    assert _wzor_html(law.formula) in lista_html, f"brak wzoru prawa {law.slug}"


def test_lista_grupuje_prawa_po_kategorii(lista_html):
    grupy = by_category()

    assert len(re.findall(r'aria-labelledby="kategoria-\d+"', lista_html)) == len(grupy)
    for kategoria in grupy:
        assert _widac(lista_html, kategoria), f"brak nagłówka kategorii {kategoria!r}"


# --- strona /prawa/<slug> ----------------------------------------------------


@pytest.mark.parametrize("law", PRAWA, ids=_slug)
def test_strona_prawa_ma_polski_jezyk_i_jeden_h1(strony, law):
    html = strony[law.slug]

    assert 'lang="pl"' in html
    assert len(re.findall(r"<h1\b", html)) == 1
    assert _widac(html, law.nazwa), "nazwa prawa musi być nagłówkiem strony"


@pytest.mark.parametrize("law", PRAWA, ids=_slug)
def test_strona_prawa_nie_zostawia_nieuzupelnionych_szablonow(strony, law):
    html = strony[law.slug]

    assert "{{" not in html
    assert "{%" not in html


@pytest.mark.parametrize("law", PRAWA, ids=_slug)
def test_strona_prawa_pokazuje_wzor_wykładu_i_ascii_przez_to_html(strony, law):
    html = strony[law.slug]

    assert _element(html, "wzor-prawa") == _wzor_html(law.formula)
    assert _element(html, "wzor-ascii") == _wzor_html(law.formula_ascii, "ascii")


@pytest.mark.parametrize("law", PRAWA, ids=_slug)
def test_strona_prawa_ma_wyjasnienie_i_przyklad(strony, law):
    html = strony[law.slug]

    assert _widac(html, law.po_ludzku), "brak akapitu „Po ludzku”"
    assert _widac(html, law.przyklad), "brak akapitu „Przykład z życia”"


@pytest.mark.parametrize("law", PRAWA, ids=_slug)
def test_strona_prawa_ma_kazdy_krok_z_wzorami(strony, law):
    html = strony[law.slug]

    for numer, krok in enumerate(law.kroki, start=1):
        assert _widac(html, krok.opis), f"brak opisu kroku {numer} prawa {law.slug}"
        assert _wzor_html(krok.przed) in html, f"brak wzoru „przed” kroku {numer}"
        assert _wzor_html(krok.po) in html, f"brak wzoru „po” kroku {numer}"


@pytest.mark.parametrize("law", PRAWA, ids=_slug)
def test_strona_prawa_ma_kazdy_czesty_blad(strony, law):
    html = strony[law.slug]

    for numer, blad in enumerate(law.czeste_bledy, start=1):
        assert _widac(html, blad), f"brak błędu {numer} prawa {law.slug}"


@pytest.mark.parametrize("law", PRAWA, ids=_slug)
def test_strona_prawa_linkuje_do_quiz_i_listy(strony, law):
    html = strony[law.slug]

    assert f'href="/quiz?prawo={law.slug}"' in html
    assert '<a href="/prawa">' in html


@pytest.mark.parametrize("law", PRAWA, ids=_slug)
def test_strona_prawa_wstawia_tablice_prawdy_i_wlasciwy_rysunek(strony, law):
    html = strony[law.slug]
    klasa, rola = OCZEKIWANY_RYSUNEK[law.wizualizacja]

    assert 'class="truth-table-mount"' in html, "brak komponentu tablicy prawdy"
    assert 'data-rola="tablica-prawdy"' in html
    assert f'class="{klasa}"' in html, f"brak rysunku dla wizualizacji {law.wizualizacja!r}"
    assert f'data-rola="{rola}"' in html
    assert f'data-formula="{escape(law.formula)}"' in html, "komponent nie zna wzoru prawa"


@pytest.mark.parametrize("law", PRAWA, ids=_slug)
def test_strona_prawa_ma_sam_wzor_prawa_w_komponentach(strony, law):
    """Komponenty dostają wzór prawa, a nie wzór ostatniego kroku."""
    html = strony[law.slug]
    montaze = re.findall(r'data-formula="([^"]*)"', html)

    assert montaze, "strona prawa nie wstawia żadnego komponentu z wzorem"
    for wzor in montaze:
        assert wzor == str(escape(law.formula)), f"komponent dostał wzór {wzor!r}"


# --- szablony ----------------------------------------------------------------


def test_szablon_prawa_wstawia_tablice_prawdy_i_wybiera_rysunek():
    """Tablica prawdy stoi w szablonie, rysunek wybiera ``RYSUNKI`` w Pythonie.

    Dzięki temu regułę „``gates`` i ``switch`` → bramki, ``sets`` → zbiory,
    ``chain`` → kroki” sprawdza test funkcji, a nie porównywanie napisów w HTML.
    """
    tresc = SZABLON_PRAWA.read_text("utf-8")

    assert PARTIAL_TABLICY in tresc, "szablon prawo.html nie wstawia tablicy prawdy"
    assert "{% include rysunek %}" in tresc, "rysunek musi zależeć od pola wizualizacja"


def test_rysunki_uzywaja_wszystkich_trzech_partiali():
    assert set(widoki.RYSUNKI.values()) == PARTIALE_RYSUNKOW


def test_szablon_prawa_ma_sekcje_w_kolejnosci_z_karty():
    tresc = SZABLON_PRAWA.read_text("utf-8")
    pozycje = [tresc.index(sekcja) for sekcja in KOLEJNOSC_SEKCJI]

    assert pozycje == sorted(pozycje), "sekcje strony są w złej kolejności"


@pytest.mark.parametrize("szablon", [SZABLON_PRAWA, SZABLON_LISTY])
def test_szablony_uzywaja_safe_tylko_na_wzorach(szablon):
    wyrazenia = [d["wyrazenie"].strip() for d in WZORZEC_SAFE.finditer(szablon.read_text("utf-8"))]

    assert wyrazenia, f"{szablon.name} nie wstawia wzorów przez |safe"
    for wyrazenie in wyrazenia:
        assert "formula_to_html" in wyrazenie, f"|safe na {wyrazenie!r}"


# --- brak prawa (404) --------------------------------------------------------


def test_nieznany_adres_daje_404_po_polsku(klient):
    odpowiedz = klient.get("/prawa/nie-ma-takiego-prawa")
    html = odpowiedz.get_data(as_text=True)

    assert odpowiedz.status_code == 404
    assert odpowiedz.headers["Content-Type"].startswith("text/html")
    assert "Nie ma takiego prawa" in html
    assert 'href="/prawa"' in html, "komunikat musi prowadzić do listy praw"
    assert "{{" not in html
    assert "{%" not in html


def test_nieznany_adres_nie_wypisuje_znacznikow_z_adresu(klient):
    odpowiedz = klient.get("/prawa/%3Cscript%3Ealert(1)")
    html = odpowiedz.get_data(as_text=True)

    assert odpowiedz.status_code == 404
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# --- nawigacja poprzednie / następne ----------------------------------------


def _linki_nawigacji(html: str) -> list[str]:
    """Slugi praw, do których prowadzi nawigacja „poprzednie / następne”."""
    return re.findall(r'href="/prawa/([^"]+)"', _nawigacja(html))


def test_nawigacja_ukrywa_brakujacy_kierunek_na_poczatku_i_koncu(strony):
    """Wybór: brakujący kierunek jest **ukryty** — strona nie zawija listy.

    Zawijanie myliłoby czytelnika: przy pierwszym prawie nie wiadomo, czy
    „poprzednie” prowadzi do końca listy, czy do błędu.
    """
    assert _linki_nawigacji(strony[PRAWA[0].slug]) == [PRAWA[1].slug]
    assert _linki_nawigacji(strony[PRAWA[-1].slug]) == [PRAWA[-2].slug]


def test_nawigacja_prowadzi_do_sasiadow_z_rejestru(strony):
    if len(PRAWA) < 3:
        pytest.skip("rejestr ma mniej niż trzy prawa")

    assert _linki_nawigacji(strony[PRAWA[1].slug]) == [PRAWA[0].slug, PRAWA[2].slug]


def test_nawigacja_jest_zwyklymi_odnosnikami(strony):
    html = _nawigacja(strony[PRAWA[0].slug])

    assert '<a class="btn' in html
    assert "Następne prawo" in html


# --- API ---------------------------------------------------------------------


def test_api_praw_zwraca_liste_z_rejestru(klient):
    odpowiedz = klient.get("/api/prawa")

    assert odpowiedz.status_code == 200
    dane = odpowiedz.get_json()
    assert dane["ok"] is True
    assert len(dane["prawa"]) == len(PRAWA)
    assert [prawo["slug"] for prawo in dane["prawa"]] == [law.slug for law in PRAWA]


def test_api_praw_ma_dokladnie_umowione_pola(klient):
    pola = {"slug", "nazwa", "kategoria", "formula", "formula_ascii", "wizualizacja"}

    for prawo in klient.get("/api/prawa").get_json()["prawa"]:
        assert set(prawo) == pola


@pytest.mark.parametrize("law", PRAWA, ids=_slug)
def test_api_praw_zgadza_sie_z_rejestrem(klient, law):
    prawa = {prawo["slug"]: prawo for prawo in klient.get("/api/prawa").get_json()["prawa"]}
    wpis = prawa[law.slug]

    assert wpis["nazwa"] == law.nazwa
    assert wpis["kategoria"] == law.kategoria
    assert wpis["formula"] == law.formula
    assert wpis["formula_ascii"] == law.formula_ascii
    assert wpis["wizualizacja"] == law.wizualizacja


def test_api_praw_nie_wysyla_html_ani_odpowiedzi_quiz(klient):
    tresc = klient.get("/api/prawa").get_data(as_text=True)

    assert "<span" not in tresc
    assert "poprawna" not in tresc
