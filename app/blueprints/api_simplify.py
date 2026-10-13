"""API krokowego przekształcania formuł.

Endpoint ``POST /api/formula/simplify`` przyjmuje JSON ``{"formula": str, "cel": str}``
i zwraca ``ok``, ``slad`` (słownik z :meth:`app.logic.simplify.Trace.to_dict`) oraz ``blad``.

Każdy krok śladu ma dodatkowo pole ``fragment`` — tekst podformuły, którą ten krok
zastępuje (może być pusty). Pole dokłada ten moduł, bo silnik
(``app/logic/simplify.py``) opisuje krok bez wskazania zmienianego fragmentu,
a strona potrzebuje go, żeby wyróżnić fragment w obu formułach kroku.

Zgodnie z kontraktem API błąd danych to ``ok: false`` i komunikat po polsku z kodem HTTP 200.
Dotyczy to także ciała, które nie jest obiektem JSON, oraz formuły zbyt głęboko zagnieżdżonej —
dlatego łapiemy tu ``RecursionError``, tak samo jak ``app/blueprints/api_formula.py``.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.logic.formula import FormulaError, parse, subformulas, to_text
from app.logic.simplify import simplify

bp = Blueprint("api_simplify", __name__, url_prefix="/api")

#: Dozwolone cele przekształcania.
CELE = ("auto", "nnf", "dnf", "cnf")

#: Cel używany, gdy żądanie go nie poda.
CEL_DOMYSLNY = "auto"

#: Komunikat dla ciała, które nie jest obiektem JSON (lista, liczba, brak treści).
BLAD_CIALA = 'Treść żądania musi być obiektem JSON, np. {"formula": "p → q", "cel": "nnf"}.'

#: Komunikat dla formuły, która wyczerpuje stos parsera.
BLAD_ZAGNIEZDZENIA = "Formuła jest zbyt głęboko zagnieżdżona — skróć ją."


def _blad(komunikat: str):
    """Odpowiedź z błędem danych: ``ok: false`` i kod HTTP 200."""
    return jsonify(ok=False, blad=komunikat)


def _fragment(przed: str, po: str) -> str:
    """Zwraca tekst podformuły, którą ten krok zastępuje (może być pusty).

    Bierzemy **najmniejszą** podformułę formuły ``przed``, której nie ma wśród podformuł
    ``po`` — to dokładnie ten fragment, który ten krok zmienia. Przykład: dla kroku
    ``(p → q) ∧ (q → p)`` ⇒ ``(∼p ∨ q) ∧ (q → p)`` wynikiem jest ``p → q``.

    Gdy nie ma czego wskazać (obie formuły są takie same) albo tekstu nie da się sparsować,
    zwracamy pusty napis — strona pokazuje wtedy krok bez wyróżnienia.
    """
    try:
        node_przed = parse(przed)
        node_po = parse(po)
    except (FormulaError, RecursionError):
        return ""

    teksty_po = {to_text(podformula) for podformula in subformulas(node_po)}
    for podformula in subformulas(node_przed):  # od najmniejszej podformuły
        tekst = to_text(podformula)
        if tekst not in teksty_po:
            return tekst
    return ""


def _ze_fragmentami(slad: dict) -> dict:
    """Dokłada każdemu krokowi śladu pole ``fragment``."""
    for krok in slad["kroki"]:
        krok["fragment"] = _fragment(krok["przed"], krok["po"])
    return slad


@bp.post("/formula/simplify")
def simplify_formula():
    """Przekształca formułę i zwraca ślad krok po kroku."""
    dane = request.get_json(silent=True)
    if not isinstance(dane, dict):
        return _blad(BLAD_CIALA)

    formula = dane.get("formula", "")
    cel = dane.get("cel") or CEL_DOMYSLNY

    if not isinstance(formula, str) or not formula.strip():
        return _blad("Podaj formułę do przekształcenia.")

    if cel not in CELE:
        return _blad(
            f"Nieznany cel przekształcania: '{cel}'. Dozwolone cele to auto, nnf, dnf, cnf."
        )

    try:
        slad = simplify(formula, cel)
    except FormulaError as blad:
        return _blad(str(blad))
    except RecursionError:
        return _blad(BLAD_ZAGNIEZDZENIA)

    return jsonify(ok=True, slad=_ze_fragmentami(slad.to_dict()))
