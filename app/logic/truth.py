"""Tablice prawdy, klasyfikacja formuł i równoważność.

Moduł liczy tablicę prawdy dla formuły z :mod:`app.logic.formula`, nazywa wynik
(tautologia, kontrtautologię albo formułę spełnialną) i porównuje dwie formuły.

Granica: tablica i porównywanie obsługują **najwyżej 6 zmiennych** (64 wiersze).
Więcej to ``FormulaError`` — bez tej granicy formuła od użytkownika kazałaby
serwerowi policzyć miliony wierszy.

Wartości w wierszach to ``True``/``False`` (gotowe na JSON). Tylko
:func:`markdown_table` wypisuje je jako ``1``/``0``, zgodnie z notacją wykładu.

Wiersze idą od wszystkich jedynek do wszystkich zer, a pierwsza zmienna zmienia się
najrzadziej — tak jak w tabelach z wykładu.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from dataclasses import dataclass

from app.logic.formula import FormulaError, Node, evaluate, subformulas, to_text, variables

#: Największa liczba zmiennych, dla której liczymy tablicę prawdy.
MAX_VARIABLES = 6

#: Nazwa pola na wyniki w wierszu. Nie może być zarazem nazwą zmiennej.
_VALUES_FIELD = "values"

_TAUTOLOGY = "tautologia"
_CONTRADICTION = "kontrtautologia"
_SATISFIABLE = "spełnialna"


@dataclass(frozen=True)
class TruthTable:
    """Policzona tablica prawdy.

    ``rows`` to lista słowników ``{"p": True, "q": False, "values": [True, False]}``:
    wartościowanie zmiennych pod ich nazwami, a pod ``values`` — wynik każdej kolumny.
    """

    variables: list[str]
    columns: list[str]
    rows: list[dict]
    classification: str

    def to_dict(self) -> dict:
        """Zwraca dane gotowe na JSON (listy i słowniki Pythona)."""
        return {
            "variables": list(self.variables),
            "columns": list(self.columns),
            "rows": [dict(row) for row in self.rows],
            "classification": self.classification,
        }


def _valid_names(names: list[str]) -> list[str]:
    """Sprawdza nazwy zmiennych: granica 6 zmiennych i nazwa zarezerwowana."""
    if _VALUES_FIELD in names:
        raise FormulaError(
            f"Nazwa zmiennej '{_VALUES_FIELD}' jest zarezerwowana: pod nią trzymamy wynik "
            "formuły w wierszu tablicy prawdy."
        )
    if len(names) > MAX_VARIABLES:
        raise FormulaError(
            f"Jest {len(names)} zmiennych — tablica prawdy i porównywanie obsługują najwyżej "
            f"{MAX_VARIABLES} (czyli {2**MAX_VARIABLES} wierszy)."
        )
    return names


def _checked_variables(node: Node) -> list[str]:
    """Nazwy zmiennych formuły, sprawdzone pod kątem granicy i nazwy zarezerwowanej."""
    return _valid_names(variables(node))


def _environments(names: list[str]) -> Iterator[dict[str, bool]]:
    """Kolejne wartościowania: od samych jedynek, pierwsza zmienna zmienia się najrzadziej."""
    for values in itertools.product((True, False), repeat=len(names)):
        yield dict(zip(names, values, strict=True))


def _name(values: list[bool]) -> str:
    """Nazywa formułę po wynikach wszystkich wierszy."""
    if all(values):
        return _TAUTOLOGY
    if not any(values):
        return _CONTRADICTION
    return _SATISFIABLE


def build(node: Node, with_subformulas: bool = True) -> TruthTable:
    """Liczy tablicę prawdy formuły.

    ``with_subformulas=True`` daje kolumnę na każdą podformułę (od najmniejszej do całej
    formuły). ``False`` daje jedną kolumnę z całą formułą.
    """
    names = _checked_variables(node)
    parts = subformulas(node) if with_subformulas else [node]
    columns = [to_text(part) for part in parts]

    rows: list[dict] = []
    whole: list[bool] = []
    for env in _environments(names):
        whole.append(evaluate(node, env))
        rows.append({**env, _VALUES_FIELD: [evaluate(part, env) for part in parts]})

    return TruthTable(
        variables=list(names),
        columns=columns,
        rows=rows,
        classification=_name(whole),
    )


def classify(node: Node) -> str:
    """Nazywa formułę: ``"tautologia"``, ``"kontrtautologia"`` albo ``"spełnialna"``."""
    names = _checked_variables(node)
    return _name([evaluate(node, env) for env in _environments(names)])


def is_tautology(node: Node) -> bool:
    """Czy formuła jest prawdziwa przy każdym wartościowaniu."""
    return classify(node) == _TAUTOLOGY


def is_contradiction(node: Node) -> bool:
    """Czy formuła jest fałszywa przy każdym wartościowaniu."""
    return classify(node) == _CONTRADICTION


def counterexample(a: Node, b: Node) -> dict[str, bool] | None:
    """Pierwsze wartościowanie, przy którym formuły różnią się wynikiem.

    Zwraca ``None``, gdy formuły są równoważne.
    """
    names = _valid_names(sorted(set(variables(a)) | set(variables(b))))
    for env in _environments(names):
        if evaluate(a, env) != evaluate(b, env):
            return env
    return None


def equivalent(a: Node, b: Node) -> bool:
    """Czy formuły mają ten sam wynik przy każdym wartościowaniu."""
    return counterexample(a, b) is None


def markdown_table(table: TruthTable) -> str:
    """Wypisuje tablicę jako tabelę Markdown (wartości jako ``1`` i ``0``)."""
    header = [*table.variables, *table.columns]
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
    ]
    for row in table.rows:
        cells = [str(int(row[nazwa])) for nazwa in table.variables]
        cells += [str(int(wartosc)) for wartosc in row[_VALUES_FIELD]]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
