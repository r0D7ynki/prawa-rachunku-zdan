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
from html import unescape
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

#: Znaczniki wyróżnionego fragmentu kroku (karta PRZ-143) — otwierający i zamykający.
WZORZEC_MARK = re.compile(r'<mark class="krok-fragment"[^>]*>|</mark>')

#: Prawa, na których karta PRZ-143 sprawdza sekcję „Krok po kroku”.
PRAWA_KROKOW = ("de-morgan-1", "rozdzielnosc-1")

#: Zdanie wprowadzające sekcji kroków — wymaga go karta PRZ-143.
WPROWADZENIE_KROKOW = "Zamieniamy lewą stronę prawa na prawą."


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


def _bez_mark(html: str) -> str:
    """HTML bez znaczników ``<mark>``.

    Wzór z wyróżnionym fragmentem nie jest już znakiem w znak tym, co zwraca
    ``formula.to_html`` — ``<mark>`` stoi w środku. Zdjęcie samych znaczników
    odtwarza wyjście ``to_html``, więc test nadal pilnuje, że wzór idzie przez
    ``to_html``, a nie przez surowy napis (karta PRZ-143).
    """
    return WZORZEC_MARK.sub("", html)


def _sekcja_krokow(html: str) -> str:
    """Wnętrze sekcji „Krok po kroku”: od jej nagłówka do sekcji tablicy prawdy."""
    poczatek = html.index('id="naglowek-kroki"')
    koniec = html.index('id="naglowek-tablica-prawdy"')

    assert poczatek < koniec, "sekcja kroków musi stać przed tablicą prawdy"
    return html[poczatek:koniec]


def _kroki_sekcji(sekcja: str) -> list[str]:
    """Bloki ``<li class="krok">`` sekcji kroków, w kolejności ze strony."""
    return re.findall(r'<li class="krok">(?P<tresc>.*?)</li>', sekcja, re.DOTALL)


def _marki(blok: str) -> list[str]:
    """Teksty objęte znacznikiem ``<mark>`` w jednym kroku."""
    return re.findall(r'<mark class="krok-fragment"[^>]*>(?P<tresc>.*?)</mark>', blok, re.DOTALL)


def _tekst(html: str) -> str:
    """Sam tekst fragmentu HTML: bez znaczników, z rozwiązanymi encjami."""
    return unescape(re.sub(r"<[^>]+>", "", html)).strip()


def _zdanie_zmiany(blok: str) -> str:
    """Zdanie z różnicy pod jednym krokiem."""
    dopasowanie = re.search(r'<p class="krok-zmiana[^"]*">(?P<tresc>.*?)</p>', blok, re.DOTALL)

    assert dopasowanie, "krok ze zmianą musi mieć zdanie z różnicy"
    return _tekst(dopasowanie["tresc"])


def _fragmenty_zdania(zdanie: str) -> tuple[str, str]:
    """Fragmenty, które zdanie z różnicy nazywa: ``(przed, po)``.

    „Zamieniamy A na B” daje ``(A, B)``, „Dopisujemy B” — ``("", B)``,
    a „Usuwamy A” — ``(A, "")``. Pusty napis znaczy „ta strona się nie zmienia”.
    """
    bez_koncowki = zdanie.split(" — to ")[0]
    if bez_koncowki.startswith("Zamieniamy "):
        przed, _, po = bez_koncowki.removeprefix("Zamieniamy ").partition(" na ")
        return przed, po
    if bez_koncowki.startswith("Dopisujemy "):
        return "", bez_koncowki.removeprefix("Dopisujemy ")
    assert bez_koncowki.startswith("Usuwamy "), f"nieznane zdanie z różnicy: {zdanie!r}"
    return bez_koncowki.removeprefix("Usuwamy "), ""


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
    # Bez znaczników ``<mark>``, żeby porównywać z gołym wyjściem ``to_html``.
    html = _bez_mark(strony[law.slug])

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


# --- sekcja „Krok po kroku” (karta PRZ-143) ----------------------------------


def test_dlaczego_wolno_zwraca_zdanie_po_polsku():
    """Kryterium 1: słownik reguł daje niepuste zdanie dla praw z karty."""
    for regula in (*PRAWA_KROKOW, "założenie"):
        zdanie = laws.dlaczego_wolno(regula)

        assert zdanie.strip(), f"brak zdania dla reguły {regula!r}"
        assert zdanie.endswith("."), f"zdanie dla reguły {regula!r} nie jest zdaniem"


def test_dlaczego_wolno_dla_nowej_reguly_nie_zostawia_pustego_miejsca():
    """Nowa reguła w treści prawa dostaje zdanie ogólne, a nie pusty napis."""
    zdanie = laws.dlaczego_wolno("regula-ktorej-jeszcze-nie-ma")

    assert zdanie.strip()
    assert zdanie.endswith(".")


def test_plakietka_prawa_nazywa_regule_albo_punkt_wyjscia():
    """Kryterium 2: „założenie” to „punkt wyjścia”, a reguła — nazwa prawa."""
    assert widoki.plakietka_prawa("założenie") == "punkt wyjścia"
    for slug in PRAWA_KROKOW:
        assert widoki.plakietka_prawa(slug) == laws.get(slug).nazwa
    assert widoki.plakietka_prawa("regula-spoza-rejestru") == "regula-spoza-rejestru"


@pytest.mark.parametrize("slug", PRAWA_KROKOW)
def test_kazdy_krok_ma_plakietke_z_nazwa_prawa(strony, slug):
    """Kryterium 2: nad wzorami każdego kroku stoi nazwa użytego prawa."""
    law = laws.get(slug)
    bloki = _kroki_sekcji(_sekcja_krokow(strony[slug]))

    assert len(bloki) == len(law.kroki)
    for numer, (krok, blok) in enumerate(zip(law.kroki, bloki, strict=True), start=1):
        nazwa = escape(widoki.plakietka_prawa(krok.reguła))
        wzorzec = f'<span class="krok-plakietka badge text-bg-secondary">{nazwa}</span>'

        assert wzorzec in blok, f"krok {numer} prawa {slug} nie ma plakietki prawa"


@pytest.mark.parametrize("slug", PRAWA_KROKOW)
def test_kazdy_krok_wyroznia_fragment_w_obu_wzorach(strony, slug):
    """Kryterium 3: wzór „przed” i „po” ma fragment w ``<mark>`` z opisem zmiany."""
    law = laws.get(slug)
    sekcja = _sekcja_krokow(strony[slug])
    bloki = _kroki_sekcji(sekcja)

    assert len(bloki) == len(law.kroki)
    assert sekcja.count('aria-label="ten fragment zastępujemy"') == 2 * len(law.kroki)
    for numer, blok in enumerate(bloki, start=1):
        marki = _marki(blok)

        assert len(marki) == 2, f"krok {numer} prawa {slug} nie ma dwóch wyróżnień"
        assert all(fragment.strip() for fragment in marki), "wyróżnienie nie może być puste"


@pytest.mark.parametrize("slug", PRAWA_KROKOW)
def test_zdanie_zmiany_wymienia_uzyte_prawo(strony, slug):
    """Kryterium 3: krok, który coś zmienia, ma zdanie z różnicy z nazwą prawa."""
    law = laws.get(slug)
    sekcja = _sekcja_krokow(strony[slug])
    zmieniajace = [krok for krok in law.kroki if krok.przed != krok.po]

    assert zmieniajace, f"prawo {slug} nie ma kroku ze zmianą"
    assert sekcja.count('class="krok-zmiana') == len(zmieniajace)
    for krok in zmieniajace:
        koncowka = f"— to {escape(widoki.plakietka_prawa(krok.reguła))}."

        assert koncowka in sekcja, f"zdanie zmiany kroku {krok.reguła!r} nie nazywa prawa"


@pytest.mark.parametrize("slug", PRAWA_KROKOW)
def test_zdanie_zmiany_nazywa_dokladnie_wyroznione_fragmenty(strony, slug):
    """Kryterium 3: zdanie z różnicy cytuje dokładnie te fragmenty, co ``<mark>``.

    Wzór z wyróżnieniem jest tym, co widać, więc zdanie musi nazywać ten sam
    fragment — inaczej początkujący szuka w formule tekstu, którego tam nie ma.
    """
    law = laws.get(slug)
    bloki = _kroki_sekcji(_sekcja_krokow(strony[slug]))

    assert len(bloki) == len(law.kroki)
    for numer, (krok, blok) in enumerate(zip(law.kroki, bloki, strict=True), start=1):
        przed_mark, po_mark = (_tekst(fragment) for fragment in _marki(blok))

        if krok.przed == krok.po:
            assert "krok-zmiana" not in blok, f"krok {numer} bez zmiany nie ma zdania"
            continue
        fragment, fragment_po = _fragmenty_zdania(_zdanie_zmiany(blok))

        assert fragment or fragment_po, f"krok {numer} prawa {slug} bez zdania z różnicy"
        if fragment:
            assert fragment == przed_mark, f"krok {numer}: zdanie nie cytuje wzoru „przed”"
        if fragment_po:
            assert fragment_po == po_mark, f"krok {numer}: zdanie nie cytuje wzoru „po”"


@pytest.mark.parametrize("slug", PRAWA_KROKOW)
def test_kazdy_krok_ma_zdanie_dlaczego_wolno(strony, slug):
    """Kryterium 4: pod każdym krokiem stoi zdanie „dlaczego wolno”."""
    law = laws.get(slug)
    sekcja = _sekcja_krokow(strony[slug])
    naglowek = "<strong>Dlaczego wolno:</strong>"

    assert sekcja.count(naglowek) == len(law.kroki)
    for krok in law.kroki:
        zdanie = escape(laws.dlaczego_wolno(krok.reguła))

        assert f"{naglowek} {zdanie}" in sekcja, f"brak zdania dla kroku {krok.reguła!r}"


@pytest.mark.parametrize("slug", PRAWA_KROKOW)
def test_sekcja_krokow_ma_zdanie_wprowadzajace(strony, slug):
    """Kryterium 5: sekcja mówi, że zamieniamy lewą stronę prawa na prawą."""
    sekcja = _sekcja_krokow(strony[slug])

    assert WPROWADZENIE_KROKOW in sekcja
    assert "zachowuje sens formuły" in sekcja


@pytest.mark.parametrize("slug", PRAWA_KROKOW)
def test_sekcja_krokow_nie_ma_guizikow_ani_numerkow(strony, slug):
    """Kryterium 6: bez odtwarzania i bez numerków — zostają tylko strzałki."""
    sekcja = _sekcja_krokow(strony[slug])

    for napis in ("Odtwórz", "Pauza", "Od nowa", "krok-numer", "lista-krokow"):
        assert napis not in sekcja, f"sekcja kroków pokazuje {napis!r}"
    assert "list-unstyled" in sekcja, "lista kroków musi być bez numeracji"


@pytest.mark.parametrize("slug", PRAWA_KROKOW)
def test_sekcja_krokow_uzywa_komponentu_strzalek(strony, slug):
    """Sekcja nadal chodzi krok po kroku komponentem PRZ-124 (tylko ‹ ›)."""
    sekcja = _sekcja_krokow(strony[slug])

    assert 'class="stepper-mount" data-stepper' in sekcja
    assert "/static/css/stepper.css" in sekcja
    assert "/static/js/steps.js" in sekcja


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
    # Adres z `%3Cscript%3E` nie może wypisać się jako znacznik — pokazujemy go
    # w ucieczce. Od karty PRZ-138 `base.html` ma własny skrypt inline, więc nie
    # żądamy tu już „żadnego <script> na stronie”, tylko braku wstrzykniętego.
    assert "<script>alert(1)" not in html, "adres wypisany jako znacznik"
    assert "&lt;script&gt;" in html, "adres wypisany bez ucieczki"


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
