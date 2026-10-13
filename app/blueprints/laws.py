"""Strony praw: lista ``/prawa`` i strona jednego prawa ``/prawa/<slug>``.

Treść pochodzi w całości z rejestru ``app.logic.laws`` — ten moduł niczego nie
dopisuje i nie zakłada, ile praw jest w zestawie. Wzory rysuje
``app.logic.formula.to_html``, a wynik wstawiamy do szablonu przez ``|safe``,
tak samo jak ``app/blueprints/wstep.py``. Komponenty interaktywne
(tablica prawdy, rysunek) są zwykłymi ``{% include %}`` z katalogu
``app/templates/partials/`` — wypełniają je karty PRZ-011, PRZ-012 i PRZ-013.

Od karty PRZ-123 oba rysunki prawa (schemat bramek i diagram zbiorów) liczy
:mod:`app.logic.diagrams` — serwer, nie przeglądarka. Ten moduł przygotowuje
gotowe kroki rysunków (``bramki`` i ``zbiory``) dla szablonu. Karta PRZ-141
dokłada numer kroku z adresu (``/prawa/<slug>?krok=2``): rysunki otwierają się
wtedy na wskazanym kroku, także bez JavaScriptu.

Sekcję „Krok po kroku" buduje ten moduł (karta PRZ-143): porównuje formułę przed
krokiem z formułą po kroku, wyróżnia zmieniony fragment znacznikiem ``<mark>``
i dokłada do każdego kroku nazwę użytego prawa oraz zdanie „dlaczego wolno".
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from flask import Blueprint, render_template, request
from markupsafe import Markup, escape

from app.logic.diagrams import gates_svg, kroki_gates, kroki_sets, sets_svg
from app.logic.formula import FormulaError, Node, parse, subformulas, to_html, to_text, variables
from app.logic.law_model import Law, Step
from app.logic.laws import all_laws, by_category, dlaczego_wolno, get

bp = Blueprint("laws", __name__)

#: Partial rysunku dla każdej wartości pola ``Law.wizualizacja``.
#: ``switch`` (wyłącznik) pokazujemy bramkami, ``chain`` — śladem kroków.
#: Te same reguły opisuje karta PRZ-010 w sekcji „Context”. Od PRZ-123 strona prawa
#: pokazuje **oba** diagramy, więc ``_gates.html`` i ``_sets.html`` różni tylko
#: kolejność figur (patrz ``partials/_diagramy.html``).
RYSUNKI: dict[str, str] = {
    "gates": "partials/_gates.html",
    "switch": "partials/_gates.html",
    "sets": "partials/_sets.html",
    "chain": "partials/_steps.html",
}

#: Rysunek dla nieznanej wartości ``Law.wizualizacja``. Rejestr już sprawdza to pole
#: (``laws.validate``), więc to tylko zabezpieczenie przed pustą sekcją na stronie.
RYSUNEK_ZAPASOWY = "partials/_steps.html"

#: Token formuły: nazwa zmiennej, operator albo nawias. Spacje nie tworzą tokenów —
#: nie zmieniają formuły, a tylko rozpychają zapis (karta PRZ-143).
_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[^\sA-Za-z_]")

#: Operatory dwuargumentowe. Gdy zmiana zaczyna się albo kończy na takim
#: operatorze, wyróżnienie rozszerzamy na cały jego argument — inaczej fragment
#: byłby urwany (``∧ r``), a zdanie pod krokiem niezrozumiałe (karta PRZ-143).
_BINARNE = frozenset("∧∨→≡")

#: Opis wyróżnionego fragmentu dla czytnika ekranu. Tego samego napisu używa
#: ``steps.js`` na stronie przekształcania, więc znacznik ``<mark>`` brzmi wszędzie
#: tak samo. Sam kolor nigdy nie jest jedynym nośnikiem informacji o zmianie.
_TEKST_FRAGMENTU = "ten fragment zastępujemy"


def formula_to_html(text: str, styl: str = "wyklad") -> Markup:
    """Zwraca wzór jako bezpieczny HTML z ``formula.to_html``.

    Gdy napis nie jest poprawną formułą, zwracamy go jako tekst bez znaczników.
    Dzięki temu brakujące przecinki w treści prawa pokazują brzydki wzór, a nie
    stronę z błędem 500. Poprawną treść rejestru sprawdza ``tests/test_laws.py``,
    a ``tests/test_laws_views.py`` pilnuje, że każdy wzór idzie przez ``to_html``.
    """
    try:
        return Markup(to_html(parse(text), styl))
    except FormulaError:
        return escape(text)


def drawing(law: Law) -> str:
    """Zwraca ścieżkę partialu z rysunkiem dla tego prawa."""
    return RYSUNKI.get(law.wizualizacja, RYSUNEK_ZAPASOWY)


def _wartosciowanie(node: Node) -> dict[str, bool]:
    """Wartościowanie dla schematu bramek: wszystkie zmienne prawdziwe.

    To pierwszy wiersz tablicy prawdy (``app.logic.truth`` liczy wiersze w tej samej
    kolejności), więc rysunek pokazuje wartości podformuł z wykładu: same jedynki.
    """
    return dict.fromkeys(variables(node), True)


def _kroki_rysunku(
    czesci: list[Node],
    kroki: list[dict],
    rysuj: Callable[[int], Markup],
) -> list[dict]:
    """Zamienia kroki z ``diagrams`` na dane dla szablonu: wzór i gotowy SVG.

    Krok ``i`` odpowiada podformule ``czesci[i]`` — obie listy powstają w tej samej
    kolejności (``formula.subformulas``), więc wzór i rysunek opisują ten sam stan.
    """
    return [
        {
            "opis": krok["opis"],
            "wzor": formula_to_html(to_text(czesci[numer])),
            "svg": rysuj(numer),
        }
        for numer, krok in enumerate(kroki)
    ]


def _od_kroku(kroki: list[dict], krok: int | None) -> list[dict]:
    """Przestawia kroki rysunku tak, żeby krok ``krok`` stał pierwszy.

    Strona pokazuje pierwszy krok z listy, a ``wizualizacje.js`` zawsze startuje
    od pierwszego szablonu — dlatego wybór kroku z adresu to przestawienie listy,
    a nie osobny rysunek. Lista jest zamknięta w kółko: kroki po wybranym idą
    dalej w swojej kolejności, a te przed nim na koniec, więc wszystkie zostają
    na stronie (karta PRZ-141). Numer spoza listy przycinamy do jej końców.
    """
    if krok is None or not kroki:
        return kroki
    numer = max(0, min(krok, len(kroki) - 1))
    return kroki[numer:] + kroki[:numer]


def _krok_z_adresu(wartosc: str | None) -> int | None:
    """Numer kroku z adresu (``?krok=2``); brak wartości albo śmieć to „od początku”."""
    if wartosc is None:
        return None
    try:
        return int(wartosc.strip())
    except ValueError:
        return None


def diagramy(law: Law, krok: int | None = None) -> dict[str, dict]:
    """Oba rysunki prawa razem z krokami, gotowe dla szablonu (PRZ-123, PRZ-141).

    Gdy wzór prawa się nie parsuje, zwracamy puste listy kroków — strona pokaże wzór
    i komunikat, a nie błąd 500 (tak samo zachowuje się ``formula_to_html``).

    ``krok`` to numer z adresu (``?krok=N``) — otwiera stronę na wskazanym kroku
    rysunku, bez JavaScriptu. Listę kroków przesuwa :func:`_od_kroku`.
    """
    try:
        node = parse(law.formula)
    except FormulaError:
        return {"bramki": {"kroki": []}, "zbiory": {"kroki": []}}

    wartosci = _wartosciowanie(node)
    czesci = subformulas(node)
    bramki = _kroki_rysunku(
        czesci,
        kroki_gates(node),
        lambda numer: gates_svg(node, wartosci, krok=numer),
    )
    zbiory = _kroki_rysunku(
        czesci,
        kroki_sets(node),
        lambda numer: sets_svg(node, krok=numer),
    )
    return {
        "bramki": {"kroki": _od_kroku(bramki, krok)},
        "zbiory": {"kroki": _od_kroku(zbiory, krok)},
    }


def neighbours(law: Law) -> tuple[Law | None, Law | None]:
    """Zwraca ``(poprzednie, następne)`` prawo w kolejności nauki.

    Pierwsze prawo nie ma poprzedniego, ostatnie — następnego; wtedy zwracamy
    ``None``. Strona **ukrywa** brakujący kierunek, a nie zawija go na drugi
    koniec listy: czytelnik ma widzieć, gdzie kończy się zestaw, a nie wracać
    niespodziewanie na początek. Prawo spoza rejestru też daje ``(None, None)``.
    """
    prawa = all_laws()
    for index, current in enumerate(prawa):
        if current.slug != law.slug:
            continue
        poprzednie = prawa[index - 1] if index > 0 else None
        nastepne = prawa[index + 1] if index + 1 < len(prawa) else None
        return poprzednie, nastepne
    return None, None


# ---------------------------------------------------------------------------
# Sekcja „Krok po kroku" (karta PRZ-143)
# ---------------------------------------------------------------------------


def plakietka_prawa(regula: str) -> str:
    """Zwraca nazwę prawa użytego w kroku — treść plakietki nad strzałką.

    Reguła to zwykle ``slug`` prawa z rejestru, więc nazwę bierzemy z ``laws.get``.
    Krok początkowy ma regułę ``"założenie"`` i plakietkę „punkt wyjścia".
    Reguła spoza rejestru pokazuje się pod swoją nazwą — strona nie ma prawa
    zniknąć, gdy treść użyje reguły, której rejestr jeszcze nie zna.
    """
    if regula == "założenie":
        return "punkt wyjścia"
    prawo = get(regula)
    return prawo.nazwa if prawo is not None else regula


def _tokeny(formula: str) -> list[tuple[str, int]]:
    """Tokeny formuły z ich pozycją w tekście: zmienna, operator albo nawias.

    Spacje pomijamy — nie zmieniają formuły, a tylko rozpychają zapis.
    """
    return [(token.group(0), token.start()) for token in _TOKEN.finditer(formula)]


def _srodek_zmiany(
    przed: list[tuple[str, int]], po: list[tuple[str, int]]
) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
    """Zwraca zakresy tokenów, którymi różnią się formuły: ``(przed, po)``.

    Odciskamy wspólny początek i wspólny koniec, a zmieniony środek zostaje —
    dlatego wynik nigdy nie zależy od tego, któremu wystąpieniu zmiennej
    dopasuje się dopasowanie sekwencji. ``None`` znaczy „ta strona się nie
    zmienia": krok tylko dopisuje albo usuwa fragment.
    """
    poczatek = 0
    while poczatek < len(przed) and poczatek < len(po) and przed[poczatek][0] == po[poczatek][0]:
        poczatek += 1
    koniec_przed = len(przed)
    koniec_po = len(po)
    while (
        koniec_przed > poczatek
        and koniec_po > poczatek
        and przed[koniec_przed - 1][0] == po[koniec_po - 1][0]
    ):
        koniec_przed -= 1
        koniec_po -= 1
    return (
        (poczatek, koniec_przed - 1) if koniec_przed > poczatek else None,
        (poczatek, koniec_po - 1) if koniec_po > poczatek else None,
    )


def _pary_nawiasow(tokeny: list[str]) -> dict[int, int]:
    """Mapa nawiasów: indeks nawiasu → indeks nawiasu z pary."""
    stos: list[int] = []
    pary: dict[int, int] = {}
    for indeks, token in enumerate(tokeny):
        if token == "(":
            stos.append(indeks)
        elif token == ")" and stos:
            otwarcie = stos.pop()
            pary[otwarcie] = indeks
            pary[indeks] = otwarcie
    return pary


def _w_nawiasach(
    tokeny: list[str], pary: dict[int, int], zakres: tuple[int, int]
) -> tuple[int, int]:
    """Rozszerza zakres tokenów do wszystkich par nawiasów, które na niego nachodzą.

    Bez tego kroku de Morgana wyróżniałby urwane ``∼(p ∨`` zamiast całego
    ``∼(p ∨ q)``, a rozdzielność — ``(r ∧ p) ∨ (r ∧ q`` bez nawiasu zamykającego.
    Zakres rozszerzamy z obu stron aż do ustalenia, żeby wyróżnienie zawsze miało
    zbilansowane nawiasy. Gdy zmiana nie dotyka nawiasów, zakres zostaje bez zmian.
    """
    poczatek, koniec = zakres
    rosnie = True
    while rosnie:
        rosnie = False
        for otwarcie, zamkniecie in pary.items():
            if otwarcie >= zamkniecie or otwarcie > koniec or zamkniecie < poczatek:
                continue
            if otwarcie < poczatek or zamkniecie > koniec:
                poczatek = min(poczatek, otwarcie)
                koniec = max(koniec, zamkniecie)
                rosnie = True
    return poczatek, koniec


def _z_operandami(
    tokeny: list[str], pary: dict[int, int], zakres: tuple[int, int]
) -> tuple[int, int]:
    """Rozszerza zakres tak, żeby nie zaczynał się i nie kończył w połowie argumentu.

    Gdy pierwszy token zmiany to operator dwuargumentowy, bierzemy też argument
    z jego lewej strony; gdy ostatni — argument z prawej. Przeczenie na skraju
    zakresu też potrzebuje swojego argumentu, a przeczenie **przed** zakresem
    należy do niego. Bez tego zdanie pod krokiem brzmiałoby „Zamieniamy ∧ r na
    r ∧" albo „Zamieniamy p → p na ∼p → ∼", co początkującemu nic nie mówi.
    """
    poczatek, koniec = zakres
    while poczatek > 0 and tokeny[poczatek - 1] == "∼":
        poczatek -= 1
    if tokeny[poczatek] in _BINARNE:
        poczatek = _argument_w_lewo(tokeny, pary, poczatek)
    if tokeny[koniec] in _BINARNE or tokeny[koniec] == "∼":
        koniec = _argument_w_prawo(tokeny, pary, koniec)
    return poczatek, koniec


def _argument_w_lewo(tokeny: list[str], pary: dict[int, int], indeks: int) -> int:
    """Indeks pierwszego tokenu argumentu stojącego przed tokenem ``indeks``."""
    if indeks == 0:
        return indeks
    pozycja = indeks - 1
    if tokeny[pozycja] == ")" and pozycja in pary:
        pozycja = pary[pozycja]
    # Argument może zaczynać się od przeczeń, np. ∼∼p albo ∼(p ∨ q).
    while pozycja > 0 and tokeny[pozycja - 1] == "∼":
        pozycja -= 1
    return pozycja


def _argument_w_prawo(tokeny: list[str], pary: dict[int, int], indeks: int) -> int:
    """Indeks ostatniego tokenu argumentu stojącego za tokenem ``indeks``."""
    pozycja = indeks + 1
    if pozycja >= len(tokeny):
        return indeks
    while pozycja < len(tokeny) and tokeny[pozycja] == "∼":
        pozycja += 1
    if pozycja >= len(tokeny):
        return len(tokeny) - 1
    if tokeny[pozycja] == "(" and pozycja in pary:
        return pary[pozycja]
    return pozycja


def _na_znaki(tokeny: list[tuple[str, int]], zakres: tuple[int, int]) -> tuple[int, int]:
    """Zamienia zakres tokenów na zakres znaków w tekście formuły."""
    poczatek = tokeny[zakres[0]][1]
    ostatni = tokeny[zakres[1]]
    return poczatek, ostatni[1] + len(ostatni[0])


def _zakres_zmiany(
    formula: str, tokeny: list[tuple[str, int]], zmiana: tuple[int, int] | None
) -> tuple[int, int]:
    """Zakres znaków zmienionego fragmentu jednej formuły.

    Bez zmiany po tej stronie zwracamy całą formułę: wyróżnienie musi mieć co
    objąć, a zdanie pod krokiem mówi, co się stało ze stroną drugą.
    """
    if zmiana is None:
        return 0, len(formula)
    teksty = [tekst for tekst, _ in tokeny]
    pary = _pary_nawiasow(teksty)
    zakres = _w_nawiasach(teksty, pary, _z_operandami(teksty, pary, zmiana))
    return _na_znaki(tokeny, zakres)


def zakresy_zmiany(przed: str, po: str) -> tuple[tuple[int, int], tuple[int, int]]:
    """Zwraca zakresy znaków, którymi różnią się formuły kroku: ``(przed, po)``."""
    tokeny_przed = _tokeny(przed)
    tokeny_po = _tokeny(po)
    zmiana_przed, zmiana_po = _srodek_zmiany(tokeny_przed, tokeny_po)
    return (
        _zakres_zmiany(przed, tokeny_przed, zmiana_przed),
        _zakres_zmiany(po, tokeny_po, zmiana_po),
    )


def zmieniony_fragment(przed: str, po: str) -> tuple[str, str]:
    """Zwraca zmieniony fragment formuły przed i po kroku.

    Porównujemy teksty token po tokenie, a zakres rozszerzamy do najmniejszej
    formuły, która obejmuje zmianę: grupy w nawiasach razem z jej argumentami.
    Gdy jedna strona nie zmienia się wcale (krok tylko dopisuje albo usuwa
    fragment), fragmentem jest cała jej formuła.
    """
    (poczatek_przed, koniec_przed), (poczatek_po, koniec_po) = zakresy_zmiany(przed, po)
    return przed[poczatek_przed:koniec_przed], po[poczatek_po:koniec_po]


def _granice_html(
    wzor_html: str, formula: str, poczatek: int, koniec: int
) -> tuple[int, int] | None:
    """Zamienia zakres znaków formuły na pozycje wstawienia ``<mark>`` w jej HTML.

    ``to_html`` opakowuje każdy operator w ``<span>``, więc pozycja znaku
    w tekście to nie pozycja w HTML. Idziemy po HTML, pomijamy znaczniki i liczymy
    same znaki formuły. Wyróżnienie otwieramy przed znacznikiem, w którym stoi
    pierwszy znak fragmentu, a zamykamy po znacznikach zamykających — inaczej
    ``<mark>`` przecięłoby ``<span>`` i HTML przestałby być poprawny.

    ``None`` znaczy „nie da się wyróżnić": wzór nie ma tyle znaków co formuła,
    bo się nie sparsował i poszedł na stronę jako zwykły tekst.
    """
    otwarte: list[int] = []
    start = stop = None
    glebokosc_w_stop = 0
    licznik = 0
    indeks = 0
    while indeks < len(wzor_html):
        if wzor_html[indeks] == "<":
            zamkniecie = wzor_html.index(">", indeks) + 1
            if wzor_html.startswith("</", indeks):
                if otwarte:
                    otwarte.pop()
            else:
                otwarte.append(indeks)
            indeks = zamkniecie
            continue
        if licznik == poczatek:
            start = otwarte[0] if otwarte else indeks
        licznik += 1
        indeks += 1
        if licznik == koniec:
            stop = indeks
            glebokosc_w_stop = len(otwarte)
    if start is None or stop is None or licznik != len(formula):
        return None
    while glebokosc_w_stop and wzor_html.startswith("</", stop):
        stop = wzor_html.index(">", stop) + 1
        glebokosc_w_stop -= 1
    return start, stop


def zaznacz_fragment(wzor_html: str, formula: str, zakres: tuple[int, int]) -> Markup:
    """Wstawia ``<mark>`` w HTML formuły na miejscu zmienionego fragmentu.

    Gdy zakresu nie da się wskazać w HTML, zwracamy wzór bez wyróżnienia —
    ozdabianie wzoru nigdy nie może wywrócić strony ani zepsuć znaczników.
    """
    granice = _granice_html(wzor_html, formula, *zakres)
    if granice is None:
        return Markup(wzor_html)
    start, stop = granice
    otwarcie = f'<mark class="krok-fragment" aria-label="{_TEKST_FRAGMENTU}">'
    return Markup(f"{wzor_html[:start]}{otwarcie}{wzor_html[start:stop]}</mark>{wzor_html[stop:]}")


@dataclass(frozen=True)
class KrokWidoku:
    """Jeden krok sekcji „Krok po kroku" gotowy do wstawienia w szablon.

    ``przed`` i ``po`` to wzory w HTML ze wyróżnionym fragmentem (``<mark>``),
    ``plakietka`` to nazwa użytego prawa, a ``zmiana`` to zdanie z różnicy —
    puste dla kroku, który nic nie zmienia.
    """

    plakietka: str
    przed: Markup
    po: Markup
    opis: str
    zmiana: str
    dlaczego: str


def kroki_widoku(law: Law) -> list[KrokWidoku]:
    """Przygotowuje kroki prawa dla szablonu: wzory z wyróżnieniem i wyjaśnienia."""
    return [_krok_widoku(krok) for krok in law.kroki]


def _wyklad(formula: str) -> str:
    """Formuła w notacji wykładu — dokładnie ten tekst, który widać w HTML wzoru.

    ``to_html`` pomija nawiasy, które nie zmieniają sensu (``(p ∨ q) ∨ r``
    rysuje jako ``p ∨ q ∨ r``). Zakres zmiany liczymy na tym samym tekście,
    który pokazujemy — inaczej wyróżnienie trafiłoby obok wzoru. Gdy formuła
    się nie parsuje, zwracamy tekst wejściowy: strona pokaże go bez wyróżnienia.
    """
    try:
        return to_text(parse(formula))
    except FormulaError:
        return formula


def _zdanie_zmiany(
    przed: str,
    po: str,
    zakres_przed: tuple[int, int],
    zakres_po: tuple[int, int],
    zmiana_przed: tuple[int, int] | None,
    zmiana_po: tuple[int, int] | None,
    plakietka: str,
) -> str:
    """Zdanie pod krokiem: co dokładnie zmieniło się między wzorami.

    Krok może dopisywać fragment, usuwać go albo zamieniać — i tak nazywamy zmianę.
    „Zamieniamy ∼(p ∨ q) na ∼∼" dla kroku, który tylko dopisuje parę przeczeń,
    myliłoby początkującego. Krok bez zmian (punkt wyjścia) nie dostaje zdania.
    """
    if przed == po:
        return ""
    fragment = przed[zakres_przed[0] : zakres_przed[1]]
    fragment_po = po[zakres_po[0] : zakres_po[1]]
    if zmiana_przed is None:
        return f"Dopisujemy {fragment_po} — to {plakietka}."
    if zmiana_po is None:
        return f"Usuwamy {fragment} — to {plakietka}."
    return f"Zamieniamy {fragment} na {fragment_po} — to {plakietka}."


def _krok_widoku(krok: Step) -> KrokWidoku:
    """Buduje jeden krok: plakietkę, wzory z ``<mark>``, opis, zmianę i „dlaczego"."""
    przed_wyklad = _wyklad(krok.przed)
    po_wyklad = _wyklad(krok.po)
    tokeny_przed = _tokeny(przed_wyklad)
    tokeny_po = _tokeny(po_wyklad)
    zmiana_przed, zmiana_po = _srodek_zmiany(tokeny_przed, tokeny_po)
    zakres_przed = _zakres_zmiany(przed_wyklad, tokeny_przed, zmiana_przed)
    zakres_po = _zakres_zmiany(po_wyklad, tokeny_po, zmiana_po)
    plakietka = plakietka_prawa(krok.reguła)
    return KrokWidoku(
        plakietka=plakietka,
        przed=zaznacz_fragment(str(formula_to_html(krok.przed)), przed_wyklad, zakres_przed),
        po=zaznacz_fragment(str(formula_to_html(krok.po)), po_wyklad, zakres_po),
        opis=krok.opis,
        zmiana=_zdanie_zmiany(
            przed_wyklad, po_wyklad, zakres_przed, zakres_po, zmiana_przed, zmiana_po, plakietka
        ),
        dlaczego=dlaczego_wolno(krok.reguła),
    )


@bp.get("/prawa")
def lista_praw():
    """Lista praw pogrupowana po kategorii; każda pozycja prowadzi do strony prawa."""
    grupy = by_category()
    return render_template(
        "prawa_lista.html",
        grupy=grupy,
        liczba=sum(len(prawa) for prawa in grupy.values()),
        formula_to_html=formula_to_html,
    )


@bp.get("/prawa/<slug>")
def strona_prawa(slug: str):
    """Strona jednego prawa albo komunikat 404, gdy nie ma prawa o tym adresie.

    ``?krok=N`` otwiera oba rysunki na kroku N — numer spoza zakresu pokazuje
    ostatni krok. Działa bez JavaScriptu, bo kroki rysuje serwer (karta PRZ-141).
    """
    law = get(slug)
    if law is None:
        return render_template("nie_ma_prawa.html", slug=slug), 404

    poprzednie, nastepne = neighbours(law)
    rysunki = diagramy(law, _krok_z_adresu(request.args.get("krok")))
    return render_template(
        "prawo.html",
        prawo=law,
        poprzednie=poprzednie,
        nastepne=nastepne,
        rysunek=drawing(law),
        bramki=rysunki["bramki"],
        zbiory=rysunki["zbiory"],
        formula_to_html=formula_to_html,
        kroki=kroki_widoku(law),
    )
