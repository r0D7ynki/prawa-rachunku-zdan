"""Układ: wzory i tabele nie wychodzą poza kafelki (karty PRZ-140 i PRZ-156).

Projekt nie ma przeglądarki w bramce ani runnera JS (``AGENTS.md``, zasada 6),
więc o układ pytamy statycznie: czytamy arkusze CSS oraz HTML wyrenderowanych stron.
Sprawdzamy to, o co proszą karty:

* ``.formula`` nie zabrania zawijania (żadna jej reguła nie ma ``white-space: nowrap``),
* ``.formula`` łamie długi wzór (``overflow-wrap: anywhere``),
* istnieje klasa ``.formula-blok`` — wzór, który lepiej przewinąć niż łamać,
* ``prawa_lista.html`` i ``prawo.html`` używają tej klasy przy wzorach,
* na ``/prawa`` każdy wzór stoi w elemencie z klasą ``formula``,
* lista praw to pionowa kolumna kafelków ``a.karta-prawa`` o szerokości swojej treści,
  bez klas siatki Bootstrapa (karta PRZ-156),
* kafelek na ``/prawa`` jest jednym odnośnikiem pokazującym nazwę i wzór — bez kategorii
  i bez odnośnika „opis” — a kursor i fokus podświetlają jego tło i obwódkę (karta PRZ-168).

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


# ---------------------------------------------------------------------------
# Lista praw: pionowa kolumna kafelków o szerokości treści (karta PRZ-156)
# ---------------------------------------------------------------------------

SZABLON_LISTY = KATALOG_SZABLONOW / "prawa_lista.html"

#: Klasy siatki Bootstrapa, które z listy praw miały zniknąć (karta PRZ-156).
KLASY_SIATKI = ("row", "col")


def _klasy_siatki(tresc: str) -> list[str]:
    """Nazwy klas siatki Bootstrapa znalezione w szablonie (posortowane)."""
    znalezione = {
        klasa
        for zbior in _klasy_html(tresc)
        for klasa in zbior
        if klasa.startswith("row") or klasa == "col" or klasa.startswith("col-")
    }
    return sorted(znalezione)


class ZbieraczKafelkow(HTMLParser):
    """Zbiera kafelki ``a.karta-prawa`` i nagłówki ich sekcji ze strony ``/prawa``.

    Dla każdego kafelka notujemy znacznik, nazwę, wzór, cały widoczny tekst, adres
    odnośnika i odnośniki zagnieżdżone w kafelku, a także numer sekcji, w której
    kafelek stoi (``naglowki[numer]`` to jej ``<h2>``).

    Strukturę czytamy ``html.parser``-em, nie wyrażeniem regularnym: wzór ma
    zagnieżdżone ``<span>``, więc dopasowanie po napisie skończyłoby się za wcześnie
    (ten sam powód, co w ``ZbieraczFormul``).
    """

    #: Znacznik kafelka: cały kafelek jest odnośnikiem (karta PRZ-168).
    ZNACZNIK_KAFELKA = "a"

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.kafelki: list[dict[str, object]] = []
        self.naglowki: list[str] = []
        self._stos: list[tuple[str, str | None]] = []
        self._bufor: dict[str, list[str]] = {}
        self._kafelek: dict[str, object] | None = None
        self._glebokosc = 0
        self._naglowek: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ZNACZNIKI_PUSTE:
            return
        atrybuty = dict(attrs)
        klasy = (atrybuty.get("class") or "").split()

        # Nagłówki kategorii poznajemy po `id` (szablon listy: `kategoria-1`, `kategoria-2`, …);
        # inne `<h2>` (np. spis lekcji w `base.html`) nie opisują listy praw.
        if tag == "h2" and self._kafelek is None:
            self._naglowek = [] if (atrybuty.get("id") or "").startswith("kategoria-") else None
            return

        if tag == self.ZNACZNIK_KAFELKA and "karta-prawa" in klasy and self._kafelek is None:
            self._kafelek = {
                "znacznik": tag,
                "nazwa": "",
                "wzor": "",
                "tekst": "",
                "href": atrybuty.get("href"),
                "odnosniki": [],
                "sekcja": len(self.naglowki) - 1,
            }
            self._bufor = {rola: [] for rola in ("nazwa", "wzor", "tekst")}
            self._glebokosc = 0
            self._stos = []
            return

        if self._kafelek is None:
            return

        self._glebokosc += 1
        rola = None
        if "karta-prawa-nazwa" in klasy:
            rola = "nazwa"
        elif "formula-blok" in klasy:
            rola = "wzor"
        if tag == "a":
            # Odnośnik w środku kafelka (np. dawne „opis”) — kafelek ma być cały odnośnikiem.
            self._kafelek["odnosniki"].append(atrybuty.get("href"))
        self._stos.append((tag, rola))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Znacznik samozamykający (``<br />``) nie otwiera elementu."""
        return

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2" and self._naglowek is not None and self._kafelek is None:
            self.naglowki.append(" ".join("".join(self._naglowek).split()))
            self._naglowek = None
            return

        if self._kafelek is None:
            return

        if tag == self.ZNACZNIK_KAFELKA and self._glebokosc == 0:
            for rola, czesci in self._bufor.items():
                self._kafelek[rola] = " ".join("".join(czesci).split())
            self.kafelki.append(self._kafelek)
            self._kafelek = None
            return

        if self._stos:
            self._stos.pop()
            self._glebokosc -= 1

    def handle_data(self, dane: str) -> None:
        if self._naglowek is not None and self._kafelek is None:
            self._naglowek.append(dane)
            return
        if self._kafelek is None:
            return
        self._bufor["tekst"].append(dane)
        rola = next((rola for _, rola in reversed(self._stos) if rola), None)
        if rola is not None:
            self._bufor[rola].append(dane)


@pytest.fixture(scope="module")
def kafelki(lista_praw: str) -> ZbieraczKafelkow:
    """Kafelki praw odczytane ze strony ``/prawa``."""
    zbieracz = ZbieraczKafelkow()
    zbieracz.feed(lista_praw)
    return zbieracz


# --- arkusz: kolumna kafelków o szerokości treści ---------------------------


def test_lista_praw_nie_uzywa_siatki_bootstrapa():
    """Kryterium karty: ``prawa_lista.html`` bez klas ``row`` i ``col-*``."""
    klasy = _klasy_siatki(SZABLON_LISTY.read_text(encoding="utf-8"))

    assert not klasy, f"prawa_lista.html nadal używa siatki Bootstrapa: {klasy}"


def _tresci_wyboru(css: str, klasa: str, *bez: str) -> list[str]:
    """Treści reguł dotyczących klasy ``klasa``, z pominięciem tych z ``bez`` w selektorze."""
    return [
        tresc
        for selektor, tresc in _reguly(css)
        if _selektor_klasy(selektor, klasa) and not any(slowo in selektor for slowo in bez)
    ]


def test_lista_praw_jest_kolumna():
    """Kryterium karty: ``.lista-praw`` układa kafelki jeden pod drugim."""
    tresci = _tresci_wyboru(_arkusz("app.css"), "lista-praw", "karta-prawa")

    assert tresci, "app.css nie ma reguły .lista-praw"
    calosc = " ".join(tresci)
    assert "display: flex" in calosc, ".lista-praw nie jest kontenerem flexboxa"
    assert "flex-direction: column" in calosc, ".lista-praw nie układa kafelków w pionie"
    assert "gap: 0.75rem" in calosc, ".lista-praw nie rozsuwa kafelków"
    assert "align-items: flex-start" in calosc, (
        ".lista-praw rozciąga kafelki na całą szerokość zamiast dać im szerokość treści"
    )


def test_kafelek_stoi_w_jednej_linii():
    """Karta: w kafelku nazwa, wzór, kategoria i „opis” idą obok siebie.

    Pytamy o regułę kafelka **wewnątrz** kontenera listy (``div.lista-praw .karta-prawa``),
    nie o samą klasę ``.lista-praw``. Kafelek sam z siebie układa części w kolumnie
    (``.karta-prawa`` ma ``flex-direction: column`` — tak stoi na stronie głównej),
    więc jedna linia to wyłącznie zasługa nowej reguły. Test pada, gdy reguły nie ma;
    selektor musi wskazywać jednocześnie kontener i kafelek.
    """
    reguly = [
        tresc
        for selektor, tresc in _reguly(_arkusz("app.css"))
        if _selektor_klasy(selektor, "lista-praw") and _selektor_klasy(selektor, "karta-prawa")
    ]

    assert reguly, "app.css nie ma reguły dla kafelka w liście praw (div.lista-praw .karta-prawa)"
    assert any("flex-direction: row" in tresc for tresc in reguly), (
        "kafelek listy praw nie układa części w jednej linii"
    )


def test_waski_ekran_uklada_kafelek_jeden_pod_drugim():
    """Karta: w wąskim oknie części kafelka schodzą w dół, a wzór dostaje całą szerokość."""
    wzorzec_bloku = r"@media[^{]*max-width:\s*576px\s*\)[^{]*\{(?P<tresc>.*?)\n\}"
    wzorzec_reguly = r"div\.lista-praw\s+\.karta-prawa\s*\{[^}]*flex-direction:\s*column"
    blok = re.search(wzorzec_bloku, _arkusz("app.css"), re.DOTALL)

    assert blok, "app.css nie ma bloku @media (max-width: 576px)"
    assert re.search(wzorzec_reguly, blok["tresc"]), (
        "w wąskim oknie kafelek listy praw nadal ściska wzór w jednej linii"
    )


def test_karta_prawa_ma_szerokosc_swojej_tresci():
    """Kryterium karty: ``.karta-prawa`` ma ``width: auto`` i ``max-width: 100%``."""
    tresci = _tresci_regul(_arkusz("app.css"), "karta-prawa")

    assert any("width: auto" in tresc for tresc in tresci), ".karta-prawa bez width: auto"
    assert any("max-width: 100%" in tresc for tresc in tresci), ".karta-prawa bez max-width: 100%"


def test_kafelek_odnosnika_ma_hover_i_fokus(kafelki: ZbieraczKafelkow):
    """Kryterium karty PRZ-168: kafelek-odnośnik podświetla tło i obwódkę, bez podkreślenia.

    Pytamy o pełny selektor (``.karta-prawa`` **oraz** ``:hover`` / ``:focus-visible``):
    samą klasę dzielą z listą inne strony, więc reguła bez pseudoklasy niczego tu nie
    dowodzi. Obwódkę fokusu czytamy z reguły ``:focus-visible``, bo tylko ona opisuje
    stan klawiatury.
    """
    css = _arkusz("app.css")

    assert any("text-decoration: none" in tresc for tresc in _tresci_regul(css, "karta-prawa")), (
        ".karta-prawa jest odnośnikiem bez text-decoration: none — nazwa i wzór się podkreślą"
    )

    hover = [
        tresc
        for selektor, tresc in _reguly(css)
        if _selektor_klasy(selektor, "karta-prawa") and ":hover" in selektor
    ]
    assert hover, "app.css nie ma reguły .karta-prawa:hover"
    assert any("background" in tresc for tresc in hover), (
        ".karta-prawa:hover nie podświetla tła kafelka"
    )

    fokus = [
        tresc
        for selektor, tresc in _reguly(css)
        if _selektor_klasy(selektor, "karta-prawa") and ":focus-visible" in selektor
    ]
    assert fokus, "app.css nie ma reguły .karta-prawa:focus-visible"
    calosc_fokusu = " ".join(fokus)
    assert "outline" in calosc_fokusu, ".karta-prawa:focus-visible nie rysuje obwódki"
    assert "background" in calosc_fokusu, ".karta-prawa:focus-visible nie podświetla tła"


def test_wzor_w_kafelku_sie_nie_zawija():
    """Kryterium karty: wzór w kafelku jest w jednej linii i przewija się w środku."""
    tresci = _tresci_regul(_arkusz("app.css"), "formula-blok")

    assert tresci, "app.css nie ma reguły .formula-blok"
    calosc = " ".join(tresci)
    assert "white-space: nowrap" in calosc, "wzór w kafelku może się zawinąć"
    assert "overflow-x: auto" in calosc, "wzór szerszy niż ekran wyjdzie z kafelka"
    assert "max-width: 100%" in calosc, "wzór może rozepchnąć kafelek"


# --- strona: kafelki praw ----------------------------------------------------


def test_kazde_prawo_ma_kafelek(kafelki: ZbieraczKafelkow):
    """Kryterium karty: każdy kafelek to ``a.karta-prawa``, po jednym na prawo."""
    prawa = all_laws()

    assert len(kafelki.kafelki) == len(prawa), (
        f"na /prawa jest {len(kafelki.kafelki)} kafelków, a praw jest {len(prawa)}"
    )
    assert {kafelek["znacznik"] for kafelek in kafelki.kafelki} == {"a"}, (
        "kafelek listy praw nie jest odnośnikiem"
    )
    assert {kafelek["href"] for kafelek in kafelki.kafelki} == {
        f"/prawa/{prawo.slug}" for prawo in prawa
    }, "odnośniki w kafelkach nie prowadzą do wszystkich praw"


def test_kafelek_pokazuje_tylko_nazwe_i_wzor(kafelki: ZbieraczKafelkow):
    """Kryterium karty: w kafelku są nazwa i wzór — bez kategorii i bez odnośnika „opis”.

    Porównujemy **cały** widoczny tekst kafelka z nazwą i wzorem prawa. Dzięki temu
    wychwyci każde dodatkowe słowo w kafelku — także nazwę kategorii, której napis
    nie zawsze da się rozpoznać po samym słowie („de Morgan” siedzi w nazwie
    „I prawo de Morgana”).
    """
    assert kafelki.kafelki, "strona /prawa nie ma kafelków"
    prawa = {f"/prawa/{prawo.slug}": prawo for prawo in all_laws()}

    for kafelek in kafelki.kafelki:
        prawo = prawa[str(kafelek["href"])]
        wzor = formula.to_text(formula.parse(prawo.formula))
        assert kafelek["tekst"] == " ".join(f"{prawo.nazwa} {wzor}".split()), (
            f"kafelek {kafelek['href']} pokazuje {kafelek['tekst']!r} — ma tylko nazwę i wzór"
        )
        assert kafelek["nazwa"], f"kafelek {kafelek['href']} nie pokazuje nazwy prawa"
        assert kafelek["wzor"], f"kafelek {kafelek['href']} nie pokazuje wzoru"
        assert not kafelek["odnosniki"], (
            f"kafelek {kafelek['href']} ma w środku odnośnik {kafelek['odnosniki']!r} — "
            "cały kafelek ma być jednym odnośnikiem"
        )


def test_naglowek_kategorii_stoi_nad_swoimi_kafelkami(kafelki: ZbieraczKafelkow):
    """Kryterium karty: nagłówki kategorii zostają nad swoją częścią listy."""
    assert kafelki.naglowki, "strona /prawa nie ma nagłówków kategorii"
    assert {"podstawowe", "implikacja", "algebra"} <= set(kafelki.naglowki), (
        f"na /prawa brakuje nagłówka kategorii: {sorted(kafelki.naglowki)}"
    )
    assert {kafelek["sekcja"] for kafelek in kafelki.kafelki} == set(
        range(len(kafelki.naglowki))
    ), "jakaś kategoria nie ma kafelków albo kafelek stoi poza sekcją"
