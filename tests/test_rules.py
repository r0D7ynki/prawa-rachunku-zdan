"""Testy rejestru reguł wnioskowania i strony ``/reguly`` (karta PRZ-090).

Testy nie wierzą danym na słowo:

* każdą tautologię liczą od nowa przez ``truth.is_tautology`` — pole ``tautologia``
  naprawdę musi być tautologią, a nie tylko tak wyglądać,
* przesłanki, wnioski, tautologie i nazwy porównują z ``docs/TRESC-WYKLAD2.md`` —
  dowód, że nic nie zostało wymyślone poza przykładami dla DM1, DM2 i KP, których
  tabela wykładu nie ma (te trzy przykłady mają osobny test),
* wzory na stronie porównują z wynikiem ``formula.to_html``, więc test nie zakłada
  konkretnego znaku operatora ani nawiasów, które ``to_html`` dodaje sam.
"""

from __future__ import annotations

import re
from html import unescape
from itertools import chain
from pathlib import Path
from urllib.parse import quote

import pytest
from markupsafe import Markup

from app import create_app
from app.blueprints import reguly as widok
from app.logic import truth
from app.logic.formula import parse, to_html
from app.logic.rules import DODATKOWA, PIERWOTNA, Rule, get, rules

ADRES = "/reguly"

#: Kolejność kodów z tabel wykładu: siedem pierwotnych, potem trzy dodatkowe.
KODY = ["RO", "OK", "DK", "OA", "DA", "DR", "OR", "DM1", "DM2", "KP"]

#: Reguły, których przykłady wykład podaje wprost w tabeli. Dla DM1, DM2 i KP tabela
#: nie ma kolumny „Przykład”, więc te trzy przykłady dopisał wykonawca karty.
KODY_Z_PRZYKLADEM_W_WYKLADZIE = ["RO", "OK", "DK", "OA", "DA", "DR", "OR"]

#: Kody reguł dodatkowych — tabela wykładu ma je w osobnej sekcji.
KODY_DODATKOWE = ["DM1", "DM2", "KP"]

#: Plik ze źródłem treści („źródło prawdy” dla stron wykładu 2).
WYKLAD = Path(__file__).resolve().parents[1] / "docs" / "TRESC-WYKLAD2.md"

#: Arkusz stylów strony — kreska schematu musi być w nim malowana.
ARKUSZ = Path(__file__).resolve().parents[1] / "app" / "static" / "css" / "reguly.css"

#: Karta jednej reguły; numerujemy je w kodzie po ``id``.
KARTA = re.compile(
    r'<article class="karta-reguly" id="regula-(?P<kod>[a-z0-9]+)".*?</article>',
    re.DOTALL,
)
KOD_NA_KARCIE = re.compile(r'<span class="regula-kod">(?P<kod>[A-Z0-9]+)</span>')
PRZESLANKA = re.compile(r'<li class="formula">(?P<tresc>.*?)</li>', re.DOTALL)
ODNOSNIK_PLACU_ZABAW = re.compile(
    r'href="(?P<href>/plac-zabaw\?formula=[^"]+)"[^>]*>\s*Sprawdź w placu zabaw'
)
ZNACZNIK = re.compile(r"<[^>]+>")
SPACJE = re.compile(r"\s+")
KRESKA = re.compile(r'<div class="regula-kreska" aria-hidden="true"></div>')


def _tekst(fragment: str) -> str:
    """Widoczny tekst fragmentu HTML — bez znaczników, ze odmienionymi encjami."""
    return SPACJE.sub(" ", unescape(ZNACZNIK.sub("", fragment))).strip()


def _wzory(regula: Rule) -> list[str]:
    """Wszystkie tautologie reguły: główna i dodatkowe."""
    return [regula.tautologia, *regula.tautologie_dodatkowe]


def _wnioski(regula: Rule) -> list[str]:
    """Wszystkie wnioski reguły: główny i dodatkowe."""
    return [regula.wniosek, *regula.wnioski_dodatkowe]


@pytest.fixture(scope="module")
def wyklad() -> str:
    return WYKLAD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def klient():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def html(klient) -> str:
    return klient.get(ADRES).get_data(as_text=True)


@pytest.fixture(scope="module")
def karty(html) -> dict[str, str]:
    """HTML każdej karty reguły, kluczowany małymi literami kodu (``"ro"``)."""
    return {dopasowanie["kod"]: dopasowanie.group(0) for dopasowanie in KARTA.finditer(html)}


# ---------------------------------------------------------------------------
# Rejestr: kolejność, komplet pól, wyszukiwanie po kodzie
# ---------------------------------------------------------------------------


def test_rejestr_ma_dziesiec_regul_w_kolejnosci_wykladu():
    assert [regula.kod for regula in rules()] == KODY


def test_rejestr_grupuje_reguly_pierwotne_i_dodatkowe():
    pierwotne = [regula.kod for regula in rules() if regula.typ == PIERWOTNA]
    dodatkowe = [regula.kod for regula in rules() if regula.typ == DODATKOWA]

    assert pierwotne == KODY[:7]
    assert dodatkowe == KODY_DODATKOWE


def test_rejestr_zwraca_kopie_listy():
    """Wołający nie może przez przypadek zmienić rejestru."""
    pierwsza = rules()
    pierwsza.clear()

    assert [regula.kod for regula in rules()] == KODY


@pytest.mark.parametrize("kod", KODY)
def test_get_zwraca_regule_o_podanym_kodzie(kod):
    regula = get(kod)

    assert regula is not None
    assert regula.kod == kod
    assert regula is get(kod), "get ma zwracać ten sam obiekt co rules()"


def test_get_zwraca_none_dla_nieznanego_kodu():
    assert get("XX") is None
    assert get("") is None


@pytest.mark.parametrize("kod", ["ro", " ro ", "Ro"])
def test_get_nie_zwraca_uwagi_na_wielkosc_liter_i_spacje(kod):
    regula = get(kod)

    assert regula is not None
    assert regula.kod == "RO"


@pytest.mark.parametrize("regula", rules(), ids=KODY)
def test_kazda_regula_ma_niepuste_pola(regula):
    assert regula.kod.isupper()
    assert regula.nazwa.strip()
    assert regula.typ in (PIERWOTNA, DODATKOWA)
    assert regula.przeslanki and all(p.strip() for p in regula.przeslanki)
    assert regula.wniosek.strip()
    assert regula.tautologia.strip()
    assert regula.przyklad.strip()
    assert regula.opis.strip()


def test_pelna_nazwa_jest_tylko_u_reguly_odrywania():
    """Wykład podaje łacińską nazwę tylko dla Modus Ponens; reszta ma puste pole."""
    z_nazwa = {regula.kod for regula in rules() if regula.pelna_nazwa}

    assert z_nazwa == {"RO"}
    assert get("RO").pelna_nazwa == "Modus Ponens"


def test_dwie_reguly_maja_po_dwie_wersje_wniosku():
    """OK i OR wykład podaje w dwóch wersjach — obie muszą być w rejestrze."""
    dodatkowe: dict[str, list[str]] = {}
    tautologie: dict[str, list[str]] = {}
    for regula in rules():
        if regula.wnioski_dodatkowe:
            dodatkowe[regula.kod] = regula.wnioski_dodatkowe
        if regula.tautologie_dodatkowe:
            tautologie[regula.kod] = regula.tautologie_dodatkowe

    assert dodatkowe == {"OK": ["Ψ"], "OR": ["Ψ → Φ"]}
    assert tautologie == {"OK": ["((p ∧ q) → q)"]}


# ---------------------------------------------------------------------------
# Treść: tautologie i pochodzenie danych
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kod", "tautologia"),
    [(regula.kod, wzor) for regula in rules() for wzor in _wzory(regula)],
)
def test_kazda_tautologia_reguly_jest_tautologia(kod, tautologia):
    drzewo = parse(tautologia)

    assert truth.is_tautology(drzewo), f"{kod}: {tautologia} nie jest tautologią"
    assert truth.classify(drzewo) == "tautologia"


@pytest.mark.parametrize("regula", rules(), ids=KODY)
def test_przeslanki_wnioski_i_tautologie_pochodza_z_wykladu(regula, wyklad):
    """Każdy wzór z rejestru jest przepisany z tabeli wykładu — nic nie zostało wymyślone."""
    for wzor in chain(regula.przeslanki, _wnioski(regula), _wzory(regula)):
        assert wzor in wyklad, f"{regula.kod}: {wzor!r} nie występuje w dokumencie wykładu"


@pytest.mark.parametrize("regula", rules(), ids=KODY)
def test_nazwy_regul_pochodza_z_wykladu(regula, wyklad):
    assert regula.nazwa in wyklad, f"{regula.kod}: nazwy {regula.nazwa!r} nie ma w wykładzie"
    if regula.pelna_nazwa:
        assert regula.pelna_nazwa in wyklad


@pytest.mark.parametrize("kod", KODY_Z_PRZYKLADEM_W_WYKLADZIE)
def test_przyklady_z_wykladu_sa_przepisane_dokladnie(kod, wyklad):
    assert get(kod).przyklad in wyklad


@pytest.mark.parametrize("kod", KODY_DODATKOWE)
def test_przyklady_regul_dodatkowych_sa_zdaniami_o_tej_samej_regule(kod):
    """Wykład nie ma przykładów dla DM1, DM2 i KP — sprawdzamy, że przykład jest sensowny.

    Test nie porównuje z dokumentem (tam tych przykładów nie ma), tylko pilnuje, że
    przykład nadaje się na lekcję: to nie pusty napis, a opis jest krótki.
    """
    regula = get(kod)

    assert regula.przyklad.endswith(".")
    assert len(regula.przyklad.split()) >= 5
    assert len(regula.opis.split()) <= 40


# ---------------------------------------------------------------------------
# Strona: kod odpowiedzi, nagłówek, karty
# ---------------------------------------------------------------------------


def test_strona_odpowiada_200(klient, html):
    assert klient.get(ADRES).status_code == 200
    assert 'lang="pl"' in html


def test_strona_ma_dokladnie_jeden_h1(html):
    assert len(re.findall(r"<h1\b", html)) == 1


def test_strona_pokazuje_dziesiec_kart_regul(html, karty):
    assert len(karty) == len(KODY)
    assert sorted(karty) == sorted(kod.lower() for kod in KODY)
    assert [dopasowanie["kod"] for dopasowanie in KOD_NA_KARCIE.finditer(html)] == KODY


def test_strona_ma_sekcje_pierwotnych_i_dodatkowych(html):
    sekcje = re.findall(r'<h2 id="naglowek-(?:pierwotne|dodatkowe)">(?P<tytul>[^<]+)</h2>', html)

    assert sekcje == ["Reguły pierwotne", "Reguły dodatkowe"]


@pytest.mark.parametrize("kod", KODY, ids=KODY)
def test_karta_pokazuje_kod_i_nazwe(kod, karty):
    fragment = karty[kod.lower()]
    regula = get(kod)

    assert f'<span class="regula-kod">{kod}</span>' in fragment
    assert _tekst(fragment).startswith(f"{kod} {regula.nazwa}")


@pytest.mark.parametrize("kod", KODY, ids=KODY)
def test_karta_pokazuje_przeslanki_nad_kreska_a_wniosek_pod(karty, kod):
    """Kolejność elementów jest wymogiem karty: przesłanki, kreska, wniosek."""
    fragment = karty[kod.lower()]
    regula = get(kod)

    pozycja_przeslanek = fragment.index('<ul class="regula-przeslanki">')
    pozycja_kreski = fragment.index('<div class="regula-kreska"')
    pozycja_wniosku = fragment.index('<p class="regula-wniosek')

    assert pozycja_przeslanek < pozycja_kreski < pozycja_wniosku
    przeslanki = PRZESLANKA.findall(fragment)
    assert len(przeslanki) == len(regula.przeslanki)
    for przeslanka, oczekiwana in zip(przeslanki, regula.przeslanki, strict=True):
        assert _tekst(przeslanka) == _tekst(widok.metazmienne_to_html(oczekiwana))


@pytest.mark.parametrize("kod", KODY, ids=KODY)
def test_karta_pokazuje_wniosek_i_tautologie_w_html(karty, kod):
    fragment = karty[kod.lower()]
    regula = get(kod)

    wniosek = _tekst(fragment.split('<p class="regula-wniosek formula">', 1)[1].split("</p>", 1)[0])
    oczekiwany = " oraz ".join(_tekst(widok.metazmienne_to_html(w)) for w in _wnioski(regula))
    assert wniosek == oczekiwany

    tautologie = _tekst(
        fragment.split('<dd class="regula-tautologia formula">', 1)[1].split("</dd>", 1)[0]
    )
    oczekiwane = " oraz ".join(_tekst(to_html(parse(w))) for w in _wzory(regula))
    assert tautologie == oczekiwane


@pytest.mark.parametrize("kod", ["OK", "OR"])
def test_dwie_wersje_reguly_stoja_obok_siebie_na_stronie(karty, kod):
    """OK i OR pokazują oba wnioski, a OK także obie tautologie z wykładu."""
    fragment = karty[kod.lower()]

    assert _tekst(fragment).count("oraz") >= 1
    assert len(KRESKA.findall(fragment)) == 1


@pytest.mark.parametrize("kod", KODY, ids=KODY)
def test_karta_pokazuje_przyklad_i_opis(karty, kod):
    fragment = karty[kod.lower()]
    regula = get(kod)

    assert regula.przyklad in unescape(fragment)
    assert regula.opis in unescape(fragment)


@pytest.mark.parametrize("kod", KODY, ids=KODY)
def test_odnosnik_do_placu_zabaw_niesie_tautologie_reguly(karty, kod):
    fragment = karty[kod.lower()]
    odnosnik = ODNOSNIK_PLACU_ZABAW.search(fragment)

    assert odnosnik, f"{kod}: brak odnośnika „Sprawdź w placu zabaw”"
    assert odnosnik["href"] == f"/plac-zabaw?formula={quote(get(kod).tautologia)}"
    # Dziesięć odnośników ma ten sam napis, więc każdy musi powiedzieć, której reguły dotyczy.
    assert f'aria-label="Sprawdź tautologię reguły {kod}' in fragment


def test_kazda_karta_ma_kreske_jako_element_html(html, karty):
    """Kreska schematu to ``div.regula-kreska`` malowany w CSS, a nie znak „—”."""
    assert len(KRESKA.findall(html)) == len(KODY)
    for fragment in karty.values():
        for kreska in KRESKA.findall(fragment):
            assert _tekst(kreska) == "", "kreska nie może mieć treści — inaczej to nie kreska"

    styl = ARKUSZ.read_text(encoding="utf-8")
    assert ".regula-kreska" in styl
    assert "border-top" in styl


def test_strona_bez_javascriptu_pokazuje_cala_tresc(html, karty):
    """Treść reguł jest w HTML — żaden skrypt jej nie dorysowuje."""
    for regula in rules():
        assert regula.przyklad in html
        assert _tekst(to_html(parse(regula.tautologia))) in _tekst(karty[regula.kod.lower()])

    assert "reguly.js" not in html


# ---------------------------------------------------------------------------
# Rysowanie wzorów z metazmiennymi
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "wzor",
    [wzor for regula in rules() for wzor in chain(regula.przeslanki, _wnioski(regula))],
)
def test_metazmienne_to_html_nie_gubi_znakow_ani_kolejnosci(wzor):
    """Rysunek wzoru musi dać ten sam tekst: te same znaki w tej samej kolejności."""
    narysowany = widok.metazmienne_to_html(wzor)

    assert isinstance(narysowany, Markup)
    assert _tekst(narysowany) == wzor
    if any(operator in wzor for operator in ("∧", "∨", "→", "≡", "∼")):
        assert re.search(r'class="op-(and|or|imp|iff|neg)"', narysowany), (
            f"{wzor!r} bez klasy operatora — spójniki nie wyglądałyby jak na innych stronach"
        )


def test_metazmienne_to_html_oddaje_bledny_napis_bez_znacznikow():
    """Błąd w danych nie może wywrócić strony — oddajemy napis jako tekst."""
    narysowany = widok.metazmienne_to_html("Φ oraz Ψ")

    assert _tekst(narysowany) == "Φ oraz Ψ"
    assert "<span" not in narysowany


def test_formula_to_html_oddaje_bledny_napis_bez_znacznikow():
    assert _tekst(widok.formula_to_html("p i q")) == "p i q"
