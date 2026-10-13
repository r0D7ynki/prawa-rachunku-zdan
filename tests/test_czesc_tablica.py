"""Testy komponentu interaktywnej tablicy prawdy (karty PRZ-011 i PRZ-073).

Tablica powstaje w przeglądarce z danych API, więc testy nie mogą jej narysować.
Sprawdzają to, co da się sprawdzić bez przeglądarki:

* co partial oddaje serwerowi (atrybuty kontenera, pliki statyczne, ``<noscript>``,
  brak liczenia wartości w Jinja),
* czy API zwraca dane w kształcie, na którym opiera się skrypt (pole ``znaki``),
* jak zbudowany jest skrypt — czy adres bierze z atrybutu, czy pokazuje słowa
  ``PRAWDA``/``FAŁSZ`` obok koloru, czy obsługuje klawiaturę i błędy po polsku,
* czy tablica rośnie krok po kroku: import wspólnego ``createStepper``, kropka
  w nieodkrytej komórce, ``aria-current`` na bieżącej i przycisk „Pokaż całą tabelę”.

Wzorzec testu źródłowego jest ten sam, co w ``tests/test_czesc_kroki.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from flask import render_template

from app import create_app

ADRES = "/api/formula/table"
FORMULA = "p ∧ q"
#: Ciało funkcji wybierającej wiersz — toleruje wcięcia, ale wymaga całej treści:
#: podstawienia **wszystkich** zmiennych z wiersza i odświeżenia widoku.
WZORZEC_WYBIERZ_WIERSZ = re.compile(
    r"const wybierzWiersz = \(\) => \{\s*"
    r"for \(const nazwa of zmienne\) \{\s*"
    r"ustawienie\.set\(nazwa, wiersz\[nazwa\]\);\s*"
    r"\}\s*"
    r"odswiez\(\);\s*\};"
)
KATALOG_STATYCZNY = Path(__file__).resolve().parents[1] / "app" / "static"
PARTIAL = (
    Path(__file__).resolve().parents[1] / "app" / "templates" / "partials" / "_truth_table.html"
)


@pytest.fixture
def aplikacja():
    return create_app({"TESTING": True})


@pytest.fixture
def klient(aplikacja):
    return aplikacja.test_client()


def _renderuj(aplikacja, **zmienne):
    with aplikacja.test_request_context():
        return render_template("partials/_truth_table.html", **zmienne)


# ---------------------------------------------------------------------------
# API — kształt danych, na którym opiera się skrypt
# ---------------------------------------------------------------------------


def test_api_tablica_daje_znaki_zero_jeden(klient):
    """Skrypt czyta wartości z pola ``znaki`` — muszą być ``1``/``0``, nie ``true``/``false``."""
    odpowiedz = klient.post(ADRES, json={"formula": FORMULA})

    assert odpowiedz.status_code == 200
    dane = odpowiedz.get_json()
    assert dane["ok"] is True
    assert dane["znaki"]
    for wiersz in dane["znaki"]:
        for nazwa in dane["tabela"]["variables"]:
            assert wiersz[nazwa] in (0, 1)
        assert all(wartosc in (0, 1) for wartosc in wiersz["values"])


def test_api_tablica_ma_cala_formule_w_ostatniej_kolumnie(klient):
    """Skrypt pokazuje wynik całej formuły jako ostatnią wartość wiersza."""
    dane = klient.post(ADRES, json={"formula": FORMULA}).get_json()

    assert dane["tabela"]["columns"][-1] == FORMULA
    assert len(dane["tabela"]["columns"]) == len(dane["znaki"][0]["values"])


def test_api_tablica_blednej_formuly_daje_blad_po_polsku(klient):
    """Ten błąd trafia do panelu obok tabeli — musi mieć komunikat, nie kod 500."""
    odpowiedz = klient.post(ADRES, json={"formula": "p ∧"})

    assert odpowiedz.status_code == 200
    dane = odpowiedz.get_json()
    assert dane["ok"] is False
    assert dane["blad"].strip()


# ---------------------------------------------------------------------------
# Partial
# ---------------------------------------------------------------------------


def test_partial_renderuje_montaz_z_formula(aplikacja):
    html = _renderuj(aplikacja, formula=FORMULA)

    assert 'class="truth-table-mount"' in html
    assert f'data-formula="{FORMULA}"' in html
    assert 'data-rola="tablica-prawdy"' in html


def test_partial_bierze_adres_api_ze_skryptu_strony(aplikacja):
    """Adres endpointu wyznacza ``url_for``, więc zmiana trasy nie psuje komponentu."""
    html = _renderuj(aplikacja, formula=FORMULA)

    assert f'data-adres="{ADRES}"' in html


def test_partial_dolacza_pliki_statyczne(aplikacja):
    html = _renderuj(aplikacja, formula=FORMULA)

    assert "/static/js/truth-table.js" in html
    assert "/static/css/truth-table.css" in html


def test_partial_dolacza_styl_paska_krokow(aplikacja):
    """Pasek kroków rysuje `stepper.js`, więc jego style muszą być na stronie."""
    html = _renderuj(aplikacja, formula=FORMULA)

    assert "/static/css/stepper.css" in html


def test_partial_nie_liczy_wartosci_w_jinja(aplikacja):
    """Partial nie ma liczyć logiki — żadnych pętli, warunków ani filtrów."""
    zrodlo = PARTIAL.read_text(encoding="utf-8")

    assert "{%" not in zrodlo
    assert "|" not in zrodlo


def test_partial_ma_noscript_z_formula(aplikacja):
    """Bez JavaScriptu użytkownik widzi wzór i wyjaśnienie, czego brakuje."""
    html = _renderuj(aplikacja, formula=FORMULA)

    assert "<noscript>" in html
    assert "JavaScript" in html
    assert FORMULA in html


def test_partial_bez_surowego_szablonu_w_wyniku(aplikacja):
    html = _renderuj(aplikacja, formula=FORMULA)

    assert "{{" not in html
    assert "{%" not in html


def test_widok_na_stronie_ma_tablice_z_adresem_api(klient):
    """Komponent jest już podłączony do prawdziwej strony (lekcja „Formuły”)."""
    html = klient.get("/formuly").get_data(as_text=True)

    assert 'class="truth-table-mount"' in html
    assert f'data-adres="{ADRES}"' in html
    assert "/static/js/truth-table.js" in html


def test_widok_na_stronie_dolacza_styl_paska_krokow(klient):
    """Pasek kroków pod tabelą potrzebuje `stepper.css` także na prawdziwej stronie."""
    html = klient.get("/formuly").get_data(as_text=True)

    assert "/static/css/stepper.css" in html


# ---------------------------------------------------------------------------
# Pliki statyczne
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sciezka", ["js/truth-table.js", "css/truth-table.css"])
def test_pliki_komponentu_istnieja_i_nie_sa_puste(sciezka):
    plik = KATALOG_STATYCZNY / sciezka

    assert plik.is_file()
    assert plik.stat().st_size > 0


@pytest.fixture(scope="module")
def skrypt():
    return (KATALOG_STATYCZNY / "js" / "truth-table.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def styl():
    return (KATALOG_STATYCZNY / "css" / "truth-table.css").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Skrypt
# ---------------------------------------------------------------------------


def test_skrypt_bierze_adres_z_atrybutu(skrypt):
    """Adres z atrybutu, nie wklejony na sztywno host — inaczej test idzie na produkcję."""
    assert "dataset.adres" in skrypt
    assert "http://" not in skrypt
    assert "https://" not in skrypt


def test_skrypt_wola_api_postem_z_jsonem(skrypt):
    assert "fetch(" in skrypt
    assert '"POST"' in skrypt
    assert "Content-Type" in skrypt
    assert "application/json" in skrypt
    assert ADRES in skrypt


def test_skrypt_czyta_wartosci_z_pola_znaki(skrypt):
    """Wartości bierzemy z API — skrypt nie liczy logiki sam."""
    assert "dane.znaki" in skrypt
    assert "dane.tabela.variables" in skrypt
    assert "dane.tabela.columns" in skrypt


def test_skrypt_pokazuje_slowa_obok_koloru(skrypt):
    """Słowa muszą być w kodzie, który je wypisuje — nie tylko w komentarzu."""
    assert 'const PRAWDA = "PRAWDA";' in skrypt
    assert 'const FAŁSZ = "FAŁSZ";' in skrypt
    assert "return znak === 1 ? PRAWDA : FAŁSZ;" in skrypt


def test_skrypt_pokazuje_wartosc_znakiem_i_slowem(skrypt):
    assert "tt-znak" in skrypt
    assert "tt-slownie" in skrypt


def test_skrypt_obsluguje_klawiature(skrypt):
    """Klikalny wiersz nie jest przyciskiem, więc sam obsługuje Enter i spację."""
    assert 'setAttribute("tabindex", "0")' in skrypt
    assert "keydown" in skrypt
    assert '"Enter"' in skrypt
    assert '" "' in skrypt


def test_skrypt_klikane_komorki_to_przyciski(skrypt):
    """Element ``button`` sam obsługuje Enter i spację — nie trzeba własnego ``keydown``."""
    assert 'element("button", "tt-komorka")' in skrypt
    assert 'przycisk.type = "button"' in skrypt


def test_skrypt_odbiera_klikniecie_komorki_od_wiersza(skrypt):
    """Bez tego kliknięcie zmiennej ustawiałoby cały wiersz zamiast jednej zmiennej."""
    assert "stopPropagation" in skrypt


def test_skrypt_klikniecie_wiersza_wybiera_cale_ustawienie(skrypt):
    """Kliknięcie wiersza myszą jest osobną ścieżką od klawiatury.

    Wiersz ``<tr>`` nie jest przyciskiem, więc sam musi mieć podsłuch ``click``.
    Bez tej linii wybór ustawienia działałby tylko z Entera i spacji, a kliknięcie
    myszą nie robiłoby nic — i żaden inny test by tego nie zauważył.
    """
    assert 'tr.addEventListener("click", wybierzWiersz)' in skrypt
    assert WZORZEC_WYBIERZ_WIERSZ.search(skrypt), (
        "obsługa wiersza ma brać wszystkie zmienne z tego wiersza i odświeżać widok"
    )


def test_skrypt_obsluguje_blad_api_i_siec(skrypt):
    assert "!dane.ok" in skrypt
    assert "dane.blad" in skrypt
    assert "Nie udało się połączyć z serwerem" in skrypt
    assert "Nie udało się wczytać tablicy prawdy" in skrypt


def test_skrypt_pokazuje_stan_wczytywania(skrypt):
    assert "Wczytuję tablicę prawdy" in skrypt


def test_skrypt_ma_panel_ustawienia(skrypt):
    assert "Twoje ustawienie" in skrypt
    assert "Wynik całej formuły" in skrypt
    assert "Wyczyść wybór" in skrypt


def test_skrypt_ustawia_arie_dla_filtrow_i_wyniku(skrypt):
    assert "aria-pressed" in skrypt
    assert "aria-live" in skrypt
    assert 'setAttribute("role", "status")' in skrypt


def test_skrypt_filtruje_i_podswietla_wiersze(skrypt):
    assert "tt-odfiltrowany" in skrypt
    assert "tt-wybrany" in skrypt
    assert "classList.toggle" in skrypt


def test_skrypt_nie_wstawia_tresci_przez_innerhtml(skrypt):
    # W komentarzu słowo może wystąpić, ale w kodzie nie ma prawa.
    assert ".innerHTML" not in skrypt
    assert "insertAdjacentHTML" not in skrypt
    assert "document.write" not in skrypt


def test_skrypt_ma_uwage_o_ostatniej_kolumnie(skrypt):
    """Bez podpowiedzi początkujący nie zgadnie, która kolumna to cała formuła."""
    assert "Ostatnia kolumna to cała formuła" in skrypt


# ---------------------------------------------------------------------------
# Prowadzenie krok po kroku (karta PRZ-073)
# ---------------------------------------------------------------------------


def test_skrypt_importuje_wspolny_stepper(skrypt):
    """Pasek kroków ma być wspólny (karta PRZ-072), a nie wklejony drugi raz."""
    assert 'from "/static/js/stepper.js"' in skrypt
    assert "import { createStepper }" in skrypt
    assert "createStepper({" in skrypt


def test_skrypt_oddaje_stepperowi_wlasny_kontener(skrypt):
    """Komponent pisze tylko do swojego kontenera — karta daje mu go w `mount`."""
    assert 'setAttribute("data-stepper", "")' in skrypt
    assert "mount: montazKrokow" in skrypt


def test_skrypt_buduje_kroki_z_odpowiedzi_api(skrypt):
    """Kroki powstają z danych API: kolumna wynikowa, wiersz po wierszu."""
    assert "function zbudujKroki" in skrypt
    assert "tytul: `Kolumna ${etykieta}`" in skrypt
    assert "TEKSTY.wiersz" in skrypt


def test_numer_kroku_jest_numerem_komorki(skrypt):
    """Bez tego „Dalej” odkrywałoby raz jedną, raz kilka komórek."""
    assert "numerKolumny.get(kolumna) * liczbaWierszy + wiersz" in skrypt
    assert "komorka.numer <= indeks" in skrypt
    assert "komorka.numer === indeks" in skrypt


def test_kroki_pomijaja_kolumny_zmiennych(skrypt):
    """Kolumny zmiennych są odkryte od początku, więc nie dostają własnych kroków."""
    assert "const kolumnyKrokow = kolumny" in skrypt
    assert "zmienne.includes(etykieta) ? null : indeks" in skrypt
    assert "komorka.numer === null || komorka.numer <= indeks" in skrypt
    assert "for (const [pozycja, kolumna] of kolumnyKrokow.entries())" in skrypt


def test_skrypt_ukrywa_nieodkryte_komorki_kropka(skrypt):
    """Student ma widzieć, jak tabela rośnie — przyszłe komórki pokazują kropkę."""
    assert 'ukryta: "·"' in skrypt
    assert 'element("span", "tt-ukryte", TEKSTY.ukryta)' in skrypt
    assert 'classList.toggle("tt-odkryta", odkryta)' in skrypt


def test_skrypt_oznacza_biezaca_komorke_arie_current(skrypt):
    """Bieżąca komórka musi być opisana, nie tylko obramowana kolorem."""
    assert 'setAttribute("aria-current", "true")' in skrypt
    assert 'removeAttribute("aria-current")' in skrypt
    assert "function opisKomorki" in skrypt
    assert "TEKSTY.nieodkryta" in skrypt


def test_skrypt_wyroznia_biezaca_kolumne_naglowkiem(skrypt):
    assert "tt-biezaca-kolumna" in skrypt
    assert 'classList.toggle("tt-biezaca", jestBiezaca)' in skrypt


def test_skrypt_ma_przycisk_pokaz_cala_tabele(skrypt):
    """Przycisk przydaje się przy sprawdzaniu: przeskakuje na ostatni krok."""
    assert 'pokazWszystko: "Pokaż całą tabelę"' in skrypt
    assert 'element("button", "btn btn-outline-primary btn-sm", TEKSTY.pokazWszystko)' in skrypt
    assert "stepper.go(stepper.length - 1)" in skrypt


def test_skrypt_konczy_podsumowaniem_z_klasyfikacja(skrypt):
    """Ostatni krok mówi, czym jest formuła, i ile wierszy ma jedynkę."""
    assert "TEKSTY.podsumowanie" in skrypt
    assert "Formuła jest ${NAZWY_KLASYFIKACJI[klasyfikacja] || klasyfikacja}." in skrypt
    assert 'ileJedynek: "Wierszy z jedynką"' in skrypt
    assert 'tautologia: "tautologią"' in skrypt


def test_kroki_maja_tytul_i_opis_dla_steppera(skrypt):
    """`createStepper` czyta pola `tytul` i `opis` — bez nich pasek byłby pusty."""
    assert "steps: kroki" in skrypt
    assert "onStep: (indeks) => pokazKrok(indeks)" in skrypt


def test_skrypt_zachowuje_filtrowanie_po_komorkach_zmiennych(skrypt):
    """Zachowanie z karty PRZ-011 zostaje: kliknięcie zmiennej filtruje wiersze."""
    assert 'przycisk.setAttribute("aria-pressed", "false")' in skrypt
    assert "ustawienie.set(nazwa, znak)" in skrypt
    assert "tt-odfiltrowany" in skrypt


def test_skrypt_nie_wstawia_danych_z_api_przez_innerhtml(skrypt):
    """Kroki i wartości pochodzą z API — nie mogą trafić do DOM jako kod."""
    assert ".innerHTML" not in skrypt
    assert "insertAdjacentHTML" not in skrypt
    assert "outerHTML" not in skrypt
    assert "document.write" not in skrypt


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------


def test_styl_rozroznia_stany_wiersza(styl):
    assert ".tt-wybrany" in styl
    assert ".tt-odfiltrowany" in styl
    assert '.tt-komorka[aria-pressed="true"]' in styl


def test_styl_zachowuje_widocznosc_fokusu(styl):
    """Element interaktywny bez widocznego fokusu nie działa z klawiatury."""
    assert ":focus-visible" in styl


def test_styl_ukrywa_nieodkryte_komorki(styl):
    """Kropka zamiast wartości: wartość pokazuje się dopiero z klasą `tt-odkryta`."""
    assert ".tt-komorka-wyniku .tt-ukryte" in styl
    assert ".tt-komorka-wyniku .tt-wartosc" in styl
    assert ".tt-komorka-wyniku.tt-odkryta .tt-wartosc" in styl


def test_styl_nie_zdradza_wyniku_tlem_przed_odkryciem(styl):
    """Tło w kolorze prawdy/fałszu pokazywałoby wynik przed krokiem."""
    assert ".tt-komorka-wyniku.tt-wynik-1," in styl
    assert "background-color: transparent;" in styl


def test_styl_wyroznia_biezaca_komorke_i_kolumne(styl):
    """Bieżący krok widać po obramowaniu i nagłówku, nie tylko po kolorze."""
    assert ".tt-komorka-wyniku.tt-biezaca" in styl
    assert ".tt-naglowek-podformuly.tt-biezaca-kolumna" in styl
    assert ".tt-kroki-pasek" in styl
