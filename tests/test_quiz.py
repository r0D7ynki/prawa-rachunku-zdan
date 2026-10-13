"""Testy generatora quizu (PRZ-007)."""

from __future__ import annotations

import random

import pytest

from app.logic import laws, truth
from app.logic.formula import parse
from app.logic.quiz import RODZAJE, Question, check, generate

#: Początek pytania o równoważność. Test wycina z niego formułę pytania.
POCZATEK_ROWNOWAZNOSCI = "Która formuła jest równoważna formule "

#: Szkielet pytania o błąd: test wycina z niego obie formuły przekształcenia.
POCZATEK_BLEDU = "W przekształceniu formuły "
ROZDZIELACZ_BLEDU = " w formułę "
KONIEC_BLEDU = " jest błąd. Co poszło nie tak?"

#: Opis, który nigdy nie może być poprawną odpowiedzią w pytaniu o błąd.
OPIS_BEZ_BLEDU = "Nic — przekształcenie jest poprawne."

#: Prawo z ``podstawowe.py`` — jego treść jest zawsze dostępna.
PRAWO_PODSTAWOWE = "wylaczony-srodek"


def _rodzaj(pytanie: Question) -> str:
    """Rodzaj pytania — token zapisany w identyfikatorze pytania."""
    return next(czesc for czesc in pytanie.id.split("-") if czesc in RODZAJE)


def _tresc(pytanie: Question) -> tuple[str, str, str]:
    """Treść pytania bez seeda i numeru z ``id`` — do porównywania zestawów."""
    return (pytanie.prawo, _rodzaj(pytanie), pytanie.pytanie)


def _pytania_rodzaju(rodzaj: str, seedy: range = range(3)) -> list[Question]:
    """Wszystkie pytania danego rodzaju: każde prawo razy kilka seedów.

    Bierzemy wszystkie prawa, a nie jedno losowe prawo, żeby test nie zależał od tego,
    które wzory wypadły w losowaniu.
    """
    return [
        pytanie
        for law in laws.all_laws()
        for seed in seedy
        for pytanie in generate(prawo=law.slug, seed=seed, ile=100)
        if _rodzaj(pytanie) == rodzaj
    ]


def _formula_z_pytania(pytanie: Question) -> str:
    """Formuła, o którą pyta pytanie o równoważność."""
    assert pytanie.pytanie.startswith(POCZATEK_ROWNOWAZNOSCI)
    assert pytanie.pytanie.endswith("?")
    return pytanie.pytanie[len(POCZATEK_ROWNOWAZNOSCI) : -1]


def _formuly_z_pytania_o_blad(pytanie: Question) -> tuple[str, str]:
    """Formuła przed i po błędnym przekształceniu, o które pyta pytanie."""
    assert pytanie.pytanie.startswith(POCZATEK_BLEDU)
    assert pytanie.pytanie.endswith(KONIEC_BLEDU)
    srodek = pytanie.pytanie[len(POCZATEK_BLEDU) : -len(KONIEC_BLEDU)]
    przed, po = srodek.split(ROZDZIELACZ_BLEDU)
    return przed, po


def _slug_prawa() -> str:
    """Prawo do testów: ``de-morgan-1``, a gdy tej treści jeszcze nie ma — z ``podstawowe.py``."""
    if laws.get("de-morgan-1") is None:
        return PRAWO_PODSTAWOWE
    return "de-morgan-1"


# ---------------------------------------------------------------------------
# Powtarzalność i losowość
# ---------------------------------------------------------------------------


def test_ten_sam_seed_daje_ten_sam_zestaw():
    pierwszy = generate(seed=7, ile=5)
    drugi = generate(seed=7, ile=5)

    assert pierwszy == drugi
    assert [pytanie.opcje for pytanie in pierwszy] == [pytanie.opcje for pytanie in drugi]


def test_rozne_seedy_daja_rozne_zestawy():
    """Zestawy z różnych seedów różnią się wyborem pytań, a nie tylko numerami w ``id``."""
    pierwszy = {_tresc(pytanie) for pytanie in generate(seed=1)}
    drugi = {_tresc(pytanie) for pytanie in generate(seed=2)}

    assert pierwszy != drugi
    assert pierwszy - drugi


def test_ten_sam_seed_daje_ten_sam_zestaw_jednego_prawa():
    slug = _slug_prawa()

    assert generate(prawo=slug, seed=4) == generate(prawo=slug, seed=4)


def test_generate_nie_uzywa_globalnego_random():
    random.seed(2026)
    przed = random.getstate()

    generate(seed=7)
    generate(seed=None)

    assert random.getstate() == przed


def test_bez_seeda_tez_powstaje_zestaw():
    assert len(generate(ile=3, seed=None)) == 3


def test_kolejnosc_odpowiedzi_jest_losowana():
    """Odpowiedzi z pola ``quiz`` mają poprawną na pierwszym miejscu — quiz ją tasuje."""
    numery = {pytanie.poprawna for seed in range(6) for pytanie in generate(seed=seed, ile=15)}

    assert numery - {0}


# ---------------------------------------------------------------------------
# Wybór prawa i budowa pytania
# ---------------------------------------------------------------------------


def test_generate_z_prawem_daje_tylko_to_prawo():
    slug = _slug_prawa()
    pytania = generate(prawo=slug, seed=3)

    assert len(pytania) == 5
    assert {pytanie.prawo for pytanie in pytania} == {slug}


def test_prawo_z_podstawowe_daje_piec_pytan():
    pytania = generate(prawo=PRAWO_PODSTAWOWE, seed=3, ile=5)

    assert len(pytania) == 5
    assert {pytanie.prawo for pytanie in pytania} == {PRAWO_PODSTAWOWE}


def test_nieznane_prawo_nie_daje_pytan():
    assert generate(prawo="nie-ma-takiego-prawa", seed=1) == []


@pytest.mark.parametrize("slug", [law.slug for law in laws.all_laws()])
def test_kazde_prawo_ma_piec_pytan(slug):
    assert len(generate(prawo=slug, seed=3, ile=5)) == 5


def test_kazde_pytanie_ma_poprawna_budowe():
    pytania = generate(seed=7, ile=20)
    slugi = {law.slug for law in laws.all_laws()}

    assert len(pytania) == 20
    assert len({pytanie.id for pytanie in pytania}) == len(pytania)
    for pytanie in pytania:
        assert 3 <= len(pytanie.opcje) <= 4
        assert len(set(pytanie.opcje)) == len(pytanie.opcje)
        assert 0 <= pytanie.poprawna < len(pytanie.opcje)
        assert pytanie.podpowiedz.strip()
        assert pytanie.wyjasnienie.strip()
        assert pytanie.prawo in slugi


def test_zestaw_ma_wszystkie_rodzaje_pytan():
    rodzaje = {_rodzaj(pytanie) for pytanie in generate(seed=7, ile=40)}

    assert rodzaje == set(RODZAJE)


# ---------------------------------------------------------------------------
# Pytania o równoważność
# ---------------------------------------------------------------------------


def test_dystraktory_rownowaznosci_nie_sa_rownowazne_formule_pytania():
    pytania = _pytania_rodzaju("rownowaznosc")

    assert pytania, "zestaw powinien zawierać pytania o równoważność"
    for pytanie in pytania:
        wzor = parse(_formula_z_pytania(pytanie))
        poprawna = parse(pytanie.opcje[pytanie.poprawna])
        assert truth.equivalent(poprawna, wzor)
        for numer, opcja in enumerate(pytanie.opcje):
            if numer == pytanie.poprawna:
                continue
            assert not truth.equivalent(parse(opcja), wzor)


def test_przeksztalcenie_w_pytaniu_o_blad_naprawde_jest_bledne():
    pytania = _pytania_rodzaju("blad")

    assert pytania, "zestaw powinien zawierać pytania o błąd"
    for pytanie in pytania:
        przed, po = _formuly_z_pytania_o_blad(pytanie)
        assert not truth.equivalent(parse(przed), parse(po))
        if OPIS_BEZ_BLEDU in pytanie.opcje:
            assert pytanie.opcje[pytanie.poprawna] != OPIS_BEZ_BLEDU


# ---------------------------------------------------------------------------
# Sprawdzanie odpowiedzi
# ---------------------------------------------------------------------------


def test_check_przyjmuje_poprawna_odpowiedz():
    pytanie = generate(seed=3)[0]

    assert check(None, 3, pytanie.id, pytanie.poprawna) is True


def test_check_odrzuca_kazda_inna_odpowiedz():
    pytanie = generate(seed=3)[0]

    for numer in range(len(pytanie.opcje)):
        if numer == pytanie.poprawna:
            continue
        assert check(None, 3, pytanie.id, numer) is False


def test_check_odrzuca_nieznane_id():
    assert check(None, 3, "nie-ma-takiego-pytania", 0) is False
    assert check(None, 3, "", 0) is False


def test_check_odrzuca_odpowiedz_ktora_nie_jest_liczba():
    pytanie = generate(seed=3)[0]

    assert check(None, 3, pytanie.id, "0") is False
    assert check(None, 3, pytanie.id, None) is False


def test_check_dziala_dla_pytania_spoza_pierwszej_piatki():
    """Przeglądarka może pobrać dłuższy zestaw, a ``check`` nie dostaje liczby pytań."""
    pytanie = generate(seed=5, ile=20)[-1]

    assert check(None, 5, pytanie.id, pytanie.poprawna) is True


def test_check_dziala_dla_jednego_prawa():
    slug = _slug_prawa()
    pytanie = generate(prawo=slug, seed=9)[0]

    assert check(slug, 9, pytanie.id, pytanie.poprawna) is True


def test_check_nie_znajduje_pytania_innego_prawa():
    pytanie = generate(prawo=PRAWO_PODSTAWOWE, seed=9)[0]

    assert check("identycznosci", 9, pytanie.id, pytanie.poprawna) is False


# ---------------------------------------------------------------------------
# Odpowiedź nie wycieka do przeglądarki
# ---------------------------------------------------------------------------


def test_to_public_dict_ukrywa_odpowiedz_i_wyjasnienie():
    pytanie = generate(seed=4)[0]
    dane = pytanie.to_public_dict()

    assert "poprawna" not in dane
    assert "wyjasnienie" not in dane
    assert dane["id"] == pytanie.id
    assert dane["prawo"] == pytanie.prawo
    assert dane["pytanie"] == pytanie.pytanie
    assert dane["opcje"] == pytanie.opcje
    assert dane["podpowiedz"] == pytanie.podpowiedz
