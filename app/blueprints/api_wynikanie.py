"""API wynikania logicznego: ``POST /api/wynikanie``.

Sprawdza, czy teza ``Ψ`` wynika logicznie z założeń ``Φ1 … Φn``.

Wynikanie to tautologiczność implikacji ``(Φ1 ∧ … ∧ Φn) → Ψ``. Tę samą własność
zapisujemy w kodzie jako równoważność ``Φ1 ∧ … ∧ Φn ≡ (Φ1 ∧ … ∧ Φn) ∧ Ψ``:
wartościowania, przy których strony różnią się wynikiem, to dokładnie kontrprzykłady —
założenia prawdziwe, a teza fałszywa. Sprawdzenie liczy ``truth.equivalent``,
a kontrprzykład ``truth.counterexample``.

Funkcję :func:`check_entailment` woła też strona ``/konsekwencja``: formularz działa
bez JavaScriptu i liczy wynik tym samym kodem (karta PRZ-083).

Zasada wspólna dla całego API: **błąd danych to nie awaria**. Brak pola, zły typ,
za dużo założeń i nieparsowalna formuła dają ``ok: false``, pole ``blad`` po polsku
i kod HTTP 200. Dane od użytkownika nigdy nie kończą się kodem 500.
"""

from __future__ import annotations

from typing import Any, TypeAlias

from flask import Blueprint, Response, jsonify, request

from app.logic import truth
from app.logic.formula import And, FormulaError, Node, parse, variables

bp = Blueprint("api_wynikanie", __name__, url_prefix="/api")

#: Najwięcej założeń w jednym pytaniu. Dłuższa lista to błąd danych.
MAX_ZALOZEN = 10

#: Najwięcej zmiennych w założeniach i tezie razem — tyle obsługuje tablica prawdy.
MAX_VARIABLES = 6

#: Najdłuższa pojedyncza formuła. Chroni serwer przed ogromnym wejściem.
MAX_FORMULA_LENGTH = 500

#: Wynik sprawdzenia: kształt odpowiedzi API (``ok``, ``wynika``, ``kontrprzyklad``, ``blad``).
Wynik: TypeAlias = dict[str, Any]


class BadInput(Exception):
    """Błąd danych wejściowych — trafia do pola ``blad``, nie do kodu 500."""


def _error(message: str) -> Wynik:
    """Wynik błędnych danych: ``ok: false``, komunikat po polsku, brak kontrprzykładu."""
    return {"ok": False, "wynika": False, "kontrprzyklad": None, "blad": message}


def _ok(wynika: bool, kontrprzyklad: dict[str, bool] | None) -> Wynik:
    """Wynik poprawny. Wartości kontrprzykładu zapisujemy jako ``1`` i ``0``."""
    return {
        "ok": True,
        "wynika": wynika,
        "kontrprzyklad": None if kontrprzyklad is None else _zero_one(kontrprzyklad),
        "blad": "",
    }


def _zero_one(env: dict[str, bool]) -> dict[str, int]:
    """Wartościowanie jako ``1`` i ``0`` — tak pokazujemy wartości na wykładzie."""
    return {name: int(value) for name, value in env.items()}


def _assumption_texts(zalozenia: object) -> list[str]:
    """Czyta listę założeń i pilnuje jej kształtu; puste wiersze pomija."""
    if zalozenia is None:
        raise BadInput("Brakuje pola 'zalozenia' — podaj listę formuł założeń.")
    if not isinstance(zalozenia, list):
        raise BadInput("Pole 'zalozenia' musi być listą formuł.")
    for text in zalozenia:
        if not isinstance(text, str):
            raise BadInput("Każde założenie musi być tekstem.")
    return [text for text in (text.strip() for text in zalozenia) if text]


def _thesis_text(teza: object) -> str:
    """Czyta tezę; brak pola i zły typ to błąd danych."""
    if teza is None:
        raise BadInput("Brakuje pola 'teza' — podaj formułę tezy.")
    if not isinstance(teza, str):
        raise BadInput("Pole 'teza' musi być tekstem.")
    return teza.strip()


def _check_length(text: str, opis: str) -> str:
    """Pilnuje limitu długości pojedynczej formuły."""
    if len(text) > MAX_FORMULA_LENGTH:
        raise BadInput(f"{opis} ma {len(text)} znaków — limit to {MAX_FORMULA_LENGTH} znaków.")
    return text


def _parse_assumptions(texts: list[str]) -> list[Node]:
    """Zamienia założenia na drzewa formuł; komunikat mówi, które założenie jest złe."""
    if not texts:
        raise BadInput("Podaj co najmniej jedno założenie.")
    if len(texts) > MAX_ZALOZEN:
        raise BadInput(f"Założeń jest {len(texts)} — limit to {MAX_ZALOZEN}.")
    nodes: list[Node] = []
    for numer, text in enumerate(texts, start=1):
        _check_length(text, f"Założenie {numer}")
        try:
            nodes.append(parse(text))
        except FormulaError as error:
            raise FormulaError(f"Założenie {numer}: {error}") from error
    return nodes


def _parse_thesis(text: str) -> Node:
    """Zamienia tezę na drzewo formuły; komunikat mówi, że chodzi o tezę."""
    if not text:
        raise BadInput("Podaj tezę.")
    _check_length(text, "Teza")
    try:
        return parse(text)
    except FormulaError as error:
        raise FormulaError(f"Teza: {error}") from error


def _check_variables(nodes: list[Node]) -> None:
    """Pilnuje granicy 6 zmiennych — tyle wierszy tablicy prawdy liczy ``truth``."""
    names = sorted({name for node in nodes for name in variables(node)})
    if len(names) > MAX_VARIABLES:
        raise BadInput(
            f"W formułach jest {len(names)} zmiennych ({', '.join(names)}) — "
            f"limit to {MAX_VARIABLES}."
        )


def _conjunction(nodes: list[Node]) -> Node:
    """Koniunkcja założeń ``Φ1 ∧ Φ2 ∧ … ∧ Φn`` — od lewej, jak w zapisie wykładu."""
    result = nodes[0]
    for node in nodes[1:]:
        result = And(result, node)
    return result


def check_entailment(zalozenia: object, teza: object) -> Wynik:
    """Sprawdza, czy teza wynika z założeń. Zwraca wynik w kształcie odpowiedzi API.

    Nigdy nie rzuca: błąd danych opisuje pole ``blad``, a ``ok`` jest wtedy fałszem.
    Funkcji używa endpoint ``POST /api/wynikanie`` i formularz strony ``/konsekwencja``.
    """
    try:
        return _check(zalozenia, teza)
    except (BadInput, FormulaError) as error:
        return _error(str(error))
    except RecursionError:
        return _error("Formuła jest zbyt głęboko zagnieżdżona — skróć ją.")


def _check(zalozenia: object, teza: object) -> Wynik:
    """Właściwe sprawdzenie; błędy danych podnosi jako wyjątki."""
    assumptions = _parse_assumptions(_assumption_texts(zalozenia))
    thesis = _parse_thesis(_thesis_text(teza))
    _check_variables([*assumptions, thesis])

    conjunction = _conjunction(assumptions)
    # Dołożenie tezy do założeń nic nie zmienia dokładnie wtedy, gdy teza wynika.
    augmented = And(conjunction, thesis)
    if truth.equivalent(conjunction, augmented):
        return _ok(wynika=True, kontrprzyklad=None)
    return _ok(wynika=False, kontrprzyklad=truth.counterexample(conjunction, augmented))


@bp.post("/wynikanie")
def wynikanie() -> Response:
    """Sprawdza wynikanie dla ``{"zalozenia": ["p → q", "∼q"], "teza": "∼p"}``.

    Odpowiedź ma pola ``ok``, ``wynika``, ``kontrprzyklad`` (słownik ``{"p": 1}``
    albo ``null``) i ``blad``. Błędne dane to ``ok: false`` i kod HTTP 200.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(
            _error(
                'Treść żądania musi być obiektem JSON, np. {"zalozenia": ["p → q"], "teza": "q"}.'
            )
        )
    return jsonify(check_entailment(payload.get("zalozenia"), payload.get("teza")))
