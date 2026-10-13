"""Dowody założeniowe z wykładu 2 (karta PRZ-091).

Ten moduł jest dla dowodów tym, czym ``app.logic.rules`` dla reguł wnioskowania:
trzyma **dane** w kolejności z wykładu, a nie logikę dowodzenia. Źródłem prawdy jest
``docs/TRESC-WYKLAD2.md``, sekcje „3. Dowód założeniowy wprost”, „4. Dowód założeniowy
nie wprost” i „5. Niepoprawne rozumowania i kontrprzykład”. Wiersze dowodów A–F są
przepisane z tabel wykładu wiersz po wierszu — numery, formuły i uzasadnienia.

Dowód to lista wierszy. Każdy wiersz mówi, **z czego** powstał: pole ``z`` trzyma numery
wierszy użytych w tym kroku (puste przy założeniach, bo one niczego nie wyprowadzają).
Dzięki temu widok narysuje strzałkę od tych wierszy do nowego wiersza, a test sprawdzi,
że każdy numer istnieje w tym samym dowodzie.

Rodzaje dowodów (pole ``Proof.rodzaj``):

* ``RODZAJ_WPROST`` — wypisujemy założenia i tworzymy kolejne wiersze regułami,
* ``RODZAJ_NIE_WPROST`` — do założeń dokładamy zanegowaną tezę i szukamy sprzeczności,
* ``RODZAJ_WIELOKROTNE`` — dowód nie wprost z dodatkowymi założeniami (wiersze 4.1–5.4),
  rozpisany na dwa przypadki.

Wiersz „Sprzeczność 5, 7” zamyka dowód nie wprost: jego formuła nie jest formułą, więc
``is_contradiction`` rozpoznaje go po napisie, a pole ``z`` wskazuje parę wierszy, które
sobie przeczą. Tę samą informację pokazuje strona (podświetlenie obu wierszy).
"""

from __future__ import annotations

from dataclasses import dataclass

#: Uzasadnienia wierszy, które niczego nie wyprowadzają — stoją wprost z wykładu.
ZALOZENIE = "Założenie"
Z_DOW_NIE_WPROST = "Z dow. nie wprost"
DODATKOWE_ZALOZENIE = "Dodatkowe założenie"

#: Uzasadnienia bez wskazania innych wierszy: ``z`` takich wierszy jest puste.
UZASADNIENIA_BEZ_Z = (ZALOZENIE, Z_DOW_NIE_WPROST, DODATKOWE_ZALOZENIE)

#: Napis, od którego zaczyna się formuła wiersza sprzeczności („Sprzeczność 5, 7”).
SPRZECZNOSC = "Sprzeczność"

#: Rodzaje dowodów. Trzymamy je jako stałe, żeby widok i testy nie powtarzały napisów.
RODZAJ_WPROST = "wprost"
RODZAJ_NIE_WPROST = "nie-wprost"
RODZAJ_WIELOKROTNE = "wielokrotne"


@dataclass(frozen=True)
class ProofLine:
    """Jeden wiersz dowodu, dokładnie jak w tabeli wykładu.

    ``z`` to numery wierszy, z których ten wiersz korzysta (puste przy założeniach).
    ``formula`` wiersza sprzeczności to napis „Sprzeczność 5, 7” — nie formuła.
    """

    nr: str  # "1", "4.1"
    formula: str  # "(p ∨ q) → (r ∨ s)"
    uzasadnienie: str  # "RO 2, 3" albo "Założenie" albo "Sprzeczność 5, 7"
    z: list[str]  # numery wierszy, z których korzysta: ["2", "3"]


@dataclass(frozen=True)
class Proof:
    """Cały dowód: tytuł, rodzaj, teza i kolejne wiersze."""

    id: str  # "A" … "F"
    tytul: str
    rodzaj: str  # "wprost" | "nie-wprost" | "wielokrotne"
    teza: str  # formuła tezy do pokazania
    wiersze: list[ProofLine]
    opis: str


#: Dowód A — dowód wprost. Pierwsze dwa wiersze to założenia, potem dwie implikacje
#: rozdzielone regułą OK, a wiersze 5 i 6 powstają przez RO.
_DOWOD_A = Proof(
    id="A",
    tytul="Przechodniość implikacji",
    rodzaj=RODZAJ_WPROST,
    teza="((p → q) ∧ (q → r)) → (p → r)",
    opis=(
        "Jeżeli pierwsze zdanie pociąga drugie, a drugie pociąga trzecie, "
        "to pierwsze pociąga trzecie."
    ),
    wiersze=[
        ProofLine("1", "(p → q) ∧ (q → r)", ZALOZENIE, []),
        ProofLine("2", "p", ZALOZENIE, []),
        ProofLine("3", "p → q", "OK 1", ["1"]),
        ProofLine("4", "q → r", "OK 1", ["1"]),
        ProofLine("5", "q", "RO 2, 3", ["2", "3"]),
        ProofLine("6", "r", "RO 4, 5", ["4", "5"]),
    ],
)

#: Dowód B — dowód wprost z alternatywą. Wiersz 4 to kontrapozycja w akcji: z p → ∼s
#: i p dostajemy ∼s, a potem z alternatywy r ∨ s (wiersz 6) i ∼s zostaje samo r.
_DOWOD_B = Proof(
    id="B",
    tytul="Alternatywa w następniku",
    rodzaj=RODZAJ_WPROST,
    teza="(((p ∨ q) → (r ∨ s)) ∧ (p → ∼s) ∧ p) → r",
    opis=("Z p wynika ∼s, a skoro p ∨ q pociąga r ∨ s, to przy ∼s zostaje samo r."),
    wiersze=[
        ProofLine("1", "(p ∨ q) → (r ∨ s)", ZALOZENIE, []),
        ProofLine("2", "p → ∼s", ZALOZENIE, []),
        ProofLine("3", "p", ZALOZENIE, []),
        ProofLine("4", "∼s", "RO 2, 3", ["2", "3"]),
        ProofLine("5", "p ∨ q", "DA 3", ["3"]),
        ProofLine("6", "r ∨ s", "RO 1, 5", ["1", "5"]),
        ProofLine("7", "r", "OA 4, 6", ["4", "6"]),
    ],
)

#: Dowód C — dowód nie wprost. Wiersz 3 dokłada zanegowaną tezę dowodu wprost (∼q),
#: a wiersz 8 zamyka dowód, bo ∼r z wiersza 5 przeczy r z wiersza 7.
_DOWOD_C = Proof(
    id="C",
    tytul="Kontrapozycja w koniunkcji",
    rodzaj=RODZAJ_NIE_WPROST,
    teza="((p ∧ q) → r) → ((p ∧ ∼r) → ∼q)",
    opis=("Zakładamy p i ∼r oraz q i dochodzimy do sprzeczności: r i ∼r naraz."),
    wiersze=[
        ProofLine("1", "(p ∧ q) → r", ZALOZENIE, []),
        ProofLine("2", "p ∧ ∼r", ZALOZENIE, []),
        ProofLine("3", "q", Z_DOW_NIE_WPROST, []),
        ProofLine("4", "p", "OK 2", ["2"]),
        ProofLine("5", "∼r", "OK 2", ["2"]),
        ProofLine("6", "p ∧ q", "DK 3, 4", ["3", "4"]),
        ProofLine("7", "r", "RO 1, 6", ["1", "6"]),
        ProofLine("8", f"{SPRZECZNOSC} 5, 7", "—", ["5", "7"]),
    ],
)

#: Dowód D — dowód nie wprost przez prawa de Morgana i kontrapozycję: z ∼(q ∨ s)
#: dostajemy ∼q i ∼s, z kontrapozycji ∼p i ∼r, a wiersz 13 przeczy wierszowi 3.
_DOWOD_D = Proof(
    id="D",
    tytul="Dwa przypadki",
    rodzaj=RODZAJ_NIE_WPROST,
    teza="((p → q) ∧ (r → s) ∧ (p ∨ r)) → (q ∨ s)",
    opis=("Skoro zachodzi p lub r, a każde z nich pociąga swój następnik, to zachodzi q lub s."),
    wiersze=[
        ProofLine("1", "p → q", ZALOZENIE, []),
        ProofLine("2", "r → s", ZALOZENIE, []),
        ProofLine("3", "p ∨ r", ZALOZENIE, []),
        ProofLine("4", "∼(q ∨ s)", Z_DOW_NIE_WPROST, []),
        ProofLine("5", "∼q", "DM1 4", ["4"]),
        ProofLine("6", "∼s", "DM1 4", ["4"]),
        ProofLine("7", "∼q → ∼p", "KP 1", ["1"]),
        ProofLine("8", "∼s → ∼r", "KP 2", ["2"]),
        ProofLine("9", "∼p", "RO 5, 7", ["5", "7"]),
        ProofLine("10", "∼r", "RO 6, 8", ["6", "8"]),
        ProofLine("11", "∼p ∧ ∼r", "DK 9, 10", ["9", "10"]),
        ProofLine("12", "∼(p ∨ r)", "DM2 11", ["11"]),
        ProofLine("13", f"{SPRZECZNOSC} 3, 12", "—", ["3", "12"]),
    ],
)

#: Dowód E — dowód nie wprost z założeniem ∼p i zanegowaną tezą ∼s. Wiersz 6 korzysta
#: z OA na alternatywie trzech zdań, a wiersz 10 przeczy wierszowi 7.
_DOWOD_E = Proof(
    id="E",
    tytul="Z założeniem ∼p",
    rodzaj=RODZAJ_NIE_WPROST,
    teza="(((p ∨ q) → r) ∧ (r → s) ∧ (p ∨ q ∨ s)) → (∼p → s)",
    opis=("Skoro ∼p, a zachodzi p, q lub s, to przy ∼s zostaje q, z którego idziemy do r."),
    wiersze=[
        ProofLine("1", "(p ∨ q) → r", ZALOZENIE, []),
        ProofLine("2", "r → s", ZALOZENIE, []),
        ProofLine("3", "p ∨ q ∨ s", ZALOZENIE, []),
        ProofLine("4", "∼p", ZALOZENIE, []),
        ProofLine("5", "∼s", Z_DOW_NIE_WPROST, []),
        ProofLine("6", "p ∨ q", "OA 3, 5", ["3", "5"]),
        ProofLine("7", "r", "RO 1, 6", ["1", "6"]),
        ProofLine("8", "∼s → ∼r", "KP 2", ["2"]),
        ProofLine("9", "∼r", "RO 5, 8", ["5", "8"]),
        ProofLine("10", f"{SPRZECZNOSC} 7, 9", "—", ["7", "9"]),
    ],
)

#: Dowód F — wielokrotne założenia. Zanegowana teza to ∼q, więc dowód rozbija się na dwa
#: przypadki: p (wiersze 4.1–4.4) i ∼p (wiersze 5.1–5.4). Każdy z nich kończy się
#: sprzecznością, więc ∼q nie może być prawdziwe.
_DOWOD_F = Proof(
    id="F",
    tytul="Wielokrotne założenia",
    rodzaj=RODZAJ_WIELOKROTNE,
    teza="((p → (q ∧ r)) ∧ (∼p → (s ∧ t)) ∧ ∼t) → q",
    opis=("∼t wyklucza ∼p, więc zachodzi p, a wtedy z pierwszego założenia wynika q."),
    wiersze=[
        ProofLine("1", "p → (q ∧ r)", ZALOZENIE, []),
        ProofLine("2", "∼p → (s ∧ t)", ZALOZENIE, []),
        ProofLine("3", "∼t", ZALOZENIE, []),
        ProofLine("4", "∼q", Z_DOW_NIE_WPROST, []),
        ProofLine("4.1", "p", DODATKOWE_ZALOZENIE, []),
        ProofLine("4.2", "q ∧ r", "RO 1, 4.1", ["1", "4.1"]),
        ProofLine("4.3", "q", "OK 4.2", ["4.2"]),
        ProofLine("4.4", f"{SPRZECZNOSC} 4.3, 4", "—", ["4.3", "4"]),
        ProofLine("5.1", "∼p", DODATKOWE_ZALOZENIE, []),
        ProofLine("5.2", "s ∧ t", "RO 2, 5.1", ["2", "5.1"]),
        ProofLine("5.3", "t", "OK 5.2", ["5.2"]),
        ProofLine("5.4", f"{SPRZECZNOSC} 3, 5.3", "—", ["3", "5.3"]),
    ],
)

#: Sześć dowodów z wykładu, w kolejności A–F (najpierw wprost, potem nie wprost).
_PROOFS: tuple[Proof, ...] = (_DOWOD_A, _DOWOD_B, _DOWOD_C, _DOWOD_D, _DOWOD_E, _DOWOD_F)


def proofs() -> list[Proof]:
    """Zwraca sześć dowodów A–F, w kolejności z wykładu.

    Oddajemy kopię listy, żeby wołający nie zmienił rejestru przez przypadek.
    """
    return list(_PROOFS)


def get(proof_id: str) -> Proof | None:
    """Zwraca dowód o podanym identyfikatorze (``"A"``) albo ``None``.

    Wielkość liter i spacje wokół identyfikatora nie mają znaczenia (``" a "`` to ``A``).
    """
    szukany = str(proof_id).strip().upper()
    for dowod in _PROOFS:
        if dowod.id.upper() == szukany:
            return dowod
    return None


def is_contradiction(line: ProofLine) -> bool:
    """Czy wiersz zamyka dowód nie wprost („Sprzeczność 5, 7”).

    Wiersz sprzeczności nie ma formuły — jego ``formula`` to napis z numerami wierszy,
    które sobie przeczą. Ta funkcja trzyma wiedzę o tym napisie w jednym miejscu: widok
    wybiera po niej wiersz do podświetlenia, a test pomija taki wiersz przy sprawdzaniu,
    czy formuły się parsują.
    """
    return line.formula.startswith(SPRZECZNOSC)
