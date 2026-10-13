"""Testy rejestru praw (``app.logic.laws``) i treści w ``app.logic.laws_data``.

Testy nie zakładają liczby praw. Sprawdzają własności, które musi mieć **każde**
prawo, więc nowy plik treści (PRZ-004, PRZ-005, PRZ-024) ich nie zepsuje — albo
spełnia kontrakt, albo test pada i wskazuje brakujące pole.
"""

from __future__ import annotations

import importlib
import inspect
from dataclasses import replace
from pathlib import Path

import pytest

from app.logic import formula, laws, laws_data, truth
from app.logic.law_model import Law
from app.logic.laws import all_laws, by_category, categories, get, validate
from app.logic.laws_data import podstawowe

#: Prawa z tej karty — sprawdzamy tylko ich wzajemną kolejność, nie liczbę praw.
PODSTAWOWE = (
    "wylaczony-srodek",
    "identycznosci",
    "podwojne-przeczenie",
    "definiowanie-implikacji",
    "kontrapozycji",
)

#: Liczba słów w jednym zdaniu treści „po ludzku”.
MAX_SLOW_W_ZDANIU = 20


def _equivalent(lewa: str, prawa: str) -> bool:
    """Czy dwie formuły z treści praw są równoważne. Parsuje oba napisy."""
    return truth.equivalent(formula.parse(lewa), formula.parse(prawa))


def _pliki_tresci() -> list[str]:
    """Nazwy modułów treści leżących w pakiecie ``laws_data``."""
    katalog = Path(laws_data.__file__).parent
    return sorted(sciezka.stem for sciezka in katalog.glob("*.py") if sciezka.stem != "__init__")


def _zdania(tekst: str) -> list[str]:
    """Dzieli tekst na zdania po kropce, wykrzykniku i znaku zapytania."""
    zdania: list[str] = []
    biezace: list[str] = []
    for znak in tekst:
        biezace.append(znak)
        if znak in ".!?":
            zdania.append("".join(biezace).strip())
            biezace = []
    if "".join(biezace).strip():
        zdania.append("".join(biezace).strip())
    return zdania


# ---------------------------------------------------------------------------
# Rejestr: automatyczne znajdowanie treści
# ---------------------------------------------------------------------------


def test_pakiet_tresci_jest_pusty():
    assert Path(laws_data.__file__).read_text(encoding="utf-8").strip() == ""


def test_kazdy_plik_tresci_wystawia_liste_laws():
    assert _pliki_tresci(), "pakiet laws_data nie ma żadnego pliku treści"
    for nazwa in _pliki_tresci():
        module = importlib.import_module(f"{laws.DATA_PACKAGE}.{nazwa}")
        assert isinstance(module.LAWS, list), f"{nazwa}.LAWS musi być listą"
        assert module.LAWS, f"{nazwa}.LAWS nie może być puste"
        for prawo in module.LAWS:
            assert isinstance(prawo, Law), f"{nazwa}: element LAWS nie jest obiektem Law"


def test_rejestr_nie_zna_nazw_plikow_tresci():
    """``laws.py`` znajduje treść sam, a nie przez import po nazwie."""
    zrodlo = inspect.getsource(laws)
    for nazwa in _pliki_tresci():
        assert nazwa not in zrodlo, f"laws.py wspomina plik treści '{nazwa}' po nazwie"


# ---------------------------------------------------------------------------
# Lista praw i wyszukiwanie
# ---------------------------------------------------------------------------


def test_rejestr_zwraca_niepusta_liste_praw():
    prawa = all_laws()
    assert prawa
    for prawo in prawa:
        assert isinstance(prawo, Law)


def test_slugi_sa_unikalne():
    slugi = [prawo.slug for prawo in all_laws()]
    assert len(slugi) == len(set(slugi))


def test_prawa_podstawowe_ida_w_kolejnosci_nauki():
    slugi = [prawo.slug for prawo in all_laws()]
    for slug in PODSTAWOWE:
        assert slug in slugi, f"brak prawa {slug} w rejestrze"
    pozycje = [slugi.index(slug) for slug in PODSTAWOWE]
    assert pozycje == sorted(pozycje)


def test_get_zwraca_prawo():
    prawo = get("kontrapozycji")
    assert isinstance(prawo, Law)
    assert prawo.slug == "kontrapozycji"


def test_get_nieznanego_sluga_zwraca_none():
    assert get("nie-ma-takiego-prawa") is None


def test_by_category_grupuje_prawa():
    grupy = by_category()
    assert set(grupy) == {prawo.kategoria for prawo in all_laws()}
    assert "podstawowe" in grupy
    assert "implikacja" in grupy
    for kategoria, prawa in grupy.items():
        assert prawa
        for prawo in prawa:
            assert prawo.kategoria == kategoria


def test_categories_w_kolejnosci_pierwszego_wystapienia():
    oczekiwane: list[str] = []
    for prawo in all_laws():
        if prawo.kategoria not in oczekiwane:
            oczekiwane.append(prawo.kategoria)
    assert categories() == oczekiwane


# ---------------------------------------------------------------------------
# Sprawdzanie treści
# ---------------------------------------------------------------------------


def _podmien_pierwsze_prawo(monkeypatch: pytest.MonkeyPatch, **zmiany: object) -> None:
    """Podmienia pierwsze prawo podstawowe na wersję ze zmienionym polem."""
    prawo = replace(podstawowe.LAWS[0], **zmiany)
    monkeypatch.setattr(podstawowe, "LAWS", [prawo])


def test_validate_pusta_dla_obecnej_tresci():
    assert validate() == []


def test_validate_przyjmuje_nowa_kategorie(monkeypatch: pytest.MonkeyPatch):
    """Rejestr nie narzuca listy kategorii — ``dodatkowe`` ma przechodzić."""
    _podmien_pierwsze_prawo(monkeypatch, kategoria="dodatkowe")
    assert validate() == []


def test_validate_zglasza_puste_pole(monkeypatch: pytest.MonkeyPatch):
    _podmien_pierwsze_prawo(monkeypatch, nazwa="")
    problemy = validate()
    assert problemy
    assert any("nazwa" in problem for problem in problemy)


def test_validate_zglasza_nieznany_rysunek(monkeypatch: pytest.MonkeyPatch):
    _podmien_pierwsze_prawo(monkeypatch, wizualizacja="hologram")
    problemy = validate()
    assert problemy
    assert any("hologram" in problem for problem in problemy)


def test_validate_zglasza_zly_indeks_odpowiedzi(monkeypatch: pytest.MonkeyPatch):
    pytanie = dict(podstawowe.LAWS[0].quiz[0], poprawna=99)
    _podmien_pierwsze_prawo(monkeypatch, quiz=[pytanie])
    problemy = validate()
    assert problemy
    assert any("poprawna" in problem for problem in problemy)


def test_validate_zglasza_zbyt_malo_krokow(monkeypatch: pytest.MonkeyPatch):
    _podmien_pierwsze_prawo(monkeypatch, kroki=podstawowe.LAWS[0].kroki[:1])
    problemy = validate()
    assert problemy
    assert any("kroki" in problem for problem in problemy)


# ---------------------------------------------------------------------------
# Treść każdego prawa
# ---------------------------------------------------------------------------


def test_kazde_prawo_ma_wypelnione_pola():
    for prawo in all_laws():
        where = prawo.slug
        for pole in (
            "slug",
            "nazwa",
            "kategoria",
            "formula",
            "formula_ascii",
            "lewa",
            "prawa",
            "po_ludzku",
            "przyklad",
            "wizualizacja",
        ):
            wartosc = getattr(prawo, pole)
            assert isinstance(wartosc, str) and wartosc.strip(), f"{where}: puste pole {pole}"
        assert prawo.wizualizacja in laws.WIZUALIZACJE, f"{where}: nieznany rysunek"


def test_lewa_i_prawa_sa_rownowazne():
    for prawo in all_laws():
        assert _equivalent(prawo.lewa, prawo.prawa), f"{prawo.slug}: strony nie są równoważne"


def test_wzor_kazdego_prawa_jest_tautologia():
    """Wzór prawa musi się parsować i być prawdziwy przy każdym wartościowaniu."""
    for prawo in all_laws():
        wzor = formula.parse(prawo.formula)
        assert truth.is_tautology(wzor), f"{prawo.slug}: wzór {prawo.formula} nie jest tautologią"
        formula.parse(prawo.formula_ascii)


def test_kroki_zmieniaja_formule_rownowaznie():
    for prawo in all_laws():
        where = prawo.slug
        kroki = prawo.kroki
        assert 3 <= len(kroki) <= 6, f"{where}: kroków jest {len(kroki)}, a ma być od 3 do 6"
        assert kroki[0].reguła == "założenie", (
            f"{where}: pierwszy krok musi mieć regułę 'założenie'"
        )
        assert kroki[-1].po == prawo.prawa, f"{where}: ostatni krok nie kończy się na polu prawa"
        for krok in kroki:
            assert krok.opis.strip(), f"{where}: krok bez opisu"
            assert _equivalent(krok.przed, krok.po), (
                f"{where}: krok '{krok.opis}' nie jest równoważny"
            )
        for poprzedni, nastepny in zip(kroki, kroki[1:], strict=False):
            assert _equivalent(poprzedni.po, nastepny.przed), (
                f"{where}: krok '{nastepny.opis}' nie zaczyna się tam, gdzie kończy poprzedni"
            )


def test_po_ludzku_jest_dosyc_dlugie_i_ma_krotkie_zdania():
    for prawo in all_laws():
        assert len(prawo.po_ludzku) >= 80, f"{prawo.slug}: 'po_ludzku' ma za mało znaków"
        for zdanie in _zdania(prawo.po_ludzku):
            slowa = len(zdanie.split())
            assert slowa <= MAX_SLOW_W_ZDANIU, f"{prawo.slug}: zdanie ma {slowa} słów: {zdanie}"


def test_czeste_bledy_maja_od_dwoch_do_trzech_wpisow():
    for prawo in all_laws():
        assert 2 <= len(prawo.czeste_bledy) <= 3, f"{prawo.slug}: zła liczba częstych błędów"
        for blad in prawo.czeste_bledy:
            assert blad.strip(), f"{prawo.slug}: pusty wpis w czeste_bledy"


def test_quiz_ma_poprawne_pytania():
    for prawo in all_laws():
        assert 2 <= len(prawo.quiz) <= 3, f"{prawo.slug}: zła liczba pytań quizu"
        for numer, pytanie in enumerate(prawo.quiz, start=1):
            where = f"{prawo.slug}, pytanie {numer}"
            assert pytanie["pytanie"].strip(), f"{where}: puste pytanie"
            assert 3 <= len(pytanie["opcje"]) <= 4, f"{where}: zła liczba odpowiedzi"
            for opcja in pytanie["opcje"]:
                assert opcja.strip(), f"{where}: pusta odpowiedź"
            assert 0 <= pytanie["poprawna"] < len(pytanie["opcje"]), f"{where}: zły indeks"
            assert pytanie["podpowiedz"].strip(), f"{where}: brak podpowiedzi"
            assert pytanie["wyjasnienie"].strip(), f"{where}: brak wyjaśnienia"
