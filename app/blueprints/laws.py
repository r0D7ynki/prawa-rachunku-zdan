"""Strony praw: lista ``/prawa`` i strona jednego prawa ``/prawa/<slug>``.

Treść pochodzi w całości z rejestru ``app.logic.laws`` — ten moduł niczego nie
dopisuje i nie zakłada, ile praw jest w zestawie. Wzory rysuje
``app.logic.formula.to_html``, a wynik wstawiamy do szablonu przez ``|safe``,
tak samo jak ``app/blueprints/wstep.py``. Komponenty interaktywne
(tablica prawdy, rysunek) są zwykłymi ``{% include %}`` z katalogu
``app/templates/partials/`` — wypełniają je karty PRZ-011, PRZ-012 i PRZ-013.

Od karty PRZ-123 oba rysunki prawa (schemat bramek i diagram zbiorów) liczy
:mod:`app.logic.diagrams` — serwer, nie przeglądarka. Ten moduł przygotowuje
gotowe kroki rysunków (``bramki`` i ``zbiory``) dla szablonu.
"""

from __future__ import annotations

from collections.abc import Callable

from flask import Blueprint, render_template
from markupsafe import Markup, escape

from app.logic.diagrams import gates_svg, kroki_gates, kroki_sets, sets_svg
from app.logic.formula import FormulaError, Node, parse, subformulas, to_html, to_text, variables
from app.logic.law_model import Law
from app.logic.laws import all_laws, by_category, get

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


def diagramy(law: Law) -> dict[str, dict]:
    """Oba rysunki prawa razem z krokami, gotowe dla szablonu (karta PRZ-123).

    Gdy wzór prawa się nie parsuje, zwracamy puste listy kroków — strona pokaże wzór
    i komunikat, a nie błąd 500 (tak samo zachowuje się ``formula_to_html``).
    """
    try:
        node = parse(law.formula)
    except FormulaError:
        return {"bramki": {"kroki": []}, "zbiory": {"kroki": []}}

    wartosci = _wartosciowanie(node)
    czesci = subformulas(node)
    return {
        "bramki": {
            "kroki": _kroki_rysunku(
                czesci,
                kroki_gates(node),
                lambda numer: gates_svg(node, wartosci, krok=numer),
            )
        },
        "zbiory": {
            "kroki": _kroki_rysunku(
                czesci,
                kroki_sets(node),
                lambda numer: sets_svg(node, krok=numer),
            )
        },
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
    """Strona jednego prawa albo komunikat 404, gdy nie ma prawa o tym adresie."""
    law = get(slug)
    if law is None:
        return render_template("nie_ma_prawa.html", slug=slug), 404

    poprzednie, nastepne = neighbours(law)
    rysunki = diagramy(law)
    return render_template(
        "prawo.html",
        prawo=law,
        poprzednie=poprzednie,
        nastepne=nastepne,
        rysunek=drawing(law),
        bramki=rysunki["bramki"],
        zbiory=rysunki["zbiory"],
        formula_to_html=formula_to_html,
    )
