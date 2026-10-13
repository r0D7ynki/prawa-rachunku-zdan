"""Rejestr wykładów i lekcji — jedno źródło prawdy dla nawigacji.

Menu, spis treści, okruszki i odnośniki „poprzednia/następna lekcja” czytają
kolejność stron z tego modułu. Dodanie wykładu to dopisanie jednej listy tutaj,
a nie zmiana wielu szablonów.

Kontrakt modułu opisuje ``docs/ARCHITEKTURA.md``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Lesson:
    """Pojedyncza lekcja kursu wraz z miejscem w nawigacji."""

    slug: str  # "formuly"
    sciezka: str  # "/formuly"
    tytul: str  # "Formuły i wartościowanie"
    opis: str  # jedno zdanie, do 20 słów
    wyklad: int  # numer wykładu
    ikona: str  # krótki znak, np. "≡"


@dataclass(frozen=True)
class Lecture:
    """Wykład: numer, tytuł, opis i należące do niego lekcje."""

    numer: int
    tytul: str  # "Klasyczny rachunek zdań"
    opis: str
    lekcje: tuple[Lesson, ...]
    gotowy: bool  # False = „wkrótce”


#: Osiem lekcji wykładu 1 — kolejność jest kolejnością nauki.
_LEKCJE_WYKLADU_1: tuple[Lesson, ...] = (
    Lesson(
        slug="wstep",
        sciezka="/wstep",
        tytul="Wstęp",
        opis="Czym zajmuje się logika i jak odróżnić poprawne wnioskowanie od błędnego.",
        wyklad=1,
        ikona="▶",
    ),
    Lesson(
        slug="formuly",
        sciezka="/formuly",
        tytul="Formuły i wartościowanie",
        opis="Budujesz formuły ze zdań prostych i nadajesz im wartość 1 albo 0.",
        wyklad=1,
        ikona="≡",
    ),
    Lesson(
        slug="tautologie",
        sciezka="/tautologie",
        tytul="Tautologie i kontrtautologie",
        opis="Odróżniasz formuły zawsze prawdziwe od zawsze fałszywych i od spełnialnych.",
        wyklad=1,
        ikona="⊤",
    ),
    Lesson(
        slug="przeksztalcanie",
        sciezka="/przeksztalcanie",
        tytul="Przekształcanie formuł",
        opis="Upraszczasz formułę krok po kroku, aż zostanie czytelny wynik.",
        wyklad=1,
        ikona="⇄",
    ),
    Lesson(
        slug="kpn",
        sciezka="/kpn",
        tytul="KPN — koniunkcyjna postać normalna",
        opis="Sprowadzasz każdą formułę do iloczynu sum zmiennych i ich negacji.",
        wyklad=1,
        ikona="∧",
    ),
    Lesson(
        slug="prawa",
        sciezka="/prawa",
        tytul="Prawa rachunku zdań",
        opis="Poznajesz czternaście praw i używasz ich w przekształceniach.",
        wyklad=1,
        ikona="∨",
    ),
    Lesson(
        slug="plac-zabaw",
        sciezka="/plac-zabaw",
        tytul="Plac zabaw",
        opis="Wpisujesz własną formułę i sprawdzasz jej tablicę prawdy oraz uproszczenie.",
        wyklad=1,
        ikona="✎",
    ),
    Lesson(
        slug="quiz",
        sciezka="/quiz",
        tytul="Quiz",
        opis="Sprawdzasz, czy rozpoznajesz prawa i czy bezbłędnie je stosujesz.",
        wyklad=1,
        ikona="?",
    ),
)

#: Cztery lekcje wykładu 2 — kolejność jest kolejnością nauki.
_LEKCJE_WYKLADU_2: tuple[Lesson, ...] = (
    Lesson(
        slug="konsekwencja",
        sciezka="/konsekwencja",
        tytul="Wynikanie logiczne",
        opis="Kiedy teza wynika z założeń i co to znaczy, że założenia są sprzeczne.",
        wyklad=2,
        ikona="⊨",
    ),
    Lesson(
        slug="reguly",
        sciezka="/reguly",
        tytul="Reguły wnioskowania",
        opis="Dziesięć reguł: od odrywania po kontrapozycję, każda ze schematem i przykładem.",
        wyklad=2,
        ikona="⊢",
    ),
    Lesson(
        slug="dowody",
        sciezka="/dowody",
        tytul="Dowody założeniowe",
        opis="Dowód wprost i nie wprost, krok po kroku, ze strzałkami od użytych wierszy.",
        wyklad=2,
        ikona="⇓",
    ),
    Lesson(
        slug="rezolucja",
        sciezka="/rezolucja",
        tytul="Rezolucja",
        opis="Sklejanie klauzul: od KPN, przez kolejne rezolucje, do sprzeczności.",
        wyklad=2,
        ikona="□",
    ),
)

#: Trzy wykłady kursu. Wykład 3 to jeszcze zapowiedź na przyszłość.
_WYKLADY: tuple[Lecture, ...] = (
    Lecture(
        numer=1,
        tytul="Klasyczny rachunek zdań",
        opis="Zdania, formuły, tautologie i prawa — cały materiał pierwszego wykładu.",
        lekcje=_LEKCJE_WYKLADU_1,
        gotowy=True,
    ),
    Lecture(
        numer=2,
        tytul="Konsekwencja logiczna i dowody",
        opis="Wynikanie, reguły wnioskowania, dowody założeniowe i rezolucja.",
        lekcje=_LEKCJE_WYKLADU_2,
        gotowy=True,
    ),
    Lecture(
        numer=3,
        tytul="Elementy teorii zbiorów i relacji",
        opis="Zbiory, relacje i funkcje jako język dalszej części kursu. Materiał w przygotowaniu.",
        lekcje=(),
        gotowy=False,
    ),
)

#: Pozycje narzędziowe menu: stałe odnośniki poza ścieżką lekcji.
_NARZEDZIA: tuple[dict, ...] = (
    {"sciezka": "/prawa", "tytul": "Prawa", "ikona": "§"},
    {"sciezka": "/plac-zabaw", "tytul": "Plac zabaw", "ikona": "✎"},
    {"sciezka": "/quiz", "tytul": "Quiz", "ikona": "?"},
    {"sciezka": "/slowniczek", "tytul": "Słowniczek", "ikona": "▤"},
    {"sciezka": "/jak-czytac", "tytul": "Jak czytać", "ikona": "▸"},
)


def lectures() -> list[Lecture]:
    """Zwraca wykłady w kolejności numerów."""
    return sorted(_WYKLADY, key=lambda wyklad: wyklad.numer)


def lessons() -> list[Lesson]:
    """Zwraca wszystkie lekcje po kolei — płaska lista w kolejności nauki."""
    return [lekcja for wyklad in lectures() for lekcja in wyklad.lekcje]


def lesson(sciezka: str) -> Lesson | None:
    """Zwraca lekcję o podanej ścieżce albo ``None``, gdy ścieżki nie ma w rejestrze."""
    for kandydat in lessons():
        if kandydat.sciezka == sciezka:
            return kandydat
    return None


def lecture(numer: int) -> Lecture | None:
    """Zwraca wykład o podanym numerze albo ``None``."""
    for kandydat in lectures():
        if kandydat.numer == numer:
            return kandydat
    return None


def _sasiad(sciezka: str, krok: int) -> Lesson | None:
    """Zwraca lekcję o ``krok`` dalej w płaskiej liście; poza listą — ``None``."""
    wszystkie = lessons()
    for indeks, kandydat in enumerate(wszystkie):
        if kandydat.sciezka != sciezka:
            continue
        nowy_indeks = indeks + krok
        if 0 <= nowy_indeks < len(wszystkie):
            return wszystkie[nowy_indeks]
        return None
    return None


def previous(sciezka: str) -> Lesson | None:
    """Zwraca lekcję poprzedzającą podaną ścieżkę albo ``None``."""
    return _sasiad(sciezka, -1)


def next(sciezka: str) -> Lesson | None:
    """Zwraca lekcję następującą po podanej ścieżce albo ``None``."""
    return _sasiad(sciezka, 1)


def tool_links() -> list[dict]:
    """Zwraca pozycje narzędziowe menu: Prawa, Plac zabaw, Quiz, Słowniczek, Jak czytać.

    Każda pozycja to słownik ``{"sciezka", "tytul", "ikona"}``. Zwracamy kopie, żeby
    szablon albo wywołujący nie zmienił wspólnej listy modułu.
    """
    return [dict(pozycja) for pozycja in _NARZEDZIA]
