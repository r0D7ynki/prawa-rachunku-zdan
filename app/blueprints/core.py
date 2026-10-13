"""Endpointy techniczne: stan aplikacji i obsługa błędów."""

from __future__ import annotations

from flask import Blueprint, jsonify

bp = Blueprint("core", __name__)


@bp.get("/zdrowie")
def health():
    """Zwraca stan aplikacji. Testy i bramka sprawdzają ten adres."""
    return jsonify({"status": "ok", "aplikacja": "prawa-rachunku-zdan"})
