"""Lekcja druga kursu: ``/formuly`` — język rachunku zdań i wartościowanie.

Treść odwzorowuje wykład 1 („Logika pragmatyczna”, PWr): slajdy „Język rachunku zdań”,
„Formuły logiczne” i „Wartościowanie formuły”. Wzory zamienia na HTML
``app.logic.formula.to_html`` (karta PRZ-001), a wartości w tablicach liczy
``app.logic.formula.evaluate`` — dzięki temu na stronie nie ma wpisanych na sztywno
zer i jedynek, których nikt nie sprawdził. Ten sam moduł nie zakłada, że partial
tablicy prawdy jest już gotowy: wstawiamy go przez ``{% include %}``, więc brak
skryptu (karta PRZ-011) nie psuje treści lekcji.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any

from flask import Blueprint, render_template
from markupsafe import Markup, escape

from app.logic.formula import FormulaError, evaluate, parse, to_html

bp = Blueprint("formuly", __name__)

#: Zmienne tej lekcji — dwa i trzy, bo tyle mają wzory z wykładu.
ZMIENNE_PQ = ("p", "q")
ZMIENNE_PQR = ("p", "q", "r")

#: Pięć spójników z wykładu: (wzór, jak czytamy, nazwa).
SPOJNIKI: list[tuple[str, str, str]] = [
    ("∼p", "nieprawda, że p (nie p)", "negacja"),
    ("p ∧ q", "p i q", "koniunkcja"),
    ("p ∨ q", "p lub q", "alternatywa"),
    ("p → q", "jeżeli p, to q (z p wynika q)", "implikacja"),
    ("p ≡ q", "p wtedy i tylko wtedy, gdy q", "równoważność"),
]

#: Te same spójniki w notacji popularnej. Pokażemy je przez ``to_html(..., styl="unicode")``.
INNE_ZAPISY = ("∼p", "p ≡ q")

#: Przykłady formuł logicznych z wykładu — od najprostszej.
PRZYKLADY_FORMUL: list[str] = [
    "p",
    "q",
    "∼p",
    "p ∨ q",
    "p → q",
    "(p ∨ q) ∧ (p → q)",
    "∼((p ∨ q) ∧ (p → q)) ≡ p",
    "p ∨ q → r",
]

#: Formuła niejednoznaczna z wykładu: bez nawiasów nie wiadomo, co liczyć pierwsze.
FORMULA_NIEJEDNOZNACZNA = "p ∨ q → r"

#: Dwie wersje zapisu ``p ∨ q → r``. ``zapis`` to notacja z nawiasami (jak pisze
#: wykład), ``wzor`` — ten sam wzór dla parsera.
WERSJE_NAWIASOW: list[dict[str, str]] = [
    {
        "nazwa": "Wersja A",
        "zapis": "(p ∨ q) → r",
        "wzor": "p ∨ q → r",
        "opis": (
            "Nawias obejmuje alternatywę. Najpierw liczymy p ∨ q, a potem implikację. "
            "Bez nawiasu czytamy ten zapis tak samo: implikacja wiąże najsłabiej."
        ),
        "skrot": "A",
    },
    {
        "nazwa": "Wersja B",
        "zapis": "p ∨ (q → r)",
        "wzor": "p ∨ (q → r)",
        "opis": "Nawias obejmuje implikację. Najpierw liczymy q → r, a potem alternatywę.",
        "skrot": "B",
    },
]

#: Zdanie z wykładu (cytat dosłowny) i jego formalizacja.
ZDANIE_UCZENIE = (
    "Jeżeli uczyłem się, to zdam, i jeżeli zdam, to będę szczęśliwy; "
    "wynika z tego, że jeżeli nie będę szczęśliwy, to się nie uczyłem."
)

#: Podstawienie do zdania o uczeniu się: (zmienna, zdanie z języka polskiego).
PODSTAWIENIE_UCZENIE: list[tuple[str, str]] = [
    ("p", "uczyłem się"),
    ("q", "zdam"),
    ("r", "będę szczęśliwy"),
]

FORMALIZACJA_UCZENIE = "((p → q) ∧ (q → r)) → (∼r → ∼p)"

#: Przykład „formuła to nie zdanie”: wzór i podstawienie zwykłych zdań.
FORMULA_PODSTAWIENIA = "((p → q) ∧ ∼q) → ∼p"
PODSTAWIENIE_LICZBY: list[tuple[str, str]] = [("p", "3 > 2"), ("q", "3 > 1")]

#: Wartościowanie krok po kroku z wykładu i układ wartości z tego przykładu.
WARTOSCIOWANIE = "(p ∨ ∼q) → (r ∧ (p → q))"
UKLAD_WARTOSCIOWANIA: dict[str, bool] = {"p": True, "q": False, "r": True}

#: Formuła, którą pokaże partial tablicy prawdy (karta PRZ-011).
FORMULA_POKAZOWA = "p → q"


@dataclass(frozen=True)
class Kolumna:
    """Kolumna wynikowa tablicy prawdy.

    ``wzor`` to wzór, który liczymy i wypisujemy. ``nazwa`` to nazwa pomocnicza
    z wykładu (α, β, γ) — pokazujemy ją przed wzorem, np. ``α = p ∨ ∼q``.
    """

    wzor: str
    nazwa: str = ""


#: Kolumny pełnej tablicy spójników (punkt 8 wykładu).
KOLUMNY_SPOJNIKOW: list[Kolumna] = [
    Kolumna("∼p"),
    Kolumna("p ∧ q"),
    Kolumna("p ∨ q"),
    Kolumna("p → q"),
    Kolumna("p ≡ q"),
]

#: Kolumny tablicy wartościowania. α, β, γ to podformuły pomocnicze z wykładu,
#: a ostatnia kolumna to cała formuła, czyli α → γ.
KOLUMNY_WARTOSCIOWANIA: list[Kolumna] = [
    Kolumna("∼q"),
    Kolumna("p ∨ ∼q", nazwa="α"),
    Kolumna("p → q", nazwa="β"),
    Kolumna("r ∧ (p → q)", nazwa="γ"),
    Kolumna(WARTOSCIOWANIE),
]

#: Kolumny tablicy dla przykładu „formuła to nie zdanie”.
KOLUMNY_PODSTAWIENIA: list[Kolumna] = [
    Kolumna("p → q"),
    Kolumna("∼q"),
    Kolumna("(p → q) ∧ ∼q"),
    Kolumna("∼p"),
    Kolumna(FORMULA_PODSTAWIENIA),
]


def formula_to_html(text: str, styl: str = "wyklad") -> Markup:
    """Zwraca wzór jako bezpieczny HTML z ``formula.to_html``.

    Gdy napis nie jest poprawną formułą, zwracamy go jako tekst bez znaczników —
    treść lekcji nigdy nie kończy się błędem 500. Wynik wstawiamy w szablonie przez
    ``|safe``, tak samo jak ``app/blueprints/wstep.py`` i ``app/blueprints/laws.py``.
    """
    try:
        return Markup(to_html(parse(text), styl))
    except FormulaError:
        return escape(text)


def tabela_prawdy(
    kolumny: Sequence[Kolumna],
    zmienne: Sequence[str] = ZMIENNE_PQ,
    wartosciowania: Sequence[Mapping[str, bool]] | None = None,
) -> dict[str, Any]:
    """Liczy tablicę prawdy i zwraca ją gotową dla szablonu.

    Argumenty:
        kolumny: kolumny wynikowe w kolejności z wykładu.
        zmienne: kolumny wejściowe; domyślnie ``p`` i ``q``.
        wartosciowania: wybrane układy wartości (np. jeden wiersz z wykładu).
            Domyślnie liczymy wszystkie układy — dla dwóch zmiennych cztery.

    Zwraca słownik z kluczami ``zmienne``, ``kolumny`` i ``wiersze``. Każdy wiersz ma
    listę wartości zmiennych i listę wyników zapisanych jako ``"1"`` albo ``"0"``.
    """
    uklady = list(wartosciowania) if wartosciowania is not None else _uklady(zmienne)
    return {
        "zmienne": list(zmienne),
        "kolumny": [{"nazwa": kolumna.nazwa, "wzor": kolumna.wzor} for kolumna in kolumny],
        "wiersze": [
            {
                "zmienne": [_znak(uklad[nazwa]) for nazwa in zmienne],
                "wyniki": [_wartosc(kolumna.wzor, uklad) for kolumna in kolumny],
            }
            for uklad in uklady
        ],
    }


def _uklady(zmienne: Sequence[str]) -> list[dict[str, bool]]:
    """Wszystkie układy wartości zmiennych, od samych jedynek (p = 1, q = 1, …)."""
    return [
        dict(zip(zmienne, wartosci, strict=True))
        for wartosci in product((True, False), repeat=len(zmienne))
    ]


def _znak(wartosc: bool) -> str:
    """Zapisuje wartość logiczną tak, jak wykład: ``1`` (prawda) albo ``0`` (fałsz)."""
    return "1" if wartosc else "0"


def _wartosc(wzor: str, uklad: Mapping[str, bool]) -> str:
    """Liczy wartość wzoru dla układu wartości i zapisuje ją jako ``1`` albo ``0``."""
    return _znak(evaluate(parse(wzor), uklad))


def _wersje_nawiasow() -> list[dict[str, Any]]:
    """Dwie wersje niejednoznacznego zapisu razem z ich pełnymi tablicami prawdy."""
    return [
        {**wersja, "tabela": tabela_prawdy([Kolumna(wersja["wzor"])], ZMIENNE_PQR)}
        for wersja in WERSJE_NAWIASOW
    ]


def _rozne_wiersze(wersje: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Wiersze, w których obie wersje dają inny wynik.

    Bez tego przykładu uczeń nie widzi, że nawias zmienia sens: obie tablice trzeba
    porównać wiersz po wierszu.
    """
    pierwsza, druga = (wersja["tabela"]["wiersze"] for wersja in wersje)
    return [
        {
            **dict(zip(ZMIENNE_PQR, wiersz_a["zmienne"], strict=True)),
            "wersja_a": wiersz_a["wyniki"][0],
            "wersja_b": wiersz_b["wyniki"][0],
        }
        for wiersz_a, wiersz_b in zip(pierwsza, druga, strict=True)
        if wiersz_a["wyniki"] != wiersz_b["wyniki"]
    ]


def _wynik_wartosciowania() -> str:
    """Wynik formuły wartościowania dla układu z wykładu (jeden wiersz)."""
    tabela = tabela_prawdy(KOLUMNY_WARTOSCIOWANIA, ZMIENNE_PQR, [UKLAD_WARTOSCIOWANIA])
    return tabela["wiersze"][0]["wyniki"][-1]


def _wynik_podstawienia() -> str:
    """Wynik formuły po podstawieniu zdań prawdziwych (jeden wiersz)."""
    tabela = tabela_prawdy(KOLUMNY_PODSTAWIENIA, ZMIENNE_PQ, [{"p": True, "q": True}])
    return tabela["wiersze"][0]["wyniki"][-1]


@bp.get("/formuly")
def formuly():
    """Lekcja: zmienne zdaniowe, spójniki, definicja formuły i wartościowanie."""
    wersje = _wersje_nawiasow()
    return render_template(
        "formuly.html",
        formula_to_html=formula_to_html,
        spojniki=SPOJNIKI,
        inne_zapisy=INNE_ZAPISY,
        przyklady_formul=PRZYKLADY_FORMUL,
        formula_niejednoznaczna=FORMULA_NIEJEDNOZNACZNA,
        wersje_nawiasow=wersje,
        rozne_wiersze=_rozne_wiersze(wersje),
        liczba_ukladow=len(wersje[0]["tabela"]["wiersze"]),
        zdanie_uczenie=ZDANIE_UCZENIE,
        podstawienie_uczenie=PODSTAWIENIE_UCZENIE,
        formalizacja=FORMALIZACJA_UCZENIE,
        formula_podstawienia=FORMULA_PODSTAWIENIA,
        podstawienie_liczby=PODSTAWIENIE_LICZBY,
        tabela_podstawienia=tabela_prawdy(
            KOLUMNY_PODSTAWIENIA, ZMIENNE_PQ, [{"p": True, "q": True}]
        ),
        wynik_podstawienia=_wynik_podstawienia(),
        wartosciowanie=WARTOSCIOWANIE,
        uklad_wartosciowania=UKLAD_WARTOSCIOWANIA,
        tabela_wartosciowania=tabela_prawdy(
            KOLUMNY_WARTOSCIOWANIA, ZMIENNE_PQR, [UKLAD_WARTOSCIOWANIA]
        ),
        wynik_wartosciowania=_wynik_wartosciowania(),
        tabela_spojnikow=tabela_prawdy(KOLUMNY_SPOJNIKOW, ZMIENNE_PQ),
        #: Partial tablicy prawdy (karta PRZ-011) czyta zmienną ``formula``.
        formula=FORMULA_POKAZOWA,
    )
