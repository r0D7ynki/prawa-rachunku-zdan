"""Strona ``/dowody`` — dowody założeniowe z wykładu 2 (karta PRZ-091).

Treść dowodów pochodzi w całości z rejestru ``app.logic.proofs``; ten moduł niczego nie
dopisuje i nie zakłada, ile dowodów jest w zestawie. Widok zamienia dane na gotowe do
wstawienia fragmenty: numer wiersza, wzór w HTML, uzasadnienie i opis kroku dla paska
kroków (komponent PRZ-072).

Wzory rysuje ``app.logic.formula.to_html`` i tylko one idą w szablonie przez ``|safe``.
Napisy, które formułami nie są („Sprzeczność 5, 7”, kontrprzykład ``p = 0``), zostają
tekstem — ``formula_to_html`` oddaje wtedy napis bez znaczników. Dzięki temu literówka
w treści pokaże brzydki wzór, a nie stronę z błędem 500.

Kody reguł z uzasadnień (``RO 2, 3``, ``DM1 4``) prowadzimy do pełnych nazw przez rejestr
``app.logic.rules``. Student widzi więc przy wierszu nie tylko „RO”, ale i „Reguła
odrywania”. Nieznany kod nie psuje strony: zostaje sam napis z wykładu.

Kroki paska lecą do skryptu jako JSON w atrybucie ``data-kroki``. Każdy krok niesie numer
wiersza, listę ``z`` (z czego powstał) i kod reguły, więc ``dowody.js`` rysuje strzałkę
„wiersze 2 i 3 → wiersz 5” bez własnej wiedzy o dowodach.
"""

from __future__ import annotations

import json

from flask import Blueprint, render_template
from markupsafe import Markup, escape

from app.logic import rules as rejestr_regul
from app.logic.formula import FormulaError, parse, to_html
from app.logic.proofs import (
    RODZAJ_NIE_WPROST,
    RODZAJ_WIELOKROTNE,
    RODZAJ_WPROST,
    UZASADNIENIA_BEZ_Z,
    Proof,
    ProofLine,
    is_contradiction,
    proofs,
)

#: Nazwa blueprintu i trasa to tokeny interfejsu (adres ``/dowody`` z mapy kodu).
bp = Blueprint("dowody", __name__)

#: Wstęp do każdego rodzaju dowodu. Kolejność jest kolejnością nauki: najpierw dowód
#: wprost, potem nie wprost, na końcu przypadki z dodatkowymi założeniami.
RODZAJE: tuple[dict, ...] = (
    {
        "kod": RODZAJ_WPROST,
        "tytul": "Dowód wprost",
        "opis": (
            "W pierwszych wierszach wypisujemy założenia. Każdy następny wiersz powstaje "
            "z wcześniejszych znanymi regułami, aż jednym z wierszy będzie teza. "
            "Tak wyglądają dowody A i B."
        ),
    },
    {
        "kod": RODZAJ_NIE_WPROST,
        "tytul": "Dowód nie wprost",
        "opis": (
            "Do założeń dokładamy zanegowaną tezę i prowadzimy dowód tak samo. "
            "Kończymy, gdy otrzymamy dwa wiersze sprzeczne: Φ oraz ∼Φ. Sprzeczność "
            "znaczy, że zaprzeczenie tezy było fałszywe, czyli teza jest prawdziwa."
        ),
    },
    {
        "kod": RODZAJ_WIELOKROTNE,
        "tytul": "Dowód z wielokrotnymi założeniami",
        "opis": (
            "Gdy jeden ciąg wierszy nie wystarcza, rozpatrujemy przypadki. Dodatkowe "
            "założenie otwiera poddowód, a jego wiersze numerujemy jak 4.1 i 4.2. Każdy "
            "przypadek musi doprowadzić do sprzeczności — tak wygląda dowód F."
        ),
    },
)

#: Sekcja „Skąd kontrprzykład” — tabela z ``docs/TRESC-WYKLAD2.md``, sekcja
#: „5. Niepoprawne rozumowania i kontrprzykład”. Wiersze dowodu są tam wypisane po kolei,
#: a obok stoi wartościowanie, przy którym założenia są prawdziwe, a wniosek fałszywy.
PRZYKLADY_KONTRPRZYKLADU: tuple[dict, ...] = (
    {
        "rozumowanie": "Azor nie jest psem, zatem nie jest zwierzęciem.",
        "wiersze": ("p → q", "∼p", "q"),
        "kontrprzyklad": "p = 0, q = 1",
        "komentarz": "Azor-kot: nie jest psem, a jest zwierzęciem.",
    },
    {
        "rozumowanie": (
            "Prawa moralne i niepostępowanie według nich prowadzą do niekonsekwencji, "
            "a niekonsekwencja do złego postępowania."
        ),
        "wiersze": ("(p ∧ ∼q) → r", "r → t", "p ∧ q", "t"),
        "kontrprzyklad": "p = 1, q = 1, t = 1, r dowolne",
        "komentarz": "Założenia są prawdziwe, a wniosek „nie postępuję źle” fałszywy.",
    },
)


def formula_to_html(text: str) -> Markup:
    """Zwraca wzór jako bezpieczny HTML z ``formula.to_html``.

    Gdy napis nie jest poprawną formułą, oddajemy go jako zwykły tekst — brak przecinka
    w treści pokaże brzydki wzór, a nie stronę z błędem 500. Poprawną treść dowodów
    sprawdza ``tests/test_dowody.py``.
    """
    try:
        return Markup(to_html(parse(text)))
    except FormulaError:
        return escape(text)


def _wymien(elementy: list[str]) -> str:
    """Wypisuje elementy po polsku: „2”, „2 i 3”, „1, 2 i 3”."""
    if len(elementy) <= 1:
        return elementy[0] if elementy else ""
    return f"{', '.join(elementy[:-1])} i {elementy[-1]}"


def _kod_reguly(wiersz: ProofLine) -> str:
    """Kod reguły z uzasadnienia (``"RO 2, 3"`` → ``"RO"``); ``""`` dla założeń.

    Założenia nie powołują się na żadną regułę, więc nie mają kodu. Wiersz sprzeczności
    też nie ma uzasadnienia — jego ``uzasadnienie`` to kreska „—”, a nie kod.
    """
    if wiersz.uzasadnienie in UZASADNIENIA_BEZ_Z:
        return ""
    kod = wiersz.uzasadnienie.split(maxsplit=1)[0]
    return kod if kod.isupper() else ""


def _nazwa_reguly(wiersz: ProofLine) -> str:
    """Pełna nazwa reguły z rejestru ``app.logic.rules``; ``""``, gdy kodu nie ma."""
    regula = rejestr_regul.get(_kod_reguly(wiersz))
    return regula.nazwa if regula is not None else ""


def _opis_kroku(wiersz: ProofLine) -> str:
    """Zdanie po polsku pod paskiem kroków. Mówi, co powstaje i z czego."""
    if is_contradiction(wiersz):
        return f"Sprzeczność wierszy {_wymien(wiersz.z)} — koniec dowodu."
    nazwa = _nazwa_reguly(wiersz)
    if nazwa:
        return f"{nazwa} ({_kod_reguly(wiersz)}) — z wierszy {_wymien(wiersz.z)}."
    return f"{wiersz.uzasadnienie}."


def _wiersz_widoku(wiersz: ProofLine) -> dict:
    """Dane jednego wiersza tabeli: gotowy HTML wzoru, opis i znaczniki dla skryptu."""
    sprzecznosc = is_contradiction(wiersz)
    return {
        "nr": wiersz.nr,
        # Napis wiersza idzie do szablonu surowy — rysuje go dopiero ``formula_to_html``.
        # Wiersz sprzeczności nie jest formułą, więc ta funkcja oddaje go jako tekst.
        "formula": wiersz.formula,
        "uzasadnienie": wiersz.uzasadnienie,
        "nazwa_reguly": _nazwa_reguly(wiersz),
        "sprzecznosc": sprzecznosc,
        # Wiersze poddowodu (4.1–5.4) pokazujemy z wcięciem — widać, że należą do
        # dodatkowego założenia, a nie do głównego ciągu dowodu.
        "wciety": "." in wiersz.nr,
        # Wiersz sprzeczności niesie opis słowny, więc sam kolor nic nie znaczy.
        "aria_label": (
            f"Wiersz {wiersz.nr}: sprzeczność wierszy {_wymien(wiersz.z)}. Koniec dowodu."
            if sprzecznosc
            else ""
        ),
    }


def _krok_widoku(wiersz: ProofLine) -> dict:
    """Krok paska kroków: tytuł, opis i to, co skrypt potrzebuje do strzałki."""
    return {
        "tytul": f"Wiersz {wiersz.nr}",
        "opis": _opis_kroku(wiersz),
        "nr": wiersz.nr,
        "z": list(wiersz.z),
        "regula": _kod_reguly(wiersz),
        "regula_nazwa": _nazwa_reguly(wiersz),
        "sprzecznosc": is_contradiction(wiersz),
    }


def _dowod_widoku(dowod: Proof) -> dict:
    """Dowód gotowy dla szablonu: wiersze tabeli i kroki paska jako JSON."""
    kroki = [_krok_widoku(wiersz) for wiersz in dowod.wiersze]
    return {
        "id": dowod.id,
        "tytul": dowod.tytul,
        "rodzaj": dowod.rodzaj,
        "opis": dowod.opis,
        "teza": dowod.teza,
        "wiersze": [_wiersz_widoku(wiersz) for wiersz in dowod.wiersze],
        "liczba_wierszy": len(dowod.wiersze),
        "kroki": kroki,
        "kroki_json": json.dumps(kroki, ensure_ascii=False),
    }


@bp.get("/dowody")
def dowody():
    """Lekcja: dowód wprost, dowód nie wprost, wielokrotne założenia i kontrprzykład."""
    wszystkie = [_dowod_widoku(dowod) for dowod in proofs()]
    return render_template(
        "dowody.html",
        dowody=wszystkie,
        rodzaje=RODZAJE,
        przyklady=PRZYKLADY_KONTRPRZYKLADU,
        liczba_dowodow=len(wszystkie),
        liczba_wierszy=sum(dowod["liczba_wierszy"] for dowod in wszystkie),
        formula_to_html=formula_to_html,
    )
