"""Czwarta lekcja kursu: ``/przeksztalcanie`` — nawiasy, kolejność i podstawianie.

Treść odwzorowuje wykład 1 („Logika pragmatyczna”, PWr): slajdy „Przekształcanie formuł”.
Lekcja odpowiada na trzy pytania:

1. kiedy w łańcuchu samych alternatyw wolno opuścić nawiasy i zmienić kolejność,
2. dlaczego z implikacją tego samego zrobić nie wolno,
3. jak podstawiać formuły pod zmienne tautologii.

Wszystkie wzory rysuje ``app.logic.formula.to_html``, a wartości w tabelach liczy
``app.logic.truth`` — na stronie nie ma ani jednej wpisanej ręcznie jedynki ani zera.
Nazwy praw pochodzą z rejestru ``app.logic.laws``, więc nie rozjadą się z treścią praw.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from flask import Blueprint, render_template
from markupsafe import Markup, escape

from app.logic import truth
from app.logic.formula import FormulaError, parse, to_html
from app.logic.laws import get

bp = Blueprint("przeksztalcanie", __name__)

#: Spójnik łączący ogniwa łańcucha. To ten sam znak i ta sama klasa HTML, którymi
#: ``formula.to_html`` spina strony równoważności — dzięki temu wszystkie spójniki
#: na stronie wyglądają tak samo. Zgodności pilnuje test
#: ``test_spojnik_lancucha_to_ten_sam_znak_co_w_to_html``.
SPOJNIK_ROWNAWAZANIA = "≡"

#: Punkt 2 i 5 wykładu: wzory, które trzeba porównać wiersz po wierszu.
IMPLIKACJA_LEWA = "(p → q) → r"
IMPLIKACJA_PRAWA = "p → (q → r)"

#: Punkt 3 wykładu: podstawienie w prawie definiowania implikacji.
PODSTAWIENIE_BAZA = "(p → q) ≡ (∼p ∨ q)"
PODSTAWIENIE_P = "p → q"
PODSTAWIENIE_Q = "p ∧ q"
PODSTAWIENIE_WYNIK = "((p → q) → (p ∧ q)) ≡ (∼(p → q) ∨ (p ∧ q))"

#: Prawo, z którym łatwo pomylić podstawianie (decyzja D16).
ZASTEPOWANIE_ROWNYCH = "zastepowanie-rownych"
PODSTAWIENIE_REGULA = "podstawianie"


# ---------------------------------------------------------------------------
# Wzory lekcji
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Ogniwo:
    """Jeden wzór łańcucha wraz z informacją, skąd się wziął.

    ``slugi`` to slugi praw z rejestru ``app.logic.laws`` — strona zrobi z nich
    odnośniki. ``dzialania`` to czynności, które nie mają własnego prawa (np.
    opuszczanie nawiasów). Pierwsze ogniwo to punkt wyjścia: nie ma ani jednego,
    ani drugiego. ``komentarz`` mówi jednym zdaniem, co się stało z wzorem.
    """

    formula: str
    slugi: tuple[str, ...] = ()
    dzialania: tuple[str, ...] = ()
    komentarz: str = ""


#: Łańcuch równoważności z punktu 1 wykładu. Dwie pierwsze formuły różni tylko
#: nawias, a trzecia jest już zapisem płaskim — dlatego strona tłumaczy, że nawias
#: zewnętrzny nic nie zmienia.
LANCUCH: tuple[Ogniwo, ...] = (
    Ogniwo(
        "((p ∨ ∼q) ∨ r)",
        komentarz="Punkt wyjścia z wykładu: pierwszy nawias obejmuje tylko dwie z trzech części.",
    ),
    Ogniwo(
        "(p ∨ (∼q ∨ r))",
        slugi=("lacznosc-alternatywy",),
        komentarz="Nawias przesuwamy w prawo — na to pozwala łączność alternatywy.",
    ),
    Ogniwo(
        "(p ∨ ∼q ∨ r)",
        dzialania=("opuszczanie nawiasów",),
        komentarz="Nawiasy znikają: w łańcuchu samych alternatyw nic nie zmieniają.",
    ),
    Ogniwo(
        "(∼q ∨ p ∨ r)",
        slugi=("przemiennosc-alternatywy",),
        komentarz="Kolejność składników też wolno zmienić — to przemienność.",
    ),
)


@dataclass(frozen=True)
class KrokPodstawiania:
    """Jeden z trzech kroków podstawiania formuł do tautologii.

    ``wzory`` to formuły pokazywane w tym kroku, ``podstawienia`` to pary
    ``(zmienna, formuła)`` — co pod co wstawiamy. Każdy napis z obu pól idzie przez
    ``to_html``. ``slugi`` to prawa z rejestru, na które krok się powołuje.
    """

    tytul: str
    opis: str
    wzory: tuple[str, ...] = ()
    podstawienia: tuple[tuple[str, str], ...] = ()
    slugi: tuple[str, ...] = ()


#: Trzy kroki podstawiania z punktu 3 wykładu.
KROKI_PODSTAWIENIA: tuple[KrokPodstawiania, ...] = (
    KrokPodstawiania(
        tytul="Bierzemy tautologię",
        opis=(
            "Zaczynamy od prawa definiowania implikacji. To tautologia, czyli formuła "
            "prawdziwa przy każdym wartościowaniu."
        ),
        wzory=(PODSTAWIENIE_BAZA,),
        slugi=("definiowanie-implikacji",),
    ),
    KrokPodstawiania(
        tytul="Podstawiamy formuły pod zmienne",
        opis=(
            "Podstawienie obejmuje wszystkie wystąpienia zmiennej. Jedna zmienna "
            "dostaje jedną formułę."
        ),
        podstawienia=(("p", PODSTAWIENIE_P), ("q", PODSTAWIENIE_Q)),
    ),
    KrokPodstawiania(
        tytul="Otrzymujemy nową tautologię",
        opis=(
            "Powstała formuła też jest prawdziwa przy każdym wartościowaniu. "
            "Nie trzeba liczyć jej tablicy od nowa — wystarczy, że podstawiliśmy do tautologii."
        ),
        wzory=(PODSTAWIENIE_WYNIK,),
        slugi=(PODSTAWIENIE_REGULA,),
    ),
)


@dataclass(frozen=True)
class KrokUproszczenia:
    """Jeden wiersz tabeli upraszczania z punktu 4 wykładu.

    ``wzor_prawa`` to wzór użytego prawa w wersji z tego kroku (np. ``(q ∨ q) ≡ q``),
    gdy wykład pokazuje go obok nazwy. Pusty napis znaczy „sama nazwa wystarczy”.
    """

    formula: str
    slugi: tuple[str, ...] = ()
    dzialania: tuple[str, ...] = ()
    wyjasnienie: str = ""
    wzor_prawa: str = ""


#: Pięć kroków upraszczania — dokładnie przykład z wykładu, od kroku 0.
KROKI_UPROSZCZENIA: tuple[KrokUproszczenia, ...] = (
    KrokUproszczenia(
        "∼(∼r ∧ (∼q ∧ p)) ∨ q",
        wyjasnienie="Punkt wyjścia — jeszcze nic nie robimy.",
    ),
    KrokUproszczenia(
        "(r ∨ ∼(∼q ∧ p)) ∨ q",
        slugi=("de-morgan-1", "podwojne-przeczenie"),
        wyjasnienie="Zdejmujemy negację z koniunkcji.",
    ),
    KrokUproszczenia(
        "(r ∨ (q ∨ ∼p)) ∨ q",
        slugi=("de-morgan-1", "podwojne-przeczenie"),
        wyjasnienie="Zdejmujemy negację z drugiej koniunkcji.",
    ),
    KrokUproszczenia(
        "∼p ∨ r ∨ q ∨ q",
        dzialania=("opuszczanie nawiasów", "przemienność"),
        wyjasnienie="Porządkujemy składniki.",
    ),
    KrokUproszczenia(
        "∼p ∨ r ∨ q",
        slugi=("idempotencja-alternatywy",),
        wyjasnienie="Usuwamy powtórzenie — powtórzony składnik stoi teraz raz.",
        wzor_prawa="(q ∨ q) ≡ q",
    ),
)

#: Formuła, od której zaczyna się upraszczanie, i ta, na której się kończy.
UPROSZCZENIE_START = KROKI_UPROSZCZENIA[0].formula
UPROSZCZENIE_KONIEC = KROKI_UPROSZCZENIA[-1].formula


# ---------------------------------------------------------------------------
# Narzędzia
# ---------------------------------------------------------------------------


def formula_to_html(text: str) -> Markup:
    """Zwraca wzór jako bezpieczny HTML z ``formula.to_html``.

    Gdy napis nie jest poprawną formułą, oddajemy go jako zwykły tekst — literówka
    w treści lekcji nie może kończyć się błędem 500. Wynik wstawiamy w szablonie
    przez ``|safe``, tak samo jak ``app/blueprints/tautologie.py``.
    """
    try:
        return Markup(to_html(parse(text)))
    except FormulaError:
        return escape(text)


def opis_prawa(slug: str) -> dict[str, str | None]:
    """Nazwa prawa z rejestru, jego wzór i slug do odnośnika.

    Prawa dodatkowe powstają w karcie PRZ-024, więc teoretycznie rejestr może sluga
    jeszcze nie znać. Wtedy zostaje sam slug i strona nie pokazuje odnośnika do
    strony, której nie ma. Poprawność slugów pilnuje ``tests/test_przeksztalcanie.py``.
    """
    prawo = get(slug)
    if prawo is None:
        return {"nazwa": slug, "slug": None, "formula": ""}
    return {"nazwa": prawo.nazwa, "slug": slug, "formula": prawo.formula}


def prawa_kroku(slugi: Sequence[str], dzialania: Sequence[str] = ()) -> list[dict[str, str | None]]:
    """Prawa jednego kroku: najpierw prawa z rejestru, potem działania bez własnego prawa."""
    opisane = [opis_prawa(slug) for slug in slugi]
    opisane.extend({"nazwa": dzialanie, "slug": None, "formula": ""} for dzialanie in dzialania)
    return opisane


def porownanie(lewa: str, prawa: str) -> dict[str, Any]:
    """Porównuje dwie formuły wiersz po wierszu i zwraca gotową tabelę.

    Klucze wyniku:

    - ``lewa`` i ``prawa`` — porównywane wzory (szablon zamieni je na HTML),
    - ``zmienne`` — kolumny wejściowe w kolejności z tablicy prawdy,
    - ``wiersze`` — lista słowników ``{"zmienne": ["1", "0", …], "lewa": "1",
      "prawa": "0", "rozny": True}``; ``rozny`` mówi, czy wzory mają w tym wierszu
      różne wartości,
    - ``roznich`` — ile wierszy ma różne wartości,
    - ``wszystkich`` — ile wierszy ma tabela.

    Wartości liczy ``app.logic.truth``, więc tabela na stronie nie może rozjechać
    się z tym, co naprawdę znaczą wzory.
    """
    tabela_lewa = truth.build(parse(lewa), with_subformulas=False)
    tabela_prawa = truth.build(parse(prawa), with_subformulas=False)

    wiersze: list[dict[str, Any]] = []
    for wiersz_lewy, wiersz_prawy in zip(tabela_lewa.rows, tabela_prawa.rows, strict=True):
        wartosc_lewa = wiersz_lewy["values"][0]
        wartosc_prawa = wiersz_prawy["values"][0]
        wiersze.append(
            {
                "zmienne": [_znak(wiersz_lewy[nazwa]) for nazwa in tabela_lewa.variables],
                "lewa": _znak(wartosc_lewa),
                "prawa": _znak(wartosc_prawa),
                "rozny": wartosc_lewa != wartosc_prawa,
            }
        )

    return {
        "lewa": lewa,
        "prawa": prawa,
        "zmienne": list(tabela_lewa.variables),
        "wiersze": wiersze,
        "roznich": sum(1 for wiersz in wiersze if wiersz["rozny"]),
        "wszystkich": len(wiersze),
    }


def wniosek_porownania(dane: dict[str, Any]) -> str:
    """Zdanie pod tabelą: czy wzory różnią się w którymkolwiek wierszu.

    Wniosek liczymy z tabeli, więc nie może rozjechać się z jej zawartością.
    """
    if dane["roznich"]:
        return (
            f"Wzory różnią się w {dane['roznich']} z {dane['wszystkich']} wierszy — "
            "już jeden taki wiersz wystarczy, żeby powiedzieć, że nie są równoważne."
        )
    return (
        f"Wzory mają tę samą wartość w każdym z {dane['wszystkich']} wierszy, więc są równoważne."
    )


def wniosek_podstawienia(wynik: str) -> str:
    """Zdanie pod przykładem podstawiania: czy wynik naprawdę jest tautologią."""
    tabela = truth.build(parse(wynik), with_subformulas=False)
    if truth.is_tautology(parse(wynik)):
        return (
            f"Sprawdzone tablicą prawdy: wynik ma same jedynki w {len(tabela.rows)} wierszach, "
            "więc też jest tautologią."
        )
    return "Ten wzór nie ma samych jedynek — podstawienie się nie udało."


def _znak(wartosc: bool) -> str:
    """Zapisuje wartość logiczną tak, jak wykład: ``1`` (prawda) albo ``0`` (fałsz)."""
    return "1" if wartosc else "0"


# ---------------------------------------------------------------------------
# Widok
# ---------------------------------------------------------------------------


@bp.get("/przeksztalcanie")
def przeksztalcanie():
    """Lekcja: opuszczanie nawiasów, kolejność składników i podstawianie formuł."""
    porownanie_implikacji = porownanie(IMPLIKACJA_LEWA, IMPLIKACJA_PRAWA)
    porownanie_uproszczenia = porownanie(UPROSZCZENIE_START, UPROSZCZENIE_KONIEC)
    return render_template(
        "przeksztalcanie.html",
        formula_to_html=formula_to_html,
        prawa_kroku=prawa_kroku,
        spojnik=SPOJNIK_ROWNAWAZANIA,
        lancuch=LANCUCH,
        implikacja_lewa=IMPLIKACJA_LEWA,
        implikacja_prawa=IMPLIKACJA_PRAWA,
        porownanie_implikacji=porownanie_implikacji,
        wniosek_implikacji=wniosek_porownania(porownanie_implikacji),
        kroki_podstawiania=KROKI_PODSTAWIENIA,
        podstawienie_wynik=PODSTAWIENIE_WYNIK,
        wniosek_podstawienia=wniosek_podstawienia(PODSTAWIENIE_WYNIK),
        zastepowanie=opis_prawa(ZASTEPOWANIE_ROWNYCH),
        kroki_uproszczenia=KROKI_UPROSZCZENIA,
        uproszczenie_start=UPROSZCZENIE_START,
        uproszczenie_koniec=UPROSZCZENIE_KONIEC,
        porownanie_uproszczenia=porownanie_uproszczenia,
        wniosek_uproszczenia=wniosek_porownania(porownanie_uproszczenia),
        #: Partial tablicy prawdy (karta PRZ-011) czyta zmienną ``formula``.
        formula=IMPLIKACJA_LEWA,
    )
