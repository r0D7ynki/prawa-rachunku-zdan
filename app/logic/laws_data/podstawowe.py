"""Treść trzech pierwszych praw: wyłączony środek, identyczność, podwójne przeczenie.

Ten plik jest wzorcem jakości dla kolejnych plików treści (PRZ-004, PRZ-005, PRZ-024):
każde prawo ma wyjaśnienie po ludzku, przykład z życia, kroki, częste błędy i quiz.

Formuły zapisujemy znakami, które przyjmuje ``app.logic.formula``: ``∼``, ``∧``,
``∨``, ``→``, ``≡``.
"""

from __future__ import annotations

from app.logic.law_model import Law, Step

#: Prawa T1–T3 z wykładu trzymają się razem na początku listy.
kolejnosc = 1

LAWS: list[Law] = [
    Law(
        slug="wylaczony-srodek",
        nazwa="Prawo wyłączonego środka",
        kategoria="podstawowe",
        formula="p ∨ ∼p",
        formula_ascii="p | ~p",
        lewa="p ∨ ∼p",
        prawa="p ∨ ∼p",
        po_ludzku=(
            "Wyobraź sobie okno: albo jest otwarte, albo nie jest otwarte. "
            "Trzeciej możliwości nie ma. "
            "Tak samo zdanie „p lub nie p” jest zawsze prawdziwe, "
            "niezależnie od tego, co podstawimy za p."
        ),
        przyklad=(
            "Patrzysz w niebo: świeci słońce albo nie świeci. "
            "Jedno z tych dwóch zdań jest zawsze prawdziwe."
        ),
        kroki=[
            Step(
                opis="Bierzemy formułę z lewej strony prawa.",
                reguła="założenie",
                przed="p ∨ ∼p",
                po="p ∨ ∼p",
            ),
            Step(
                opis="Zdanie p znaczy to samo co ∼∼p, więc wartość formuły się nie zmienia.",
                reguła="podwojne-przeczenie",
                przed="p ∨ ∼p",
                po="∼∼p ∨ ∼p",
            ),
            Step(
                opis="Zdejmujemy podwójne przeczenie i wracamy do zapisu z prawa.",
                reguła="podwojne-przeczenie",
                przed="∼∼p ∨ ∼p",
                po="p ∨ ∼p",
            ),
        ],
        czeste_bledy=[
            "Ktoś szuka trzeciej możliwości: zdania ani prawdziwego, ani fałszywego. "
            "W rachunku zdań zdanie ma zawsze jedną z dwóch wartości.",
            "Ktoś pisze ∼p ∨ ∼p i twierdzi, że to to samo. To dwa razy to samo zdanie, "
            "a nie zdanie i jego zaprzeczenie.",
            "Ktoś mówi, że prawo działa tylko wtedy, gdy znamy odpowiedź. "
            "Prawo mówi o wartościach logicznych, a nie o naszej wiedzy.",
        ],
        wizualizacja="switch",
        quiz=[
            {
                "pytanie": "Który zapis jest prawem wyłączonego środka?",
                "opcje": ["p ∨ ∼p", "p ∧ ∼p", "∼p ∨ ∼p", "p → ∼p"],
                "poprawna": 0,
                "podpowiedz": "Szukamy zdania prawdziwego przy każdej wartości p.",
                "wyjasnienie": (
                    "Prawo wyłączonego środka to p ∨ ∼p. Zawsze prawdziwe jest p "
                    "albo jego zaprzeczenie."
                ),
            },
            {
                "pytanie": "Czym jest formuła, która ma wartość 1 przy każdym wartościowaniu?",
                "opcje": [
                    "Tautologią",
                    "Kontrtautologią",
                    "Formułą spełnialną",
                    "Formułą sprzeczną",
                ],
                "poprawna": 0,
                "podpowiedz": "Sprawdź kolejno p prawdziwe i p fałszywe.",
                "wyjasnienie": (
                    "Taka formuła to tautologia. Formuła p ∨ ∼p jest tautologią, "
                    "bo oba wartościowania dają 1."
                ),
            },
            {
                "pytanie": "Jak czytamy formułę p ∨ ∼p po polsku?",
                "opcje": [
                    "Prawdą jest, że p, albo prawdą jest, że nie p",
                    "Prawdą jest, że p, i jednocześnie nie p",
                    "Jeżeli p, to nie p",
                ],
                "poprawna": 0,
                "podpowiedz": "Znak ∨ czytamy „lub”, a znak ∼ to zaprzeczenie.",
                "wyjasnienie": (
                    "Alternatywa jest prawdziwa, gdy prawdziwy jest choć jeden składnik. "
                    "Tutaj zawsze któryś z nich jest prawdziwy."
                ),
            },
        ],
    ),
    Law(
        slug="identycznosci",
        nazwa="Prawo identyczności",
        kategoria="podstawowe",
        formula="p → p",
        formula_ascii="p -> p",
        lewa="p → p",
        prawa="p → p",
        po_ludzku=(
            "Jeżeli dziś jest wtorek, to dziś jest wtorek. "
            "Zdanie brzmi dziwnie, ale zawsze jest prawdziwe. "
            "Mówi tylko, że każde zdanie wynika z samego siebie. "
            "Dlatego p → p jest tautologią."
        ),
        przyklad=(
            "Jeżeli świeci słońce, to świeci słońce. "
            "Takie zdanie jest zawsze prawdziwe, choć nic nowego nie mówi."
        ),
        kroki=[
            Step(
                opis="Bierzemy formułę z lewej strony prawa.",
                reguła="założenie",
                przed="p → p",
                po="p → p",
            ),
            Step(
                opis="Kontrapozycja zapisuje tę samą implikację od tyłu: jeżeli nie p, to nie p.",
                reguła="kontrapozycji",
                przed="p → p",
                po="∼p → ∼p",
            ),
            Step(
                opis="Podwójne przeczenie znika z obu stron i wracamy do p → p.",
                reguła="podwojne-przeczenie",
                przed="∼p → ∼p",
                po="p → p",
            ),
        ],
        czeste_bledy=[
            "Ktoś odrzuca p → p, bo nic z niego nie wynika. To prawda, ale takie zdanie "
            "jest zawsze prawdziwe i dlatego jest tautologią.",
            "Ktoś podstawia dwie różne zmienne i pisze p → q. W prawie identyczności "
            "po obu stronach stoi to samo zdanie.",
        ],
        wizualizacja="chain",
        quiz=[
            {
                "pytanie": "Jaką wartość ma formuła p → p?",
                "opcje": ["Zawsze 1", "Zawsze 0", "Tyle samo co p", "Tyle samo co ∼p"],
                "poprawna": 0,
                "podpowiedz": "Podstaw za p najpierw prawdę, a potem fałsz.",
                "wyjasnienie": (
                    "Dla p = 1 mamy 1 → 1, czyli prawdę. Dla p = 0 mamy 0 → 0, "
                    "też prawdę. Wynik to zawsze 1."
                ),
            },
            {
                "pytanie": "Dlaczego implikacja p → p jest zawsze prawdziwa?",
                "opcje": [
                    "Bo implikacja jest fałszywa tylko wtedy, gdy z prawdy wynika fałsz",
                    "Bo zdanie p jest zawsze prawdziwe",
                    "Bo implikacja jest prawdziwa tylko dla prawdziwych zdań",
                ],
                "poprawna": 0,
                "podpowiedz": "Zapisz implikację jako alternatywę ∼p ∨ p.",
                "wyjasnienie": (
                    "Implikacja zawodzi tylko w układzie prawda → fałsz. Tutaj obie strony "
                    "są tym samym zdaniem, więc taki układ nie występuje."
                ),
            },
        ],
    ),
    Law(
        slug="podwojne-przeczenie",
        nazwa="Prawo podwójnego przeczenia",
        kategoria="podstawowe",
        formula="∼∼p ≡ p",
        formula_ascii="~~p <-> p",
        lewa="∼∼p",
        prawa="p",
        po_ludzku=(
            "Dwa przeczenia stojące obok siebie znoszą się, tak jak dwa minusy "
            "w mnożeniu. Zdanie „nieprawda, że nieprawda, że p” mówi dokładnie to samo co p. "
            "Wartość logiczna się nie zmienia, zmienia się tylko zapis."
        ),
        przyklad="Jeżeli nie jest prawdą, że nie zdam, to zdam.",
        kroki=[
            Step(
                opis="Bierzemy lewą stronę prawa: dwa przeczenia przed zdaniem p.",
                reguła="założenie",
                przed="∼∼p",
                po="∼∼p",
            ),
            Step(
                opis="Do całej formuły dopisujemy podwójne przeczenie — wartość się nie zmienia.",
                reguła="podwojne-przeczenie",
                przed="∼∼p",
                po="∼∼∼∼p",
            ),
            Step(
                opis="Dwie pary przeczeń znoszą się i zostaje samo p. To prawa strona prawa.",
                reguła="podwojne-przeczenie",
                przed="∼∼∼∼p",
                po="p",
            ),
        ],
        czeste_bledy=[
            "Ktoś zdejmuje jedno przeczenie i czyta ∼∼p jako ∼p. Zdjąć trzeba oba.",
            "Ktoś skraca ∼p ∨ ∼p do p. Znoszą się tylko przeczenia stojące jedno pod drugim.",
        ],
        wizualizacja="chain",
        quiz=[
            {
                "pytanie": "Czym różni się wartość formuły ∼∼p od wartości p?",
                "opcje": [
                    "Niczzym — obie mają tę samą wartość",
                    "Jest odwrotna",
                    "∼∼p ma zawsze wartość 1",
                    "∼∼p ma zawsze wartość 0",
                ],
                "poprawna": 0,
                "podpowiedz": "Podstaw za p prawdę, a potem fałsz.",
                "wyjasnienie": (
                    "Dla p = 1 mamy ∼1 = 0, a potem ∼0 = 1. Dla p = 0 jest odwrotnie, "
                    "ale wynik znów równa się p."
                ),
            },
            {
                "pytanie": "Ile wynosi ∼∼p, gdy p jest prawdą?",
                "opcje": ["1", "0", "Zależy od zdania p"],
                "poprawna": 0,
                "podpowiedz": "Policz od środka: najpierw ∼p.",
                "wyjasnienie": "Dla p = 1 mamy ∼1 = 0, a potem ∼0 = 1. Wynik wraca do p.",
            },
        ],
    ),
]
