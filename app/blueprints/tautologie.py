"""Lekcja trzecia kursu: ``/tautologie`` — definicja tautologii i metoda skrócona.

Treść odwzorowuje wykład 1 („Logika pragmatyczna”, PWr): slajdy „Tautologie rachunku
zdań” i „Tautologie”. Wzory zamienia na HTML ``app.logic.formula.to_html``, a wartości
w tablicach liczy ``app.logic.formula.evaluate`` — dzięki temu na stronie nie ma
wpisanych na sztywno zer i jedynek, których nikt nie sprawdził.

Spis T1–T14 powstaje z rejestru praw (``app.logic.laws.all_laws``), więc numeracja
i nazwy nie rozjadą się z treścią praw.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any

from flask import Blueprint, render_template
from markupsafe import Markup, escape

from app.logic.formula import And, FormulaError, Imp, Node, Not, Var, evaluate, parse, to_html
from app.logic.law_model import Law
from app.logic.laws import all_laws

bp = Blueprint("tautologie", __name__)

#: Zmienne tablic tej lekcji — jedna, dwie i trzy, bo tyle mają wzory z wykładu.
ZMIENNE_P = ("p",)
ZMIENNE_PQ = ("p", "q")
ZMIENNE_PQR = ("p", "q", "r")

#: Prawo wyłączonego środka — najprostsza tautologia (punkt 2 wykładu).
WYLACZONY_SRODEK = "p ∨ ∼p"

#: Formuła dowodzona pełną tablicą (punkt 3 wykładu).
FORMULA_DOWODU = "((p → q) ∧ ∼q) → ∼p"

#: Podformuła α z dowodu, czyli ``α = (p → q) ∧ ∼q``.
ALFA_DOWODU = "(p → q) ∧ ∼q"

#: Formuła sprawdzana metodą skróconą (punkt 4 wykładu).
FORMULA_METODY = "((p → q) ∧ (q → r)) → (∼r → ∼p)"

#: Poprzednik i następnik formuły z metody skróconej: γ = α ∧ β oraz δ = ∼r → ∼p.
POPRZEDNIK_METODY = "(p → q) ∧ (q → r)"
NASTEPNIK_METODY = "∼r → ∼p"

#: Kategoria praw spoza spisu T1–T14 — wykład nie nadaje im numeru.
KATEGORIA_DODATKOWE = "dodatkowe"

#: Nagłówki skrócone z wykładu, w których litery α, β, γ, δ są nazwami podformuł,
#: a nie zmiennymi zdaniowymi. Parser przyjmuje tylko litery ASCII, więc drzewo
#: budujemy wprost: ``to_html`` rysuje każdy ``Var`` po nazwie, więc te nagłówki
#: idą tą samą drogą co zwykłe wzory.
NASTEPNIK_ALFA: Node = Imp(Var("α"), Not(Var("p")))
POPRZEDNIK_GAMMA: Node = And(Var("α"), Var("β"))
FORMULA_GAMMA_DELTA: Node = Imp(Var("γ"), Var("δ"))


@dataclass(frozen=True)
class Kolumna:
    """Kolumna tablicy prawdy.

    ``wzor`` to wzór, którego wartości liczymy. ``nazwa`` to nazwa pomocnicza
    z wykładu (α, β, γ, δ) — nagłówek pokaże ją przed wzorem, np. ``α = p → q``.
    ``naglowek`` podstawia drzewo rysowane zamiast ``wzor``; potrzebne tam, gdzie
    wykład pisze nagłówek skrótem (``α → ∼p``), bo wtedy sam wzór nie wystarcza.
    """

    wzor: str
    nazwa: str = ""
    naglowek: Node | None = None


#: Kolumny tablicy prawa wyłączonego środka — dwie, dokładnie jak na wykładzie.
KOLUMNY_SRODKA: list[Kolumna] = [
    Kolumna("∼p"),
    Kolumna(WYLACZONY_SRODEK),
]

#: Kolumny pełnej tablicy dowodu — siedem, dokładnie jak na wykładzie.
KOLUMNY_DOWODU: list[Kolumna] = [
    Kolumna("p → q"),
    Kolumna("∼q"),
    Kolumna(ALFA_DOWODU, nazwa="α"),
    Kolumna("∼p"),
    Kolumna(FORMULA_DOWODU, naglowek=NASTEPNIK_ALFA),
]

#: Kolumny tablicy metody skróconej — osiem, dokładnie jak na wykładzie.
KOLUMNY_METODY: list[Kolumna] = [
    Kolumna("p → q", nazwa="α"),
    Kolumna("q → r", nazwa="β"),
    Kolumna(POPRZEDNIK_METODY, nazwa="γ", naglowek=POPRZEDNIK_GAMMA),
    Kolumna(NASTEPNIK_METODY, nazwa="δ"),
    Kolumna(FORMULA_METODY, naglowek=FORMULA_GAMMA_DELTA),
]

#: Wiersze dowodu w kolejności z wykładu: od p = 0 i q = 0.
UKLADY_DOWODU: list[dict[str, bool]] = [
    {"p": False, "q": False},
    {"p": False, "q": True},
    {"p": True, "q": False},
    {"p": True, "q": True},
]

#: Dwa przypadki, które zostają po metodzie skróconej. Następnik δ jest fałszywy
#: tylko dla r = 0 i p = 1, więc zmienna q może być jedynką albo zerem.
UKLADY_METODY: list[dict[str, bool]] = [
    {"p": True, "q": True, "r": False},
    {"p": True, "q": False, "r": False},
]

#: Cztery kroki rozumowania z metody skróconej. ``wzor`` to formuła, którą rysuje
#: ``to_html``; krok bez wzoru to sam wniosek słowny.
KROKI_METODY: list[dict[str, str]] = [
    {
        "wzor": "",
        "opis": (
            "Implikacja jest fałszywa tylko wtedy, gdy poprzednik jest prawdziwy, "
            "a następnik fałszywy."
        ),
    },
    {
        "wzor": FORMULA_METODY,
        "opis": "Cała formuła może więc być fałszywa tylko wtedy, gdy fałszywy jest jej następnik.",
    },
    {
        "wzor": NASTEPNIK_METODY,
        "opis": "Następnik jest fałszywy dokładnie dla r = 0 i p = 1.",
    },
    {
        "wzor": "",
        "opis": "Zostają więc dwa przypadki: q = 1 oraz q = 0. Liczymy je w tabeli niżej.",
    },
]


def formula_to_html(text: str, styl: str = "wyklad") -> Markup:
    """Zwraca wzór jako bezpieczny HTML z ``formula.to_html``.

    Gdy napis nie jest poprawną formułą, oddajemy go jako zwykły tekst — treść
    lekcji nigdy nie kończy się błędem 500. Wynik wstawiamy w szablonie przez
    ``|safe``, tak samo jak ``app/blueprints/formuly.py`` i ``wstep.py``.
    """
    try:
        return Markup(to_html(parse(text), styl))
    except FormulaError:
        return escape(text)


def naglowek_to_html(kolumna: Mapping[str, Any]) -> Markup:
    """Nagłówek kolumny tablicy: nazwa z wykładu i wzór z ``formula.to_html``.

    ``kolumna["naglowek"]`` to drzewo pokazywane zamiast ``kolumna["wzor"]`` —
    potrzebne przy nagłówkach skróconych (``α → ∼p``), których parser nie przyjmie.
    """
    wzor = kolumna["naglowek"] or parse(kolumna["wzor"])
    czesci = [escape(f"{kolumna['nazwa']} = ")] if kolumna["nazwa"] else []
    czesci.append(Markup(to_html(wzor)))
    return Markup("").join(czesci)


def tabela_prawdy(
    kolumny: Sequence[Kolumna],
    zmienne: Sequence[str] = ZMIENNE_PQ,
    wartosciowania: Sequence[Mapping[str, bool]] | None = None,
) -> dict[str, Any]:
    """Liczy tablicę prawdy i zwraca ją gotową dla szablonu.

    Argumenty:
        kolumny: kolumny wynikowe w kolejności z wykładu.
        zmienne: kolumny wejściowe; domyślnie ``p`` i ``q``.
        wartosciowania: wybrane układy wartości (np. dwa przypadki z wykładu).
            Domyślnie liczymy wszystkie układy — dla dwóch zmiennych cztery.

    Zwraca słownik z kluczami ``zmienne``, ``kolumny`` i ``wiersze``. Każdy wiersz
    ma listę wartości zmiennych i listę wyników zapisanych jako ``"1"`` (prawda)
    albo ``"0"`` (fałsz), tak jak wykład.
    """
    uklady = list(wartosciowania) if wartosciowania is not None else _wszystkie_uklady(zmienne)
    return {
        "zmienne": list(zmienne),
        "kolumny": [
            {"wzor": kolumna.wzor, "nazwa": kolumna.nazwa, "naglowek": kolumna.naglowek}
            for kolumna in kolumny
        ],
        "wiersze": [
            {
                "zmienne": [_znak(uklad[nazwa]) for nazwa in zmienne],
                "wyniki": [_wartosc(kolumna.wzor, uklad) for kolumna in kolumny],
            }
            for uklad in uklady
        ],
    }


def wniosek_tautologii(tabela: Mapping[str, Any]) -> str:
    """Zdanie podsumowujące tablicę: czy ostatnia kolumna to same jedynki.

    Liczymy je z tablicy, więc wniosek na stronie nie może rozjechać się z jej
    zawartością.
    """
    wszystkie = len(tabela["wiersze"])
    jedynki = sum(1 for wiersz in tabela["wiersze"] if wiersz["wyniki"][-1] == "1")
    if wszystkie and jedynki == wszystkie:
        return (
            f"Ostatnia kolumna ma same jedynki, w każdym z {wszystkie} wierszy jest 1. "
            "Formuła jest więc tautologią."
        )
    return (
        f"Ostatnia kolumna nie ma samych jedynek, jedynka stoi tylko w {jedynki} "
        f"z {wszystkie} wierszy. Formuła nie jest tautologią."
    )


def prawa_spisu() -> list[Law]:
    """Prawa spisu T1–T14: wszystko poza kategorią ``dodatkowe``, w kolejności nauki."""
    return [prawo for prawo in all_laws() if prawo.kategoria != KATEGORIA_DODATKOWE]


def prawa_dodatkowe() -> list[Law]:
    """Prawa z kategorii ``dodatkowe`` — wykład nie nadaje im numeru ``T``."""
    return [prawo for prawo in all_laws() if prawo.kategoria == KATEGORIA_DODATKOWE]


def tabela_tautologii() -> list[dict[str, str]]:
    """Wiersze T1–T14 z rejestru praw: numer, wzór i nazwa z odnośnikiem.

    Numer nadajemy po kolei prawom spoza kategorii ``dodatkowe``. Kolejność pilnuje
    pole ``kolejnosc`` modułów treści, po którym sortuje ``all_laws()``, więc spis
    na stronie nie rozjedzie się z treścią praw.
    """
    return [
        {
            "numer": f"T{numer}",
            "formula": prawo.formula,
            "nazwa": prawo.nazwa,
            "slug": prawo.slug,
        }
        for numer, prawo in enumerate(prawa_spisu(), start=1)
    ]


def _wszystkie_uklady(zmienne: Sequence[str]) -> list[dict[str, bool]]:
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


@bp.get("/tautologie")
def tautologie():
    """Lekcja: definicja tautologii, dowód pełną tablicą i metoda skrócona."""
    tabela_srodka = tabela_prawdy(KOLUMNY_SRODKA, ZMIENNE_P)
    tabela_dowodu = tabela_prawdy(KOLUMNY_DOWODU, ZMIENNE_PQ, UKLADY_DOWODU)
    tabela_metody = tabela_prawdy(KOLUMNY_METODY, ZMIENNE_PQR, UKLADY_METODY)
    return render_template(
        "tautologie.html",
        formula_to_html=formula_to_html,
        naglowek_to_html=naglowek_to_html,
        wylaczony_srodek=WYLACZONY_SRODEK,
        tabela_srodka=tabela_srodka,
        wniosek_srodka=wniosek_tautologii(tabela_srodka),
        formula_dowodu=FORMULA_DOWODU,
        tabela_dowodu=tabela_dowodu,
        wniosek_dowodu=wniosek_tautologii(tabela_dowodu),
        formula_metody=FORMULA_METODY,
        kroki_metody=KROKI_METODY,
        tabela_metody=tabela_metody,
        wniosek_metody=wniosek_tautologii(tabela_metody),
        tautologie=tabela_tautologii(),
        prawa_dodatkowe=prawa_dodatkowe(),
        #: Partial tablicy prawdy (karta PRZ-011) czyta zmienną ``formula``.
        formula=FORMULA_DOWODU,
    )
