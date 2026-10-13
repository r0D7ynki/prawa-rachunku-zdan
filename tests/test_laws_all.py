"""Test kompletności zestawu 14 praw (karta PRZ-016).

Karta zamyka projekt, więc ten plik pilnuje **całości** rejestru, a nie jednego
pliku treści. Sprawdza, że:

* prawa o kategorii innej niż ``dodatkowe`` to dokładnie 14 pozycji T1–T14
  z tabeli w ``docs/TRESC-PRAW.md`` — z tymi samymi sługami, nazwami,
  kategoriami i wzorami, w kolejności z wykładu,
* prawa dodatkowe (``app/logic/laws_data/dodatkowe.py``) są obecne i mają
  kategorię ``dodatkowe``,
* każde prawo ma pełną treść: ``lewa`` i ``prawa``, kroki, częste błędy i quiz,
* każdy krok jest równoważny temu, co przed nim stało,
* ``validate()`` nie zgłasza problemów.

Wzory porównujemy drzewem formuły (``formula.same``), bo wykład zapisuje
podwójne przeczenie jako ``∼(∼p)``, a rejestr jako ``∼∼p`` — to ta sama formuła.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.logic import formula, truth
from app.logic.law_model import Law
from app.logic.laws import all_laws, get, validate
from app.logic.laws_data import dodatkowe

DOKUMENT_TRESCI = Path(__file__).resolve().parents[1] / "docs" / "TRESC-PRAW.md"

#: Wiersz tabeli T1–T14 z ``docs/TRESC-PRAW.md``: numer, slug, nazwa, kategoria,
#: wzór w notacji wykładu i plik treści.
WIERSZ_TABELI = re.compile(
    r"^\|\s*(?P<numer>\d+)\s*"
    r"\|\s*`(?P<slug>[^`]+)`\s*"
    r"\|\s*(?P<nazwa>[^|]+?)\s*"
    r"\|\s*(?P<kategoria>[^|]+?)\s*"
    r"\|\s*`(?P<formula>[^`]+)`\s*"
    r"\|\s*`(?P<plik>[^`]+)`\s*\|",
    re.MULTILINE,
)

#: Wzory obowiązujące z wykładu — karta PRZ-016 wymienia je wprost.
WZORY_WYKLADU = {
    "de-morgan-1": "∼(p ∨ q) ≡ (∼p ∧ ∼q)",
    "de-morgan-2": "∼(p ∧ q) ≡ (∼p ∨ ∼q)",
    "rozdzielnosc-1": "((p ∨ q) ∧ r) ≡ ((p ∧ r) ∨ (q ∧ r))",
    "rozdzielnosc-2": "((p ∧ q) ∨ r) ≡ ((p ∨ r) ∧ (q ∨ r))",
    "zastepowanie-rownych": "(p ≡ q) ≡ ((p → q) ∧ (q → p))",
}

#: Kategoria praw spoza listy T1–T14.
KATEGORIA_DODATKOWE = "dodatkowe"

#: Pola ``Law``, bez których treść prawa nie jest pełna.
POLA_TEKSTOWE = (
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
)


def _dokument() -> str:
    """Treść dokumentu ``docs/TRESC-PRAW.md``."""
    return DOKUMENT_TRESCI.read_text(encoding="utf-8")


def _wiersze_tabeli() -> list[dict[str, str]]:
    """Wiersze tabeli T1–T14 z ``docs/TRESC-PRAW.md``."""
    return [dopasowanie.groupdict() for dopasowanie in WIERSZ_TABELI.finditer(_dokument())]


def _prawa_t1_t14() -> list[Law]:
    """Prawa spoza kategorii ``dodatkowe`` — lista T1–T14."""
    return [prawo for prawo in all_laws() if prawo.kategoria != KATEGORIA_DODATKOWE]


def _prawa_dodatkowe() -> list[Law]:
    return [prawo for prawo in all_laws() if prawo.kategoria == KATEGORIA_DODATKOWE]


def _rownowazne(lewa: str, prawa: str) -> bool:
    """Czy dwie formuły z treści są równoważne. Parsuje oba napisy."""
    return truth.equivalent(formula.parse(lewa), formula.parse(prawa))


# ---------------------------------------------------------------------------
# Zgodność z tabelą w docs/TRESC-PRAW.md
# ---------------------------------------------------------------------------


def test_dokument_tresci_ma_czternascie_pozycji():
    wiersze = _wiersze_tabeli()

    assert len(wiersze) == 14, f"tabela T1–T14 ma {len(wiersze)} pozycji"
    assert [wiersz["numer"] for wiersz in wiersze] == [str(n) for n in range(1, 15)]


def test_prawa_spoza_dodatkowych_to_dokladnie_tabela_t1_t14():
    oczywiste = [wiersz["slug"] for wiersz in _wiersze_tabeli()]

    assert [prawo.slug for prawo in _prawa_t1_t14()] == oczywiste


def test_kazde_prawo_z_tabeli_ma_te_sama_nazwe_i_kategorie():
    for wiersz in _wiersze_tabeli():
        prawo = get(wiersz["slug"])
        # Tabela skraca jedną nazwę kropką („Prawo zastępowania równ.”), więc
        # wystarczy, że nazwa z rejestru zaczyna się od tej z tabeli.
        nazwa_z_tabeli = wiersz["nazwa"].rstrip(".")

        assert prawo is not None, f"brak prawa {wiersz['slug']} z tabeli T1–T14"
        assert prawo.nazwa.startswith(nazwa_z_tabeli), f"{prawo.slug}: inna nazwa niż w tabeli"
        assert prawo.kategoria == wiersz["kategoria"], f"{prawo.slug}: inna kategoria niż w tabeli"


def test_wzory_praw_zgadzaja_sie_z_tabela():
    for wiersz in _wiersze_tabeli():
        prawo = get(wiersz["slug"])
        assert prawo is not None, f"brak prawa {wiersz['slug']} z tabeli T1–T14"
        assert formula.same(formula.parse(prawo.formula), formula.parse(wiersz["formula"])), (
            f"{prawo.slug}: rejestr ma {prawo.formula!r}, a wykład {wiersz['formula']!r}"
        )


def test_wzory_wymienione_w_karcie_maja_dokladny_zapis():
    for slug, wzor in WZORY_WYKLADU.items():
        prawo = get(slug)
        assert prawo is not None, f"brak prawa {slug}"
        assert prawo.formula == wzor, f"{slug}: {prawo.formula!r} zamiast {wzor!r}"


# ---------------------------------------------------------------------------
# Prawa dodatkowe
# ---------------------------------------------------------------------------


def test_prawa_dodatkowe_sa_obecne_i_pochodza_z_pliku_dodatkowe():
    z_rejestru = {prawo.slug for prawo in _prawa_dodatkowe()}

    assert z_rejestru, "rejestr nie ma praw dodatkowych"
    assert z_rejestru == {prawo.slug for prawo in dodatkowe.LAWS}


def test_prawa_dodatkowe_nie_udaja_pozycji_z_listy_t1_t14():
    dodatkowe_slugi = {prawo.slug for prawo in dodatkowe.LAWS}

    assert dodatkowe_slugi.isdisjoint({prawo.slug for prawo in _prawa_t1_t14()})


# ---------------------------------------------------------------------------
# Pełna treść każdego prawa
# ---------------------------------------------------------------------------


def test_kazde_prawo_ma_pelna_tresc():
    for prawo in all_laws():
        for pole in POLA_TEKSTOWE:
            wartosc = getattr(prawo, pole)
            assert isinstance(wartosc, str) and wartosc.strip(), f"{prawo.slug}: puste pole {pole}"
        assert len(prawo.po_ludzku) >= 80, f"{prawo.slug}: 'po_ludzku' ma za mało znaków"
        assert len(prawo.czeste_bledy) >= 2, f"{prawo.slug}: mniej niż dwa częste błędy"
        assert len(prawo.quiz) >= 2, f"{prawo.slug}: mniej niż dwa pytania quizu"


def test_lewa_i_prawa_kazdego_prawa_parsuja_sie_i_sa_rownowazne():
    for prawo in all_laws():
        assert formula.parse(prawo.lewa) is not None, f"{prawo.slug}: 'lewa' się nie parsuje"
        assert formula.parse(prawo.prawa) is not None, f"{prawo.slug}: 'prawa' się nie parsuje"
        assert _rownowazne(prawo.lewa, prawo.prawa), f"{prawo.slug}: strony nie są równoważne"


def test_kazdy_krok_jest_rownowazny_i_sklada_sie_w_ciag():
    for prawo in all_laws():
        kroki = prawo.kroki

        assert kroki, f"{prawo.slug}: brak kroków"
        assert kroki[0].reguła == "założenie", f"{prawo.slug}: pierwszy krok bez reguły 'założenie'"
        assert kroki[-1].po == prawo.prawa, f"{prawo.slug}: ostatni krok nie kończy się na 'prawa'"

        for numer, krok in enumerate(kroki, start=1):
            assert _rownowazne(krok.przed, krok.po), (
                f"{prawo.slug}: krok {numer} nie jest równoważny"
            )
        for poprzedni, nastepny in zip(kroki, kroki[1:], strict=False):
            assert _rownowazne(poprzedni.po, nastepny.przed), (
                f"{prawo.slug}: krok '{nastepny.opis}' nie zaczyna się tam, gdzie kończy poprzedni"
            )


def test_validate_nie_zglasza_problemow():
    assert validate() == []
