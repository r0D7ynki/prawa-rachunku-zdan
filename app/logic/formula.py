"""AST, parser i wypisywanie formuł rachunku zdań.

Moduł zamienia tekst formuły na drzewo (``parse``) i wypisuje drzewo z powrotem:
jako tekst w stylu ``wyklad``, ``unicode``, ``ascii`` albo ``latex`` (``to_text``) oraz
jako bezpieczny HTML (``to_html``). Domyślny styl to ``wyklad`` — notacja z wykładu:
``∼`` (U+223C) i ``≡`` (U+2261).

Wejście parsera przyjmuje znaki wykładowe, znaki popularne oraz odpowiedniki ASCII:

============ ============ =================================
Znaczenie    Wykład       Inne dopuszczone
============ ============ =================================
negacja      ``∼``        ``¬``, ``~``, ``!``, ``not``
koniunkcja   ``∧``        ``&``, ``^``, ``and``
alternatywa  ``∨``        ``|``, ``+``, ``or``
implikacja   ``→``        ``->``, ``=>``, ``implies``
równoważność ``≡``        ``↔``, ``<->``, ``<=>``, ``iff``
============ ============ =================================

Kolejność wiązania od najsłabszego: ``≡``, ``→`` (prawostronna), ``∨``, ``∧``, ``∼``.
Nazwa zmiennej to litera albo wyraz (``[A-Za-z_][A-Za-z0-9_]*``), np. ``p``, ``deszcz``.

Parser jest napisany ręcznie (tokenizacja + rekurencyjne zejście). Moduł nigdy nie używa
``eval``, ``exec`` ani ``compile`` na tekście wejściowym.
"""

from __future__ import annotations

import html
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass


class FormulaError(ValueError):
    """Błąd składni formuły. Komunikat po polsku."""


@dataclass(frozen=True)
class Var:
    """Zmienna zdaniowa, np. ``p``."""

    name: str


@dataclass(frozen=True)
class Not:
    """Negacja ``¬p``."""

    child: Node


@dataclass(frozen=True)
class And:
    """Koniunkcja ``p ∧ q``."""

    left: Node
    right: Node


@dataclass(frozen=True)
class Or:
    """Alternatywa ``p ∨ q``."""

    left: Node
    right: Node


@dataclass(frozen=True)
class Imp:
    """Implikacja ``p → q``."""

    left: Node
    right: Node


@dataclass(frozen=True)
class Iff:
    """Równoważność ``p ↔ q``."""

    left: Node
    right: Node


Node = Var | Not | And | Or | Imp | Iff

__all__ = [
    "And",
    "FormulaError",
    "Iff",
    "Imp",
    "Node",
    "Not",
    "Or",
    "Var",
    "depth",
    "evaluate",
    "normalize",
    "parse",
    "replace",
    "same",
    "size",
    "subformulas",
    "to_html",
    "to_text",
    "variables",
]


# ---------------------------------------------------------------------------
# Tokenizacja
# ---------------------------------------------------------------------------

#: Słowa-klucze: pisane małymi literami, działa tylko całe słowo.
_KEYWORDS = {
    "not": "NOT",
    "and": "AND",
    "or": "OR",
    "implies": "IMP",
    "iff": "IFF",
}

#: Operatory jednoliterowe i nawiasy.
#: ``∼`` to U+223C (TILDE OPERATOR) z wykładu, a nie ``~`` U+007E.
#: ``≡`` to U+2261 (IDENTICAL TO) z wykładu, a nie ``=``.
_SINGLE = {
    "∼": "NOT",
    "¬": "NOT",
    "~": "NOT",
    "!": "NOT",
    "∧": "AND",
    "&": "AND",
    "^": "AND",
    "∨": "OR",
    "|": "OR",
    "+": "OR",
    "→": "IMP",
    "≡": "IFF",
    "↔": "IFF",
    "(": "LPAREN",
    ")": "RPAREN",
}

_OPERATOR_KINDS = ("AND", "OR", "IMP", "IFF", "NOT")


@dataclass(frozen=True)
class _Token:
    """Pojedynczy token. ``pos`` to pozycja w tekście liczona od 1 (dla komunikatów)."""

    kind: str
    text: str
    pos: int


def _is_name_start(char: str) -> bool:
    """Czy znak może zaczynać nazwę zmiennej (tylko ASCII, zgodnie z kontraktem)."""
    return char.isascii() and (char.isalpha() or char == "_")


def _is_name_char(char: str) -> bool:
    """Czy znak może być kolejnym znakiem nazwy zmiennej."""
    return char.isascii() and (char.isalnum() or char == "_")


def _tokenize(text: str) -> list[_Token]:
    """Zamienia tekst na listę tokenów. Nieznany znak to ``FormulaError``."""
    tokens: list[_Token] = []
    position = 0
    length = len(text)
    while position < length:
        char = text[position]
        if char.isspace():
            position += 1
            continue

        pair = text[position : position + 2]
        triple = text[position : position + 3]
        if triple in ("<->", "<=>"):
            tokens.append(_Token("IFF", triple, position + 1))
            position += 3
            continue
        if pair in ("->", "=>"):
            tokens.append(_Token("IMP", pair, position + 1))
            position += 2
            continue
        if char in _SINGLE:
            tokens.append(_Token(_SINGLE[char], char, position + 1))
            position += 1
            continue
        if _is_name_start(char):
            end = position + 1
            while end < length and _is_name_char(text[end]):
                end += 1
            word = text[position:end]
            tokens.append(_Token(_KEYWORDS.get(word, "VAR"), word, position + 1))
            position = end
            continue

        raise FormulaError(f"Nieznany znak: '{char}' (pozycja {position + 1}).")
    return tokens


# ---------------------------------------------------------------------------
# Parser: rekurencyjne zejście
# ---------------------------------------------------------------------------


class _Parser:
    """Parser rekurencyjnego zejścia. Kolejność metod = kolejność wiązania."""

    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._index = 0
        self._last_operator: str | None = None

    def parse(self) -> Node:
        """Zwraca drzewo albo podnosi ``FormulaError``."""
        if not self._tokens:
            raise FormulaError("Formuła jest pusta. Wpisz np. p ∧ q.")
        node = self._parse_iff()
        leftover = self._peek()
        if leftover is None:
            return node
        if leftover.kind == "RPAREN":
            raise FormulaError(f"Nieoczekiwany nawias zamykający ')' (pozycja {leftover.pos}).")
        raise FormulaError(
            f"Nieoczekiwany fragment po formule: '{leftover.text}' "
            f"(pozycja {leftover.pos}) — brakuje operatora."
        )

    def _peek(self) -> _Token | None:
        if self._index < len(self._tokens):
            return self._tokens[self._index]
        return None

    def _advance(self) -> _Token:
        token = self._tokens[self._index]
        self._index += 1
        if token.kind in _OPERATOR_KINDS:
            self._last_operator = token.text
        elif token.kind in ("VAR", "LPAREN"):
            self._last_operator = None
        return token

    def _parse_iff(self) -> Node:
        node = self._parse_imp()
        while True:
            token = self._peek()
            if token is None or token.kind != "IFF":
                return node
            self._advance()
            node = Iff(node, self._parse_imp())

    def _parse_imp(self) -> Node:
        node = self._parse_or()
        token = self._peek()
        if token is not None and token.kind == "IMP":
            self._advance()
            return Imp(node, self._parse_imp())
        return node

    def _parse_or(self) -> Node:
        node = self._parse_and()
        while True:
            token = self._peek()
            if token is None or token.kind != "OR":
                return node
            self._advance()
            node = Or(node, self._parse_and())

    def _parse_and(self) -> Node:
        node = self._parse_not()
        while True:
            token = self._peek()
            if token is None or token.kind != "AND":
                return node
            self._advance()
            node = And(node, self._parse_not())

    def _parse_not(self) -> Node:
        token = self._peek()
        if token is not None and token.kind == "NOT":
            self._advance()
            return Not(self._parse_not())
        return self._parse_primary()

    def _parse_primary(self) -> Node:
        token = self._peek()
        if token is None:
            if self._last_operator is not None:
                raise FormulaError(
                    f"Nieoczekiwany koniec formuły — po operatorze "
                    f"'{self._last_operator}' brakuje argumentu."
                )
            raise FormulaError("Nieoczekiwany koniec formuły — brakuje argumentu.")
        if token.kind == "VAR":
            self._advance()
            return Var(token.text)
        if token.kind == "LPAREN":
            opening = self._advance()
            node = self._parse_iff()
            closing = self._peek()
            if closing is None:
                raise FormulaError(
                    f"Brakuje nawiasu zamykającego ')' do nawiasu otwartego w pozycji "
                    f"{opening.pos}."
                )
            if closing.kind != "RPAREN":
                raise FormulaError(
                    f"Brakuje nawiasu zamykającego ')' do nawiasu otwartego w pozycji "
                    f"{opening.pos}; zamiast tego: '{closing.text}'."
                )
            self._advance()
            return node
        raise FormulaError(f"Brakuje argumentu w miejscu '{token.text}' (pozycja {token.pos}).")


def parse(text: str) -> Node:
    """Zamienia tekst formuły na drzewo AST.

    Pomija spacje i wcięcia. Pusty tekst oraz błąd składni to ``FormulaError``
    z komunikatem po polsku.
    """
    return _Parser(_tokenize(text)).parse()


# ---------------------------------------------------------------------------
# Drzewo: przechodzenie
# ---------------------------------------------------------------------------


def _children(node: Node) -> tuple[Node, ...]:
    """Dzieci węzła. Liść (``Var``) nie ma dzieci."""
    if isinstance(node, Var):
        return ()
    if isinstance(node, Not):
        return (node.child,)
    return (node.left, node.right)


def _walk(node: Node) -> Iterator[Node]:
    """Przechodzi drzewo w kolejności podwójnej (dzieci przed rodzicem)."""
    for child in _children(node):
        yield from _walk(child)
    yield node


# ---------------------------------------------------------------------------
# Wypisywanie
# ---------------------------------------------------------------------------

#: Siła wiązania; większa liczba = wiąże mocniej.
_PRECEDENCE = {Var: 6, Not: 5, And: 4, Or: 3, Imp: 2, Iff: 1}

#: Które pole stylu odpowiada któremu operatorowi dwuargumentowemu.
_BINARY_STYLE_KEY = {And: "and", Or: "or", Imp: "imp", Iff: "iff"}

#: Klasa HTML operatora. Nazwy są stałe (umowa z ``docs/ARCHITEKTURA.md``).
_HTML_CLASS = {Not: "op-neg", And: "op-and", Or: "op-or", Imp: "op-imp", Iff: "op-iff"}

_STYLES = {
    "wyklad": {"not": "∼", "and": "∧", "or": "∨", "imp": "→", "iff": "≡"},
    "unicode": {"not": "¬", "and": "∧", "or": "∨", "imp": "→", "iff": "↔"},
    "ascii": {"not": "~", "and": "&", "or": "|", "imp": "->", "iff": "<->"},
    "latex": {
        "not": "\\neg ",
        "and": "\\land",
        "or": "\\lor",
        "imp": "\\to",
        "iff": "\\leftrightarrow",
    },
}


def _style(style: str) -> dict[str, str]:
    """Zwraca zestaw symboli dla stylu albo podnosi ``FormulaError``."""
    symbols = _STYLES.get(style)
    if symbols is None:
        allowed = ", ".join(sorted(_STYLES))
        raise FormulaError(f"Nieznany styl zapisu: '{style}'. Dozwolone: {allowed}.")
    return symbols


def _render(
    node: Node,
    symbols: dict[str, str],
    decorate: Callable[[str, str], str] | None = None,
    escape_vars: bool = False,
) -> tuple[int, str]:
    """Zwraca ``(siła wiązania, napis)`` — napis bez zewnętrznych nawiasów.

    ``decorate`` to funkcja zamieniająca symbol operatora i jego klasę HTML na gotowy
    napis (np. ``<span class="op-neg">∼</span>``). ``escape_vars`` włącza escapowanie
    nazw zmiennych (dla HTML).
    """
    if isinstance(node, Var):
        name = html.escape(node.name, quote=True) if escape_vars else node.name
        return _PRECEDENCE[Var], name

    if isinstance(node, Not):
        precedence, inner = _render(node.child, symbols, decorate, escape_vars)
        if precedence < _PRECEDENCE[Not]:
            inner = f"({inner})"
        symbol = _symbol(symbols["not"], _HTML_CLASS[Not], decorate)
        return _PRECEDENCE[Not], symbol + inner

    precedence = _PRECEDENCE[type(node)]
    right_associative = isinstance(node, Imp)
    left_precedence, left = _render(node.left, symbols, decorate, escape_vars)
    right_precedence, right = _render(node.right, symbols, decorate, escape_vars)
    if left_precedence < precedence or (left_precedence == precedence and right_associative):
        left = f"({left})"
    if right_precedence < precedence or (right_precedence == precedence and not right_associative):
        right = f"({right})"
    symbol = _symbol(symbols[_BINARY_STYLE_KEY[type(node)]], _HTML_CLASS[type(node)], decorate)
    return precedence, f"{left} {symbol} {right}"


def _symbol(symbol: str, html_class: str, decorate: Callable[[str, str], str] | None = None) -> str:
    """Ozdabia symbol operatora, jeśli podano funkcję ``decorate``."""
    if decorate is None:
        return symbol
    return decorate(symbol, html_class)


def to_text(node: Node, style: str = "wyklad") -> str:
    """Wypisuje drzewo jako tekst w stylu ``wyklad``, ``unicode``, ``ascii`` albo ``latex``.

    Domyślnie notacja z wykładu (``∼``, ``≡``). Nawiasy pojawiają się tylko tam,
    gdzie zmieniają sens formuły. Nieznany styl to ``FormulaError``.
    """
    symbols = _style(style)
    return _render(node, symbols)[1]


def to_html(node: Node, styl: str = "wyklad") -> str:
    """Wypisuje drzewo jako bezpieczny HTML w podanym stylu (domyślnie ``wyklad``).

    Każdy znak pochodzący z wejścia (nazwa zmiennej) jest escapowany, a operatory są
    opakowane w ``<span>`` z klasą operatora (``op-neg``, ``op-and``, ``op-or``,
    ``op-imp``, ``op-iff``). Wynik nadaje się do wstawienia przez ``|safe``.
    """
    symbols = _style(styl)

    def decorate(symbol: str, html_class: str) -> str:
        return f'<span class="{html_class}">{symbol}</span>'

    return _render(node, symbols, decorate, escape_vars=True)[1]


# ---------------------------------------------------------------------------
# Właściwości formuły
# ---------------------------------------------------------------------------


def variables(node: Node) -> list[str]:
    """Zwraca posortowane nazwy zmiennych bez powtórzeń."""
    names = {current.name for current in _walk(node) if isinstance(current, Var)}
    return sorted(names)


def evaluate(node: Node, env: Mapping[str, bool]) -> bool:
    """Liczy wartość formuły dla pełnego przypisania zmiennych.

    Brak wartości zmiennej w ``env`` to ``FormulaError``.
    Wartość zmiennej niebędąca typu ``bool`` to ``FormulaError``.
    """
    if isinstance(node, Var):
        if node.name not in env:
            raise FormulaError(f"Brakuje wartości zmiennej '{node.name}'.")
        val = env[node.name]
        if not isinstance(val, bool):
            raise FormulaError(
                f"Wartość zmiennej '{node.name}' musi być typu bool, "
                f"otrzymano {type(val).__name__}."
            )
        return val
    if isinstance(node, Not):
        return not evaluate(node.child, env)
    if isinstance(node, And):
        return evaluate(node.left, env) and evaluate(node.right, env)
    if isinstance(node, Or):
        return evaluate(node.left, env) or evaluate(node.right, env)
    if isinstance(node, Imp):
        return (not evaluate(node.left, env)) or evaluate(node.right, env)
    if isinstance(node, Iff):
        return evaluate(node.left, env) == evaluate(node.right, env)
    raise FormulaError(f"Nieznany węzeł formuły: {type(node).__name__}.")


def size(node: Node) -> int:
    """Zwraca liczbę wystąpień zmiennych (liści) w drzewie."""
    return sum(1 for current in _walk(node) if isinstance(current, Var))


def depth(node: Node) -> int:
    """Zwraca głębokość drzewa. Liść ma głębokość 1."""
    if isinstance(node, Var):
        return 1
    return 1 + max(depth(child) for child in _children(node))


def subformulas(node: Node) -> list[Node]:
    """Zwraca wszystkie podformuły bez powtórzeń, od najmniejszej.

    Wynik zawiera także całą formułę. Kolejność: rosnąca liczba liści; przy równej
    liczbie zachowana jest kolejność przejścia drzewa (dzieci przed rodzicem).
    """
    result: list[Node] = []
    seen: set[Node] = set()
    for current in _walk(node):
        if current not in seen:
            seen.add(current)
            result.append(current)
    return sorted(result, key=size)


def replace(node: Node, target: Node, replacement: Node) -> Node:
    """Podmienia każde poddrzewo równe ``target`` na ``replacement``."""
    if node == target:
        return replacement
    if isinstance(node, Var):
        return node
    if isinstance(node, Not):
        return Not(replace(node.child, target, replacement))
    left = replace(node.left, target, replacement)
    right = replace(node.right, target, replacement)
    # And, Or, Imp i Iff mają pola (left, right), więc konstruktor z type(node) pasuje.
    return type(node)(left, right)


#: Kolejność typów przy porządkowaniu stron (bierzemy ją pod uwagę w ``_order_key``).
_ORDER_RANK = {Var: 0, Not: 1, And: 2, Or: 3, Imp: 4, Iff: 5}


def _order_key(node: Node) -> tuple:
    """Klucz porządku drzew. Pierwsza liczba to typ, więc typy się nie mieszają."""
    if isinstance(node, Var):
        return (_ORDER_RANK[Var], node.name)
    if isinstance(node, Not):
        return (_ORDER_RANK[Not], _order_key(node.child))
    return (_ORDER_RANK[type(node)], _order_key(node.left), _order_key(node.right))


def normalize(node: Node) -> Node:
    """Porządkuje strony ``∧`` i ``∨`` w stałej kolejności.

    Pozostałe operatory zachowują kolejność argumentów, bo ona zmienia sens.
    """
    if isinstance(node, Var):
        return node
    if isinstance(node, Not):
        return Not(normalize(node.child))
    left = normalize(node.left)
    right = normalize(node.right)
    if isinstance(node, (And, Or)) and _order_key(right) < _order_key(left):
        left, right = right, left
    return type(node)(left, right)


def same(a: Node, b: Node) -> bool:
    """Sprawdza, czy drzewa są takie same po ``normalize``."""
    return normalize(a) == normalize(b)
