"""Treść praw dodatkowych: idempotencja i reguła podstawiania.

Wykład używa tych praw w przykładach przekształceń, ale nie należą one do listy
T1–T14. Strona pokazuje je w osobnej kategorii ``dodatkowe``, żeby nie mylić
numeracji czternastu praw podstawowych.

Uwaga o kolejności: ``kolejnosc`` porządkuje **moduły** (patrz ``laws.py``),
a nie pojedyncze prawa. Ten moduł ma numer 101, więc trzy prawa z listy ``LAWS``
trafiają na koniec nauki — po czternastu prawach T1–T14 (moduły 1–5).

Uwaga o regule podstawiania: to nie jest równoważność dwóch różnych formuł.
Pola ``lewa``, ``prawa`` i kroki opisują **przykład** zastosowania reguły
z wykładu. Sprawdzenie równoważności przechodzi, bo obie strony przykładu
są tautologiami.
"""

from __future__ import annotations

from app.logic.law_model import Law, Step

#: Prawa dodatkowe stoją po całej liście T1–T14.
kolejnosc = 101

LAWS: list[Law] = [
    Law(
        slug="idempotencja-alternatywy",
        nazwa="Prawo idempotencji alternatywy",
        kategoria="dodatkowe",
        formula="(p ∨ p) ≡ p",
        formula_ascii="(p | p) <-> p",
        lewa="p ∨ p",
        prawa="p",
        po_ludzku=(
            "Ktoś mówi: dziś pada deszcz albo dziś pada deszcz. "
            "Powiedział to samo dwa razy, więc wystarczy powiedzieć raz. "
            "Tak samo formuła p ∨ p mówi dokładnie tyle, co samo p. "
            "Powtarzanie tego samego zdania nic nie zmienia."
        ),
        przyklad=(
            "Ktoś mówi: idziemy do kina albo idziemy do kina. "
            "To zdanie znaczy dokładnie to samo, co: idziemy do kina."
        ),
        kroki=[
            Step(
                opis="Bierzemy lewą stronę prawa: to samo zdanie zapisane dwa razy.",
                reguła="założenie",
                przed="p ∨ p",
                po="p ∨ p",
            ),
            Step(
                opis="Drugie zdanie zapisujemy jako ∼∼p — to ta sama wartość logiczna.",
                reguła="podwojne-przeczenie",
                przed="p ∨ p",
                po="p ∨ ∼∼p",
            ),
            Step(
                opis="Wracamy do p: podwójne zaprzeczenie ∼∼p to dokładnie zdanie p.",
                reguła="podwojne-przeczenie",
                przed="p ∨ ∼∼p",
                po="p ∨ p",
            ),
            Step(
                opis="Widzimy dwa razy to samo zdanie p, więc skracamy je do jednego p.",
                reguła="idempotencja-alternatywy",
                przed="p ∨ p",
                po="p",
            ),
        ],
        czeste_bledy=[
            "Ktoś skraca p ∨ q do p. Powtórzone musi być to samo zdanie po obu stronach znaku ∨.",
            "Ktoś dodaje wartości i mówi, że p ∨ p to 2. W rachunku zdań liczą się tylko 1 i 0.",
            "Ktoś skraca ∼p ∨ ∼p do p. Powtórzone jest przeczenie, więc zostaje ∼p.",
        ],
        wizualizacja="chain",
        quiz=[
            {
                "pytanie": "Która formuła jest równoważna formule p ∨ p?",
                "opcje": ["p", "∼p", "∼p ∨ ∼p", "p ∧ ∼p"],
                "poprawna": 0,
                "podpowiedz": "Zapisz obie strony w tablicy prawdy.",
                "wyjasnienie": (
                    "Alternatywa dwóch takich samych zdań ma tę samą wartość co jedno z nich. "
                    "Dlatego p ∨ p to to samo co p."
                ),
            },
            {
                "pytanie": "Jaką wartość ma formuła p ∨ p, gdy p jest fałszem?",
                "opcje": ["0", "1", "Zależy od zdania p", "Tyle samo co ∼p"],
                "poprawna": 0,
                "podpowiedz": (
                    "Alternatywa jest prawdziwa wtedy, gdy choć jeden składnik jest prawdziwy."
                ),
                "wyjasnienie": (
                    "Dla p = 0 oba składniki są fałszywe, więc cała alternatywa ma wartość 0. "
                    "To ta sama wartość co p."
                ),
            },
            {
                "pytanie": "Co mówi prawo idempotencji alternatywy?",
                "opcje": [
                    "Powtórzone zdanie w alternatywie można zapisać raz",
                    "Zdanie i jego zaprzeczenie dają razem prawdę",
                    "Kolejność składników alternatywy nie zmienia wyniku",
                ],
                "poprawna": 0,
                "podpowiedz": "Porównaj p ∨ p z samym p.",
                "wyjasnienie": (
                    "Idempotencja znaczy „to samo działanie dwa razy”. Tutaj powtórzona "
                    "alternatywa zwija się do jednego zdania."
                ),
            },
        ],
    ),
    Law(
        slug="idempotencja-koniunkcji",
        nazwa="Prawo idempotencji koniunkcji",
        kategoria="dodatkowe",
        formula="(p ∧ p) ≡ p",
        formula_ascii="(p & p) <-> p",
        lewa="p ∧ p",
        prawa="p",
        po_ludzku=(
            "Ktoś obiecuje: posprzątam pokój i posprzątam pokój. "
            "Obiecuje dokładnie to samo, co jedno sprzątanie. "
            "Formuła p ∧ p mówi więc tyle, co samo p. "
            "Powtarzanie tego samego zdania nic tu nie zmienia."
        ),
        przyklad=("Ktoś mówi: kupię chleb i kupię chleb. Wystarczy powiedzieć raz: kupię chleb."),
        kroki=[
            Step(
                opis="Bierzemy lewą stronę prawa: to samo zdanie zapisane dwa razy.",
                reguła="założenie",
                przed="p ∧ p",
                po="p ∧ p",
            ),
            Step(
                opis="Drugie zdanie zapisujemy jako ∼∼p — to ta sama wartość logiczna.",
                reguła="podwojne-przeczenie",
                przed="p ∧ p",
                po="p ∧ ∼∼p",
            ),
            Step(
                opis="Wracamy do p: podwójne zaprzeczenie ∼∼p to dokładnie zdanie p.",
                reguła="podwojne-przeczenie",
                przed="p ∧ ∼∼p",
                po="p ∧ p",
            ),
            Step(
                opis="Widzimy dwa razy to samo zdanie p, więc skracamy je do jednego p.",
                reguła="idempotencja-koniunkcji",
                przed="p ∧ p",
                po="p",
            ),
        ],
        czeste_bledy=[
            "Ktoś skraca p ∧ q do p. Powtórzone musi być to samo zdanie po obu stronach znaku ∧.",
            "Ktoś myli koniunkcję z alternatywą i skraca p ∧ p do p ∨ p. To dwie różne formuły.",
            "Ktoś skraca ∼p ∧ ∼p do p. Powtórzone jest przeczenie, więc zostaje ∼p.",
        ],
        wizualizacja="chain",
        quiz=[
            {
                "pytanie": "Która formuła jest równoważna formule p ∧ p?",
                "opcje": ["p", "∼p", "p ∨ p", "p ∧ ∼p"],
                "poprawna": 0,
                "podpowiedz": "Sprawdź wartość formuły, gdy p jest fałszem.",
                "wyjasnienie": (
                    "Koniunkcja dwóch takich samych zdań ma tę samą wartość co jedno z nich. "
                    "Dlatego p ∧ p to to samo co p."
                ),
            },
            {
                "pytanie": "Jaką wartość ma formuła p ∧ p, gdy p jest prawdą?",
                "opcje": ["1", "0", "Zależy od zdania p", "Tyle samo co ∼p"],
                "poprawna": 0,
                "podpowiedz": (
                    "Koniunkcja jest prawdziwa tylko wtedy, gdy oba składniki są prawdziwe."
                ),
                "wyjasnienie": (
                    "Dla p = 1 oba składniki są prawdziwe, więc cała koniunkcja ma wartość 1. "
                    "To ta sama wartość co p."
                ),
            },
        ],
    ),
    Law(
        slug="podstawianie",
        nazwa="Reguła podstawiania",
        kategoria="dodatkowe",
        formula="((p → q) → (p ∧ q)) ≡ (∼(p → q) ∨ (p ∧ q))",
        formula_ascii="((p -> q) -> (p & q)) <-> (~(p -> q) | (p & q))",
        lewa="((p → q) → (p ∧ q)) ≡ (∼(p → q) ∨ (p ∧ q))",
        prawa="((p → q) → (p ∧ q)) ≡ (∼(p → q) ∨ (p ∧ q))",
        po_ludzku=(
            "Masz tautologię, czyli formułę prawdziwą przy każdym wartościowaniu. "
            "Reguła podstawiania pozwala wstawić pod zmienne dowolne formuły. "
            "Nowa formuła też jest wtedy tautologią. "
            "Nie musisz za każdym razem liczyć tablicy prawdy od nowa."
        ),
        przyklad=(
            "Ktoś mówi: jeżeli posprzątam pokój, to pójdziemy do kina. "
            "W miejsce zdania o sprzątaniu wolno wstawić dowolne inne zdanie."
        ),
        kroki=[
            Step(
                opis=(
                    "Bierzemy formułę z lewej strony: to wynik podstawienia "
                    "w prawie definiowania implikacji."
                ),
                reguła="założenie",
                przed="((p → q) → (p ∧ q)) ≡ (∼(p → q) ∨ (p ∧ q))",
                po="((p → q) → (p ∧ q)) ≡ (∼(p → q) ∨ (p ∧ q))",
            ),
            Step(
                opis="Bez podstawienia ten wzór to znane prawo: jeżeli p, to q, czyli nie p lub q.",
                reguła="podstawianie",
                przed="((p → q) → (p ∧ q)) ≡ (∼(p → q) ∨ (p ∧ q))",
                po="(p → q) ≡ (∼p ∨ q)",
            ),
            Step(
                opis="Pod zmienną p podstawiamy formułę p → q, a pod q formułę p ∧ q.",
                reguła="podstawianie",
                przed="(p → q) ≡ (∼p ∨ q)",
                po="((p → q) → (p ∧ q)) ≡ (∼(p → q) ∨ (p ∧ q))",
            ),
        ],
        czeste_bledy=[
            "Ktoś podstawia formułę pod jedną zmienną, a drugą zostawia. Podstawienie obejmuje "
            "wszystkie wystąpienia zmiennej.",
            "Ktoś wstawia pod tę samą zmienną dwie różne formuły w jednym podstawieniu. "
            "Jedna zmienna dostaje jedną formułę.",
            "Ktoś stosuje regułę do formuły, która nie jest tautologią, i dziwi się, że wynik "
            "nie jest tautologią.",
        ],
        wizualizacja="chain",
        quiz=[
            {
                "pytanie": "Co mówi reguła podstawiania?",
                "opcje": [
                    "Podstawienie w tautologii daje nową tautologię",
                    "Każdą formułę wolno zastąpić jej zaprzeczeniem",
                    "Zmienną wolno zastąpić tylko inną zmienną",
                ],
                "poprawna": 0,
                "podpowiedz": "Zastanów się, co się dzieje z wartościami formuły po podstawieniu.",
                "wyjasnienie": (
                    "Tautologia jest prawdziwa przy każdym wartościowaniu. Podstawienie formuł "
                    "pod zmienne nie psuje tej własności."
                ),
            },
            {
                "pytanie": (
                    "Formuła p → p jest tautologią. Co powstanie po podstawieniu p := (q ∧ r)?"
                ),
                "opcje": [
                    "(q ∧ r) → (q ∧ r), czyli znowu tautologia",
                    "q → r, czyli formuła spełnialna",
                    "∼(q ∧ r), czyli kontrtautologia",
                ],
                "poprawna": 0,
                "podpowiedz": "Podstawiamy tę samą formułę w oba miejsca, w których stoi p.",
                "wyjasnienie": (
                    "Pod oba wystąpienia p wchodzi formuła q ∧ r. Powstaje (q ∧ r) → (q ∧ r), "
                    "a to nadal tautologia."
                ),
            },
            {
                "pytanie": "Czego nie wolno zrobić w jednym podstawieniu?",
                "opcje": [
                    "Dać pod jedną zmienną dwóch różnych formuł",
                    "Podstawić formuły zbudowanej z dwóch zmiennych",
                    "Podstawić formuły z przeczeniem",
                ],
                "poprawna": 0,
                "podpowiedz": "Jedna zmienna to jedno miejsce na formułę.",
                "wyjasnienie": (
                    "Podstawienie jest jednolitym wstawieniem: każde wystąpienie zmiennej "
                    "dostaje tę samą formułę."
                ),
            },
        ],
    ),
]
