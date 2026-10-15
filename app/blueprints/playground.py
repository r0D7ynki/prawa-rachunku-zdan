"""Plac zabaw: własna formuła i cztery widoki wyniku (karta PRZ-014).

Widok ``/plac-zabaw`` nie liczy logiki. Pokazuje formularz, klawiaturę symboli,
cztery przykłady na start i puste miejsca na wyniki. Liczy serwerowe API, a strony
woła JavaScript (``app/static/js/playground.js``):

* ``POST /api/formula/parse`` — forma wykładowa i lista zmiennych,
* ``POST /api/formula/table`` — tablica prawdy i klasyfikacja,
* ``POST /api/formula/simplify`` — krokowe uproszczenie,
* ``POST /api/equivalence`` — porównanie dwóch formuł i kontrprzykład.

Formuła z adresu (``?formula=...``) trafia do pola **przez szablon Jinja**, a nie
przez JavaScript. Dzięki temu odnośnik z formułą działa także bez skryptów.
Szablon wypisuje ją zwykłym ``{{ formula }}`` — Jinja sama escapuje znaki, więc
parametr nigdy nie staje się znacznikiem HTML i nie trzeba filtra ``|safe``.
"""

from __future__ import annotations

from flask import Blueprint, render_template, request

bp = Blueprint("playground", __name__)

#: Formuła w polu, gdy adres nie podaje własnej.
DEFAULT_FORMULA = "p → (q ∧ ∼r)"

#: Druga formuła do porównania, gdy adres nie podaje własnej.
DEFAULT_SECOND = "∼p ∨ q"

#: Symbole wstawiane przyciskami klawiatury — w kolejności z zapisu formuły.
SYMBOLS = ("∼", "¬", "∧", "∨", "→", "≡", "↔", "(", ")")

#: Przykłady na start. Kliknięcie wstawia formułę do pola.
EXAMPLES = ("p → q", "∼(p ∧ q)", "p ∨ ∼p", "(p → q) ∧ p")

#: Cele przekształcania dla przełącznika kroków (umowa z ``docs/ARCHITEKTURA.md``).
GOALS = ("auto", "nnf", "dnf", "cnf")


@bp.get("/plac-zabaw")
def plac_zabaw():
    """Pokazuje formularz i miejsca na wyniki; logikę liczy dopiero API.

    Wartości pól pochodzą z parametrów adresu, więc wynik da się wysłać linkiem.
    Gdy parametru brak, pole dostaje wartość domyślną — nie pustkę.
    """
    formula = request.args.get("formula", DEFAULT_FORMULA)
    druga = request.args.get("druga", DEFAULT_SECOND)
    return render_template(
        "plac_zabaw.html",
        formula=formula,
        druga=druga,
        symbole=SYMBOLS,
        przyklady=EXAMPLES,
        cele=GOALS,
    )
