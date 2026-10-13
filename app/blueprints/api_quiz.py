"""API quizu: ``POST /api/quiz/generate`` i ``POST /api/quiz/check`` (karta PRZ-015).

Endpointy korzystają z generatora :mod:`app.logic.quiz`. Podział pracy jest taki,
jak w kontrakcie (``docs/ARCHITEKTURA.md``, sekcja „API”):

* ``generate`` zwraca pytania przez :meth:`app.logic.quiz.Question.to_public_dict`,
  więc **nie ma** w nich ani poprawnej odpowiedzi, ani wyjaśnienia. Przeglądarka
  zna tylko identyfikator pytania i ziarno zestawu.
* ``check`` liczy pytania od nowa z tego samego ziarna i porównuje wybrany numer
  z poprawnym. Wyjaśnienie dokładamy z tego samego zestawu, bo przeglądarka go nie zna.

Zgodnie z kontraktem API błąd danych to ``ok: false`` i komunikat po polsku z kodem
HTTP 200 — dotyczy to także ciała, które nie jest obiektem JSON, nieznanego prawa,
nieznanego identyfikatora pytania i odpowiedzi poza zakresem. Wyjaśnienie wraca
także wtedy, gdy odpowiedź była błędna: to ono pokazuje poprawną odpowiedź.
"""

from __future__ import annotations

import secrets

from flask import Blueprint, jsonify, request

from app.logic import laws
from app.logic.quiz import Question, check, generate

bp = Blueprint("api_quiz", __name__, url_prefix="/api")

#: Liczba pytań, gdy żądanie jej nie poda.
ILE_DOMYSLNE = 5

#: Największa liczba pytań w jednym zestawie — chroni przed żądaniem całego rejestru
#: po wielokroć i przed odpowiedzią bez sensownego rozmiaru.
ILE_MAX = 50

#: Liczba pytań, przy której ``generate`` zwraca cały zestaw wybranych praw.
#: ``check`` szuka pytania w całym zestawie, więc i tu musimy mieć wszystkie pytania;
#: ``ile`` jest tylko górnym ograniczeniem wycinania, więc duża wartość nic nie psuje.
ILE_CALY_ZESTAW = 10_000

#: Komunikat dla ciała, które nie jest obiektem JSON (lista, liczba, brak treści).
BLAD_CIALA = 'Treść żądania musi być obiektem JSON, np. {"ile": 3, "seed": 1}.'


def _blad(komunikat: str):
    """Odpowiedź z błędem danych: ``ok: false`` i kod HTTP 200."""
    return jsonify(ok=False, blad=komunikat)


def _zakres(wartosc: object) -> tuple[str | None, str | None]:
    """Sprawdza pole ``prawo`` i zwraca ``(slug, komunikat błędu)``.

    ``None`` i pusty tekst znaczą „wszystkie prawa”. Nieznany slug to błąd danych,
    a nie pusty zestaw — inaczej literówka w adresie wyglądałaby jak brak pytań.
    """
    if wartosc is None:
        return None, None
    if not isinstance(wartosc, str):
        return None, "Pole „prawo” musi być tekstem (slug prawa) albo null."
    slug = wartosc.strip()
    if not slug:
        return None, None
    if laws.get(slug) is None:
        return None, f"Nie mamy prawa o adresie „{slug}”."
    return slug, None


def _ziarno(wartosc: object) -> int | None:
    """Sprawdza pole ``seed``: liczba całkowita nieujemna albo ``None``."""
    if isinstance(wartosc, bool) or not isinstance(wartosc, int) or wartosc < 0:
        return None
    return wartosc


def _znajdz(prawo: str | None, seed: int, pytanie_id: str) -> Question | None:
    """Szuka pytania w całym zestawie wybranych praw — po identyfikatorze.

    Potrzebujemy całego zestawu, a nie tylko pierwszych ``ile`` pytań, bo przeglądarka
    mogła dostać krótszy wycinek, a i tak odsyła nam identyfikator pytania z niego.
    """
    for pytanie in generate(prawo=prawo, ile=ILE_CALY_ZESTAW, seed=seed):
        if pytanie.id == pytanie_id:
            return pytanie
    return None


@bp.post("/quiz/generate")
def generate_quiz():
    """Losuje zestaw pytań i zwraca go bez poprawnych odpowiedzi."""
    dane = request.get_json(silent=True)
    if not isinstance(dane, dict):
        return _blad(BLAD_CIALA)

    prawo, blad = _zakres(dane.get("prawo"))
    if blad:
        return _blad(blad)

    ile = dane.get("ile", ILE_DOMYSLNE)
    if isinstance(ile, bool) or not isinstance(ile, int):
        return _blad("Pole „ile” musi być liczbą całkowitą.")
    if not 1 <= ile <= ILE_MAX:
        return _blad(f"Liczba pytań musi być od 1 do {ILE_MAX}.")

    seed = _ziarno(dane.get("seed"))
    if seed is None:
        seed = secrets.randbelow(2**32)

    pytania = generate(prawo=prawo, ile=ile, seed=seed)
    return jsonify(ok=True, seed=seed, pytania=[pytanie.to_public_dict() for pytanie in pytania])


@bp.post("/quiz/check")
def check_answer():
    """Sprawdza odpowiedź i zwraca wyjaśnienie — także dla odpowiedzi błędnej."""
    dane = request.get_json(silent=True)
    if not isinstance(dane, dict):
        return _blad(BLAD_CIALA)

    prawo, blad = _zakres(dane.get("prawo"))
    if blad:
        return _blad(blad)

    seed = _ziarno(dane.get("seed"))
    if seed is None:
        return _blad("Pole „seed” musi być liczbą całkowitą z zestawu pytań.")

    pytanie_id = dane.get("id")
    if not isinstance(pytanie_id, str) or not pytanie_id.strip():
        return _blad("Pole „id” musi być identyfikatorem pytania.")

    odpowiedz = dane.get("odpowiedz")
    if isinstance(odpowiedz, bool) or not isinstance(odpowiedz, int):
        return _blad("Pole „odpowiedz” musi być numerem wybranej odpowiedzi.")

    pytanie = _znajdz(prawo, seed, pytanie_id)
    if pytanie is None:
        return _blad(f"Nie znam pytania o identyfikatorze „{pytanie_id}”.")
    if not 0 <= odpowiedz < len(pytanie.opcje):
        return _blad(
            f"Pytanie ma {len(pytanie.opcje)} odpowiedzi — numer musi być od 0 do "
            f"{len(pytanie.opcje) - 1}."
        )

    return jsonify(
        ok=True,
        poprawna=check(prawo, seed, pytanie_id, odpowiedz),
        wyjasnienie=pytanie.wyjasnienie,
    )
