"""Testy komponentu interaktywnej tablicy prawdy (karty PRZ-011, PRZ-073, PRZ-121 i PRZ-142).

Tablica powstaje w przeglądarce z danych API, więc testy nie mogą jej narysować.
Sprawdzają to, co da się sprawdzić bez przeglądarki (patrz ``AGENTS.md``, zasada 6):

* co partial oddaje serwerowi (atrybuty kontenera, pliki statyczne, ``<noscript>``,
  brak liczenia wartości w Jinja),
* czy API zwraca dane w kształcie, na którym opiera się skrypt (pole ``znaki``),
* jak zbudowany jest skrypt — czy adres bierze z atrybutu, czy pokazuje słowa
  ``PRAWDA``/``FAŁSZ`` obok koloru, czy obsługuje klawiaturę i błędy po polsku,
* czy tablica rośnie krok po kroku: import wspólnego ``createStepper``,
  ``aria-current`` na bieżącej komórce i przycisk „Pokaż odpowiedź”,
* czy da się wpisywać wartości (karta PRZ-121): pole ``input`` w zakrytej komórce,
  klasy oceny ``komorka-dobrze`` i ``komorka-zle``, wynik „Sprawdź całą tabelę”
  słowami oraz klawisze ``Enter`` i ``Backspace`` w polu,
* czy strony praw i tautologii (karta PRZ-142) pokazują tablicę bez oceny:
  ``data-pokaz-oceny="false"``, brak przycisku „Sprawdź całą tabelę” i brak zdania
  o klasyfikacji formuły,
* czy z widoku zniknęły guziki kroków („Odtwórz”, „Pauza”, „Od nowa”) i kropki kroków.

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
#: Napisy, których w widoku tablicy być nie może (karta PRZ-121 usuwa guziki kroków).
NAPISY_GUZIKOW = ("Odtwórz", "Pauza", "Od nowa")
#: Licznik kroków w widoku: „krok 3 z 7”. Wolno go mieć tylko w tekście dla czytnika.
WZORZEC_LICZNIKA = re.compile(r"krok \d+ z")
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


def _blok(kod: str, poczatek: str) -> str:
    """Zwraca fragment kodu od napisu ``poczatek`` do zamykającego nawiasu klamrowego.

    Liczymy nawiasy, bo interesują nas całe ciała funkcji i obsługi zdarzeń —
    po samym wcięciu test pękałby przy każdej zmianie formatowania.
    """
    start = kod.index(poczatek)
    glebokosc = 0
    for pozycja, znak in enumerate(kod[start:], start=start):
        if znak == "{":
            glebokosc += 1
        elif znak == "}":
            glebokosc -= 1
            if glebokosc == 0:
                return kod[start : pozycja + 1]
    raise AssertionError(f"brak zamknięcia bloku: {poczatek}")


def _sekcja_tablicy_prawdy(html: str) -> str:
    """Fragment HTML sekcji „Tablica prawdy”: od jej nagłówka do końca sekcji.

    Cięcie po ``</section>`` wystarcza, bo sekcja tablicy nie zawiera sekcji
    zagnieżdżonej. Dzięki temu sprawdzamy samą tablicę, a nie menu, w którym
    słowo „tautologie” stoi w każdej nawigacji.
    """
    start = html.index('id="naglowek-tablica-prawdy"')
    return html[start : html.index("</section>", start)]


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


def test_partial_domyslnie_pokazuje_ocene(aplikacja):
    """Strona, która nie zna flagi (np. ``/formuly``), dostaje tablicę z oceną."""
    html = _renderuj(aplikacja, formula=FORMULA)

    assert 'data-pokaz-oceny="true"' in html


def test_partial_bez_oceny_ustawia_false(aplikacja):
    """``pokaz_ocene=false`` przechodzi do atrybutu, z którego czyta skrypt (PRZ-142)."""
    html = _renderuj(aplikacja, formula=FORMULA, pokaz_ocene=False)

    assert 'data-pokaz-oceny="false"' in html
    # Partial nie traci przez to niczego innego: tablica i tak powstaje w skrypcie.
    assert 'class="truth-table-mount"' in html
    assert "/static/js/truth-table.js" in html


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
    """Partial nie ma liczyć logiki — żadnych pętli, warunków ani filtrów.

    Jedyny dozwolony blok to domyślna wartość flagi oceny (karta PRZ-142): partial
    musi przyjąć ``pokaz_ocene``, a strona, która jej nie podaje (np. ``/formuly``),
    dostaje tablicę z oceną. Wszystko inne — pętle, warunki i filtry — nadal
    jest zabronione, bo tablicę liczy API, a nie szablon.
    """
    zrodlo = PARTIAL.read_text(encoding="utf-8")

    assert "{% for" not in zrodlo
    assert "{% if" not in zrodlo
    assert "|" not in zrodlo
    assert zrodlo.count("{%") == 1, "partial może mieć tylko domyślną flagę oceny"
    assert "{% set pokaz_oceny = pokaz_ocene if pokaz_ocene is defined else true %}" in zrodlo


def test_partial_ma_noscript_z_formula(aplikacja):
    """Bez JavaScriptu użytkownik widzi wzór i wyjaśnienie, czego brakuje."""
    html = _renderuj(aplikacja, formula=FORMULA)

    assert "<noscript>" in html
    assert "JavaScript" in html
    assert FORMULA in html


def test_partial_nie_ma_guzikow_ani_kropek_krokow(aplikacja):
    """Karta PRZ-121 usuwa z widoku odtwarzanie, reset, kropki kroków i licznik."""
    html = _renderuj(aplikacja, formula=FORMULA)
    zrodlo = PARTIAL.read_text(encoding="utf-8")

    for napis in NAPISY_GUZIKOW:
        assert napis not in html
        assert napis not in zrodlo
    assert "stepper-kropka" not in html
    assert not WZORZEC_LICZNIKA.search(html)


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
# Skrypt — dane, bezpieczeństwo i filtry (karta PRZ-011)
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
# Prowadzenie krok po kroku (karta PRZ-073, pasek uproszczony przez PRZ-124)
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


def test_skrypt_pasek_ma_tylko_dwie_strzalki(skrypt):
    """Pasek to wspólny komponent: dwie strzałki i opis, bez guzików kroków.

    Karta PRZ-121 nie dokłada własnego paska ani nie nadpisuje jego napisów —
    robi to komponent (karty PRZ-072 i PRZ-124), a karta przekazuje mu tylko kroki.
    """
    assert "labels:" not in skrypt
    assert "stepper-strzalka" not in skrypt
    for napis in NAPISY_GUZIKOW:
        assert napis not in skrypt
    assert "stepper-kropka" not in skrypt
    assert "stepper-wskaznik" not in skrypt
    assert not WZORZEC_LICZNIKA.search(skrypt)


def test_skrypt_buduje_kroki_z_odpowiedzi_api(skrypt):
    """Kroki powstają z danych API: kolumna wynikowa, wiersz po wierszu."""
    assert "function zbudujKroki" in skrypt
    assert "tytul: `Kolumna ${etykieta}`" in skrypt
    assert "TEKSTY.wiersz" in skrypt


def test_numer_kroku_jest_numerem_komorki(skrypt):
    """Bez tego „Dalej” odsłaniałoby raz jedną, raz kilka komórek."""
    assert "numerKolumny.get(kolumna) * liczbaWierszy + wiersz" in skrypt
    assert "komorka.numer <= indeks" in skrypt
    assert "komorka.numer === indeks" in skrypt


def test_kroki_pomijaja_kolumny_zmiennych(skrypt):
    """Kolumny zmiennych są odkryte od początku, więc nie dostają własnych kroków."""
    assert "const kolumnyKrokow = kolumny" in skrypt
    assert "zmienne.includes(etykieta) ? null : indeks" in skrypt
    assert "komorka.numer === null || komorka.numer <= indeks" in skrypt
    assert "for (const [pozycja, kolumna] of kolumnyKrokow.entries())" in skrypt


def test_skrypt_oznacza_biezaca_komorke_arie_current(skrypt):
    """Bieżąca komórka musi być opisana, nie tylko obramowana kolorem."""
    assert 'setAttribute("aria-current", "true")' in skrypt
    assert 'removeAttribute("aria-current")' in skrypt
    assert "function opisKomorki" in skrypt


def test_skrypt_wyroznia_biezaca_kolumne_naglowkiem(skrypt):
    assert "tt-biezaca-kolumna" in skrypt
    assert 'classList.toggle("tt-biezaca", jestBiezaca)' in skrypt


def test_skrypt_ma_przycisk_pokaz_odpowiedz(skrypt):
    """Przycisk odsłania całą tabelę — to ocena, nie krok."""
    assert 'pokazOdpowiedz: "Pokaż odpowiedź"' in skrypt
    assert 'element("button", "btn btn-outline-primary btn-sm", TEKSTY.pokazOdpowiedz)' in skrypt
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


def test_numer_kroku_zostaje_dla_czytnika_ekranu(skrypt):
    """Licznik kroków znika z widoku, ale czytnik ekranu ma go usłyszeć."""
    assert 'element("p", "tt-krok-opis visually-hidden")' in skrypt
    assert 'zdanieKroku.setAttribute("role", "status")' in skrypt
    assert 'zdanieKroku.setAttribute("aria-live", "polite")' in skrypt
    assert "${TEKSTY.krok} ${indeks + 1} z ${kroki.length}" in skrypt
    assert 'krok: "Krok"' in skrypt


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
# Wpisywanie wartości i ocena (karta PRZ-121)
# ---------------------------------------------------------------------------


def test_skrypt_tworzy_pole_wpisywania_w_komorce(skrypt):
    """Zakryta komórka wynikowa pokazuje pole na jedną cyfrę."""
    assert 'element("input", "tt-wejscie")' in skrypt
    assert 'wejscie.setAttribute("inputmode", "numeric")' in skrypt
    assert 'wejscie.setAttribute("maxlength", "1")' in skrypt
    assert 'const DOZWOLONE = ["0", "1"];' in skrypt


def test_skrypt_wstawia_pole_do_komorki_wyniku(skrypt):
    """Pole trafia do komórki wyniku razem ze znaczkiem oceny i wartością z tabeli."""
    assert 'element("span", "tt-ocena")' in skrypt
    assert "komorka.append(zbudujWejscie(pole), pole.znaczek, wartosc(znak));" in skrypt


def test_skrypt_ocenia_wpis_na_zero_albo_jeden(skrypt):
    """Ocenę liczymy z wartości z API — skrypt nie zgaduje wyniku sam."""
    assert "function ocena(komorka)" in skrypt
    assert "DOZWOLONE.includes(wpis)" in skrypt
    assert 'return wpis === String(oczekiwana(komorka)) ? "dobrze" : "zle";' in skrypt
    assert "function oczekiwana(komorka)" in skrypt
    assert "POLE_WARTOSCI" in _blok(skrypt, "function oczekiwana(")


def test_skrypt_nadaje_klasy_oceny(skrypt):
    """Zgodę z opisem karty: nazwy klas muszą być dokładnie takie jak w kryteriach."""
    assert 'const KLASA_DOBRZE = "komorka-dobrze";' in skrypt
    assert 'const KLASA_ZLE = "komorka-zle";' in skrypt
    assert 'classList.toggle(KLASA_DOBRZE, stan === "dobrze")' in skrypt
    assert 'classList.toggle(KLASA_ZLE, stan === "zle")' in skrypt


def test_skrypt_bez_oceny_dla_pustego_pola(skrypt):
    """Puste pole albo inny znak to brak oceny — żadnej klasy wtedy nie ma."""
    ocena = _blok(skrypt, "function ocena(")
    assert "return null;" in ocena
    pokaz = _blok(skrypt, "function pokazOcene(")
    assert "komorka.odkryta ? null : ocena(komorka)" in pokaz


def test_skrypt_mowi_slowami_co_ocenil(skrypt):
    """Kolor nie jest jedynym nośnikiem: tę samą ocenę niesie ``aria-label``."""
    assert 'ocenaDobrze: "dobrze"' in skrypt
    assert 'ocenaZle: "źle, poprawna wartość to"' in skrypt
    opis = _blok(skrypt, "function opisKomorki(")
    assert "${TEKSTY.ocenaDobrze}" in opis
    assert "${TEKSTY.ocenaZle} ${oczekiwana(komorka)}" in opis


def test_skrypt_etykietuje_kazda_komorke_kolumna_i_zmiennymi(skrypt):
    """Bez nazwy kolumny i ustawienia zmiennych tabela dla czytnika jest zagadką."""
    assert "function poczatekOpisu(komorka)" in skrypt
    assert "Kolumna ${kolumny[komorka.kolumna]}, wiersz ${komorka.wiersz + 1}" in skrypt
    assert "${nazwa} = ${wiersze[numerWiersza][nazwa]}" in skrypt
    pokaz = _blok(skrypt, "function pokazOcene(")
    assert 'komorka.element.setAttribute("aria-label", opis)' in pokaz
    assert 'komorka.wejscie.setAttribute("aria-label", opis)' in pokaz


def test_skrypt_ma_przycisk_sprawdz_cala_tabele(skrypt):
    """Przycisk ocenia wszystkie wpisy i podaje wynik słowami — to nie jest krok."""
    assert 'sprawdzTabele: "Sprawdź całą tabelę"' in skrypt
    assert 'addEventListener("click", sprawdzCalaTabele)' in skrypt
    assert "function sprawdzCalaTabele()" in skrypt


def test_skrypt_liczy_dobre_odpowiedzi_slowami(skrypt):
    """Wynik sprawdzenia to zdanie: „Dobrze: 7 z 8” albo „Wszystko dobrze!”."""
    assert 'wynikDobry: "Dobrze:"' in skrypt
    assert 'wszystkoDobrze: "Wszystko dobrze!"' in skrypt
    assert 'brakWpisow: "Wpisz 0 albo 1 w zakryte komórki, żeby sprawdzić tabelę."' in skrypt
    assert "${TEKSTY.wynikDobry} ${dobre} z ${wpisane}" in skrypt
    assert 'wynikSprawdzenia.setAttribute("aria-live", "polite")' in skrypt


def test_sprawdzenie_liczy_tylko_zakryte_komorki(skrypt):
    """Odkryta komórka pokazuje już wartość z tabeli, więc nie jest odpowiedzią studenta."""
    sprawdzenie = _blok(skrypt, "function sprawdzCalaTabele(")
    assert "komorka.odkryta ? null : ocena(komorka)" in sprawdzenie
    assert "wpisane" in sprawdzenie
    assert "dobre" in sprawdzenie


def test_skrypt_enter_przechodzi_do_nastepnej_komorki(skrypt):
    """Enter w polu ma prowadzić do następnej komórki, nie wybierać wiersza."""
    obsluga = _blok(skrypt, 'wejscie.addEventListener("keydown"')
    assert 'if (zdarzenie.key === "Enter")' in obsluga
    assert "przejdzDo(komorka, 1)" in obsluga
    przejscie = _blok(skrypt, "function przejdzDo(")
    assert ".focus()" in przejscie
    assert "if (!nastepna.odkryta)" in przejscie


def test_skrypt_backspace_czysci_komorke(skrypt):
    obsluga = _blok(skrypt, 'wejscie.addEventListener("keydown"')
    assert 'if (zdarzenie.key === "Backspace")' in obsluga
    assert "wyczysc(komorka)" in obsluga
    czyszczenie = _blok(skrypt, "function wyczysc(")
    assert 'komorka.wejscie.value = "";' in czyszczenie


def test_pole_nie_przechwytuje_strzalek(skrypt):
    """Strzałki w polu mają chodzić po znaku, a nie zmieniać kroku tabeli."""
    obsluga = _blok(skrypt, 'wejscie.addEventListener("keydown"')
    assert "stopPropagation" in obsluga
    assert '"Arrow' not in skrypt
    assert '"Home"' not in skrypt
    assert '"End"' not in skrypt


# ---------------------------------------------------------------------------
# Tryb czytania: strony praw i tautologii bez oceny tablicy (karta PRZ-142)
# ---------------------------------------------------------------------------


def test_strona_prawa_nie_ocenia_tablicy(klient):
    """Kryterium karty: w sekcji tablicy nie ma oceny formuły ani sprawdzacza."""
    html = klient.get("/prawa/de-morgan-1").get_data(as_text=True)
    sekcja = _sekcja_tablicy_prawdy(html)

    assert 'data-pokaz-oceny="false"' in sekcja, "tablica prawa nie wyłącza oceny"
    assert "Sprawdź całą tabelę" not in sekcja
    assert "tautolog" not in sekcja.lower()


def test_lekcja_tautologii_nie_ocenia_tablicy(klient):
    """Na lekcji tautologii tablica też służy czytaniu — jedno osadzenie partialu."""
    html = klient.get("/tautologie").get_data(as_text=True)

    assert html.count('data-pokaz-oceny="false"') == 1


def test_strony_z_liczeniem_zachowuja_ocene(klient):
    """Flaga jest wyjątkiem: lekcje „policz sam” dalej pokazują ocenę i sprawdzacz."""
    for adres in ("/formuly", "/przeksztalcanie", "/konsekwencja"):
        html = klient.get(adres).get_data(as_text=True)
        assert 'data-pokaz-oceny="true"' in html, adres


def test_plac_zabaw_zachowuje_sprawdzacz(klient):
    """Kryterium karty: plac zabaw zostaje bez zmian.

    Plac zabaw nie używa tego partialu — ma własny widok (`playground.js`) z polem
    formuły i przyciskiem „Sprawdź”, więc klasyfikacja i sprawdzanie zostają.
    """
    html = klient.get("/plac-zabaw").get_data(as_text=True)

    assert 'id="przycisk-sprawdz"' in html
    assert 'id="wynik-klasyfikacja"' in html
    assert "truth-table-mount" not in html, "plac zabaw nie używa partialu tablicy"


def test_skrypt_czyta_flage_oceny_z_atrybutu(skrypt):
    """Tryb czytania rozpoznajemy po atrybucie montażu, nie po adresie strony."""
    assert 'montaz.dataset.pokazOceny !== "false"' in skrypt


def test_skrypt_w_trybie_czytania_nie_ocenia_wpisow(skrypt):
    """Bez oceny nie ma czym malować klas ``komorka-dobrze`` ani ``komorka-zle``."""
    ocena = _blok(skrypt, "function ocena(")
    czesci = ocena.split("if (!ocenaWlaczona)")
    assert len(czesci) == 2, "`ocena()` nie zna trybu czytania"
    assert "return null;" in czesci[1]
    assert "ocena(komorka)" in _blok(skrypt, "function pokazOcene(")


def test_skrypt_w_trybie_czytania_nie_tworzy_przycisku_sprawdzania(skrypt):
    """Przycisk „Sprawdź całą tabelę” powstaje wyłącznie z włączoną oceną."""
    blok = _blok(skrypt, "if (ocenaWlaczona) {")
    assert "TEKSTY.sprawdzTabele" in blok
    assert 'addEventListener("click", sprawdzCalaTabele)' in blok
    assert "TEKSTY.sprawdzTabele" not in skrypt.replace(blok, "")


def test_skrypt_w_trybie_czytania_bez_oceny_formuly(skrypt):
    """„Ta formuła jest tautologią…” to ocena — w trybie czytania jej nie ma."""
    assert re.search(r"if \(ocenaWlaczona\) \{\s*const klasyfikacja =\s*KLASYFIKACJE\[", skrypt), (
        "zdanie o klasyfikacji musi powstać tylko przy włączonej ocenie"
    )
    assert skrypt.count("tt-klasyfikacja") == 1, "drugie miejsce z klasyfikacją byłoby bez osłony"
    assert re.search(r"const ocenaFormuly =\s*ocenaWlaczona \?", skrypt), (
        "podsumowanie kroków musi pomijać ocenę formuły w trybie czytania"
    )


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


def test_styl_pokazuje_pole_w_zakrytej_komorce(styl):
    """Pole wpisywania widać tylko przed odkryciem — potem pokazuje się wartość."""
    assert ".tt-komorka-wyniku .tt-wejscie" in styl
    assert ".tt-komorka-wyniku.tt-odkryta .tt-wejscie," in styl
    assert ".tt-komorka-wyniku .tt-wartosc" in styl
    assert ".tt-komorka-wyniku.tt-odkryta .tt-wartosc" in styl


def test_styl_ocenia_wpis_kolorem(styl):
    """Dobrze — zielone tło i ramka, źle — czerwone tło; oba z klasy karty."""
    assert ".tt-komorka-wyniku.komorka-dobrze {" in styl
    assert "background-color: var(--bs-success-bg-subtle, #d1e7dd);" in styl
    assert "box-shadow: inset 0 0 0 2px var(--bs-success, #198754);" in styl
    assert ".tt-komorka-wyniku.komorka-zle {" in styl
    assert "background-color: var(--bs-danger-bg-subtle, #f8d7da);" in styl


def test_styl_pokazuje_znaczek_oceny_obok_wpisu(styl):
    """Znaczek „✓”/„✕” odróżnia oceny także dla kogoś, kto nie rozróżnia barw."""
    assert ".tt-komorka-wyniku .tt-ocena {" in styl
    assert ".tt-komorka-wyniku.komorka-dobrze .tt-ocena," in styl
    assert ".tt-komorka-wyniku.tt-odkryta .tt-ocena {" in styl


def test_styl_nie_zdradza_wyniku_tlem_przed_odkryciem(styl):
    """Tło w kolorze prawdy/fałszu pokazywałoby wynik przed krokiem."""
    assert ".tt-komorka-wyniku.tt-wynik-1," in styl
    assert "background-color: transparent;" in styl


def test_styl_wyroznia_biezaca_komorke_i_kolumne(styl):
    """Bieżący krok widać po obramowaniu i nagłówku, nie tylko po kolorze."""
    assert ".tt-komorka-wyniku.tt-biezaca" in styl
    assert ".tt-naglowek-podformuly.tt-biezaca-kolumna" in styl
    assert ".tt-kroki-pasek" in styl
