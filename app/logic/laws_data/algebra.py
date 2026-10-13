"""Treść praw algebry logicznej: łączność, rozdzielność i przemienność.

Prawa T6–T11 z wykładu. Mówią, jak obchodzić się z nawiasami i kolejnością
składników w alternatywie oraz w koniunkcji. Kroki przekształceń korzystają
z praw z tego pliku oraz z ``podstawowe.py``.

Uwaga o kolejności: ``kolejnosc`` porządkuje **moduły** (patrz ``laws.py``),
a nie pojedyncze prawa. Ten moduł ma numer 3, więc sześć praw z listy ``LAWS``
trafia na pozycje 6–11 nauki — zaraz po prawach podstawowych (1–3)
i prawach o implikacji (4–5).
"""

from __future__ import annotations

from app.logic.law_model import Law, Step

#: Prawa T6–T11 stoją po prawach podstawowych i po prawach o implikacji.
kolejnosc = 3

LAWS: list[Law] = [
    Law(
        slug="lacznosc-alternatywy",
        nazwa="Prawo łączności alternatywy",
        kategoria="algebra",
        formula="((p ∨ q) ∨ r) ≡ (p ∨ (q ∨ r))",
        formula_ascii="((p | q) | r) <-> (p | (q | r))",
        lewa="(p ∨ q) ∨ r",
        prawa="p ∨ (q ∨ r)",
        po_ludzku=(
            "Trzy zdania połączone słowem „lub” dają ten sam wynik, "
            "niezależnie od nawiasów. "
            "Tak samo jest z dodawaniem: (1+2)+3 to dokładnie tyle samo co 1+(2+3). "
            "Nawias mówi tylko, którą parę łączymy najpierw. "
            "Dla alternatywy ta kolejność nie ma znaczenia."
        ),
        przyklad=(
            "Wybieram się na wycieczkę: pójdę w góry lub nad jezioro lub do lasu. "
            "Nie ma znaczenia, które dwa kierunki połączę najpierw."
        ),
        kroki=[
            Step(
                opis="Bierzemy lewą stronę prawa: najpierw łączy się p z q, a na końcu dochodzi r.",
                reguła="założenie",
                przed="(p ∨ q) ∨ r",
                po="(p ∨ q) ∨ r",
            ),
            Step(
                opis="W nawiasie zamieniamy p z q — w alternatywie kolejność nic nie zmienia.",
                reguła="przemiennosc-alternatywy",
                przed="(p ∨ q) ∨ r",
                po="(q ∨ p) ∨ r",
            ),
            Step(
                opis="Przesuwamy nawias w prawo: teraz najpierw łączy się p z r.",
                reguła="lacznosc-alternatywy",
                przed="(q ∨ p) ∨ r",
                po="q ∨ (p ∨ r)",
            ),
            Step(
                opis="Całą alternatywę przestawiamy tak, żeby q znalazło się na końcu.",
                reguła="przemiennosc-alternatywy",
                przed="q ∨ (p ∨ r)",
                po="(p ∨ r) ∨ q",
            ),
            Step(
                opis="Znowu przesuwamy nawias w prawo: teraz q łączy się z r.",
                reguła="lacznosc-alternatywy",
                przed="(p ∨ r) ∨ q",
                po="p ∨ (r ∨ q)",
            ),
            Step(
                opis="W nawiasie zamieniamy r z q i dochodzimy do prawej strony prawa.",
                reguła="przemiennosc-alternatywy",
                przed="p ∨ (r ∨ q)",
                po="p ∨ (q ∨ r)",
            ),
        ],
        czeste_bledy=[
            "Ktoś sądzi, że nawias zmienia wynik i że (p ∨ q) ∨ r to nie to samo "
            "co p ∨ (q ∨ r). Alternatywa łączy się niezależnie od nawiasów.",
            "Ktoś przenosi nawias, ale zmienia przy tym spójnik z ∨ na ∧. "
            "To już inna formuła o innej wartości.",
            "Ktoś myli łączność z przemiennością. Łączność przesuwa nawias, "
            "a przemienność zamienia miejscami całe składniki.",
        ],
        wizualizacja="gates",
        quiz=[
            {
                "pytanie": "Która formuła jest równoważna formule (p ∨ q) ∨ r?",
                "opcje": [
                    "p ∨ (q ∨ r)",
                    "(p ∧ q) ∧ r",
                    "p ∧ (q ∨ r)",
                    "(p → q) ∨ r",
                ],
                "poprawna": 0,
                "podpowiedz": "Popatrz, gdzie stoi nawias przed przekształceniem, a gdzie po nim.",
                "wyjasnienie": (
                    "Łączność alternatywy pozwala przesuwać nawias: "
                    "(p ∨ q) ∨ r to to samo co p ∨ (q ∨ r)."
                ),
            },
            {
                "pytanie": "Co mówi prawo łączności alternatywy?",
                "opcje": [
                    "Nawiasy można przesuwać bez zmiany wartości formuły",
                    "Alternatywę można zamienić na koniunkcję",
                    "Kolejność zdań zmienia wynik",
                ],
                "poprawna": 0,
                "podpowiedz": "Porównaj wynik obu formuł dla p i q prawdziwych, a r fałszywego.",
                "wyjasnienie": (
                    "Łączność dotyczy tylko nawiasów. Spójnik zostaje ten sam, "
                    "a wartość formuły się nie zmienia."
                ),
            },
            {
                "pytanie": "Które działanie w arytmetyce działa tak samo jak łączność alternatywy?",
                "opcje": ["Dodawanie", "Odejmowanie", "Dzielenie"],
                "poprawna": 0,
                "podpowiedz": "Sprawdź, czy (8−3)−2 to tyle samo co 8−(3−2).",
                "wyjasnienie": (
                    "Dodawanie jest łączne: (1+2)+3 daje tyle samo co 1+(2+3). "
                    "Odejmowanie i dzielenie łączne nie są."
                ),
            },
        ],
    ),
    Law(
        slug="lacznosc-koniunkcji",
        nazwa="Prawo łączności koniunkcji",
        kategoria="algebra",
        formula="((p ∧ q) ∧ r) ≡ (p ∧ (q ∧ r))",
        formula_ascii="((p & q) & r) <-> (p & (q & r))",
        lewa="(p ∧ q) ∧ r",
        prawa="p ∧ (q ∧ r)",
        po_ludzku=(
            "Trzy warunki połączone słowem „i” dają ten sam wynik, "
            "niezależnie od nawiasów. "
            "Kolejność, w jakiej łączymy warunki, nie zmienia tego, czy wszystkie zachodzą. "
            "To tak jak z dodawaniem: (1+2)+3 to tyle samo co 1+(2+3). "
            "Dlatego w koniunkcji nawias można przesuwać swobodnie."
        ),
        przyklad=(
            "Kupię bilet, gdy mam pieniądze i mam dokument i mam czas. "
            "Kolejność sprawdzania tych trzech warunków niczego nie zmienia."
        ),
        kroki=[
            Step(
                opis="Bierzemy lewą stronę prawa: najpierw łączy się p z q, a na końcu dochodzi r.",
                reguła="założenie",
                przed="(p ∧ q) ∧ r",
                po="(p ∧ q) ∧ r",
            ),
            Step(
                opis="W środku nawiasu zamieniamy p z q — kolejność w koniunkcji nic nie zmienia.",
                reguła="przemiennosc-koniunkcji",
                przed="(p ∧ q) ∧ r",
                po="(q ∧ p) ∧ r",
            ),
            Step(
                opis="Przesuwamy nawias w prawo: teraz najpierw łączy się p z r.",
                reguła="lacznosc-koniunkcji",
                przed="(q ∧ p) ∧ r",
                po="q ∧ (p ∧ r)",
            ),
            Step(
                opis="Całą koniunkcję przestawiamy tak, żeby q znalazło się na końcu.",
                reguła="przemiennosc-koniunkcji",
                przed="q ∧ (p ∧ r)",
                po="(p ∧ r) ∧ q",
            ),
            Step(
                opis="Znowu przesuwamy nawias w prawo: teraz q łączy się z r.",
                reguła="lacznosc-koniunkcji",
                przed="(p ∧ r) ∧ q",
                po="p ∧ (r ∧ q)",
            ),
            Step(
                opis="W nawiasie zamieniamy r z q i dochodzimy do prawej strony prawa.",
                reguła="przemiennosc-koniunkcji",
                przed="p ∧ (r ∧ q)",
                po="p ∧ (q ∧ r)",
            ),
        ],
        czeste_bledy=[
            "Ktoś przenosi nawias i zmienia przy tym spójnik z ∧ na ∨. "
            "Koniunkcja i alternatywa to różne spójniki.",
            "Ktoś myśli, że prawo działa tylko dla dwóch zdań. "
            "Koniunkcja łączy się dowolnie, także dla trzech i więcej zdań.",
            "Ktoś traktuje kolejność sprawdzania warunków w programie jak kolejność logiczną. "
            "W rachunku zdań liczy się tylko wartość, a nie moment sprawdzania.",
        ],
        wizualizacja="gates",
        quiz=[
            {
                "pytanie": "Która formuła jest równoważna formule (p ∧ q) ∧ r?",
                "opcje": [
                    "p ∧ (q ∧ r)",
                    "(p ∨ q) ∨ r",
                    "p ∨ (q ∧ r)",
                    "(p → q) ∧ r",
                ],
                "poprawna": 0,
                "podpowiedz": "Popatrz, gdzie stoi nawias przed przekształceniem, a gdzie po nim.",
                "wyjasnienie": (
                    "Łączność koniunkcji pozwala przesuwać nawias: "
                    "(p ∧ q) ∧ r to to samo co p ∧ (q ∧ r)."
                ),
            },
            {
                "pytanie": "Co mówi prawo łączności koniunkcji?",
                "opcje": [
                    "Nawiasy można przesuwać bez zmiany wartości formuły",
                    "Koniunkcję można zamienić na alternatywę",
                    "Kolejność zdań zmienia wynik",
                ],
                "poprawna": 0,
                "podpowiedz": "Sprawdź, kiedy koniunkcja jest prawdziwa. Porównaj nawiasowania.",
                "wyjasnienie": (
                    "Koniunkcja jest prawdziwa tylko wtedy, gdy wszystkie składniki są prawdziwe. "
                    "Nawias nie zmienia tego warunku."
                ),
            },
            {
                "pytanie": "Czym różni się łączność koniunkcji od łączności alternatywy?",
                "opcje": [
                    "Tylko spójnikiem: raz łączymy słowem „i”, raz słowem „lub”",
                    "Liczbą zdań: koniunkcja działa tylko dla dwóch zdań",
                    "Niczym, to jedno prawo",
                ],
                "poprawna": 0,
                "podpowiedz": "Porównaj oba wzory znak po znaku.",
                "wyjasnienie": (
                    "Oba prawa przesuwają nawias. Różni je tylko spójnik: "
                    "w koniunkcji jest to ∧, a w alternatywie ∨."
                ),
            },
        ],
    ),
    Law(
        slug="rozdzielnosc-1",
        nazwa="I prawo rozdzielności",
        kategoria="algebra",
        formula="((p ∨ q) ∧ r) ≡ ((p ∧ r) ∨ (q ∧ r))",
        formula_ascii="((p | q) & r) <-> ((p & r) | (q & r))",
        lewa="(p ∨ q) ∧ r",
        prawa="(p ∧ r) ∨ (q ∧ r)",
        po_ludzku=(
            "Mamy warunek: zachodzi p lub q, a do tego musi zachodzić r. "
            "Koniunkcja rozdziela się wtedy na oba składniki alternatywy. "
            "To tak, jakbyśmy mnożyli nawias: r wchodzi do środka "
            "i łączy się z każdym składnikiem osobno. "
            "Wynik to (p i r) lub (q i r)."
        ),
        przyklad=(
            "Mama da kieszonkowe, gdy posprzątam pokój lub umyję naczynia, "
            "a przy tym odrobię lekcje. "
            "To samo znaczy: odrobię lekcje i posprzątam pokój, "
            "albo odrobię lekcje i umyję naczynia."
        ),
        kroki=[
            Step(
                opis="Bierzemy lewą stronę prawa: alternatywa p ∨ q jest stoi w nawiasie z r.",
                reguła="założenie",
                przed="(p ∨ q) ∧ r",
                po="(p ∨ q) ∧ r",
            ),
            Step(
                opis="Przestawiamy strony koniunkcji — jej wynik się nie zmienia.",
                reguła="przemiennosc-koniunkcji",
                przed="(p ∨ q) ∧ r",
                po="r ∧ (p ∨ q)",
            ),
            Step(
                opis="Rozdzielamy koniunkcję na oba składniki alternatywy.",
                reguła="rozdzielnosc-1",
                przed="r ∧ (p ∨ q)",
                po="(r ∧ p) ∨ (r ∧ q)",
            ),
            Step(
                opis="W pierwszym nawiasie zamieniamy strony koniunkcji.",
                reguła="przemiennosc-koniunkcji",
                przed="(r ∧ p) ∨ (r ∧ q)",
                po="(p ∧ r) ∨ (r ∧ q)",
            ),
            Step(
                opis="W drugim nawiasie też zamieniamy strony i dochodzimy do prawej strony prawa.",
                reguła="przemiennosc-koniunkcji",
                przed="(p ∧ r) ∨ (r ∧ q)",
                po="(p ∧ r) ∨ (q ∧ r)",
            ),
        ],
        czeste_bledy=[
            "Ktoś rozdziela ∧ po ∨ i zapomina rozdzielić oba składniki. "
            "Koniunkcja musi trafić i do p, i do q.",
            "Ktoś rozdziela tylko pierwszy składnik i pisze (p ∧ r) ∨ q. "
            "Oba składniki alternatywy trzeba połączyć z r.",
            "Ktoś myli oba prawa rozdzielności i rozdziela ∨ po ∧ zamiast ∧ po ∨. "
            "Wtedy wychodzi inna formuła.",
        ],
        wizualizacja="sets",
        quiz=[
            {
                "pytanie": "Która formuła jest równoważna formule (p ∨ q) ∧ r?",
                "opcje": [
                    "(p ∧ r) ∨ (q ∧ r)",
                    "(p ∨ r) ∧ (q ∨ r)",
                    "(p ∧ q) ∨ r",
                    "(p ∧ r) ∧ (q ∧ r)",
                ],
                "poprawna": 0,
                "podpowiedz": "Koniunkcja z r musi wejść do obu składników alternatywy.",
                "wyjasnienie": (
                    "I prawo rozdzielności: (p ∨ q) ∧ r to to samo co (p ∧ r) ∨ (q ∧ r). "
                    "Koniunkcja rozdziela się na oba składniki."
                ),
            },
            {
                "pytanie": "Co robi I prawo rozdzielności?",
                "opcje": [
                    "Rozdziela koniunkcję na oba składniki alternatywy",
                    "Zamienia koniunkcję na alternatywę bez zmiany nawiasu",
                    "Usuwa nawias i zostawia sam spójnik",
                ],
                "poprawna": 0,
                "podpowiedz": "Policz, ile nawiasów jest po lewej stronie, a ile po prawej.",
                "wyjasnienie": (
                    "Po lewej stronie mamy jedną koniunkcję z nawiasem, "
                    "a po prawej dwie koniunkcje połączone alternatywą."
                ),
            },
            {
                "pytanie": "Które działanie w arytmetyce przypomina to prawo?",
                "opcje": [
                    "Mnożenie liczby przez nawias z sumą",
                    "Dodawanie dwóch liczb",
                    "Dzielenie przez jedną liczbę",
                ],
                "poprawna": 0,
                "podpowiedz": "Popatrz na wzór a · (b + c) = a · b + a · c.",
                "wyjasnienie": (
                    "Mnożenie przez nawias rozdziela się na oba składniki sumy. "
                    "Tak samo koniunkcja rozdziela się na oba składniki alternatywy."
                ),
            },
        ],
    ),
    Law(
        slug="rozdzielnosc-2",
        nazwa="II prawo rozdzielności",
        kategoria="algebra",
        formula="((p ∧ q) ∨ r) ≡ ((p ∨ r) ∧ (q ∨ r))",
        formula_ascii="((p & q) | r) <-> ((p | r) & (q | r))",
        lewa="(p ∧ q) ∨ r",
        prawa="(p ∨ r) ∧ (q ∨ r)",
        po_ludzku=(
            "Mamy warunek: zachodzą razem p i q, albo zachodzi samo r. "
            "Możemy to zapisać inaczej: p lub r, a jednocześnie q lub r. "
            "W zwykłej arytmetyce taka zamiana nie działa. "
            "Na przykład 2·3+4 to nie to samo co (2+4)·(3+4). "
            "W logice taka zamiana jest poprawna."
        ),
        przyklad=(
            "Weekend się uda, gdy będzie słońce i będę mieć wolne, albo gdy pojedziemy do babci. "
            "To samo znaczy: uda się, gdy będzie słońce lub pojedziemy do babci, "
            "i uda się, gdy będę mieć wolne lub pojedziemy do babci."
        ),
        kroki=[
            Step(
                opis="Bierzemy lewą stronę prawa: koniunkcja p ∧ q stoi w nawiasie razem z r.",
                reguła="założenie",
                przed="(p ∧ q) ∨ r",
                po="(p ∧ q) ∨ r",
            ),
            Step(
                opis="Przestawiamy strony alternatywy — jej wynik się nie zmienia.",
                reguła="przemiennosc-alternatywy",
                przed="(p ∧ q) ∨ r",
                po="r ∨ (p ∧ q)",
            ),
            Step(
                opis="Rozdzielamy alternatywę na oba składniki koniunkcji.",
                reguła="rozdzielnosc-2",
                przed="r ∨ (p ∧ q)",
                po="(r ∨ p) ∧ (r ∨ q)",
            ),
            Step(
                opis="W pierwszym nawiasie zamieniamy strony alternatywy.",
                reguła="przemiennosc-alternatywy",
                przed="(r ∨ p) ∧ (r ∨ q)",
                po="(p ∨ r) ∧ (r ∨ q)",
            ),
            Step(
                opis="W drugim nawiasie też zamieniamy strony i dochodzimy do prawej strony prawa.",
                reguła="przemiennosc-alternatywy",
                przed="(p ∨ r) ∧ (r ∨ q)",
                po="(p ∨ r) ∧ (q ∨ r)",
            ),
        ],
        czeste_bledy=[
            "Ktoś rozdziela ∨ po ∧ i zapomina rozdzielić oba składniki. "
            "Alternatywa musi trafić i do p, i do q.",
            "Ktoś przenosi ten wzór do arytmetyki i sądzi, że skoro a·(b+c) = a·b+a·c, "
            "to tak samo wolno zrobić w drugą stronę. W logice wolno, w arytmetyce nie.",
            "Ktoś gubi r po jednej ze stron i zostawia tylko (p ∨ r). "
            "Po prawej stronie są dwa nawiasy połączone koniunkcją.",
        ],
        wizualizacja="sets",
        quiz=[
            {
                "pytanie": "Która formuła jest równoważna formule (p ∧ q) ∨ r?",
                "opcje": [
                    "(p ∨ r) ∧ (q ∨ r)",
                    "(p ∧ r) ∨ (q ∧ r)",
                    "(p ∨ q) ∧ r",
                    "(p ∨ r) ∨ (q ∨ r)",
                ],
                "poprawna": 0,
                "podpowiedz": "Alternatywa z r musi wejść do obu składników koniunkcji.",
                "wyjasnienie": (
                    "II prawo rozdzielności: (p ∧ q) ∨ r to to samo co (p ∨ r) ∧ (q ∨ r). "
                    "Alternatywa rozdziela się na oba składniki."
                ),
            },
            {
                "pytanie": "Czym różni się II prawo rozdzielności od I?",
                "opcje": [
                    "Odwraca role spójników: alternatywa rozdziela się po koniunkcji",
                    "Niczym, oba mówią to samo",
                    "Działa tylko dla dwóch zdań, a I dla trzech",
                ],
                "poprawna": 0,
                "podpowiedz": "Porównaj, który spójnik stoi w głównym nawiasie w obu wzorach.",
                "wyjasnienie": (
                    "W I prawie koniunkcja rozdziela się po alternatywie. "
                    "W II prawie jest odwrotnie: alternatywa rozdziela się po koniunkcji."
                ),
            },
            {
                "pytanie": "Dlaczego tego wzoru nie wolno przenieść do zwykłej arytmetyki?",
                "opcje": [
                    "Bo 2·3+4 to nie to samo co (2+4)·(3+4)",
                    "Bo liczby trzeba dodawać w kolejności od najmniejszej",
                    "Bo mnożenie jest łączne tylko dla dwóch liczb",
                ],
                "poprawna": 0,
                "podpowiedz": "Policz oba wyrażenia dla prostych liczb.",
                "wyjasnienie": (
                    "Po lewej stronie wychodzi 10, a po prawej 42. "
                    "W logice taka zamiana jest poprawna, w arytmetyce nie."
                ),
            },
        ],
    ),
    Law(
        slug="przemiennosc-alternatywy",
        nazwa="Prawo przemienności alternatywy",
        kategoria="algebra",
        formula="(p ∨ q) ≡ (q ∨ p)",
        formula_ascii="(p | q) <-> (q | p)",
        lewa="p ∨ q",
        prawa="q ∨ p",
        po_ludzku=(
            "Dwa zdania połączone słowem „lub” można spokojnie zamienić miejscami. "
            "Czy powiem „pada albo jest zimno”, czy „jest zimno albo pada”, "
            "sens jest ten sam. "
            "Uwaga: z implikacją tak nie wolno. "
            "Zdanie „jeżeli p, to q” nie znaczy tego samego co „jeżeli q, to p”."
        ),
        przyklad=(
            "Pada deszcz albo świeci słońce. "
            "To samo słyszymy w zdaniu: świeci słońce albo pada deszcz."
        ),
        kroki=[
            Step(
                opis="Bierzemy lewą stronę prawa: p lub q.",
                reguła="założenie",
                przed="p ∨ q",
                po="p ∨ q",
            ),
            Step(
                opis="Zdanie p zapisujemy jako ∼∼p — to ta sama wartość.",
                reguła="podwojne-przeczenie",
                przed="p ∨ q",
                po="∼∼p ∨ q",
            ),
            Step(
                opis="Zamieniamy strony alternatywy miejscami.",
                reguła="przemiennosc-alternatywy",
                przed="∼∼p ∨ q",
                po="q ∨ ∼∼p",
            ),
            Step(
                opis="Zdejmujemy podwójne przeczenie i zostaje q ∨ p, czyli prawa strona prawa.",
                reguła="podwojne-przeczenie",
                przed="q ∨ ∼∼p",
                po="q ∨ p",
            ),
        ],
        czeste_bledy=[
            "Ktoś przenosi przemienność na implikację i pisze (p → q) ≡ (q → p). "
            "To błąd: z deszczu wynika mokra ulica, ale mokra ulica nie zawsze znaczy deszcz.",
            "Ktoś zamienia przy przestawianiu spójnik z ∨ na ∧. "
            "Koniunkcja ma inne wartości niż alternatywa.",
        ],
        wizualizacja="gates",
        quiz=[
            {
                "pytanie": "Która formuła jest równoważna formule p ∨ q?",
                "opcje": ["q ∨ p", "q ∧ p", "p → q", "∼p ∨ q"],
                "poprawna": 0,
                "podpowiedz": "Wystarczy zamienić składniki miejscami.",
                "wyjasnienie": (
                    "Przemienność alternatywy: p ∨ q to to samo co q ∨ p. "
                    "Kolejność składników nie zmienia wartości formuły."
                ),
            },
            {
                "pytanie": "Dla którego spójnika NIE wolno zamieniać stron miejscami?",
                "opcje": ["Dla implikacji", "Dla alternatywy", "Dla koniunkcji"],
                "poprawna": 0,
                "podpowiedz": "Pomyśl o zdaniu „jeżeli pada, to ulica jest mokra”.",
                "wyjasnienie": (
                    "Implikacja nie jest przemienna. Z faktu, że ulica jest mokra, "
                    "nie wynika, że pada deszcz."
                ),
            },
            {
                "pytanie": "Co mówi prawo przemienności alternatywy?",
                "opcje": [
                    "Kolejność składników nie zmienia wartości formuły",
                    "Alternatywę można zamienić na koniunkcję",
                    "Każda alternatywa jest tautologią",
                ],
                "poprawna": 0,
                "podpowiedz": "Podstaw różne wartości za p i q i porównaj obie strony.",
                "wyjasnienie": (
                    "Alternatywa jest prawdziwa, gdy choć jeden składnik jest prawdziwy. "
                    "Kolejność patrzenia na składniki nic tu nie zmienia."
                ),
            },
        ],
    ),
    Law(
        slug="przemiennosc-koniunkcji",
        nazwa="Prawo przemienności koniunkcji",
        kategoria="algebra",
        formula="(p ∧ q) ≡ (q ∧ p)",
        formula_ascii="(p & q) <-> (q & p)",
        lewa="p ∧ q",
        prawa="q ∧ p",
        po_ludzku=(
            "Dwa warunki połączone słowem „i” można zamienić miejscami. "
            "Czy powiem „mam czas i mam siłę”, czy „mam siłę i mam czas” — "
            "znaczy to samo. "
            "Oba warunki muszą zachodzić jednocześnie, "
            "a kolejność ich wymieniania nic nie zmienia. "
            "Z implikacją tak nie wolno: kolejność stron zmienia sens zdania."
        ),
        przyklad=(
            "Zjem obiad, gdy odgrzeję zupę i nakryję do stołu. "
            "To samo znaczy: nakryję do stołu i odgrzeję zupę."
        ),
        kroki=[
            Step(
                opis="Bierzemy lewą stronę prawa: p i q.",
                reguła="założenie",
                przed="p ∧ q",
                po="p ∧ q",
            ),
            Step(
                opis="Zdanie p zapisujemy jako ∼∼p — to ta sama wartość.",
                reguła="podwojne-przeczenie",
                przed="p ∧ q",
                po="∼∼p ∧ q",
            ),
            Step(
                opis="Zamieniamy strony koniunkcji miejscami.",
                reguła="przemiennosc-koniunkcji",
                przed="∼∼p ∧ q",
                po="q ∧ ∼∼p",
            ),
            Step(
                opis="Zdejmujemy podwójne przeczenie i zostaje q ∧ p, czyli prawa strona prawa.",
                reguła="podwojne-przeczenie",
                przed="q ∧ ∼∼p",
                po="q ∧ p",
            ),
        ],
        czeste_bledy=[
            "Ktoś twierdzi, że kolejność warunków zmienia wynik koniunkcji. "
            "Oba warunki muszą zachodzić jednocześnie, więc kolejność nie ma znaczenia.",
            "Ktoś przenosi przemienność na implikację i pisze (p → q) ≡ (q → p). "
            "Implikacja nie jest przemienna.",
            "Ktoś zamienia przy przestawianiu spójnik z ∧ na ∨. "
            "Wtedy wychodzi formuła o innych wartościach.",
        ],
        wizualizacja="gates",
        quiz=[
            {
                "pytanie": "Która formuła jest równoważna formule p ∧ q?",
                "opcje": ["q ∧ p", "q ∨ p", "p → q", "∼p ∧ q"],
                "poprawna": 0,
                "podpowiedz": "Wystarczy zamienić składniki miejscami.",
                "wyjasnienie": (
                    "Przemienność koniunkcji: p ∧ q to to samo co q ∧ p. "
                    "Kolejność składników nie zmienia wartości formuły."
                ),
            },
            {
                "pytanie": "Kiedy koniunkcja p ∧ q jest prawdziwa?",
                "opcje": [
                    "Gdy oba zdania są prawdziwe",
                    "Gdy choć jedno zdanie jest prawdziwe",
                    "Gdy oba zdania są fałszywe",
                ],
                "poprawna": 0,
                "podpowiedz": "Sprawdź cztery wartościowania p i q.",
                "wyjasnienie": (
                    "Koniunkcja jest prawdziwa tylko przy układzie prawda i prawda. "
                    "Ta sama zasada obowiązuje po zamianie stron."
                ),
            },
            {
                "pytanie": "Co mówi prawo przemienności koniunkcji?",
                "opcje": [
                    "Kolejność składników nie zmienia wartości formuły",
                    "Koniunkcję można zamienić na alternatywę",
                    "Każda koniunkcja jest tautologią",
                ],
                "poprawna": 0,
                "podpowiedz": "Podstaw różne wartości za p i q i porównaj obie strony.",
                "wyjasnienie": (
                    "Koniunkcja wymaga prawdy po obu stronach. "
                    "Kolejność sprawdzania składników niczego nie zmienia."
                ),
            },
        ],
    ),
]
