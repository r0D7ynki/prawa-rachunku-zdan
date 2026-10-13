"""Typy praw rachunku zdań: ``Step`` i ``Law``.

Moduł trzyma wyłącznie dane — nie zna rejestru (``app/logic/laws.py``), parsera
formuł ani widoków. Dzięki temu pliki treści z ``app/logic/laws_data/`` mogą go
importować, a import nie zrobi się cykliczny.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Law", "Step"]


@dataclass(frozen=True)
class Step:
    """Jeden krok przekształcenia: co robimy i jaka formuła z czego powstaje.

    Pola ``przed`` i ``po`` trzymają formuły w notacji wykładu (``∼``, ``∧``,
    ``∨``, ``→``, ``≡``) — ten sam zapis, który przyjmuje ``formula.parse``.
    """

    opis: str
    reguła: str
    przed: str
    po: str


@dataclass(frozen=True)
class Law:
    """Jedno prawo rachunku zdań wraz z całą treścią potrzebną na stronie.

    ``kategoria`` to dowolny niepusty napis — rejestr nie narzuca zamkniętej
    listy kategorii. ``wizualizacja`` wybiera rysunek i musi być jedną z wartości
    ``laws.WIZUALIZACJE``. ``kroki_warte`` mówi, czy sekcja „Krok po kroku” ma
    sens: przy prawach oczywistych przekształcenie to „masło maślane”, więc
    strona pokazuje wtedy jedno zdanie zamiast listy (karta PRZ-167). Domyślna
    wartość ``True`` zostawia poprawne dane, które pola nie podają.
    """

    slug: str
    nazwa: str
    kategoria: str
    formula: str
    formula_ascii: str
    lewa: str
    prawa: str
    po_ludzku: str
    przyklad: str
    kroki: list[Step]
    czeste_bledy: list[str]
    wizualizacja: str
    quiz: list[dict]
    kroki_warte: bool = True
