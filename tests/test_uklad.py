"""Układ: wzory i tabele nie wychodzą poza kafelki (karta PRZ-140).

Projekt nie ma przeglądarki w bramce ani runnera JS (``AGENTS.md``, zasada 6),
więc o układ pytamy statycznie: czytamy arkusze CSS oraz HTML wyrenderowanych stron.
Sprawdzamy to, o co prosi karta:

* ``.formula`` nie zabrania zawijania (żadna jej reguła nie ma ``white-space: nowrap``),
* ``.formula`` łamie długi wzór (``overflow-wrap: anywhere``),
* istnieje klasa ``.formula-blok`` — wzór, który lepiej przewinąć niż łamać,
* ``prawa_lista.html`` i ``prawo.html`` używają tej klasy przy wzorach,
* na ``/prawa`` każdy wzór stoi w elemencie z klasą ``formula``.

Zapytania ``@media`` czytamy spłaszczone: reguła z ich środka trafia na listę z własnym
selektorem. Dzięki temu sprawdzamy **wszystkie** reguły ``.formula``, a nie tylko pierwszą.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app import create_app
from app.logic import formula
from app.logic.laws import all_laws

KATALOG = Path(__file__).resolve().parents[1]
KATALOG_CSS = KATALOG / "app" / "static" / "css"
KATALOG_SZABLONOW = KATALOG / "app" / "templates"
ARKUSZ_APP = KATALOG_CSS / "app.css"

#: Szablony, które mają otaczać długie wzory klasą ``.formula-blok``.
SZABLONY_Z_FORMULA_BLOK = ["prawa_lista.html", "prawo.html"]

#: Reguła CSS jako para (selektor, treść). Klamry zapytań ``@media`` nie wchodzą
#: do selektora, więc ich zawartość czytamy jak zwykłe reguły.
WZORZEC_REGULY = re.compile(r"([^{}]+)\{([^{}]*)\}")
WZORZEC_KOMENTARZA = re.compile(r"/\*.*?\*/", re.DOTALL)
WZORZEC_KLASY_HTML = re.compile(r'class="([^"]*)"')


def _arkusz(nazwa: str) -> str:
    """Treść arkusza z ``app/static/css``."""
    return (KATALOG_CSS / nazwa).read_text(encoding="utf-8")


def _reguly(css: str) -> list[tuple[str, str]]:
    """Pary ``(selektor, treść)`` z arkusza; komentarze odrzucamy."""
    return WZORZEC_REGULY.findall(WZORZEC_KOMENTARZA.sub("", css))


def _selektor_klasy(selektor: str, klasa: str) -> bool:
    """Czy selektor wskazuje element o klasie ``klasa``.

    Klasę porównujemy po całym tokenie, nie po przedrostku: ``.formula-blok``
    to inna klasa niż ``.formula``.
    """
    return re.search(rf"\.{re.escape(klasa)}(?![\w-])", selektor) is not None


def _tresci_regul(css: str, klasa: str) -> list[str]:
    """Treści wszystkich reguł dotyczących danej klasy (razem z ``@media``)."""
    return [tresc for selektor, tresc in _reguly(css) if _selektor_klasy(selektor, klasa)]


def _klasy_html(tresc: str) -> list[set[str]]:
    """Zbiory klas z każdego atrybutu ``class="…"`` w treści szablonu."""
    return [set(wartosc.split()) for wartosc in WZORZEC_KLASY_HTML.findall(tresc)]


#: Znaczniki bez znacznika zamykającego — nie zmieniają zagnieżdżenia.
ZNACZNIKI_PUSTE = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "wbr"}
)


class ZbieraczFormul(HTMLParser):
    """Zbiera tekst elementów, których klasa zawiera ``formula``.

    Na stosie trzymamy, czy dany znacznik stoi w środku wzoru. Dzięki temu
    ``<span class="op-or">`` w środku wzoru nie kończy go przedwcześnie.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.wzory: list[str] = []
        self._stos: list[bool] = []
        self._bufor: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ZNACZNIKI_PUSTE:
            return
        klasy = (dict(attrs).get("class") or "").split()
        w_srodku = bool(self._stos) and self._stos[-1]
        czy_wzor = "formula" in klasy
        if czy_wzor and not w_srodku:
            self._bufor = []
        self._stos.append(w_srodku or czy_wzor)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Znacznik samozamykający (``<br />``) nie otwiera elementu."""
        return

    def handle_endtag(self, tag: str) -> None:
        if not self._stos:
            return
        w_srodku = self._stos.pop()
        if w_srodku and (not self._stos or not self._stos[-1]):
            self.wzory.append(" ".join("".join(self._bufor).split()))

    def handle_data(self, dane: str) -> None:
        if self._stos and self._stos[-1]:
            self._bufor.append(dane)


@pytest.fixture(scope="module")
def lista_praw() -> str:
    """HTML strony ``/prawa``."""
    app = create_app()
    with app.test_client() as klient:
        odpowiedz = klient.get("/prawa")

    assert odpowiedz.status_code == 200, "strona /prawa nie odpowiada"
    return odpowiedz.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Arkusz: wzór zawija się w obrębie karty
# ---------------------------------------------------------------------------


def test_formula_nie_zabrania_zawijania():
    """Kryterium karty: żadna reguła ``.formula`` nie ma ``white-space: nowrap``."""
    tresci = _tresci_regul(_arkusz("app.css"), "formula")

    assert tresci, "app.css nie ma reguły .formula"
    zakazy = [tresc for tresc in tresci if "white-space: nowrap" in tresc]
    assert not zakazy, f"reguła .formula nadal zabrania zawijania: {zakazy}"


def test_formula_lamie_dlugi_wzor():
    """Kryterium karty: ``.formula`` ma ``overflow-wrap: anywhere`` (albo ``word-break``)."""
    tresci = _tresci_regul(_arkusz("app.css"), "formula")

    assert any(
        "overflow-wrap: anywhere" in tresc or "word-break: break-word" in tresc for tresc in tresci
    ), "reguła .formula nie łamie długiego wzoru"


def test_formula_blok_przewija_wzor():
    """Kryterium karty: ``.formula-blok`` przewija wzór w poziomie."""
    tresci = _tresci_regul(_arkusz("app.css"), "formula-blok")

    assert tresci, "app.css nie ma klasy .formula-blok"
    calosc = " ".join(tresci)
    assert "overflow-x: auto" in calosc, ".formula-blok bez przewijania w poziomie"
    assert "max-width: 100%" in calosc, ".formula-blok może wyjść z karty"


def test_karty_i_kolumny_maja_min_width_zero():
    """Kryterium karty: karta albo kolumna siatki kurczy się poniżej swojej treści."""
    tresci = _tresci_regul(_arkusz("app.css"), "karta-prawa")

    assert tresci, "app.css nie ma reguły .karta-prawa"
    assert any("min-width: 0" in tresc for tresc in tresci), "karta nie ma min-width: 0"
    assert any("overflow: hidden" in tresc for tresc in tresci), "karta nie ucina treści"


# ---------------------------------------------------------------------------
# Szablony: wzór główny w klasie .formula-blok
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nazwa", SZABLONY_Z_FORMULA_BLOK)
def test_szablon_uzywa_formula_blok(nazwa):
    """Kryterium karty: oba szablony mają element ``.formula.formula-blok``."""
    tresc = (KATALOG_SZABLONOW / nazwa).read_text(encoding="utf-8")
    klasy = _klasy_html(tresc)

    assert any({"formula", "formula-blok"} <= zbior for zbior in klasy), (
        f"{nazwa}: brak elementu z klasami formula i formula-blok"
    )


# ---------------------------------------------------------------------------
# Strona: każdy wzór jest w elemencie .formula
# ---------------------------------------------------------------------------


def test_kazdy_wzor_na_liscie_praw_jest_w_elemencie_formula(lista_praw):
    """Kryterium karty: na ``/prawa`` każdy wzór stoi w elemencie ``.formula``.

    Kafelków jest tyle, ile praw, a ich tekst zgadza się z ``formula.to_text`` —
    dlatego żaden wzór nie wyciekł poza klasę, która nim zarządza.
    """
    zbieracz = ZbieraczFormul()
    zbieracz.feed(lista_praw)

    prawa = all_laws()
    assert len(zbieracz.wzory) == len(prawa), (
        f"na /prawa jest {len(zbieracz.wzory)} wzorów w .formula, a praw jest {len(prawa)}"
    )

    oczekiwane = {formula.to_text(formula.parse(prawo.formula)) for prawo in prawa}
    assert set(zbieracz.wzory) == oczekiwane, "wzór w kafelku nie zgadza się z treścią prawa"
