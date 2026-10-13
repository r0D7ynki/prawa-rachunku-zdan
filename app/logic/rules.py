"""Rejestr reguł wnioskowania z wykładu 2 (karta PRZ-090).

Jedno źródło prawdy dla strony ``/reguly`` i dla kart, które wołają regułę po kodzie
(dowód wprost i nie wprost — karta PRZ-091). Treść pochodzi z ``docs/TRESC-WYKLAD2.md``,
sekcja „2. Reguły wnioskowania”: nic nie jest tu dopisane poza przykładami dla trzech
reguł dodatkowych (DM1, DM2, KP), których tabela wykładu nie ma.

Notacja jest ta sama co w wykładzie: ``∼``, ``∧``, ``∨``, ``→``, ``≡``. W polach
``przeslanki``, ``wniosek`` i ``wnioski_dodatkowe`` stoją **metazmienne** ``Φ``, ``Ψ``,
``Θ`` — to dowolne formuły, a nie zmienne zdaniowe. Parser (``app.logic.formula``)
przyjmuje tylko nazwy ASCII, więc te napisy rysuje dopiero strona
(``app/blueprints/reguly.py``); przez ``formula.to_html`` idą z kolei ``tautologia``
i ``tautologie_dodatkowe``, bo tam są zwykłe zmienne ``p``, ``q``.

Dwie reguły mają po dwie wersje zapisu. Dla **OK** wykład podaje dwa wnioski
(``Φ ∧ Ψ ⊢ Φ`` oraz ``Φ ∧ Ψ ⊢ Ψ``) i dwie tautologie, dla **OR** — dwa wnioski
(``Φ ≡ Ψ ⊢ Φ → Ψ`` oraz ``Φ ≡ Ψ ⊢ Ψ → Φ``) i jedną wspólną tautologię. Trzymamy je
w osobnych polach (``wnioski_dodatkowe``, ``tautologie_dodatkowe``), żeby każde pole
było pojedynczym wzorem z tabeli wykładu, a nie sklejoną listą.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Typ reguły: pierwotna albo dodatkowa (podział z tabel wykładu).
PIERWOTNA = "pierwotna"
DODATKOWA = "dodatkowa"


@dataclass(frozen=True)
class Rule:
    """Jedna reguła wnioskowania.

    ``przeslanki`` i ``wniosek`` zapisujemy metazmiennymi, dokładnie jak wykład.
    ``tautologia`` to wzór, który dowodzi poprawności reguły — ma zwykłe zmienne
    ``p``, ``q``, więc parsuje się i jest tautologią (``truth.is_tautology``).
    Pola ``wnioski_dodatkowe`` i ``tautologie_dodatkowe`` są puste u ośmiu reguł;
    wypełniają je tylko OK i OR, które wykład podaje w dwóch wersjach.
    """

    kod: str
    nazwa: str
    pelna_nazwa: str
    typ: str
    przeslanki: list[str]
    wniosek: str
    tautologia: str
    przyklad: str
    opis: str
    wnioski_dodatkowe: list[str] = field(default_factory=list)
    tautologie_dodatkowe: list[str] = field(default_factory=list)


#: Reguły w kolejności z wykładu: najpierw siedem pierwotnych, potem trzy dodatkowe.
#: Każdy przykład (poza DM1, DM2 i KP) jest przepisany z kolumny „Przykład” tabeli.
_RULES: list[Rule] = [
    Rule(
        kod="RO",
        nazwa="Reguła odrywania",
        pelna_nazwa="Modus Ponens",
        typ=PIERWOTNA,
        przeslanki=["Φ → Ψ", "Φ"],
        wniosek="Ψ",
        tautologia="((p → q) ∧ p) → q",
        przyklad="Jeżeli pada śnieg, to jest zimno. Pada śnieg. Zatem jest zimno.",
        opis=(
            "Z implikacji i jej poprzednika wynika następnik. "
            "To najczęściej używana reguła w dowodach."
        ),
    ),
    Rule(
        kod="OK",
        nazwa="Opuszczanie koniunkcji",
        pelna_nazwa="",
        typ=PIERWOTNA,
        przeslanki=["Φ ∧ Ψ"],
        wniosek="Φ",
        tautologia="((p ∧ q) → p)",
        przyklad="Pada śnieg i jest zimno. Zatem pada śnieg.",
        opis="Z koniunkcji wolno wyciągnąć każdy człon. Najpierw lewy, a potem prawy.",
        wnioski_dodatkowe=["Ψ"],
        tautologie_dodatkowe=["((p ∧ q) → q)"],
    ),
    Rule(
        kod="DK",
        nazwa="Dołączanie koniunkcji",
        pelna_nazwa="",
        typ=PIERWOTNA,
        przeslanki=["Φ", "Ψ"],
        wniosek="Φ ∧ Ψ",
        tautologia="(p → (q → (p ∧ q)))",
        przyklad="Pada śnieg. Jest zimno. Zatem pada śnieg i jest zimno.",
        opis=(
            "Dwie prawdziwe formuły wolno połączyć spójnikiem „i”. "
            "Wniosek jest prawdziwy tylko wtedy, gdy prawdziwe są obie przesłanki."
        ),
    ),
    Rule(
        kod="OA",
        nazwa="Opuszczanie alternatywy",
        pelna_nazwa="",
        typ=PIERWOTNA,
        przeslanki=["Φ ∨ Ψ", "∼Φ"],
        wniosek="Ψ",
        tautologia="((p ∨ q) ∧ ∼p) → q",
        przyklad="Pada śnieg lub jest zimno. Nie pada śnieg. Zatem jest zimno.",
        opis=(
            "Znamy alternatywę i wiemy, że pierwszy człon jest fałszywy. "
            "Prawdziwy musi być więc drugi."
        ),
    ),
    Rule(
        kod="DA",
        nazwa="Dołączanie alternatywy",
        pelna_nazwa="",
        typ=PIERWOTNA,
        przeslanki=["Φ"],
        wniosek="Φ ∨ Ψ",
        tautologia="p → (p ∨ q)",
        przyklad="Pada śnieg. Zatem pada śnieg lub jest zimno.",
        opis=(
            "Z jednej prawdziwej formuły wolno zrobić alternatywę z dowolną drugą formułą. "
            "Alternatywa jest słabsza od swojego członu."
        ),
    ),
    Rule(
        kod="DR",
        nazwa="Dołączanie równoważności",
        pelna_nazwa="",
        typ=PIERWOTNA,
        przeslanki=["Φ → Ψ", "Ψ → Φ"],
        wniosek="Φ ≡ Ψ",
        tautologia="((p → q) ∧ (q → p)) → (p ≡ q)",
        przyklad=(
            "Jeżeli pada śnieg, to jest zimno, i odwrotnie. "
            "Zatem pada śnieg wtedy i tylko wtedy, gdy jest zimno."
        ),
        opis="Dwie implikacje o przeciwnych kierunkach sklejamy w jedną równoważność.",
    ),
    Rule(
        kod="OR",
        nazwa="Opuszczanie równoważności",
        pelna_nazwa="",
        typ=PIERWOTNA,
        przeslanki=["Φ ≡ Ψ"],
        wniosek="Φ → Ψ",
        tautologia="(p ≡ q) → ((p → q) ∧ (q → p))",
        przyklad=(
            "Pada śnieg wtedy i tylko wtedy, gdy jest zimno. "
            "Zatem jeżeli pada śnieg, to jest zimno."
        ),
        opis=(
            "Z równoważności wynikają obie implikacje: w prawo i w lewo. "
            "Jedna tautologia dowodzi obu."
        ),
        wnioski_dodatkowe=["Ψ → Φ"],
    ),
    Rule(
        kod="DM1",
        nazwa="I prawo de Morgana",
        pelna_nazwa="",
        typ=DODATKOWA,
        przeslanki=["∼(Φ ∨ Ψ)"],
        wniosek="∼Φ ∧ ∼Ψ",
        tautologia="∼(p ∨ q) → (∼p ∧ ∼q)",
        przyklad="Nieprawda, że pada śnieg lub jest zimno. Zatem nie pada śnieg i nie jest zimno.",
        opis=(
            "Zaprzeczenie alternatywy to koniunkcja zaprzeczeń. "
            "Reguła zamienia „lub” na „i” i zaprzecza oba człony."
        ),
    ),
    Rule(
        kod="DM2",
        nazwa="II prawo de Morgana",
        pelna_nazwa="",
        typ=DODATKOWA,
        przeslanki=["∼Φ ∧ ∼Ψ"],
        wniosek="∼(Φ ∨ Ψ)",
        tautologia="(∼p ∧ ∼q) → ∼(p ∨ q)",
        przyklad="Nie pada śnieg i nie jest zimno. Zatem nieprawda, że pada śnieg lub jest zimno.",
        opis=(
            "Ta reguła działa w drugą stronę niż DM1. "
            "Z dwóch zaprzeczeń robi jedno zaprzeczenie alternatywy."
        ),
    ),
    Rule(
        kod="KP",
        nazwa="Prawo kontrapozycji",
        pelna_nazwa="",
        typ=DODATKOWA,
        przeslanki=["Φ → Ψ"],
        wniosek="∼Ψ → ∼Φ",
        tautologia="(p → q) → (∼q → ∼p)",
        przyklad=(
            "Jeżeli pada śnieg, to jest zimno. Zatem jeżeli nie jest zimno, to nie pada śnieg."
        ),
        opis=(
            "Implikację wolno zastąpić jej kontrapozycją. "
            "Zmieniamy strony i zaprzeczamy oba człony."
        ),
    ),
]

#: Kod → reguła. Kody są unikalne — pilnuje tego ``tests/test_rules.py``.
_BY_CODE: dict[str, Rule] = {regula.kod: regula for regula in _RULES}


def rules() -> list[Rule]:
    """Zwraca reguły w kolejności z wykładu: pierwotne, potem dodatkowe.

    Kopia listy — wołający nie zmieni rejestru.
    """
    return list(_RULES)


def get(kod: str) -> Rule | None:
    """Zwraca regułę o podanym kodzie (``"RO"``) albo ``None``, gdy kodu nie ma.

    Kod porównujemy bez wielkości liter i bez spacji wokół, więc ``get("ro")``
    i ``get(" RO ")`` dają tę samą regułę.
    """
    return _BY_CODE.get(kod.strip().upper())
