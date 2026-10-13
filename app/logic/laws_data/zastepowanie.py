"""Treść prawa zastępowania równych (T14 z wykładu).

Prawo pokazuje, że równoważność ``p ≡ q`` to dwie implikacje naraz:
``p → q`` oraz ``q → p``, połączone spójnikiem ``∧``.

Ten plik **nie** dodaje reguły podstawiania formuł do tautologii. To osobne,
dodatkowe prawo w karcie PRZ-024 (``laws_data/dodatkowe.py``).
"""

from __future__ import annotations

from app.logic.law_model import Law, Step

#: Prawo T14 zamyka listę czternastu praw.
kolejnosc = 5

LAWS: list[Law] = [
    Law(
        slug="zastepowanie-rownych",
        nazwa="Prawo zastępowania równych",
        kategoria="zastępowanie",
        formula="(p ≡ q) ≡ ((p → q) ∧ (q → p))",
        formula_ascii="(p <-> q) <-> ((p -> q) & (q -> p))",
        lewa="p ≡ q",
        prawa="(p → q) ∧ (q → p)",
        po_ludzku=(
            "Równoważność p ≡ q mówi, że p jest prawdą dokładnie wtedy, gdy q jest prawdą. "
            "Zapisujemy to jako dwie implikacje naraz: jeżeli p, to q oraz jeżeli q, to p. "
            "Oba warunki muszą zachodzić jednocześnie, dlatego łączymy je spójnikiem „i”."
        ),
        przyklad=(
            "Jutro będzie poniedziałek dokładnie wtedy, gdy dzisiaj jest niedziela. "
            "Z tego wynikają dwa zdania: jeżeli jutro jest poniedziałek, "
            "to dzisiaj jest niedziela. "
            "Oraz odwrotnie: jeżeli dzisiaj jest niedziela, to jutro jest poniedziałek."
        ),
        kroki=[
            Step(
                opis="Bierzemy formułę z lewej strony prawa: p wtedy i tylko wtedy, gdy q.",
                reguła="założenie",
                przed="p ≡ q",
                po="p ≡ q",
            ),
            Step(
                opis="Dopisujemy parę przeczeń przed całą formułą — wartość się nie zmienia.",
                reguła="podwojne-przeczenie",
                przed="p ≡ q",
                po="∼∼(p ≡ q)",
            ),
            Step(
                opis="Równoważność rozbijamy na dwie implikacje i łączymy je spójnikiem „i”.",
                reguła="zastepowanie-rownych",
                przed="∼∼(p ≡ q)",
                po="∼∼((p → q) ∧ (q → p))",
            ),
            Step(
                opis="Dwa przeczenia przed koniunkcją znikają i zostaje prawa strona prawa.",
                reguła="podwojne-przeczenie",
                przed="∼∼((p → q) ∧ (q → p))",
                po="(p → q) ∧ (q → p)",
            ),
        ],
        czeste_bledy=[
            "Ktoś czyta p ≡ q jak zwykłe „jeżeli p, to q”. "
            "Brakuje drugiego kierunku: jeżeli q, to p.",
            "Ktoś łączy dwie implikacje spójnikiem „lub” zamiast „i”. "
            "Równoważność wymaga obu kierunków jednocześnie.",
            "Ktoś myli równoważność z implikacją i twierdzi, że jedno zdanie wynika z drugiego "
            "tylko w jedną stronę.",
        ],
        wizualizacja="chain",
        quiz=[
            {
                "pytanie": "Czemu jest równa równoważność p ≡ q?",
                "opcje": [
                    "(p → q) ∧ (q → p)",
                    "(p → q) ∨ (q → p)",
                    "p → q",
                    "q → p",
                ],
                "poprawna": 0,
                "podpowiedz": "Równoważność to dwie implikacje połączone spójnikiem „i”.",
                "wyjasnienie": ("p ≡ q to to samo co (p → q) ∧ (q → p): oba kierunki naraz."),
            },
            {
                "pytanie": "Co znaczy zdanie „p wtedy i tylko wtedy, gdy q”?",
                "opcje": [
                    "Oba zdania mają tę samą wartość logiczną",
                    "Z p wynika q, ale nie odwrotnie",
                    "p i q są zawsze prawdziwe",
                    "p i q są zawsze fałszywe",
                ],
                "poprawna": 0,
                "podpowiedz": "Sprawdź, kiedy równoważność jest prawdziwa.",
                "wyjasnienie": (
                    "Równoważność jest prawdziwa, gdy p i q mają tę samą wartość: "
                    "obie prawdziwe albo obie fałszywe."
                ),
            },
            {
                "pytanie": "Ile implikacji kryje się w jednej równoważności?",
                "opcje": ["Dwie", "Jedną", "Trzy", "Żadnej"],
                "poprawna": 0,
                "podpowiedz": "Policz kierunki: p do q oraz q do p.",
                "wyjasnienie": ("Równoważność to koniunkcja dwóch implikacji: p → q oraz q → p."),
            },
        ],
    ),
]
