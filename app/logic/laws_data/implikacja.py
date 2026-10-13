"""Treść dwóch praw o implikacji: definiowanie implikacji i kontrapozycja.

Prawa T4 i T5 z wykładu. Kroki pokazują, jak obie strony prawa zamieniają się
w siebie — używamy do tego także praw z ``podstawowe.py``.
"""

from __future__ import annotations

from app.logic.law_model import Law, Step

#: Prawa T4 i T5 stoją zaraz po prawach podstawowych.
kolejnosc = 2

LAWS: list[Law] = [
    Law(
        slug="definiowanie-implikacji",
        nazwa="Prawo definiowania implikacji",
        kategoria="implikacja",
        formula="(p → q) ≡ (∼p ∨ q)",
        formula_ascii="(p -> q) <-> (~p | q)",
        lewa="p → q",
        prawa="∼p ∨ q",
        po_ludzku=(
            "Ktoś obiecuje: jeżeli posprzątasz pokój, to pójdziemy do kina. "
            "Taka obietnica zawodzi tylko wtedy, gdy posprzątasz, a do kina nie pójdziemy. "
            "Dlatego implikację zapisujemy jako alternatywę: nie posprzątałeś "
            "albo idziemy do kina."
        ),
        przyklad=(
            "Mama mówi: jeżeli posprzątam pokój, to pójdziemy do kina. "
            "Obietnica zawodzi tylko wtedy, gdy posprzątam, a do kina nie pójdziemy."
        ),
        kroki=[
            Step(
                opis="Bierzemy formułę z lewej strony prawa: jeżeli p, to q.",
                reguła="założenie",
                przed="p → q",
                po="p → q",
            ),
            Step(
                opis="Zdanie p zapisujemy jako ∼∼p — to ta sama wartość.",
                reguła="podwojne-przeczenie",
                przed="p → q",
                po="∼∼p → q",
            ),
            Step(
                opis="Implikację zamieniamy na alternatywę: nieprawda, że nieprawda, że p, albo q.",
                reguła="definiowanie-implikacji",
                przed="∼∼p → q",
                po="∼∼∼p ∨ q",
            ),
            Step(
                opis="Zdejmujemy podwójne przeczenie i zostaje ∼p ∨ q, czyli prawa strona prawa.",
                reguła="podwojne-przeczenie",
                przed="∼∼∼p ∨ q",
                po="∼p ∨ q",
            ),
        ],
        czeste_bledy=[
            "Ktoś sądzi, że z fałszywego zdania nie może wynikać prawda. "
            "W implikacji układ 0 → 1 jest prawdziwy.",
            "Ktoś zapomina o przeczeniu i pisze p → q jako p ∨ q. "
            "Przed pierwszym członem musi stać negacja.",
            "Ktoś przestawia znak negacji i pisze p ∨ ∼q. To inna formuła niż ∼p ∨ q.",
        ],
        wizualizacja="gates",
        quiz=[
            {
                "pytanie": "Która formuła jest równoważna implikacji p → q?",
                "opcje": ["∼p ∨ q", "p ∨ ∼q", "∼p ∧ q", "p ∧ ∼q"],
                "poprawna": 0,
                "podpowiedz": "Zaprzecz pierwszemu członowi i zamień implikację na alternatywę.",
                "wyjasnienie": (
                    "Implikacja p → q to to samo co ∼p ∨ q: albo p nie zachodzi, albo zachodzi q."
                ),
            },
            {
                "pytanie": "Kiedy implikacja p → q jest fałszywa?",
                "opcje": [
                    "Gdy p jest prawdą, a q fałszem",
                    "Gdy p jest fałszem, a q prawdą",
                    "Gdy oba zdania są fałszem",
                    "W żadnym wypadku",
                ],
                "poprawna": 0,
                "podpowiedz": "Sprawdź cztery wartościowania p i q.",
                "wyjasnienie": (
                    "Implikacja zawodzi tylko przy układzie prawda → fałsz. "
                    "Pozostałe trzy wartościowania dają 1."
                ),
            },
        ],
    ),
    Law(
        slug="kontrapozycji",
        nazwa="Prawo kontrapozycji",
        kategoria="implikacja",
        formula="(p → q) ≡ (∼q → ∼p)",
        formula_ascii="(p -> q) <-> (~q -> ~p)",
        lewa="p → q",
        prawa="∼q → ∼p",
        po_ludzku=(
            "Ktoś mówi: jeżeli nauczę się, to zdam. "
            "Z tego wynika druga wiadomość: jeżeli nie zdałem, to się nie nauczyłem. "
            "Obie implikacje mówią to samo, tylko patrzą z drugiej strony. "
            "Tak działa prawo kontrapozycji."
        ),
        przyklad="Jeżeli nauczę się, to zdam. Zatem jeżeli nie zdałem, to się nie nauczyłem.",
        kroki=[
            Step(
                opis="Bierzemy formułę z lewej strony prawa: jeżeli p, to q.",
                reguła="założenie",
                przed="p → q",
                po="p → q",
            ),
            Step(
                opis="Implikację zapisujemy jako alternatywę: nie p albo q.",
                reguła="definiowanie-implikacji",
                przed="p → q",
                po="∼p ∨ q",
            ),
            Step(
                opis="Kolejność składników alternatywy nie zmienia wyniku.",
                reguła="przemiennosc-alternatywy",
                przed="∼p ∨ q",
                po="q ∨ ∼p",
            ),
            Step(
                opis="Zdanie q zapisujemy jako ∼∼q — to ta sama wartość.",
                reguła="podwojne-przeczenie",
                przed="q ∨ ∼p",
                po="∼∼q ∨ ∼p",
            ),
            Step(
                opis="Alternatywę zamieniamy z powrotem na implikację: jeżeli nie q, to nie p.",
                reguła="definiowanie-implikacji",
                przed="∼∼q ∨ ∼p",
                po="∼q → ∼p",
            ),
        ],
        czeste_bledy=[
            "Ktoś uznaje (p → q) ≡ (∼p → ∼q) za tautologię. To błąd: z faktu, "
            "że się nie nauczyłem, nie wynika, że nie zdam.",
            "Ktoś odwraca samą kolejność i pisze q → p. Odwrócenie członów to nie kontrapozycja.",
            "Ktoś neguje tylko jeden człon i pisze ∼q → p. Kontrapozycja neguje oba zdania.",
        ],
        wizualizacja="gates",
        quiz=[
            {
                "pytanie": "Która formuła jest kontrapozycją implikacji p → q?",
                "opcje": ["∼q → ∼p", "q → p", "∼p → ∼q", "∼q → p"],
                "poprawna": 0,
                "podpowiedz": "Odwróć kolejność i zaprzecz oba zdania.",
                "wyjasnienie": (
                    "Kontrapozycja implikacji p → q to ∼q → ∼p. Obie formuły mają tę samą wartość."
                ),
            },
            {
                "pytanie": "Co mówi prawo kontrapozycji?",
                "opcje": [
                    "Implikacja i jej kontrapozycja mają tę samą wartość",
                    "Z implikacji wynika jej odwrotność",
                    "Zaprzeczenie poprzednika pociąga zaprzeczenie następnika",
                ],
                "poprawna": 0,
                "podpowiedz": "Porównaj wartości obu implikacji dla czterech wartościowań.",
                "wyjasnienie": (
                    "p → q oraz ∼q → ∼p są równoważne. Nie wolno ich mylić "
                    "z odwrotnością q → p ani z ∼p → ∼q."
                ),
            },
            {
                "pytanie": "Który zapis jest błędem w prawie kontrapozycji?",
                "opcje": [
                    "∼p → ∼q jako kontrapozycja p → q",
                    "∼q → ∼p jako kontrapozycja p → q",
                    "p → q jako kontrapozycja ∼q → ∼p",
                ],
                "poprawna": 0,
                "podpowiedz": "Sprawdź, co się dzieje, gdy pada deszcz, ale zostaję w domu.",
                "wyjasnienie": (
                    "Z prawdy o braku nauki nie wynika fałsz zdania. Dlatego ∼p → ∼q "
                    "nie jest kontrapozycją p → q."
                ),
            },
        ],
    ),
]
