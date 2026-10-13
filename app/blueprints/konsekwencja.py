"""Lekcja wykładu 2: ``/konsekwencja`` — wynikanie logiczne i test wynikania.

Strona odwzorowuje sekcję „1. Konsekwencja logiczna” z ``docs/TRESC-WYKLAD2.md``:
definicja, znaczenie, ten sam warunek zapisany inaczej, dwa rozumowania o Azorze
i założenia sprzeczne. Na końcu stoi interaktywny test: wpisujesz założenia i tezę,
a strona mówi, czy teza wynika, i pokazuje kontrprzykład, gdy nie wynika.

Trzy rzeczy strona liczy, zamiast wpisywać je na sztywno:

* ocenę obu rozumowań o Azorze — ``truth.is_tautology`` bada zapis rozumowania,
  a ``truth.build`` znajduje wartościowanie obalające,
* wniosek pod tablicą równoważności — czy ostatnia kolumna ma same jedynki,
* wynik testu wynikania — ten sam, którego używa ``POST /api/wynikanie``
  (``check_entailment``). Formularz działa też bez JavaScriptu zwykłym POST-em.

Wzory zamienia na HTML ``formula.to_html`` (nigdy ``eval``). Napisy z metazmiennymi
``Φ`` i ``Ψ`` parser odrzuca, więc idą na stronę jako zwykły tekst — tak samo jak
nagłówki z literami α i β na ``/tautologie``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from flask import Blueprint, render_template, request
from markupsafe import Markup, escape

from app.blueprints.api_wynikanie import check_entailment
from app.logic import truth
from app.logic.formula import FormulaError, Node, parse, to_html

bp = Blueprint("konsekwencja", __name__)

#: Nazwa pola z wynikami kolumn w wierszu tablicy (umowa ze ``ARCHITEKTURA.md``).
VALUES_FIELD = "values"

#: Definicja z wykładu. Metazmienne Φ i Ψ to dowolne formuły, nie zdania p i q.
DEFINICJA = "(Φ1 ∧ Φ2 ∧ … ∧ Φn) → Ψ"

#: Ten sam warunek dla dwóch założeń — tyle pokazuje interaktywna tablica.
ROWNOZNACZNOSC_DWOCH = "(Φ1 ∧ Φ2) → Ψ  ≡  Φ1 → (Φ2 → Ψ)"

#: Wzór rozumowania poprawnego z wykładu: Azor nie jest zwierzęciem, więc nie jest psem.
AZOR_POPRAWNE = "((p → q) ∧ ∼q) → ∼p"

#: Wzór rozumowania niepoprawnego z wykładu: Azor nie jest psem, więc nie jest zwierzęciem.
AZOR_NIEPOPRAWNE = "((p → q) ∧ ∼p) → ∼q"

#: Założenia sprzeczne: z p i ∼p wynika każda teza.
ZALOZENIA_SPRZECZNE = "(p ∧ ∼p) → q"

#: Dwa założenia i teza do przykładu równoważności: sylogizm hipotetyczny.
ZALOZENIA_PRZYKLADU = ("p → q", "q → r")
TEZA_PRZYKLADU = "p → r"

#: Lewa i prawa strona równoważności dla tego przykładu.
LEWA_PRZYKLADU = "((p → q) ∧ (q → r)) → (p → r)"
PRAWA_PRZYKLADU = "(p → q) → ((q → r) → (p → r))"
ROWNOZNACZNOSC_PRZYKLADU = f"{LEWA_PRZYKLADU} ≡ {PRAWA_PRZYKLADU}"

#: Strona przekazuje partialowi ``_truth_table.html`` jedną formułę — całą równoważność.
FORMULA_TABLICY = ROWNOZNACZNOSC_PRZYKLADU


@dataclass(frozen=True)
class Rozumowanie:
    """Rozumowanie z wykładu: zdanie po polsku i jego zapis w rachunku zdań.

    ``wyjasnienie`` to jedno zdanie, które tłumaczy ocenę. Dla rozumowania
    niepoprawnego strona dokłada wyliczony kontrprzykład.
    """

    opis: str
    formula: str
    wyjasnienie: str


#: Dwa rozumowania o Azorze. p = „Azor jest psem”, q = „Azor jest zwierzęciem”.
ROZUMOWANIA: list[Rozumowanie] = [
    Rozumowanie(
        opis=(
            "Azor jest psem, więc Azor jest zwierzęciem. Azor nie jest psem. "
            "Zatem Azor nie jest zwierzęciem."
        ),
        formula=AZOR_NIEPOPRAWNE,
        wyjasnienie=(
            "Tak nie wolno wnioskować. Kontrprzykład to Azor-kot: nie jest psem, "
            "a jest zwierzęciem."
        ),
    ),
    Rozumowanie(
        opis=(
            "Azor jest psem, więc Azor jest zwierzęciem. Azor nie jest zwierzęciem. "
            "Zatem Azor nie jest psem."
        ),
        formula=AZOR_POPRAWNE,
        wyjasnienie=(
            "Tak wolno wnioskować. Wzór jest tautologią, więc nie ma wartościowania, "
            "przy którym założenia są prawdziwe, a teza fałszywa."
        ),
    ),
]


def formula_to_html(text: str, styl: str = "wyklad") -> Markup:
    """Zwraca wzór jako bezpieczny HTML z ``formula.to_html``.

    Gdy napis nie jest poprawną formułą (np. zawiera metazmienną ``Φ``), oddajemy go
    jako zwykły tekst — treść lekcji nigdy nie kończy się błędem 500. Wynik wstawiamy
    w szablonie przez ``|safe``, tak samo jak ``app/blueprints/tautologie.py``.
    """
    try:
        return Markup(to_html(parse(text), styl))
    except FormulaError:
        return escape(text)


def kontrprzyklad_slownie(wartosci: Mapping[str, int] | None) -> str:
    """Zapisuje wartościowanie słowami: ``p = 1, q = 0``.

    Puste wartościowanie (``None`` albo pusty słownik) daje pusty napis.
    """
    if not wartosci:
        return ""
    return ", ".join(f"{nazwa} = {wartosc}" for nazwa, wartosc in sorted(wartosci.items()))


def _wartosciowanie_obalejace(node: Node) -> dict[str, int] | None:
    """Pierwsze wartościowanie, przy którym formuła jest fałszywa (albo ``None``).

    Dla rozumowania to właśnie kontrprzykład: założenia są wtedy prawdziwe,
    a teza fałszywa.
    """
    tabela = truth.build(node)
    for wiersz in tabela.rows:
        if not wiersz[VALUES_FIELD][-1]:
            return {nazwa: int(wiersz[nazwa]) for nazwa in tabela.variables}
    return None


def rozumowania_azora() -> list[dict[str, Any]]:
    """Wiersze tabeli rozumowań: zapis, ocena policzona silnikiem i wyjaśnienie."""
    wiersze: list[dict[str, Any]] = []
    for rozumowanie in ROZUMOWANIA:
        node = parse(rozumowanie.formula)
        tautologia = truth.is_tautology(node)
        kontrprzyklad = None if tautologia else _wartosciowanie_obalejace(node)
        wiersze.append(
            {
                "opis": rozumowanie.opis,
                "formula": rozumowanie.formula,
                "poprawne": tautologia,
                "ocena": "poprawne" if tautologia else "niepoprawne",
                "wyjasnienie": rozumowanie.wyjasnienie,
                "kontrprzyklad": kontrprzyklad_slownie(kontrprzyklad),
            }
        )
    return wiersze


def przyklad_sprzecznych() -> dict[str, Any]:
    """Założenia sprzeczne: wzór, ocena silnika i wniosek po polsku."""
    formula = ZALOZENIA_SPRZECZNE
    tabela = truth.build(parse(formula))
    tautologia = truth.is_tautology(parse(formula))
    wierszy = len(tabela.rows)
    wniosek = (
        f"Nasz silnik policzył wszystkie {wierszy} wiersze i w każdym jest 1. "
        "Ta formuła jest tautologią, choć jej założenia są sprzeczne."
        if tautologia
        else "Ta formuła nie jest tautologią."
    )
    return {"formula": formula, "tautologia": tautologia, "wniosek": wniosek}


def wniosek_rownowaznosci() -> dict[str, Any]:
    """Wniosek pod tablicą równoważności: czy ostatnia kolumna ma same jedynki.

    Liczymy go z tablicy, więc zdanie na stronie nie rozjedzie się z jej zawartością.
    """
    tabela = truth.build(parse(ROWNOZNACZNOSC_PRZYKLADU))
    wszystkie = len(tabela.rows)
    jedynki = sum(1 for wiersz in tabela.rows if wiersz[VALUES_FIELD][-1])
    tautologia = wszystkie > 0 and jedynki == wszystkie
    wniosek = (
        f"Ostatnia kolumna ma same jedynki — w każdym z {wszystkie} wierszy jest 1. "
        "Cała równoważność jest więc tautologią."
        if tautologia
        else f"Ostatnia kolumna ma jedynkę tylko w {jedynki} z {wszystkie} wierszy."
    )
    return {"tautologia": tautologia, "wierszy": wszystkie, "wniosek": wniosek}


def wynik_dla_strony(rezultat: Mapping[str, Any] | None) -> dict[str, Any]:
    """Zamienia wynik ``check_entailment`` na dane dla szablonu.

    ``None`` znaczy „nic jeszcze nie sprawdzano” — wtedy szablon nie pokazuje wyniku.
    Kontrprzykład zamieniamy na gotowe zdanie (``p = 1, q = 0``), żeby szablon nie
    składał napisów sam.
    """
    if rezultat is None:
        return {"sprawdzono": False, "ok": False, "wynika": False, "kontrprzyklad": "", "blad": ""}
    return {
        "sprawdzono": True,
        "ok": bool(rezultat["ok"]),
        "wynika": bool(rezultat["wynika"]),
        "kontrprzyklad": kontrprzyklad_slownie(rezultat["kontrprzyklad"]),
        "blad": str(rezultat["blad"]),
    }


def _wiersze_z_pola(tekst: str) -> list[str]:
    """Dzieli pole formularza na założenia: jedna formuła w wierszu, puste odpadają."""
    return [wiersz.strip() for wiersz in tekst.splitlines() if wiersz.strip()]


def _render(
    zalozenia: str = "",
    teza: str = "",
    rezultat: Mapping[str, Any] | None = None,
) -> str:
    """Rysuje stronę. ``rezultat`` niepuste tylko po wysłaniu formularza."""
    return render_template(
        "konsekwencja.html",
        formula_to_html=formula_to_html,
        definicja=DEFINICJA,
        rownowaznosc_dwoch=ROWNOZNACZNOSC_DWOCH,
        przyklad_rownowaznosci=ROWNOZNACZNOSC_PRZYKLADU,
        zalozenia_przykladu=ZALOZENIA_PRZYKLADU,
        teza_przykladu=TEZA_PRZYKLADU,
        wniosek_rownowaznosci=wniosek_rownowaznosci(),
        azor=rozumowania_azora(),
        sprzeczne=przyklad_sprzecznych(),
        zalozenia=zalozenia,
        teza=teza,
        wynik=wynik_dla_strony(rezultat),
        formula=FORMULA_TABLICY,
    )


@bp.get("/konsekwencja")
def konsekwencja() -> str:
    """Lekcja: definicja wynikania, przykłady, założenia sprzeczne i test wynikania."""
    return _render()


@bp.post("/konsekwencja")
def konsekwencja_post() -> str:
    """Ten sam test bez JavaScriptu: formularz wysyła POST, strona pokazuje wynik."""
    zalozenia = request.form.get("zalozenia", "")
    teza = request.form.get("teza", "")
    rezultat = check_entailment(_wiersze_z_pola(zalozenia), teza)
    return _render(zalozenia=zalozenia, teza=teza, rezultat=rezultat)
