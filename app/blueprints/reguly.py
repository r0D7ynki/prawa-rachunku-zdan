"""Strona ``/reguly`` — reguły wnioskowania z wykładu 2 (karta PRZ-090).

Treść pochodzi w całości z rejestru ``app.logic.rules``; ten moduł niczego nie dopisuje
i nie zakłada, ile reguł jest w zestawie. Dwie sekcje („Reguły pierwotne” i „Reguły
dodatkowe”) powstają z pola ``Rule.typ``, więc kolejność i podział idą za wykładem.

Wzory rysuje ``app.logic.formula.to_html`` i wstawiamy je w szablonie przez ``|safe``,
tak samo jak ``app/blueprints/laws.py``. Są dwie drogi, bo w danych rejestru są dwa
rodzaje zapisu:

* ``tautologia`` i ``tautologie_dodatkowe`` mają zwykłe zmienne (``p``, ``q``) i idą
  prosto do ``formula.to_html`` (``formula_to_html``),
* ``przeslanki``, ``wniosek`` i ``wnioski_dodatkowe`` używają **metazmiennych** ``Φ``,
  ``Ψ`` — parser przyjmuje tylko nazwy ASCII, więc przed parsowaniem zamieniamy je na
  litery, a po sparsowaniu wracamy do ``Φ``/``Ψ`` w drzewie (``metazmienne_to_html``).
  Dzięki temu spójniki wyglądają tak samo jak na pozostałych stronach.

Karta reguły pokazuje przesłanki nad kreską, a wniosek pod nią. Kreska to element HTML
(``div.regula-kreska``) malowany w CSS — nie znak ``—``. Strona nie potrzebuje
JavaScriptu: cała treść jest w HTML.
"""

from __future__ import annotations

from flask import Blueprint, render_template
from markupsafe import Markup, escape

from app.logic.formula import FormulaError, Var, parse, replace, to_html
from app.logic.rules import DODATKOWA, PIERWOTNA, Rule, rules

#: Nazwa blueprintu i trasa to tokeny interfejsu (adres ``/reguly`` z mapy kodu).
bp = Blueprint("reguly", __name__)

#: Metazmienna wykładu → litera, którą przyjmuje parser. Zamiana działa tylko na czas
#: parsowania: ``formula.replace`` przywraca ``Φ``, ``Ψ``, ``Θ`` w gotowym drzewie.
#: Litery ``F``, ``G``, ``H`` nie występują w zapisach reguł, więc nie ma kolizji.
METAZMIENNE: dict[str, str] = {"Φ": "F", "Ψ": "G", "Θ": "H"}

#: Adres placu zabaw. Tautologię reguły dopisujemy do adresu jako parametr ``formula``.
PLAC_ZABAW = "/plac-zabaw"


def formula_to_html(text: str, styl: str = "wyklad") -> Markup:
    """Zwraca wzór jako bezpieczny HTML z ``formula.to_html``.

    Gdy napis nie jest poprawną formułą, oddajemy go jako zwykły tekst — brak
    przecinka w treści reguły pokaże brzydki wzór, a nie stronę z błędem 500.
    Poprawną treść rejestru sprawdza ``tests/test_rules.py``.
    """
    try:
        return Markup(to_html(parse(text), styl))
    except FormulaError:
        return escape(text)


def metazmienne_to_html(text: str) -> Markup:
    """Rysuje wzór z metazmiennymi (``Φ → Ψ``) przez ``formula.to_html``.

    Parser zna tylko nazwy ASCII, a ``Φ`` i ``Ψ`` to metazmienne z wykładu. Dlatego
    przed parsowaniem zamieniamy je na litery ``F``, ``G`` i ``H``, a po sparsowaniu
    wracamy do metazmiennych w drzewie — ``formula.to_html`` wypisuje nazwę zmiennej
    dokładnie tak, jak stoi w drzewie. Kolejność członów zostaje taka jak w wykładzie,
    bo ``parse`` i ``replace`` nie przestawiają argumentów (robi to dopiero
    ``formula.normalize``, którego tu nie wołamy).
    """
    zamiana = text
    for metazmienna, litera in METAZMIENNE.items():
        zamiana = zamiana.replace(metazmienna, litera)
    try:
        drzewo = parse(zamiana)
    except FormulaError:
        return escape(text)
    for metazmienna, litera in METAZMIENNE.items():
        drzewo = replace(drzewo, Var(litera), Var(metazmienna))
    return Markup(to_html(drzewo))


def _reguly_typu(typ: str) -> list[Rule]:
    """Reguły danego typu, w kolejności z rejestru."""
    return [regula for regula in rules() if regula.typ == typ]


@bp.get("/reguly")
def reguly():
    """Lista reguł wnioskowania: siedem pierwotnych i trzy dodatkowe."""
    pierwotne = _reguly_typu(PIERWOTNA)
    dodatkowe = _reguly_typu(DODATKOWA)
    return render_template(
        "reguly.html",
        pierwotne=pierwotne,
        dodatkowe=dodatkowe,
        liczba=len(pierwotne) + len(dodatkowe),
        formula_to_html=formula_to_html,
        metazmienne_to_html=metazmienne_to_html,
        plac_zabaw=PLAC_ZABAW,
    )
