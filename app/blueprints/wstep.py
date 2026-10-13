"""Pierwsza lekcja kursu: ``/wstep`` — co to logika i poprawne wnioskowanie.

Treść odwzorowuje wykład 1 („Logika pragmatyczna”, PWr). Wzory rysuje
``app.logic.formula.to_html``. Ten moduł powstaje w karcie PRZ-001, a znaki ``∼`` i ``≡``
dodaje karta PRZ-017, więc — tak jak ``home.py`` wobec rejestru praw — nie zakładamy, że
są już gotowe. Brak modułu ani brak znaku nie psuje strony: wzór pokazujemy wtedy jako
tekst, a nie zwracamy błędu 500.
"""

from __future__ import annotations

import importlib.util

from flask import Blueprint, render_template
from markupsafe import Markup, escape

bp = Blueprint("wstep", __name__)

#: Moduł z parserem i wypisywaniem formuł. Do czasu karty PRZ-001 może jeszcze nie istnieć.
FORMULA_MODULE = "app.logic.formula"

#: Wzór kontrapozycji: z implikacji i zaprzeczonego następnika wynika zaprzeczony poprzednik.
KONTRAPOZYCJA = "((p → q) ∧ ∼q) → ∼p"

#: Wzór odwrócenia implikacji: zaprzeczony poprzednik nie daje zaprzeczonego następnika.
ODWROCENIE_IMPLIKACJI = "((p → q) ∧ ∼p) → ∼q"

#: Znaki znane tylko notacji wykładowej. Parser przyjmuje też ``¬`` i ``↔``
#: (ARCHITEKTURA, tabela „Notacja formuł”), więc te dwa znaki wystarczą jako zapas.
ZAMIENNIKI_ZAPISU = {"∼": "¬", "≡": "↔"}


def formula_to_html(text: str) -> Markup:
    """Zwraca wzór jako bezpieczny HTML.

    Kolejność prób:

    1. ``to_html(parse(text))`` — zapis dokładnie taki, jak na wykładzie,
    2. ten sam wzór zapisany znakami, które parser zna na pewno (``¬``, ``↔``),
    3. zwykły tekst ze znakami escapowanymi.

    Krok 2 jest potrzebny do czasu karty PRZ-017: bez niego wzór z wykładu nie dotarłby
    do ``to_html``. Każda ścieżka zwraca bezpieczny HTML, więc strona nie zwraca 500.
    """
    if importlib.util.find_spec(FORMULA_MODULE) is None:
        return escape(text)
    from app.logic.formula import FormulaError, parse, to_html

    for kandydat in _warianty_zapisu(text):
        try:
            return Markup(to_html(parse(kandydat)))
        except FormulaError:
            continue
    return escape(text)


def _warianty_zapisu(text: str) -> list[str]:
    """Zwraca zapis wykładowy, a potem ten sam wzór w znakach znanych parserowi."""
    warianty = [text]
    zamieniony = text
    for znak, zamiennik in ZAMIENNIKI_ZAPISU.items():
        zamieniony = zamieniony.replace(znak, zamiennik)
    if zamieniony != text:
        warianty.append(zamieniony)
    return warianty


@bp.get("/wstep")
def wstep():
    """Strona wstępu: po co jest logika i kiedy wnioskowanie jest poprawne."""
    return render_template(
        "wstep.html",
        formula_to_html=formula_to_html,
        kontrapozycja=KONTRAPOZYCJA,
        odwrocenie_implikacji=ODWROCENIE_IMPLIKACJI,
    )
