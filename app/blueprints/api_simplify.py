"""API krokowego przekształcania formuł.

Endpoint ``POST /api/formula/simplify`` przyjmuje JSON ``{"formula": str, "cel": str}``
i zwraca ``ok``, ``slad`` (słownik z :meth:`app.logic.simplify.Trace.to_dict`) oraz ``blad``.

Zgodnie z kontraktem API błąd danych to ``ok: false`` i komunikat po polsku z kodem HTTP 200.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.logic.formula import FormulaError
from app.logic.simplify import simplify

bp = Blueprint("api_simplify", __name__, url_prefix="/api")

#: Dozwolone cele przekształcania.
CELE = ("auto", "nnf", "dnf", "cnf")

#: Cel używany, gdy żądanie go nie poda.
CEL_DOMYSLNY = "auto"


def _blad(komunikat: str):
    """Odpowiedź z błędem danych: ``ok: false`` i kod HTTP 200."""
    return jsonify(ok=False, blad=komunikat)


@bp.post("/formula/simplify")
def simplify_formula():
    """Przekształca formułę i zwraca ślad krok po kroku."""
    dane = request.get_json(silent=True) or {}
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

    return jsonify(ok=True, slad=slad.to_dict())
