"""Strony informacyjne: strona główna, „Jak czytać” i słowniczek.

Treść praw pochodzi z rejestru ``app.logic.laws`` (karta PRZ-003). Ten plik nie
zakłada treści z innych kart: pokazuje dokładnie to, co rejestr zwróci.
"""

from __future__ import annotations

import importlib.util
from typing import Any

from flask import Blueprint, render_template

bp = Blueprint("home", __name__)

#: Moduł z rejestrem praw. Do czasu karty PRZ-003 może jeszcze nie istnieć.
LAWS_MODULE = "app.logic.laws"


def _all_laws() -> list[Any]:
    """Zwraca prawa z rejestru, a gdy rejestru jeszcze nie ma — pustą listę.

    Brakującego modułu nie udajemy: strona pokazuje wtedy zero praw, więc
    użytkownik nie zobaczy odnośnika do strony, której nie ma.
    """
    if importlib.util.find_spec(LAWS_MODULE) is None:
        return []
    from app.logic.laws import all_laws

    return list(all_laws())


@bp.get("/")
def index():
    """Strona główna: co to rachunek zdań i jak korzystać ze strony."""
    return render_template("home.html", prawa=_all_laws())


@bp.get("/jak-czytac")
def jak_czytac():
    """Objaśnia symbole i sposób czytania tablicy prawdy."""
    return render_template("jak_czytac.html")


@bp.get("/slowniczek")
def slowniczek():
    """Słowniczek pojęć używanych w prawach."""
    return render_template("slowniczek.html")
