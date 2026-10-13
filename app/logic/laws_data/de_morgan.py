"""Treść dwóch praw de Morgana: zaprzeczenie alternatywy i koniunkcji.

Prawa T12 i T13 z wykładu. Na wykładzie **I** prawo de Morgana dotyczy
alternatywy (``∨``), a **II** koniunkcji (``∧``) — odwrotnie niż w wielu
podręcznikach. Ta kolejność jest obowiązująca.

Wizualizacja to ``sets``: oba prawa widać na diagramach zbiorów, gdzie
dopełnienie sumy równa się części wspólnej dopełnień.
"""

from __future__ import annotations

from app.logic.law_model import Law, Step

#: Prawa T12 i T13 stoją po prawach algebry.
kolejnosc = 4

LAWS: list[Law] = [
    Law(
        slug="de-morgan-1",
        nazwa="I prawo de Morgana",
        kategoria="de Morgan",
        formula="∼(p ∨ q) ≡ (∼p ∧ ∼q)",
        formula_ascii="~(p | q) <-> (~p & ~q)",
        lewa="∼(p ∨ q)",
        prawa="∼p ∧ ∼q",
        po_ludzku=(
            "Ktoś mówi: nie jest prawdą, że pójdę do kina lub do teatru. "
            "Z tego wynika, że nie pójdę do kina i nie pójdę do teatru. "
            "Zaprzeczenie alternatywy zamienia „lub” na „i”. "
            "Każdy człon dostaje przy tym własne przeczenie."
        ),
        przyklad=(
            "Nie jest prawdą, że pójdę do kina lub do teatru. "
            "Zatem nie pójdę do kina i nie pójdę do teatru."
        ),
        kroki=[
            Step(
                opis="Bierzemy formułę z lewej strony prawa: nieprawda, że p lub q.",
                reguła="założenie",
                przed="∼(p ∨ q)",
                po="∼(p ∨ q)",
            ),
            Step(
                opis="Dopisujemy parę przeczeń przed całą formułą — wartość się nie zmienia.",
                reguła="podwojne-przeczenie",
                przed="∼(p ∨ q)",
                po="∼∼∼(p ∨ q)",
            ),
            Step(
                opis="Zaprzeczenie alternatywy to koniunkcja zaprzeczeń, czyli ∼p ∧ ∼q.",
                reguła="de-morgan-1",
                przed="∼∼∼(p ∨ q)",
                po="∼∼(∼p ∧ ∼q)",
            ),
            Step(
                opis="Dwa przeczenia przed koniunkcją znikają i zostaje prawa strona prawa.",
                reguła="podwojne-przeczenie",
                przed="∼∼(∼p ∧ ∼q)",
                po="∼p ∧ ∼q",
            ),
        ],
        czeste_bledy=[
            "Ktoś neguje tylko pierwszy człon i pisze ∼p ∨ q. "
            "Przeczenie obejmuje całe zdanie w nawiasie.",
            "Ktoś zmienia spójnik, ale zapomina o przeczeniach: pisze p ∧ q. "
            "Każdy składnik musi dostać własne przeczenie.",
            "Ktoś zostawia spójnik „lub” bez zmiany i pisze ∼p ∨ ∼q. "
            "Zaprzeczenie alternatywy zamienia ją na koniunkcję.",
        ],
        wizualizacja="sets",
        quiz=[
            {
                "pytanie": "Która formuła jest równoważna formule ∼(p ∨ q)?",
                "opcje": ["∼p ∧ ∼q", "∼p ∨ ∼q", "p ∧ q", "∼p ∧ q"],
                "poprawna": 0,
                "podpowiedz": "Zaprzecz obu zdaniom i zamień „lub” na „i”.",
                "wyjasnienie": (
                    "Zaprzeczenie alternatywy to koniunkcja zaprzeczeń, czyli ∼p ∧ ∼q."
                ),
            },
            {
                "pytanie": "Jak brzmi I prawo de Morgana?",
                "opcje": [
                    "Zaprzeczenie alternatywy to koniunkcja zaprzeczeń",
                    "Zaprzeczenie alternatywy to alternatywa zaprzeczeń",
                    "Zaprzeczenie koniunkcji to alternatywa zaprzeczeń",
                ],
                "poprawna": 0,
                "podpowiedz": "Popatrz, co dzieje się ze spójnikiem po zaprzeczeniu.",
                "wyjasnienie": (
                    "I prawo de Morgana mówi: ∼(p ∨ q) ≡ (∼p ∧ ∼q). "
                    "Spójnik „lub” zamienia się na „i”."
                ),
            },
            {
                "pytanie": "Nie jest prawdą, że pójdę do kina lub do teatru. Co z tego wynika?",
                "opcje": [
                    "Nie pójdę do kina i nie pójdę do teatru",
                    "Nie pójdę do kina lub nie pójdę do teatru",
                    "Pójdę i do kina, i do teatru",
                ],
                "poprawna": 0,
                "podpowiedz": "Zaprzecz całemu zdaniu z „lub”.",
                "wyjasnienie": (
                    "Zaprzeczenie „lub” daje koniunkcję zaprzeczeń: ani kina, ani teatru."
                ),
            },
        ],
    ),
    Law(
        slug="de-morgan-2",
        nazwa="II prawo de Morgana",
        kategoria="de Morgan",
        formula="∼(p ∧ q) ≡ (∼p ∨ ∼q)",
        formula_ascii="~(p & q) <-> (~p | ~q)",
        lewa="∼(p ∧ q)",
        prawa="∼p ∨ ∼q",
        po_ludzku=(
            "Ktoś mówi: nie jest prawdą, że zjem obiad i pójdę na spacer. "
            "Z tego wynika, że albo nie zjem obiadu, albo nie pójdę na spacer. "
            "Zaprzeczenie koniunkcji zamienia „i” na „lub”. "
            "Każdy człon dostaje przy tym własne przeczenie."
        ),
        przyklad=(
            "Nie jest prawdą, że zjem obiad i pójdę na spacer. "
            "Zatem albo nie zjem obiadu, albo nie pójdę na spacer."
        ),
        kroki=[
            Step(
                opis="Bierzemy formułę z lewej strony prawa: nieprawda, że p i q.",
                reguła="założenie",
                przed="∼(p ∧ q)",
                po="∼(p ∧ q)",
            ),
            Step(
                opis="Dopisujemy parę przeczeń przed całą formułą — wartość się nie zmienia.",
                reguła="podwojne-przeczenie",
                przed="∼(p ∧ q)",
                po="∼∼∼(p ∧ q)",
            ),
            Step(
                opis="Zaprzeczenie koniunkcji to alternatywa zaprzeczeń, czyli ∼p ∨ ∼q.",
                reguła="de-morgan-2",
                przed="∼∼∼(p ∧ q)",
                po="∼∼(∼p ∨ ∼q)",
            ),
            Step(
                opis="Dwa przeczenia przed alternatywą znikają i zostaje prawa strona prawa.",
                reguła="podwojne-przeczenie",
                przed="∼∼(∼p ∨ ∼q)",
                po="∼p ∨ ∼q",
            ),
        ],
        czeste_bledy=[
            "Ktoś neguje tylko pierwszy człon i pisze ∼p ∧ q. "
            "Przeczenie obejmuje całe zdanie w nawiasie.",
            "Ktoś zostawia spójnik „i” bez zmiany i pisze ∼p ∧ ∼q. "
            "Zaprzeczenie koniunkcji zamienia ją na alternatywę.",
            "Ktoś sądzi, że de Morgan mówi o ∼p ∧ ∼q przy ∼(p ∧ q). "
            "To błąd: drugie prawo daje ∼p ∨ ∼q.",
        ],
        wizualizacja="sets",
        quiz=[
            {
                "pytanie": "Która formuła jest równoważna formule ∼(p ∧ q)?",
                "opcje": ["∼p ∨ ∼q", "∼p ∧ ∼q", "∼p ∨ q", "p ∨ q"],
                "poprawna": 0,
                "podpowiedz": "Zaprzecz obu zdaniom i zamień „i” na „lub”.",
                "wyjasnienie": (
                    "Zaprzeczenie koniunkcji to alternatywa zaprzeczeń, czyli ∼p ∨ ∼q."
                ),
            },
            {
                "pytanie": "Jak brzmi II prawo de Morgana?",
                "opcje": [
                    "Zaprzeczenie koniunkcji to alternatywa zaprzeczeń",
                    "Zaprzeczenie koniunkcji to koniunkcja zaprzeczeń",
                    "Zaprzeczenie alternatywy to koniunkcja zaprzeczeń",
                ],
                "poprawna": 0,
                "podpowiedz": "Popatrz, co dzieje się ze spójnikiem po zaprzeczeniu.",
                "wyjasnienie": (
                    "II prawo de Morgana mówi: ∼(p ∧ q) ≡ (∼p ∨ ∼q). "
                    "Spójnik „i” zamienia się na „lub”."
                ),
            },
            {
                "pytanie": "Nie zjem obiadu i nie pójdę na spacer to zaprzeczenie którego zdania?",
                "opcje": [
                    "Zjem obiad lub pójdę na spacer",
                    "Zjem obiad i pójdę na spacer",
                    "Zjem obiad, ale nie pójdę na spacer",
                ],
                "poprawna": 0,
                "podpowiedz": "Zaprzecz całemu zdaniu z „lub”.",
                "wyjasnienie": (
                    "Zaprzeczenie alternatywy daje koniunkcję zaprzeczeń. "
                    "Dlatego odpowiada zdaniu „zjem obiad lub pójdę na spacer”."
                ),
            },
        ],
    ),
]
