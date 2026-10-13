"""Strona ``/rezolucja`` — reguła rezolucji i dwa dowody z wykładu 2 (karta PRZ-092).

Treść pochodzi z ``docs/TRESC-WYKLAD2.md`` (sekcje „6. Reguła rezolucji”
i „7. Algorytm rezolucji”). Dane dowodów trzyma ``app.logic.resolution``; ten moduł
tylko je przygotowuje dla szablonu:

* dopisuje kolumnę „Skąd” z rodzaju kroku i jego rodziców (teksty założeń pochodzą
  z kolumny „Skąd” wykładu),
* rysuje klauzule przez ``formula.to_html`` (nigdy ``eval``) i wstawia je w szablonie
  przez ``|safe``,
* pakuje kroki w JSON do atrybutu ``data-kroki``. Skrypt ``rezolucja.js`` czyta ten
  JSON i pokazuje wiersze krok po kroku; bez JavaScriptu cała tabela zostaje w HTML.

Wiersze sprzeczne (para ``x``/``∼x`` i wiersz, który ją zamyka) dostają klasę
``wiersz-sprzecznosc`` i opis słowny dla czytnika ekranu — kolor nigdy nie jest
jedynym nośnikiem informacji.
"""

from __future__ import annotations

import json
from typing import Any

from flask import Blueprint, render_template
from markupsafe import Markup, escape

from app.logic.formula import FormulaError, parse, to_html
from app.logic.resolution import (
    RODZAJ_NEGACJA_TEZY,
    RODZAJ_REZOLUCJA,
    RODZAJ_SPRZECZNOSC,
    RODZAJ_ZALOZENIE,
    ResolutionProof,
    ResolutionStep,
    proofs,
)

#: Nazwa blueprintu i trasa to tokeny interfejsu (adres ``/rezolucja`` z mapy kodu).
bp = Blueprint("rezolucja", __name__)

#: Odnośnik do lekcji o KPN z wykładu 1 (przypomnienie w sekcji algorytmu).
KPN = "/kpn"

#: Schemat reguły rezolucji z wykładu — dwie przesłanki nad kreską i wniosek pod nią.
#: To zapis schematu (literały ``l1…ln``, ``k1…km``), a nie formuła dla parsera.
SCHEMAT_PRZESLANKI: tuple[str, ...] = (
    "l1 ∨ l2 ∨ … ∨ p ∨ … ∨ ln",
    "k1 ∨ k2 ∨ … ∨ ∼p ∨ … ∨ km",
)
SCHEMAT_WNIOSEK = "l1 ∨ l2 ∨ … ∨ ln ∨ k1 ∨ k2 ∨ … ∨ km"

#: Przykład reguły z wykładu: dwie przesłanki i wniosek z usuniętym literałem ``q``.
PRZYKLAD_PRZESLANKI: tuple[str, ...] = ("p ∨ ∼r ∨ q ∨ s", "p ∨ t ∨ ∼q")
PRZYKLAD_WNIOSEK = "p ∨ ∼r ∨ s ∨ t"

#: Cztery kroki algorytmu rezolucji z wykładu, przepisane zdanie po zdaniu.
ALGORYTM: tuple[str, ...] = (
    "Sprowadź Φ1 ∧ … ∧ Φn oraz ∼Ψ do koniunkcyjnej postaci normalnej (KPN).",
    "Wypisz wszystkie otrzymane klauzule w kolejnych wierszach.",
    "Stosuj systematycznie regułę rezolucji — także do nowo utworzonych wierszy.",
    "Dowód kończy się, gdy powstanie para wierszy sprzecznych (teza udowodniona) "
    "albo gdy nie da się utworzyć żadnej nowej klauzuli (teza nie wynika z założeń).",
)

#: Skąd pochodzą wiersze założeń — formuła z kolumny „Skąd” wykładu, kluczowana
#: identyfikatorem dowodu i numerem wiersza. Brak wpisu to założenie bez formuły.
ZRODLA_ZALOZEN: dict[str, dict[int, str]] = {
    "przyklad-1": {1: "p → q", 2: "r → s", 3: "p ∨ r"},
    "przyklad-2": {2: "p → q", 3: "∼q ∨ r", 4: "∼r"},
}


def formula_to_html(text: str, styl: str = "wyklad") -> Markup:
    """Zwraca wzór jako bezpieczny HTML z ``formula.to_html``.

    Gdy napis nie jest poprawną formułą (np. wiersz „Sprzeczność 8, 9”), oddajemy go
    jako zwykły tekst — treść lekcji nie kończy się błędem 500. Poprawność danych
    pilnuje ``tests/test_rezolucja.py``.
    """
    try:
        return Markup(to_html(parse(text), styl))
    except FormulaError:
        return escape(text)


def _sprzeczne(dowod: ResolutionProof) -> set[int]:
    """Numery wierszy, które tworzą sprzeczność: ostatni wiersz i jego rodzice."""
    ostatni = dowod.kroki[-1]
    return {ostatni.nr, *ostatni.rodzice}


def _skad(krok: ResolutionStep, zrodla: dict[int, str]) -> str:
    """Tekst kolumny „Skąd”: z czego powstał wiersz.

    Założenie pokazuje swoją formułę, negacja tezy nie ma z czego powstać, a wiersz
    rezolucji wymienia numery rodziców (literał sklejenia ma własną kolumnę).
    """
    if krok.rodzaj == RODZAJ_ZALOZENIE:
        return f"założenie {zrodla.get(krok.nr, '')}".strip()
    if krok.rodzaj == RODZAJ_NEGACJA_TEZY:
        return "negacja tezy"
    if krok.rodzaj == RODZAJ_REZOLUCJA:
        return ", ".join(str(nr) for nr in krok.rodzice)
    return "—"


def _opis_sprzecznosci(krok: ResolutionStep, sprzeczne: set[int]) -> str:
    """Zdanie dla czytnika ekranu przy wierszach tworzących sprzeczność."""
    if krok.nr not in sprzeczne:
        return ""
    if krok.rodzaj == RODZAJ_SPRZECZNOSC:
        return f"sprzeczność wierszy {krok.rodzice[0]} i {krok.rodzice[1]}"
    inny = next((nr for nr in krok.rodzice if nr != krok.nr), None)
    if inny is None:
        return "wiersz sprzeczny z ostatnim wierszem dowodu"
    return f"wiersz sprzeczny z wierszem {inny}"


def wiersze_dowodu(dowod: ResolutionProof) -> list[dict[str, Any]]:
    """Wiersze dowodu gotowe dla szablonu: klauzula, „Skąd” i opis sprzeczności."""
    zrodla = ZRODLA_ZALOZEN.get(dowod.id, {})
    sprzeczne = _sprzeczne(dowod)
    return [
        {
            "nr": krok.nr,
            "klauzula": krok.klauzula,
            "skad": _skad(krok, zrodla),
            "literal": krok.literal,
            "rodzaj": krok.rodzaj,
            "sprzeczny": krok.nr in sprzeczne,
            "opis_sprzecznosci": _opis_sprzecznosci(krok, sprzeczne),
        }
        for krok in dowod.kroki
    ]


def _opis_kroku(krok: ResolutionStep) -> str:
    """Zdanie po polsku pod paskiem kroków: co robi ten wiersz dowodu."""
    if krok.rodzaj == RODZAJ_ZALOZENIE:
        return f"Zapisujemy założenie jako klauzulę {krok.klauzula}."
    if krok.rodzaj == RODZAJ_NEGACJA_TEZY:
        return f"Dopisujemy negację tezy jako klauzulę {krok.klauzula}."
    if krok.rodzaj == RODZAJ_REZOLUCJA:
        return f"Sklejamy wiersze {krok.rodzice[0]} i {krok.rodzice[1]} na literale {krok.literal}."
    return f"Wiersze {krok.rodzice[0]} i {krok.rodzice[1]} są sprzeczne — koniec dowodu."


def kroki_dowodu(dowod: ResolutionProof) -> list[dict[str, Any]]:
    """Kroki dla paska (PRZ-072) i dla skryptu: tytuł, opis, rodzaj, rodzice, literał."""
    return [
        {
            "tytul": f"{krok.nr}. {krok.klauzula}",
            "opis": _opis_kroku(krok),
            "nr": krok.nr,
            "rodzaj": krok.rodzaj,
            "rodzice": list(krok.rodzice),
            "literal": krok.literal,
        }
        for krok in dowod.kroki
    ]


def kroki_json(kroki: list[dict[str, Any]]) -> str:
    """Kroki jako JSON do atrybutu ``data-kroki`` (bez uciekania polskich znaków)."""
    return json.dumps(kroki, ensure_ascii=False)


@bp.get("/rezolucja")
def lesson() -> str:
    """Lekcja: reguła rezolucji, algorytm w czterech krokach i dwa dowody z wykładu."""
    dowody = [
        {
            "id": dowod.id,
            "tytul": dowod.tytul,
            "opis": dowod.opis,
            "wiersze": wiersze_dowodu(dowod),
            "kroki": kroki_dowodu(dowod),
            "kroki_json": kroki_json(kroki_dowodu(dowod)),
        }
        for dowod in proofs()
    ]
    return render_template(
        "rezolucja.html",
        dowody=dowody,
        formula_to_html=formula_to_html,
        schemat_przeslanki=SCHEMAT_PRZESLANKI,
        schemat_wniosek=SCHEMAT_WNIOSEK,
        przyklad_przeslanki=PRZYKLAD_PRZESLANKI,
        przyklad_wniosek=PRZYKLAD_WNIOSEK,
        algorytm=ALGORYTM,
        kpn=KPN,
    )
