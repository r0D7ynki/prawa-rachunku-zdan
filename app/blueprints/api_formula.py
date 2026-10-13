"""API formuł: parsowanie, tablica prawdy i równoważność.

Blueprint ``api_formula`` (``url_prefix="/api"``) wystawia trzy endpointy ``POST``:

* ``/api/formula/parse`` — ``{"formula": str}`` → trzy zapisy formuły, drzewo AST i zmienne,
* ``/api/formula/table`` — ``{"formula": str, "podformuly": bool}`` → tablica prawdy,
* ``/api/equivalence`` — ``{"lewa": str, "prawa": str}`` → czy formuły są równoważne.

Zasada wspólna dla całego API: **błąd danych to nie awaria**. Brak pola, zły typ pola,
za długa i nieparsowalna formuła dają ``ok: false``, pole ``blad`` po polsku i kod HTTP 200.
Dane od użytkownika nigdy nie kończą się kodem 500.

Notacja z wykładu jest główna: pole ``wyklad`` używa ``∼`` i ``≡``, a pole ``unicode`` —
``¬`` i ``↔``. Wartości logiczne oddajemy jako ``1`` i ``0`` (pole ``znaki`` tablicy
i pole ``kontrprzyklad``), tak jak pokazujemy je na wykładzie.
"""

from __future__ import annotations

import functools
from collections.abc import Callable

from flask import Blueprint, Response, jsonify, request

from app.logic import truth
from app.logic.formula import FormulaError, Node, Not, Var, parse, to_html, to_text, variables

bp = Blueprint("api_formula", __name__, url_prefix="/api")

#: Najdłuższa formuła, jaką przyjmujemy. Dłuższa to błąd danych, nie awaria serwera.
MAX_FORMULA_LENGTH = 500

#: Nazwa pola z wynikami kolumn w wierszu tablicy (umowa z ``docs/ARCHITEKTURA.md``).
VALUES_FIELD = "values"


class _BadInput(Exception):
    """Błąd danych wejściowych — trafia do pola ``blad``, nie do kodu 500."""


def _error(message: str) -> Response:
    """Odpowiedź z błędem danych: ``ok: false``, komunikat po polsku, kod HTTP 200."""
    return jsonify({"ok": False, "blad": message})


def _ok(**fields: object) -> Response:
    """Odpowiedź poprawna. Dokłada ``ok: true`` i puste ``blad`` z umowy API."""
    return jsonify({"ok": True, "blad": "", **fields})


def _data_errors(view: Callable) -> Callable:
    """Zamienia błąd danych w odpowiedź ``ok: false`` (kod 200) zamiast awarii.

    Łapie błędy składni z :mod:`app.logic.formula` i błędy granic z :mod:`app.logic.truth`
    (za dużo zmiennych), a także zbyt głębokie zagnieżdżenie, które wyczerpuje stos.
    """

    @functools.wraps(view)
    def wrapper(*args: object, **kwargs: object) -> Response:
        try:
            return view(*args, **kwargs)
        except (_BadInput, FormulaError) as error:
            return _error(str(error))
        except RecursionError:
            return _error("Formuła jest zbyt głęboko zagnieżdżona — skróć ją.")

    return wrapper


def _json_body() -> dict:
    """Zwraca treść żądania jako słownik albo podnosi ``_BadInput``."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise _BadInput('Treść żądania musi być obiektem JSON, np. {"formula": "p ∧ q"}.')
    return payload


def _check_length(text: str, name: str) -> None:
    """Pilnuje limitu długości formuły — chroni serwer przed ogromnym wejściem."""
    if len(text) > MAX_FORMULA_LENGTH:
        raise _BadInput(
            f"Pole '{name}' ma {len(text)} znaków — limit to {MAX_FORMULA_LENGTH} znaków."
        )


def _text_field(payload: dict, name: str) -> str:
    """Czyta pole tekstowe formuły. Brak pola i zły typ to ``_BadInput``."""
    if name not in payload:
        raise _BadInput(f"Brakuje pola '{name}'.")
    value = payload[name]
    if not isinstance(value, str):
        raise _BadInput(f"Pole '{name}' musi być tekstem.")
    _check_length(value, name)
    return value


def _bool_field(payload: dict, name: str, default: bool) -> bool:
    """Czyta pole logiczne. Brak pola daje wartość domyślną, zły typ to ``_BadInput``."""
    if name not in payload:
        return default
    value = payload[name]
    if not isinstance(value, bool):
        raise _BadInput(f"Pole '{name}' musi być prawdą albo fałszem (true/false).")
    return value


def _ast_to_dict(node: Node) -> dict:
    """Zamienia drzewo formuły na drzewo JSON wg umowy API.

    Postać węzłów: ``{"typ": "Var", "nazwa": "p"}``, ``{"typ": "Not", "dziecko": {...}}``
    oraz ``{"typ": "And"|"Or"|"Imp"|"Iff", "lewy": {...}, "prawy": {...}}``.
    Rysunki w JavaScripcie budują się z tego drzewa, więc nie muszą zgadywać struktury
    formuły z tekstu.
    """
    if isinstance(node, Var):
        return {"typ": "Var", "nazwa": node.name}
    if isinstance(node, Not):
        return {"typ": "Not", "dziecko": _ast_to_dict(node.child)}
    return {
        "typ": type(node).__name__,
        "lewy": _ast_to_dict(node.left),
        "prawy": _ast_to_dict(node.right),
    }


def _zero_one(env: dict[str, bool]) -> dict[str, int]:
    """Zamienia wartościowanie na ``1`` i ``0`` — tak pokazujemy wartości na wykładzie."""
    return {name: int(value) for name, value in env.items()}


def _symbol_rows(table: truth.TruthTable) -> list[dict]:
    """Wiersze tablicy z wartościami ``1``/``0`` zamiast ``true``/``false``.

    Kształt wiersza jest taki sam jak w ``tabela.rows``: nazwy zmiennych plus pole
    ``values`` z wynikami kolumn.
    """
    data = table.to_dict()
    return [
        {
            **{name: int(row[name]) for name in data["variables"]},
            VALUES_FIELD: [int(value) for value in row[VALUES_FIELD]],
        }
        for row in data["rows"]
    ]


def _parse_side(payload: dict, name: str) -> Node:
    """Parsuje jedną stronę porównania; komunikat mówi, o które pole chodzi."""
    try:
        return parse(_text_field(payload, name))
    except FormulaError as error:
        raise FormulaError(f"Pole '{name}': {error}") from error


@bp.post("/formula/parse")
@_data_errors
def formula_parse() -> Response:
    """Zwraca formułę w trzech zapisach, jej HTML, drzewo AST i listę zmiennych."""
    node = parse(_text_field(_json_body(), "formula"))
    return _ok(
        wyklad=to_text(node, "wyklad"),
        unicode=to_text(node, "unicode"),
        ascii=to_text(node, "ascii"),
        html=to_html(node, "wyklad"),
        ast=_ast_to_dict(node),
        zmienne=variables(node),
    )


@bp.post("/formula/table")
@_data_errors
def formula_table() -> Response:
    """Liczy tablicę prawdy i nazywa formułę.

    ``podformuly`` (domyślnie ``True``) dodaje kolumnę na każdą podformułę.
    Pole ``znaki`` powtarza wiersze tablicy, ale z wartościami ``1``/``0``.
    """
    payload = _json_body()
    node = parse(_text_field(payload, "formula"))
    table = truth.build(node, with_subformulas=_bool_field(payload, "podformuly", True))
    return _ok(
        tabela=table.to_dict(),
        klasyfikacja=table.classification,
        znaki=_symbol_rows(table),
    )


@bp.post("/equivalence")
@_data_errors
def equivalence() -> Response:
    """Sprawdza, czy dwie formuły są równoważne.

    Gdy nie są, ``kontrprzyklad`` podaje pierwsze wartościowanie, przy którym wyniki
    się różnią — wartości jako ``1``/``0``. Gdy są, ``kontrprzyklad`` to ``null``.
    """
    payload = _json_body()
    left = _parse_side(payload, "lewa")
    right = _parse_side(payload, "prawa")
    counterexample = truth.counterexample(left, right)
    return _ok(
        rownowazne=counterexample is None,
        kontrprzyklad=None if counterexample is None else _zero_one(counterexample),
    )
