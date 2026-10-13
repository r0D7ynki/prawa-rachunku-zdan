"""Testy strony ``/kpn`` — klauzul, koniunkcyjnej postaci normalnej i testu tautologii.

Testy nie wierzą stronie na słowo. Wzory porównują z wynikiem ``formula.to_html``,
a nazwy i odnośniki praw — z rejestrem ``app.logic.laws``. Dzięki temu zmiana treści
praw albo wyprowadzenia nie może przejść niezauważona.

Kluczowe kryterium karty sprawdzamy dwoma drogami:

* ``truth.is_tautology`` liczy wynik dla formuły z przykładu i dla kontrprzykładu,
* ta sama reguła liczona lokalnie (para ``x`` i ``∼x`` w każdej klauzuli) musi dać
  ten sam werdykt — inaczej lekcja uczyłaby złej reguły.
"""

from __future__ import annotations

import re
from html import unescape
from pathlib import Path

import pytest
from markupsafe import Markup

from app import create_app
from app.blueprints import kpn
from app.logic import laws, truth
from app.logic.formula import FormulaError, evaluate, parse, to_html

URL = "/kpn"

#: Formuły z wykładu, wpisane w teście dosłownie — test ma padać, gdy znikną ze strony.
TAUTOLOGY_FORMULA = "(p ∨ q ∨ ∼p) ∧ (∼p ∨ q ∨ r ∨ ∼q) ∧ (∼s ∨ s)"
NON_TAUTOLOGY_FORMULA = "(p ∨ q) ∧ (∼p ∨ r)"

#: Nagłówek kolumny z klauzulą na stronie — po nim znajdujemy tabelę testu tautologii.
CLAUSE_CAPTION = "każdą klauzulę przykładu"

#: Wyrażenie wstawiane do HTML przez filtr ``|safe``.
SAFE_PATTERN = re.compile(r"\{\{(?P<expression>.*?)\|\s*safe\s*\}\}", re.DOTALL)

TEMPLATE = Path(__file__).resolve().parents[1] / "app" / "templates" / "kpn.html"

TABLE = re.compile(r"<table\b[^>]*>(?P<body>.*?)</table>", re.DOTALL)
ROW = re.compile(r"<tr>(?P<body>.*?)</tr>", re.DOTALL)
CELL = re.compile(r"<t[dh][^>]*>(?P<body>.*?)</t[dh]>", re.DOTALL)
TABLE_BODY = re.compile(r"<tbody>(?P<body>.*?)</tbody>", re.DOTALL)


@pytest.fixture(scope="module")
def client():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def html(client):
    response = client.get(URL)
    assert response.status_code == 200
    return response.get_data(as_text=True)


@pytest.fixture(scope="module")
def text(html):
    """Cała strona jako tekst: bez znaczników, z pojedynczymi spacjami."""
    return _text(html)


# --- narzędzia ---------------------------------------------------------------


def _text(fragment: str) -> str:
    """Zamienia fragment HTML na tekst: usuwa znaczniki, odmienia encje i skleja spacje."""
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment))).strip()


def _formula_html(formula: str, style: str = "wyklad") -> str:
    """Wzór jako HTML z ``formula.to_html`` — to samo, co wstawia strona."""
    return str(kpn.formula_to_html(formula, style))


def _rows(table: str) -> list[list[str]]:
    """Teksty komórek kolejnych wierszy tablicy."""
    body = TABLE_BODY.search(table).group("body")
    return [[_text(cell) for cell in CELL.findall(row)] for row in ROW.findall(body)]


def _table(html: str, caption: str) -> str:
    """Treść tablicy, której podpis (``<caption>``) zawiera dany fragment."""
    matches = [body for body in TABLE.findall(html) if caption in body]
    assert len(matches) == 1, f"nie znalazłem dokładnie jednej tablicy z {caption!r}"
    return matches[0]


def _pairs_per_rule(formula: str) -> list[bool]:
    """Werdykt reguły z lekcji: czy każda klauzula ma parę ``x`` i ``∼x``."""
    return [bool(clause.pairs) for clause in kpn.clauses_with_pairs(formula)]


# --- szkielet strony ---------------------------------------------------------


def test_page_returns_200_and_utf8_html(client):
    response = client.get(URL)
    assert response.status_code == 200
    content_type = response.headers["Content-Type"]
    assert content_type.startswith("text/html")
    assert "charset=utf-8" in content_type.lower()


def test_page_is_polish_and_has_exactly_one_h1(html):
    assert 'lang="pl"' in html
    assert len(re.findall(r"<h1\b", html)) == 1


def test_page_leaves_no_unfilled_templates(html):
    assert "{{" not in html
    assert "{%" not in html


# --- klauzula ----------------------------------------------------------------


def test_page_gives_clause_definition(text):
    assert "klauzula" in text.lower()
    assert "alternatywa zmiennych zdaniowych" in text
    assert "lista warunków połączonych słowem lub" in text


@pytest.mark.parametrize("clause", kpn.CLAUSE_EXAMPLES)
def test_page_shows_three_clause_examples(html, clause):
    assert _formula_html(clause) in html
    assert clause in kpn.CLAUSE_EXAMPLES


def test_clause_examples_are_three():
    assert len(kpn.CLAUSE_EXAMPLES) == 3


# --- koniunkcyjna postać normalna --------------------------------------------


def test_page_gives_cnf_definition(text):
    assert "koniunkcyjna postać normalna" in text.lower()
    assert "koniunkcją pewnej liczby klauzul" in text


@pytest.mark.parametrize("formula", kpn.CNF_EXAMPLES)
def test_page_shows_both_cnf_examples(html, formula):
    assert _formula_html(formula) in html


def test_cnf_examples_are_conjunctions_of_clauses():
    for formula in kpn.CNF_EXAMPLES:
        assert len(kpn.split_clauses(parse(formula))) >= 2


# --- wyprowadzenie (p → q) → ∼r ----------------------------------------------


def test_page_shows_full_implication_derivation(html):
    assert _formula_html(kpn.IMPLICATION_FORMULA) in html
    for step in kpn.IMPLICATION_STEPS:
        assert _formula_html(step.formula) in html, f"brak kroku wyprowadzenia: {step.formula!r}"


def test_implication_derivation_ends_with_card_conclusion(html):
    last = kpn.IMPLICATION_STEPS[-1].formula
    assert last == "(p ∨ ∼r) ∧ (∼q ∨ ∼r)"
    assert _formula_html(last) in html


def test_implication_derivation_has_as_many_steps_as_lecture():
    assert [step.formula for step in kpn.IMPLICATION_STEPS] == [
        "(∼p ∨ q) → ∼r",
        "∼(∼p ∨ q) ∨ ∼r",
        "(p ∧ ∼q) ∨ ∼r",
        "(p ∨ ∼r) ∧ (∼q ∨ ∼r)",
    ]


def test_distributivity_step_invokes_second_law():
    assert kpn.IMPLICATION_STEPS[-1].laws == ("rozdzielnosc-2",)


# --- wyprowadzenie p ≡ q -----------------------------------------------------


def test_page_shows_equivalence_derivation(html):
    assert _formula_html(kpn.EQUIVALENCE_FORMULA) in html
    for step in kpn.EQUIVALENCE_STEPS:
        assert _formula_html(step.formula) in html, f"brak kroku wyprowadzenia: {step.formula!r}"


def test_equivalence_derivation_ends_with_card_formula(html):
    last = kpn.EQUIVALENCE_STEPS[-1].formula
    assert last == "∼(∼(∼p ∨ q) ∨ ∼(∼q ∨ p))"
    assert _formula_html(last) in html


# --- nazwy praw przy krokach -------------------------------------------------


def test_steps_invoke_laws_from_registry(html, text):
    slugs = {
        slug
        for steps in (kpn.IMPLICATION_STEPS, kpn.EQUIVALENCE_STEPS)
        for step in steps
        for slug in step.laws
    }

    assert slugs, "wyprowadzenia muszą powoływać prawa z rejestru"
    for slug in slugs:
        law = laws.get(slug)
        assert law is not None, f"krok powołuje prawo spoza rejestru: {slug}"
        assert f'href="/prawa/{slug}"' in html
        assert law.nazwa in text


def test_every_step_has_at_least_one_law():
    for steps in (kpn.IMPLICATION_STEPS, kpn.EQUIVALENCE_STEPS):
        assert all(step.laws for step in steps)


# --- test tautologiczności ---------------------------------------------------


def test_page_gives_tautology_test_rule(text):
    assert "każdej klauzuli" in text
    assert "zmienna zdaniowa i jej negacja" in text


def test_page_shows_tautology_example(html, text):
    assert _formula_html(TAUTOLOGY_FORMULA) in html
    assert _formula_html(kpn.TAUTOLOGY_EXAMPLE) in html
    assert "Formuła jest tautologią" in text


def test_truth_says_example_is_tautology():
    assert truth.is_tautology(parse(TAUTOLOGY_FORMULA)) is True


def test_truth_says_counterexample_is_not_tautology():
    assert truth.is_tautology(parse(NON_TAUTOLOGY_FORMULA)) is False


def test_lesson_rule_agrees_with_truth():
    """Reguła z lekcji i ``truth.is_tautology`` muszą się zgadzać w obie strony."""
    for formula, verdict in ((TAUTOLOGY_FORMULA, True), (NON_TAUTOLOGY_FORMULA, False)):
        assert all(_pairs_per_rule(formula)) is verdict
        assert truth.is_tautology(parse(formula)) is verdict


def test_page_shows_complementary_pairs_in_tautology_clauses(html):
    rows = _rows(_table(html, CLAUSE_CAPTION))

    assert [row[0] for row in rows] == [
        _text(_formula_html(formula)) for formula in ("p ∨ q ∨ ∼p", "∼p ∨ q ∨ r ∨ ∼q", "∼s ∨ s")
    ]
    assert [row[1] for row in rows] == ["p", "q", "s"]


# --- kontrprzykład -----------------------------------------------------------


def test_page_shows_counterexample_with_explanation(html, text):
    assert _formula_html(NON_TAUTOLOGY_FORMULA) in html
    assert "nie jest tautologią" in text
    assert "nie ma pary" in text
    assert "∼p" in text


def test_counterexample_has_clauses_without_pairs():
    clauses = kpn.clauses_with_pairs(NON_TAUTOLOGY_FORMULA)

    assert [clause.formula for clause in clauses] == ["p ∨ q", "∼p ∨ r"]
    assert [clause.pairs for clause in clauses] == [[], []]


def test_counterexample_gives_falsifying_assignment(html):
    assignment = kpn.falsifying_assignment(NON_TAUTOLOGY_FORMULA)

    assert assignment is not None
    assert evaluate(parse(NON_TAUTOLOGY_FORMULA), assignment) is False
    for name, value in assignment.items():
        assert f"{name} = {1 if value else 0}" in _text(html)


# --- dlaczego KPN jest przydatna i wynik silnika -----------------------------


def test_page_says_why_cnf_is_useful(text):
    assert "bez wypisywania całej tablicy prawdy" in text


def test_engine_clauses_split_to_cnf_result():
    result = kpn.engine_clauses("(p → q) → ∼r")

    assert result["cnf"] == "(p ∨ ∼r) ∧ (∼q ∨ ∼r)"
    assert result["clauses"] == ["p ∨ ∼r", "∼q ∨ ∼r"]


def test_page_shows_engine_clauses(html):
    result = kpn.engine_clauses(kpn.IMPLICATION_FORMULA)
    for clause in result["clauses"]:
        assert _formula_html(clause) in html


def test_page_links_to_playground_with_formula(html):
    assert 'href="/plac-zabaw?formula=' in html
    assert "cel=cnf" in html


# --- nawigacja i bezpieczeństwo szablonu -------------------------------------


def test_page_has_previous_and_next_lesson_links(html, text):
    assert 'href="/przeksztalcanie"' in html
    assert 'href="/prawa"' in html
    assert "Poprzednia lekcja" in text
    assert "Następna lekcja" in text


def test_template_uses_safe_only_on_to_html_output():
    expressions = [
        match["expression"].strip() for match in SAFE_PATTERN.finditer(TEMPLATE.read_text("utf-8"))
    ]

    assert expressions, "szablon nie wstawia wzorów przez |safe"
    for expression in expressions:
        assert "to_html" in expression, f"|safe na {expression!r}"


# --- funkcje pomocnicze modułu -----------------------------------------------


def test_formula_to_html_returns_plain_text_without_error():
    result = kpn.formula_to_html("to nie jest formuła ((")

    assert isinstance(result, Markup)
    assert result == "to nie jest formuła (("


def test_formula_to_html_returns_html_for_formula():
    assert str(kpn.formula_to_html("∼p")) == str(to_html(parse("∼p")))


def test_split_clauses_returns_conjunction_parts():
    clauses = kpn.split_clauses(parse("(p ∨ q) ∧ ∼p ∧ (r ∨ ∼s)"))

    assert [to_html(clause) for clause in clauses] == [
        to_html(parse("p ∨ q")),
        to_html(parse("∼p")),
        to_html(parse("r ∨ ∼s")),
    ]


def test_split_clauses_keeps_single_clause():
    assert len(kpn.split_clauses(parse("p ∨ ∼q"))) == 1


def test_complementary_pairs_find_variable_with_negation():
    assert kpn.complementary_pairs("p ∨ q ∨ ∼p") == ["p"]
    assert kpn.complementary_pairs("∼p ∨ q ∨ r ∨ ∼q") == ["q"]
    assert kpn.complementary_pairs("∼s ∨ s") == ["s"]
    assert kpn.complementary_pairs("p ∨ q") == []


def test_complementary_pairs_reject_non_clause():
    with pytest.raises(FormulaError):
        kpn.complementary_pairs("p → q")


def test_clauses_with_pairs_return_text_and_pairs():
    clauses = kpn.clauses_with_pairs(NON_TAUTOLOGY_FORMULA)

    assert [clause.formula for clause in clauses] == ["p ∨ q", "∼p ∨ r"]
    assert [clause.pairs for clause in clauses] == [[], []]


def test_falsifying_assignment_for_tautology_is_none():
    assert kpn.falsifying_assignment(TAUTOLOGY_FORMULA) is None


def test_steps_for_view_takes_law_names_from_registry():
    step = kpn.Step(formula="∼p ∨ q", laws=("definiowanie-implikacji",))

    view = kpn.steps_for_view([step])

    assert view == [
        {
            "formula": "∼p ∨ q",
            "laws": [{"slug": "definiowanie-implikacji", "name": "Prawo definiowania implikacji"}],
        }
    ]
