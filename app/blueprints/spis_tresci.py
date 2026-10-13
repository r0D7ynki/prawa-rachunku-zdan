"""Spis treści kursu: wszystkie wykłady i lekcje w jednym miejscu.

Widok nie liczy niczego sam — czyta rejestr ``NAV`` wstrzykiwany przez
``create_app`` (karta PRZ-070). Dzięki temu nowy wykład albo lekcja pojawia się
tu bez zmiany tego pliku. Karta: PRZ-069.
"""

from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint("spis_tresci", __name__)


@bp.get("/spis-tresci")
def spis_tresci():
    """Pokazuje wykłady po kolei; wykłady niegotowe mają dopisek „wkrótce”."""
    return render_template("spis_tresci.html")
