"""API listy praw: ``GET /api/prawa`` (karta PRZ-010).

Endpoint zwraca to samo, co pokazuje lista ``/prawa``, tylko w formie danych:
skrót adresu, nazwę, kategorię, wzór w notacji wykładu, wzór w ASCII i rodzaj
rysunku. Poprzednia wersja narzędzi (przeglądarka, quiz i plac zabaw) może dzięki
temu zbudować listę bez zgadywania adresów ze stron HTML.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from app.logic.laws import all_laws

bp = Blueprint("api_laws", __name__, url_prefix="/api")

#: Pola prawa pokazywane w JSON-ie (patrz ``docs/ARCHITEKTURA.md``, sekcja „API”).
#: Wzoru w HTML (``to_html``) nie wysyłamy — HTML zostaje w warstwie widoków.
POLA_W_JSON: tuple[str, ...] = (
    "slug",
    "nazwa",
    "kategoria",
    "formula",
    "formula_ascii",
    "wizualizacja",
)


@bp.get("/prawa")
def prawa():
    """Zwraca wszystkie prawa w kolejności nauki."""
    return jsonify(
        ok=True,
        prawa=[{pole: getattr(law, pole) for pole in POLA_W_JSON} for law in all_laws()],
    )
