"""Hub wykładu: strona ``/wyklad/<numer>`` z opisem, listą lekcji i sąsiadami.

Widok nie wpisuje niczego ręcznie — czyta rejestr ``app.lessons`` (karta PRZ-070),
więc nowa lekcja albo nowy wykład pojawia się na stronie bez zmiany tego pliku.
Ten sam szablon obsługuje numer spoza rejestru: wtedy odpowiedź ma kod 404.
Karta: PRZ-071.
"""

from __future__ import annotations

from flask import Blueprint, render_template

from app import lessons

bp = Blueprint("wyklad", __name__)


def _sasiedzi(numer: int) -> tuple[lessons.Lecture | None, lessons.Lecture | None]:
    """Zwraca ``(poprzedni, następny)`` wykład z rejestru; na końcach listy ``None``."""
    wszystkie = lessons.lectures()
    for indeks, wyklad in enumerate(wszystkie):
        if wyklad.numer != numer:
            continue
        poprzedni = wszystkie[indeks - 1] if indeks > 0 else None
        nastepny = wszystkie[indeks + 1] if indeks + 1 < len(wszystkie) else None
        return poprzedni, nastepny
    return None, None


@bp.get("/wyklad/<numer>")
def strona_wykladu(numer: str):
    """Strona wykładu (gotowego albo zapowiedzianego) lub komunikat 404.

    Numer spoza rejestru — także taki, który nie jest liczbą (``/wyklad/abc``) —
    dostaje kod 404 i polską stronę z odnośnikiem do spisu treści.
    """
    try:
        numer_wykladu = int(numer)
    except ValueError:
        return render_template("wyklad.html", wyklad=None, numer=numer), 404

    wyklad = lessons.lecture(numer_wykladu)
    if wyklad is None:
        return render_template("wyklad.html", wyklad=None, numer=numer), 404

    poprzedni, nastepny = _sasiedzi(wyklad.numer)
    return render_template(
        "wyklad.html",
        wyklad=wyklad,
        numer=wyklad.numer,
        poprzedni=poprzedni,
        nastepny=nastepny,
    )
