"""Lekcja trzecia kursu: ``/tautologie`` — definicja tautologii i metoda skrócona.

Treść odwzorowuje wykład 1 („Logika pragmatyczna”, PWr): slajdy „Tautologie rachunku
zdań” i „Tautologie”. Wzory zamienia na HTML ``app.logic.formula.to_html``, a wartości
w tablicach liczy ``app.logic.formula.evaluate`` — dzięki temu na stronie nie ma
wpisanych na sztywno zer i jedynek, których nikt nie sprawdził.

Spis T1–T14 powstaje z rejestru praw (``app.logic.laws.all_laws``), więc numeracja
i nazwy nie rozjadą się z treścią praw.

Moduł buduje też **kroki dowodów** (karta PRZ-076): ``zbuduj_kroki_dowodu`` i
``zbuduj_kroki_metody`` zwracają listy słowników, które szablon wstawia do atrybutu
``data-kroki`` jako JSON. Jeden krok to:

``tytul``
    krótki napis do paska kroków („Krok 2. Kolumna p → q”).
``opis``
    zdanie po polsku pod tablicą — mówi, co się właśnie liczy.
``kolumny``
    numery kolumn widocznych w tym kroku, liczone od zera.
``wiersze``
    numery wierszy widocznych i czynnych. Numer równy liczbie wierszy tablicy
    oznacza wiersz podsumowania (stopkę); dodaje go ostatni krok dowodu.
``odrzucone``
    numery wierszy odrzuconych: zostają na stronie, ale gasną (metoda skrócona).
``strzalki``
    lista strzałek ``{"od": [...], "do": [...], "opis": ..., "jednostka": ...}``
    rysowanych nad tablicą. ``jednostka`` to ``"kolumna"`` (numery kolumn) albo
    ``"wiersz"`` (numery wierszy — strzałka „zawężenie”).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any

from flask import Blueprint, render_template
from markupsafe import Markup, escape

from app.logic.formula import (
    And,
    FormulaError,
    Iff,
    Imp,
    Node,
    Not,
    Or,
    Var,
    evaluate,
    parse,
    to_html,
    to_text,
)
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


#: Rodzaj jednostki w strzałce kroku: kolumna tablicy albo wiersz tablicy.
JEDNOSTKA_KOLUMNY = "kolumna"
JEDNOSTKA_WIERSZA = "wiersz"


@dataclass(frozen=True)
class Kolumna:
    """Kolumna tablicy prawdy.

    ``wzor`` to wzór, którego wartości liczymy. ``nazwa`` to nazwa pomocnicza
    z wykładu (α, β, γ, δ) — nagłówek pokaże ją przed wzorem, np. ``α = p → q``.
    ``naglowek`` podstawia drzewo rysowane zamiast ``wzor``; potrzebne tam, gdzie
    wykład pisze nagłówek skrótem (``α → ∼p``), bo wtedy sam wzór nie wystarcza.
    ``zrodla`` to numery kolumn, z których liczy się ta kolumna (w pełnej tablicy,
    razem z kolumnami zmiennych), a ``operacja`` — jej nazwa po polsku. Z tego
    powstają strzałki i opisy kroków (karta PRZ-076).
    """

    wzor: str
    nazwa: str = ""
    naglowek: Node | None = None
    zrodla: tuple[int, ...] = ()
    operacja: str = ""


#: Kolumny tablicy prawa wyłączonego środka — dwie, dokładnie jak na wykładzie.
KOLUMNY_SRODKA: list[Kolumna] = [
    Kolumna("∼p"),
    Kolumna(WYLACZONY_SRODEK),
]

#: Kolumny pełnej tablicy dowodu — siedem, dokładnie jak na wykładzie. Numery
#: w ``zrodla`` liczymy w pełnej tablicy: 0 i 1 to zmienne p i q, dalej kolumny
#: wynikowe w kolejności z listy. Z tych kolumn powstają strzałki kroków.
KOLUMNY_DOWODU: list[Kolumna] = [
    Kolumna("p → q", zrodla=(0, 1), operacja="implikacja"),
    Kolumna("∼q", zrodla=(1,), operacja="negacja"),
    Kolumna(ALFA_DOWODU, nazwa="α", zrodla=(2, 3), operacja="koniunkcja"),
    Kolumna("∼p", zrodla=(0,), operacja="negacja"),
    Kolumna(FORMULA_DOWODU, naglowek=NASTEPNIK_ALFA, zrodla=(4, 5), operacja="implikacja"),
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


def zbuduj_kroki_dowodu(tabela: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Kroki dowodu pełną tablicą: odsłanianie kolumn od lewej do prawej.

    Krok pierwszy pokazuje tylko kolumny zmiennych. Każdy następny odsłania jedną
    kolumnę wynikową i podaje strzałkę: z których kolumn liczy się nowa kolumna
    i jaką operacją. Ostatni krok dodaje wiersz podsumowania (w ``wiersze`` ma numer
    równy liczbie wierszy tablicy). Liczba kroków równa się liczbie kolumn tablicy:
    krok pierwszy to kolumny zmiennych, pięć kolejnych to kolumny wynikowe,
    a siódmy to wniosek.
    """
    zmienne = list(tabela["zmienne"])
    liczba_wierszy = len(tabela["wiersze"])
    kroki: list[dict[str, Any]] = [
        {
            "tytul": "Krok 1. Same zmienne",
            "opis": (
                f"Na starcie widzisz tylko kolumny {_wymien(zmienne)}. "
                "Kolejne kroki odsłaniają kolumny wynikowe od lewej do prawej."
            ),
            "kolumny": list(range(len(zmienne))),
            "strzalki": [],
            "wiersze": list(range(liczba_wierszy)),
            "odrzucone": [],
        }
    ]
    for numer, kolumna in enumerate(KOLUMNY_DOWODU, start=2):
        indeks = len(zmienne) + numer - 2
        kroki.append(
            {
                "tytul": f"Krok {numer}. Kolumna {_etykieta_kolumny(tabela, indeks)}",
                "opis": _opis_kolumny(tabela, kolumna, indeks),
                "kolumny": list(range(indeks + 1)),
                "strzalki": [_strzalka(kolumna.zrodla, (indeks,), kolumna.operacja)],
                "wiersze": list(range(liczba_wierszy)),
                "odrzucone": [],
            }
        )
    kroki.append(
        {
            "tytul": f"Krok {len(kroki) + 1}. Wniosek",
            "opis": _wniosek_dowodu(tabela),
            "kolumny": list(range(len(tabela["kolumny"]) + len(zmienne))),
            "strzalki": [],
            #: Ostatni numer (równy liczbie wierszy) to wiersz podsumowania ze stopki.
            "wiersze": [*range(liczba_wierszy), liczba_wierszy],
            "odrzucone": [],
        }
    )
    return kroki


def zbuduj_kroki_metody(tabela: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Kroki metody skróconej: cała tablica, gaszenie wierszy, dwa przypadki, wniosek.

    Metoda liczy tylko wiersze, w których formuła **może** być fałszywa — czyli te,
    w których następnik δ jest fałszywy (``_wiersze_zostawione``). Pozostałe wiersze
    krok drugi gasi (zostają widoczne, ale zgaszone), a krok trzeci je ukrywa.
    """
    zmienne = list(tabela["zmienne"])
    wszystkie_kolumny = list(range(len(zmienne) + len(tabela["kolumny"])))
    liczba_wierszy = len(tabela["wiersze"])
    zostawione = _wiersze_zostawione(tabela)
    odrzucone = _wiersze_odrzucone(tabela)
    nastepnik = to_text(parse(NASTEPNIK_METODY))
    nazwy_kolumn = _wymien([kolumna["nazwa"] for kolumna in tabela["kolumny"] if kolumna["nazwa"]])
    wynik = to_text(parse(FORMULA_METODY))
    zwezenie = _strzalka(odrzucone, zostawione, "zawężenie", jednostka=JEDNOSTKA_WIERSZA)
    return [
        {
            "tytul": "Krok 1. Cała tabela",
            "opis": (
                f"Trzy zmienne to {liczba_wierszy} wierszy. Wypisujemy wszystkie wartościowania."
            ),
            "kolumny": wszystkie_kolumny,
            "strzalki": [],
            "wiersze": list(range(liczba_wierszy)),
            "odrzucone": [],
        },
        {
            "tytul": "Krok 2. Odrzucamy wiersze bez szans",
            "opis": (
                f"Zostają tylko przypadki, w których {nastepnik} jest fałszywa: "
                f"{_warunki(tabela, zostawione)}"
            ),
            "kolumny": wszystkie_kolumny,
            "strzalki": [zwezenie],
            "wiersze": zostawione,
            "odrzucone": odrzucone,
        },
        {
            #: Metoda dla tej formuły zostawia dokładnie dwa przypadki (r = 0 i p = 1).
            "tytul": "Krok 3. Dwa przypadki",
            "opis": (
                f"Zostają dwa wiersze: {_przypadki(tabela, zostawione)}. "
                f"Liczymy w nich kolumny {nazwy_kolumn} oraz wynik {wynik}."
            ),
            "kolumny": wszystkie_kolumny,
            "strzalki": [zwezenie],
            "wiersze": zostawione,
            "odrzucone": [],
        },
        {
            "tytul": "Krok 4. Wniosek",
            "opis": _wniosek_metody(tabela),
            "kolumny": wszystkie_kolumny,
            "strzalki": [],
            "wiersze": zostawione,
            "odrzucone": [],
        },
    ]


def tabela_bez_odrzuconych(tabela: Mapping[str, Any]) -> dict[str, Any]:
    """Tablica bez wierszy, w których formuła nie może być fałszywa.

    Metoda skrócona liczy tylko przypadki, w których następnik δ jest fałszywy.
    W pozostałych wierszach implikacja γ → δ jest prawdziwa, więc nic nie wnoszą.
    """
    zostawione = set(_wiersze_zostawione(tabela))
    return {
        **tabela,
        "wiersze": [
            wiersz for numer, wiersz in enumerate(tabela["wiersze"]) if numer in zostawione
        ],
    }


def kroki_json(kroki: Sequence[Mapping[str, Any]]) -> str:
    """Kroki jako JSON do atrybutu ``data-kroki``.

    Znaki narodowe zostają bez zmian — strona jest w UTF-8, a atrybut escapuje Jinja.
    """
    return json.dumps(list(kroki), ensure_ascii=False)


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


def _wymien(elementy: Sequence[str]) -> str:
    """Wypisuje elementy po polsku: ``p``, ``p i q``, ``p, q i r``."""
    if len(elementy) <= 1:
        return elementy[0] if elementy else ""
    return f"{', '.join(elementy[:-1])} i {elementy[-1]}"


def _etykieta_kolumny(tabela: Mapping[str, Any], indeks: int) -> str:
    """Nazwa kolumny pełnej tablicy: zmienna (``p``), nazwa z wykładu (``α``)
    albo wzór — skrót z nagłówka, gdy wykład pisze kolumnę skrótem (``α → ∼p``).

    Numery kolumn liczymy w pełnej tablicy, razem z kolumnami zmiennych.
    """
    kolumny_zmiennych = len(tabela["zmienne"])
    if indeks < kolumny_zmiennych:
        return tabela["zmienne"][indeks]
    kolumna = tabela["kolumny"][indeks - kolumny_zmiennych]
    if kolumna["nazwa"]:
        return kolumna["nazwa"]
    if kolumna["naglowek"] is not None:
        return to_text(kolumna["naglowek"])
    return kolumna["wzor"]


def _wartosc_kolumny(tabela: Mapping[str, Any], indeks: int, numer: int) -> str:
    """Wartość kolumny pełnej tablicy w wierszu o danym numerze (``1`` albo ``0``)."""
    wiersz = tabela["wiersze"][numer]
    kolumny_zmiennych = len(tabela["zmienne"])
    if indeks < kolumny_zmiennych:
        return wiersz["zmienne"][indeks]
    return wiersz["wyniki"][indeks - kolumny_zmiennych]


def _nawias(tabela: Mapping[str, Any], indeks: int) -> str:
    """Nazwa kolumny w opisie operacji; wzór złożony dostaje nawiasy.

    Nazwy z wykładu (α, β, γ, δ) zostają bez nawiasów — wykład traktuje je jak
    litery, a nie jak złożone wzory.
    """
    kolumny_zmiennych = len(tabela["zmienne"])
    if indeks < kolumny_zmiennych:
        return tabela["zmienne"][indeks]
    kolumna = tabela["kolumny"][indeks - kolumny_zmiennych]
    if kolumna["nazwa"]:
        return kolumna["nazwa"]
    if isinstance(parse(kolumna["wzor"]), (And, Or, Imp, Iff)):
        return f"({kolumna['wzor']})"
    return kolumna["wzor"]


def _opis_operacji(tabela: Mapping[str, Any], kolumna: Kolumna) -> str:
    """Opis operacji kroku: „koniunkcja (p → q) i ∼q” albo „negacja kolumny q”."""
    if len(kolumna.zrodla) == 1:
        return f"{kolumna.operacja} kolumny {_nawias(tabela, kolumna.zrodla[0])}"
    return f"{kolumna.operacja} {_wymien([_nawias(tabela, indeks) for indeks in kolumna.zrodla])}"


def _wiersz_opisu(tabela: Mapping[str, Any], kolumna: Kolumna) -> int:
    """Numer wiersza, którego rachunek pokazuje opis kroku.

    Bierzemy pierwszy wiersz, w którym pierwsza kolumna źródłowa ma 0 — tak wykład
    pokazuje α w wierszu trzecim (0 ∧ 1 = 0). Gdy takiego wiersza nie ma, bierzemy
    pierwszy wiersz tablicy.
    """
    pierwsza = kolumna.zrodla[0]
    for numer in range(len(tabela["wiersze"])):
        if _wartosc_kolumny(tabela, pierwsza, numer) == "0":
            return numer
    return 0


def _rachunek(tabela: Mapping[str, Any], kolumna: Kolumna, numer: int) -> str:
    """Rachunek wiersza bez wyniku, np. ``0 ∧ 1`` — operatory z ``formula.to_text``.

    Wartości wstawiamy jako nazwy zmiennych, więc rachunek używa tej samej notacji
    co reszta strony — w kodzie nie ma ani jednego operatora wpisanego ręcznie.
    """
    wartosci = [Var(_wartosc_kolumny(tabela, indeks, numer)) for indeks in kolumna.zrodla]
    if len(wartosci) == 1:
        return to_text(Not(wartosci[0]))
    return to_text(type(parse(kolumna.wzor))(wartosci[0], wartosci[1]))


def _opis_kolumny(tabela: Mapping[str, Any], kolumna: Kolumna, indeks: int) -> str:
    """Opis kroku dowodu: nazwa kolumny, operacja i rachunek jednego wiersza.

    Trzyma się zapisu z wykładu: „Kolumna α: koniunkcja (p → q) i ∼q.
    W wierszu 3: 0 ∧ 1 = 0”.
    """
    numer = _wiersz_opisu(tabela, kolumna)
    return (
        f"Kolumna {_etykieta_kolumny(tabela, indeks)}: {_opis_operacji(tabela, kolumna)}. "
        f"W wierszu {numer + 1}: {_rachunek(tabela, kolumna, numer)} "
        f"= {_wartosc_kolumny(tabela, indeks, numer)}."
    )


def _indeks_wyniku(tabela: Mapping[str, Any], wzor: str) -> int:
    """Numer kolumny wynikowej o danym wzorze na liście ``kolumny`` tablicy."""
    return [kolumna["wzor"] for kolumna in tabela["kolumny"]].index(wzor)


def _wiersze_zostawione(tabela: Mapping[str, Any]) -> list[int]:
    """Numery wierszy, w których następnik δ jest fałszywy.

    Tylko takie wiersze mogą obalić formułę γ → δ, więc metoda skrócona liczy
    wyłącznie je.
    """
    delta = _indeks_wyniku(tabela, NASTEPNIK_METODY)
    return [
        numer for numer, wiersz in enumerate(tabela["wiersze"]) if wiersz["wyniki"][delta] == "0"
    ]


def _wiersze_odrzucone(tabela: Mapping[str, Any]) -> list[int]:
    """Numery wierszy odrzuconych przez metodę skróconą — cała reszta tablicy."""
    zostawione = set(_wiersze_zostawione(tabela))
    return [numer for numer in range(len(tabela["wiersze"])) if numer not in zostawione]


def _kolejnosc_zmiennych(node: Node) -> list[str]:
    """Nazwy zmiennych w kolejności pierwszego wystąpienia w formule."""
    if isinstance(node, Var):
        return [node.name]
    if isinstance(node, Not):
        return _kolejnosc_zmiennych(node.child)
    if isinstance(node, (And, Or, Imp, Iff)):
        return list(
            dict.fromkeys([*_kolejnosc_zmiennych(node.left), *_kolejnosc_zmiennych(node.right)])
        )
    return []


def _warunki(tabela: Mapping[str, Any], zostawione: Sequence[int]) -> str:
    """Wartości zmiennych stałych w zostawionych wierszach: ``r = 0 i p = 1``.

    Kolejność bierzemy z wzoru następnika — tak wykład pisze „r = 0 i p = 1”.
    """
    wiersze = [tabela["wiersze"][numer] for numer in zostawione]
    zmienne = list(tabela["zmienne"])
    czesci = []
    for zmienna in _kolejnosc_zmiennych(parse(NASTEPNIK_METODY)):
        wartosci = {wiersz["zmienne"][zmienne.index(zmienna)] for wiersz in wiersze}
        if len(wartosci) == 1:
            czesci.append(f"{zmienna} = {wartosci.pop()}")
    return _wymien(czesci)


def _przypadki(tabela: Mapping[str, Any], zostawione: Sequence[int]) -> str:
    """Zmienna, która zmienia się między zostawionymi wierszami: ``q = 1 oraz q = 0``."""
    wiersze = [tabela["wiersze"][numer] for numer in zostawione]
    zmienne = list(tabela["zmienne"])
    for zmienna in zmienne:
        wartosci = [wiersz["zmienne"][zmienne.index(zmienna)] for wiersz in wiersze]
        if len(set(wartosci)) > 1:
            return f"{zmienna} = {wartosci[0]} oraz {zmienna} = {wartosci[1]}"
    return "oba wiersze są takie same"


def _wniosek_dowodu(tabela: Mapping[str, Any]) -> str:
    """Zdanie kończące dowód pełną tablicą — liczone z ostatniej kolumny tablicy."""
    ile = len(tabela["wiersze"])
    jedynki = sum(1 for wiersz in tabela["wiersze"] if wiersz["wyniki"][-1] == "1")
    if ile and jedynki == ile:
        return "Wszystkie wiersze mają 1 — to tautologia."
    return "Nie wszystkie wiersze mają 1 — to nie jest tautologia."


def _wniosek_metody(tabela: Mapping[str, Any]) -> str:
    """Zdanie kończące metodę skróconą — liczone z wierszy, które zostały."""
    skrocona = tabela_bez_odrzuconych(tabela)
    ile = len(skrocona["wiersze"])
    jedynki = sum(1 for wiersz in skrocona["wiersze"] if wiersz["wyniki"][-1] == "1")
    if ile and jedynki == ile:
        wstep = (
            "W obu przypadkach wynik to 1"
            if ile == 2
            else f"W każdym z {ile} przypadków wynik to 1"
        )
        return f"{wstep}. Formuła jest tautologią."
    return f"Wynik to 1 tylko w {jedynki} z {ile} przypadków. Formuła nie jest tautologią."


def _strzalka(
    od: Sequence[int],
    do: Sequence[int],
    opis: str,
    jednostka: str = JEDNOSTKA_KOLUMNY,
) -> dict[str, Any]:
    """Jedna strzałka kroku: skąd, dokąd i jaka operacja.

    ``jednostka`` mówi, czy numery znaczą kolumny, czy wiersze tablicy — dzięki temu
    skrypt wie, co narysować nad tabelą, a co pokazać przy zawężaniu wierszy.
    """
    return {"od": list(od), "do": list(do), "opis": opis, "jednostka": jednostka}


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
    tabela_metody = tabela_prawdy(KOLUMNY_METODY, ZMIENNE_PQR)
    kroki_dowodu = zbuduj_kroki_dowodu(tabela_dowodu)
    kroki_metody = zbuduj_kroki_metody(tabela_metody)
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
        kroki_dowodu=kroki_dowodu,
        kroki_dowodu_json=kroki_json(kroki_dowodu),
        formula_metody=FORMULA_METODY,
        kroki_rozumowania=KROKI_METODY,
        kroki_metody=kroki_metody,
        kroki_metody_json=kroki_json(kroki_metody),
        tabela_metody=tabela_metody,
        wniosek_metody=wniosek_tautologii(tabela_metody),
        tautologie=tabela_tautologii(),
        prawa_dodatkowe=prawa_dodatkowe(),
        #: Partial tablicy prawdy (karta PRZ-011) czyta zmienną ``formula``.
        formula=FORMULA_DOWODU,
    )
