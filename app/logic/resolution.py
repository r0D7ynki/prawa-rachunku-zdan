"""Reguła rezolucji i dwa dowody z wykładu 2 (karta PRZ-092).

Ten moduł jest dla rezolucji tym, czym ``app.logic.rules`` dla reguł wnioskowania:
trzyma **dane** w kolejności z wykładu, a nie logikę. Źródłem prawdy jest
``docs/TRESC-WYKLAD2.md``, sekcje „6. Reguła rezolucji” i „7. Algorytm rezolucji”.

Numeracja wierszy i klauzule są przepisane z tabel wykładu (kolumna „Skąd” mówi,
z których wierszy powstaje nowa klauzula). Kontrakt modułu opisuje
``docs/ARCHITEKTURA.md``.

Kolejność kroków jest kolejnością wierszy w tabeli:

* ``zalozenie`` — wiersz z KPN założeń (bez rodziców),
* ``negacja-tezy`` — wiersz z negacji tezy (bez rodziców),
* ``rezolucja`` — sklejenie dwóch wcześniejszych wierszy na jednym literale,
* ``sprzecznosc`` — ostatni wiersz: para ``x`` i ``∼x`` zamyka dowód,
  więc ``literal`` jest pusty, a ``rodzice`` wskazują dwa sprzeczne wiersze.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Rodzaje kroków. Trzymamy je jako stałe, żeby widok i testy nie powtarzały napisów.
RODZAJ_ZALOZENIE = "zalozenie"
RODZAJ_NEGACJA_TEZY = "negacja-tezy"
RODZAJ_REZOLUCJA = "rezolucja"
RODZAJ_SPRZECZNOSC = "sprzecznosc"

#: Rodzaje kroków bez rodziców — wiersz wprost z wykładu.
RODZAJE_WEJSCIOWE = (RODZAJ_ZALOZENIE, RODZAJ_NEGACJA_TEZY)


@dataclass(frozen=True)
class ResolutionStep:
    """Jeden wiersz dowodu rezolucyjnego.

    ``rodzice`` to numery wierszy, z których powstała klauzula (dokładnie dwa przy
    rezolucji, puste przy wierszach z wykładu). ``literal`` mówi, na czym sklejono
    — jest pusty dla założeń, negacji tezy i wiersza sprzeczności.
    """

    nr: int
    klauzula: str  # "q ∨ r"
    rodzice: list[int]  # [1, 3]
    literal: str  # "p" — na czym sklejono; "" dla założeń i sprzeczności
    rodzaj: str  # "zalozenie" | "negacja-tezy" | "rezolucja" | "sprzecznosc"


@dataclass(frozen=True)
class ResolutionProof:
    """Cały dowód rezolucyjny: tytuł, opis i kolejne wiersze."""

    id: str
    tytul: str
    opis: str
    kroki: list[ResolutionStep]


#: Przykład 1 z wykładu: teza ``p ∨ s`` wynika z założeń ``p → q``, ``r → s``, ``p ∨ r``.
#: Wiersze 1–3 to KPN założeń, wiersze 4–5 to negacja tezy, 6–9 to kolejne sklejenia,
#: a wiersz 10 zamyka dowód sprzecznością.
_PRZYKLAD_1: ResolutionProof = ResolutionProof(
    id="przyklad-1",
    tytul="Przykład 1: teza p ∨ s",
    opis="Pokazujemy, że p ∨ s wynika z założeń p → q, r → s oraz p ∨ r.",
    kroki=[
        ResolutionStep(nr=1, klauzula="∼p ∨ q", rodzice=[], literal="", rodzaj=RODZAJ_ZALOZENIE),
        ResolutionStep(nr=2, klauzula="∼r ∨ s", rodzice=[], literal="", rodzaj=RODZAJ_ZALOZENIE),
        ResolutionStep(nr=3, klauzula="p ∨ r", rodzice=[], literal="", rodzaj=RODZAJ_ZALOZENIE),
        ResolutionStep(nr=4, klauzula="∼p", rodzice=[], literal="", rodzaj=RODZAJ_NEGACJA_TEZY),
        ResolutionStep(nr=5, klauzula="∼s", rodzice=[], literal="", rodzaj=RODZAJ_NEGACJA_TEZY),
        ResolutionStep(
            nr=6, klauzula="q ∨ r", rodzice=[1, 3], literal="p", rodzaj=RODZAJ_REZOLUCJA
        ),
        ResolutionStep(
            nr=7, klauzula="p ∨ s", rodzice=[2, 3], literal="r", rodzaj=RODZAJ_REZOLUCJA
        ),
        ResolutionStep(nr=8, klauzula="∼r", rodzice=[2, 5], literal="s", rodzaj=RODZAJ_REZOLUCJA),
        ResolutionStep(nr=9, klauzula="r", rodzice=[3, 4], literal="p", rodzaj=RODZAJ_REZOLUCJA),
        ResolutionStep(
            nr=10,
            klauzula="Sprzeczność 8, 9",
            rodzice=[8, 9],
            literal="",
            rodzaj=RODZAJ_SPRZECZNOSC,
        ),
    ],
)

#: Przykład 2 z wykładu: założenia ``p ∨ q``, ``p → q``, ``∼q ∨ r``, ``∼r`` są sprzeczne.
#: Wszystkie cztery wiersze to założenia, dwa sklejenia dają parę ``q`` i ``∼q``.
_PRZYKLAD_2: ResolutionProof = ResolutionProof(
    id="przyklad-2",
    tytul="Przykład 2: założenia sprzeczne",
    opis="Pokazujemy, że założenia p ∨ q, p → q, ∼q ∨ r oraz ∼r są sprzeczne.",
    kroki=[
        ResolutionStep(nr=1, klauzula="p ∨ q", rodzice=[], literal="", rodzaj=RODZAJ_ZALOZENIE),
        ResolutionStep(nr=2, klauzula="∼p ∨ q", rodzice=[], literal="", rodzaj=RODZAJ_ZALOZENIE),
        ResolutionStep(nr=3, klauzula="∼q ∨ r", rodzice=[], literal="", rodzaj=RODZAJ_ZALOZENIE),
        ResolutionStep(nr=4, klauzula="∼r", rodzice=[], literal="", rodzaj=RODZAJ_ZALOZENIE),
        ResolutionStep(nr=5, klauzula="q", rodzice=[1, 2], literal="p", rodzaj=RODZAJ_REZOLUCJA),
        ResolutionStep(nr=6, klauzula="∼q", rodzice=[3, 4], literal="r", rodzaj=RODZAJ_REZOLUCJA),
        ResolutionStep(
            nr=7,
            klauzula="Sprzeczność 5, 6",
            rodzice=[5, 6],
            literal="",
            rodzaj=RODZAJ_SPRZECZNOSC,
        ),
    ],
)

#: Dwa dowody z wykładu, w kolejności z sekcji „7. Algorytm rezolucji”.
_PROOFS: tuple[ResolutionProof, ...] = (_PRZYKLAD_1, _PRZYKLAD_2)


def proofs() -> list[ResolutionProof]:
    """Zwraca dwa dowody rezolucyjne z wykładu, w kolejności przykładów.

    Oddajemy kopię listy, żeby wołający nie zmienił rejestru przez przypadek.
    """
    return list(_PROOFS)
