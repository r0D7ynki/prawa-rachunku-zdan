"""Widok quizu ``/quiz`` (karta PRZ-015).

Strona sama nie liczy logiki. Pokazuje ustawienia (zakres i liczba pytań) oraz
puste miejsce na pytania; pytania pobiera i sprawdza API w ``api_quiz.py``,
wołane przez ``app/static/js/quiz.js``:

* ``POST /api/quiz/generate`` — zestaw pytań bez poprawnej odpowiedzi,
* ``POST /api/quiz/check`` — sprawdzenie wybranej odpowiedzi.

Parametr ``?prawo=<slug>`` ustawia zakres na jedno prawo **przez szablon Jinja**,
tak samo jak ``?formula=`` w ``app/blueprints/playground.py``. Dzięki temu odnośnik
z prawem działa także bez JavaScriptu. Nieznany slug nie daje błędu 404: strona
pokazuje komunikat po polsku i proponuje listę ``/prawa``. Parametr trafia do
szablonu jako zwykłe ``{{ }}``, więc Jinja sama go escapuje i nie trzeba ``|safe``.
"""

from __future__ import annotations

from flask import Blueprint, render_template, request

from app.logic.laws import all_laws, get

bp = Blueprint("quiz", __name__)

#: Liczby pytań do wyboru w formularzu startowym.
LICZBY_PYTAN = (3, 5, 10)

#: Liczba pytań zaznaczona na starcie.
DOMYSLNA_LICZBA = 5


@bp.get("/quiz")
def quiz_view():
    """Pokazuje ustawienia quizu i miejsce na pytania.

    ``?prawo=<slug>`` zaznacza jedno prawo na liście zakresu. Nieznany slug
    dodaje komunikat po polsku z odnośnikiem do ``/prawa`` — nie przerywa strony.
    """
    podane = request.args.get("prawo", "").strip()
    zakres = get(podane) if podane else None
    blad = None
    if podane and zakres is None:
        blad = f"Nie mamy prawa o adresie „{podane}”."

    return render_template(
        "quiz.html",
        prawa=all_laws(),
        liczby=LICZBY_PYTAN,
        domyslna=DOMYSLNA_LICZBA,
        zakres=zakres,
        podane=podane,
        blad=blad,
    )
