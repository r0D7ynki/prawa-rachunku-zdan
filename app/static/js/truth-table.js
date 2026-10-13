/* Interaktywna tablica prawdy z wpisywaniem wartości (karty PRZ-011, PRZ-073, PRZ-121).
   Dla każdego elementu `.truth-table-mount` pobiera tablicę z endpointu podanego
   w atrybucie `data-adres` i dorysowuje tabelę, filtry, panel „Twoje ustawienie”
   oraz pasek kroków ze wspólnego komponentu `stepper.js` (karta PRZ-072).

   Skrypt nie liczy logiki: wartości bierze gotowe z pola `znaki` odpowiedzi API
   (`1` = PRAWDA, `0` = FAŁSZ). Całą treść wstawiamy przez `textContent`, nigdy przez
   `innerHTML` — dane z serwera nie trafiają do DOM jako kod.

   Prowadzenie krok po kroku (karta PRZ-073): kroki powstają z odpowiedzi API — jedna
   kolumna wynikowa to blok kroków, wiersz po wierszu, a na końcu idzie podsumowanie
   z klasyfikacją formuły. Numer kroku jest numerem komórki, dlatego strzałka „›”
   odsłania dokładnie jedną komórkę z gotową wartością, a „‹” cofa się o jedną.
   (Znaki przycisków ustala wspólny komponent — karta PRZ-124.)

   Wpisywanie wartości (karta PRZ-121): komórka jeszcze nieodkryta pokazuje pole na
   jeden znak. Student wpisuje `0` albo `1` i od razu widzi ocenę — zielone tło
   i obramowanie (`komorka-dobrze`) albo czerwone (`komorka-zle`), a tę samą ocenę
   niosą słowa w `aria-label`, bo kolor nie jest jedynym nośnikiem informacji.
   „Sprawdź całą tabelę” maluje wszystkie wpisy i podaje wynik słowami, a „Pokaż
   odpowiedź” odsłania całą tabelę.

   Numer kroku zostaje w tekście dla czytników ekranu pod tabelą (widok go nie pokazuje).

   Nie ma tu podsłuchu na zdarzenia klawiatury dla przycisków: element `<button>`
   sam obsługuje Enter i spację (przeglądarka wysyła wtedy `click`). Własny `keydown`
   ma tylko klikalny wiersz tabeli (`<tr>` nie jest przyciskiem) oraz pole wpisywania
   (Enter przechodzi do następnej komórki, Backspace czyści). */

import { createStepper } from "/static/js/stepper.js";

const ADRES_ZAPASOWY = "/api/formula/table";

/* Słowa obok koloru — kolor nigdy nie jest jedynym nośnikiem informacji. */
const PRAWDA = "PRAWDA";
const FAŁSZ = "FAŁSZ";

/* Znaki oceny wpisu. Oba są `aria-hidden`: ten sam wynik niosą słowa w etykiecie
   komórki („dobrze” albo „źle, poprawna wartość to 1”). */
const ZNAK_DOBRZE = "✓";
const ZNAK_ZLE = "✕";

/* Co przyjmuje pole wpisywania. Puste pole albo inny znak to brak oceny. */
const DOZWOLONE = ["0", "1"];

/* Klasy oceny komórki — umowa ze stylem `app/static/css/truth-table.css`. */
const KLASA_DOBRZE = "komorka-dobrze";
const KLASA_ZLE = "komorka-zle";

const TEKSTY = {
  ladowanie: "Wczytuję tablicę prawdy…",
  siec: "Nie udało się połączyć z serwerem. Sprawdź połączenie i odśwież stronę.",
  brakTablicy: "Nie udało się wczytać tablicy prawdy.",
  podpowiedz:
    "Kliknij wartość zmiennej, żeby ją ustawić. Kliknij wiersz, żeby wybrać całe ustawienie. " +
    "W zakrytą komórkę wpisz sam 0 albo 1 — od razu zobaczysz, czy dobrze.",
  legenda:
    "Jedynka znaczy PRAWDA, zero znaczy FAŁSZ. Ostatnia kolumna to cała formuła. " +
    "Strzałki pod tabelą odsłaniają kolejne komórki z gotowymi wartościami.",
  ustawienie: "Twoje ustawienie",
  nieustawiona: "?",
  wynik: "Wynik całej formuły",
  czekanie: "Ustaw wszystkie zmienne, żeby zobaczyć wynik całej formuły.",
  wyczysc: "Wyczyść wybór",
  wybierzWiersz: "Wybierz ustawienie z tego wiersza",
  wiersz: "Wiersz",
  podsumowanie: "Podsumowanie",
  pokazOdpowiedz: "Pokaż odpowiedź",
  sprawdzTabele: "Sprawdź całą tabelę",
  wpisz: "wpisz 0 albo 1",
  ocenaDobrze: "dobrze",
  ocenaZle: "źle, poprawna wartość to",
  wynikDobry: "Dobrze:",
  wszystkoDobrze: "Wszystko dobrze!",
  brakWpisow: "Wpisz 0 albo 1 w zakryte komórki, żeby sprawdzić tabelę.",
  krok: "Krok",
  ileJedynek: "Wierszy z jedynką",
};

/* Nazwa klasyfikacji z API zamieniona na jedno zdanie po polsku. */
const KLASYFIKACJE = {
  tautologia: "Ta formuła jest tautologią — zawsze prawdziwa.",
  kontrtautologia: "Ta formuła jest kontrtautologią — zawsze fałszywa.",
  spełnialna: "Ta formuła jest spełnialna — bywa prawdziwa, bywa fałszywa.",
};

/* Ten sam podział, ale w formie wchodzącej w zdanie kroku: „Formuła jest tautologią”. */
const NAZWY_KLASYFIKACJI = {
  tautologia: "tautologią",
  kontrtautologia: "kontrtautologią",
  spełnialna: "spełnialna",
};

/* Pole z wynikami kolumn w wierszu tablicy (umowa z `docs/ARCHITEKTURA.md`). */
const POLE_WARTOSCI = "values";

/** Tworzy element z klasą i tekstem (tekst zawsze bezpiecznie, przez `textContent`). */
function element(znacznik, klasa, tekst) {
  const nowy = document.createElement(znacznik);
  if (klasa) {
    nowy.className = klasa;
  }
  if (tekst !== undefined) {
    nowy.textContent = tekst;
  }
  return nowy;
}

/** Słowo dla wartości: `1` to PRAWDA, `0` to FAŁSZ. */
function slownie(znak) {
  return znak === 1 ? PRAWDA : FAŁSZ;
}

/** Wartość w komórce: znak `1`/`0` oraz słowo PRAWDA/FAŁSZ. */
function wartosc(znak) {
  const opakowanie = element("span", "tt-wartosc");
  opakowanie.append(
    element("span", "tt-znak", String(znak)),
    element("span", "tt-slownie", slownie(znak)),
  );
  return opakowanie;
}

/** Pokazuje komunikat błędu po polsku w miejscu tabeli. */
function pokazBlad(miejsce, tekst) {
  miejsce.className = "tt-blad alert alert-warning mb-0";
  miejsce.textContent = tekst;
}

/** Nagłówek kolumny z opisem dla czytnika ekranu (bez niego tabela jest zagadką). */
function naglowekKolumny(tekst, klasa) {
  const komorka = element("th", klasa, tekst);
  komorka.setAttribute("scope", "col");
  return komorka;
}

/** Buduje nagłówek tabeli: numer wiersza, zmienne, potem kolumny podformuł. */
function zbudujNaglowek(zmienne, kolumny) {
  const naglowek = element("tr");
  naglowek.append(naglowekKolumny("Wiersz", "tt-numer-kolumny"));
  for (const nazwa of zmienne) {
    naglowek.append(naglowekKolumny(nazwa, "tt-naglowek-zmiennej"));
  }
  for (const etykieta of kolumny) {
    naglowek.append(naglowekKolumny(etykieta, "tt-naglowek-podformuly"));
  }
  return naglowek;
}

/** Kroki prowadzenia: jedna kolumna wynikowa to blok kroków, na końcu podsumowanie.
 *
 *  Numer kroku (od zera) jest numerem komórki licząc kolumna po kolumnie, dlatego
 *  „Dalej” zawsze odsłania dokładnie jedną komórkę. Ostatni krok nie ma komórki:
 *  zbiera wynik całej formuły w jedno zdanie z klasyfikacją i liczbą jedynek. */
function zbudujKroki(zmienne, kolumny, kolumnyKrokow, wiersze, klasyfikacja) {
  const kroki = [];
  for (const [pozycja, kolumna] of kolumnyKrokow.entries()) {
    const etykieta = kolumny[kolumna];
    for (const [wiersz, dane] of wiersze.entries()) {
      const znak = (dane[POLE_WARTOSCI] || [])[kolumna];
      const ustawienie = zmienne.map((nazwa) => `${nazwa} = ${dane[nazwa]}`).join(", ");
      kroki.push({
        tytul: `Kolumna ${etykieta}`,
        opis:
          `${TEKSTY.wiersz} ${wiersz + 1} (${ustawienie}): ` +
          `${etykieta} = ${znak}, czyli ${slownie(znak)}.`,
        kolumna,
        wiersz,
        numer: pozycja * wiersze.length + wiersz,
      });
    }
  }

  /* Wiersze z jedynką liczymy w ostatniej kolumnie — to cała formuła. */
  const jedynki = wiersze.filter((dane) => {
    const wartosci = dane[POLE_WARTOSCI] || [];
    return wartosci[wartosci.length - 1] === 1;
  }).length;
  kroki.push({
    tytul: TEKSTY.podsumowanie,
    opis:
      `Formuła jest ${NAZWY_KLASYFIKACJI[klasyfikacja] || klasyfikacja}. ` +
      `${TEKSTY.ileJedynek}: ${jedynki} z ${wiersze.length}.`,
    kolumna: null,
    wiersz: null,
    numer: null,
  });
  return kroki;
}

/** Rysuje gotową tablicę, prowadzenie krok po kroku, wpisywanie i filtry. */
function rysuj(montaz, formula, dane, status) {
  const zmienne = dane.tabela.variables || [];
  const kolumny = dane.tabela.columns || [];
  const wiersze = dane.znaki || [];

  /* Odpowiedź musi mieć po jednej wartości na kolumnę w każdym wierszu. Gdyby serwer
     zmienił kształt danych, wolimy komunikat niż liczbę wziętą z cudzej kolumny. */
  const spojne = wiersze.every((wiersz) => (wiersz[POLE_WARTOSCI] || []).length === kolumny.length);
  if (zmienne.length === 0 || kolumny.length === 0 || wiersze.length === 0 || !spojne) {
    pokazBlad(montaz, TEKSTY.brakTablicy);
    return;
  }

  /* Ustawienie użytkownika: nazwa zmiennej → `0` albo `1`. Zmienna nieobecna
     w mapie jest nieustawiona — pokazujemy wtedy znak zapytania. */
  const ustawienie = new Map();
  const przyciski = [];
  const wierszeDOM = [];
  /* Komórki wynikowe w siatce [wiersz][kolumna] — potrzebne do odkrywania po kroku. */
  const komorkiWyniku = [];
  /* Te same komórki w kolejności dokumentu — po nich chodzą Enter i Backspace. */
  const polaWynikow = [];
  const naglowkiWynikow = [];

  const liczbaWierszy = wiersze.length;
  /* Kroki pomijają kolumny zmiennych (karta PRZ-073): te same wartości widać już
     w kolumnach zmiennych po lewej, a te są odkryte od początku. Serwer oddaje
     w `columns` także liście formuły, więc odsiewamy je po nazwie. */
  const kolumnyKrokow = kolumny
    .map((etykieta, indeks) => (zmienne.includes(etykieta) ? null : indeks))
    .filter((indeks) => indeks !== null);
  const numerKolumny = new Map(kolumnyKrokow.map((indeks, pozycja) => [indeks, pozycja]));
  /* Numer komórki licząc kolumna po kolumnie wynikowych: to samo co numer kroku.
     Komórka kolumny zmiennej nie ma numeru — jest odkryta od początku. */
  const numerKomorki = (kolumna, wiersz) =>
    numerKolumny.has(kolumna) ? numerKolumny.get(kolumna) * liczbaWierszy + wiersz : null;

  /** Ustawienie zmiennych w wierszu komórki, po polsku: „p = 0, q = 1”. */
  function ustawienieWiersza(numerWiersza) {
    return zmienne.map((nazwa) => `${nazwa} = ${wiersze[numerWiersza][nazwa]}`).join(", ");
  }

  /** Rozpoczyna opis komórki: nazwa kolumny, numer wiersza i wartości zmiennych. */
  function poczatekOpisu(komorka) {
    return (
      `Kolumna ${kolumny[komorka.kolumna]}, wiersz ${komorka.wiersz + 1}` +
      ` (${ustawienieWiersza(komorka.wiersz)})`
    );
  }

  /** Wartość, której oczekuje tabela w tej komórce. */
  function oczekiwana(komorka) {
    return (wiersze[komorka.wiersz][POLE_WARTOSCI] || [])[komorka.kolumna];
  }

  /** Ocena wpisu: „dobrze”, „zle” albo null, gdy pole jest puste albo ma inny znak. */
  function ocena(komorka) {
    const wpis = komorka.wejscie.value;
    if (!DOZWOLONE.includes(wpis)) {
      return null;
    }
    return wpis === String(oczekiwana(komorka)) ? "dobrze" : "zle";
  }

  /** Opis komórki dla czytnika ekranu — zawsze słowami, nigdy samym kolorem. */
  function opisKomorki(komorka) {
    const poczatek = poczatekOpisu(komorka);
    if (komorka.odkryta) {
      const znak = oczekiwana(komorka);
      return `${poczatek}: ${znak}, czyli ${slownie(znak)}.`;
    }
    const stan = ocena(komorka);
    if (stan === "dobrze") {
      return `${poczatek}: ${TEKSTY.ocenaDobrze}.`;
    }
    if (stan === "zle") {
      return `${poczatek}: ${TEKSTY.ocenaZle} ${oczekiwana(komorka)}.`;
    }
    return `${poczatek}: ${TEKSTY.wpisz}.`;
  }

  /** Maluje ocenę komórki: klasy, znaczek i etykiety.
   *
   *  Odkryta komórka pokazuje wartość z tabeli, więc ocena w niej traci sens — dlatego
   *  klasy oceny zakładamy tylko w komórkach jeszcze zakrytych. Wpis studenta zostaje
   *  w polu, więc cofnięcie kroku przywraca jego odpowiedź razem z oceną. */
  function pokazOcene(komorka) {
    const stan = komorka.odkryta ? null : ocena(komorka);
    komorka.element.classList.toggle(KLASA_DOBRZE, stan === "dobrze");
    komorka.element.classList.toggle(KLASA_ZLE, stan === "zle");
    if (stan === "dobrze") {
      komorka.znaczek.textContent = ZNAK_DOBRZE;
    } else if (stan === "zle") {
      komorka.znaczek.textContent = ZNAK_ZLE;
    } else {
      komorka.znaczek.textContent = "";
    }
    const opis = opisKomorki(komorka);
    komorka.element.setAttribute("aria-label", opis);
    komorka.wejscie.setAttribute("aria-label", opis);
  }

  /** Przechodzi do najbliższego pola w danym kierunku, które da się jeszcze wpisać. */
  function przejdzDo(komorka, kierunek) {
    const start = polaWynikow.indexOf(komorka);
    for (let pozycja = start + kierunek; polaWynikow[pozycja]; pozycja += kierunek) {
      const nastepna = polaWynikow[pozycja];
      if (!nastepna.odkryta) {
        nastepna.wejscie.focus();
        return;
      }
    }
  }

  /** Backspace: czyści wpis, a w pustym polu cofa do poprzedniej komórki. */
  function wyczysc(komorka) {
    if (komorka.wejscie.value === "") {
      przejdzDo(komorka, -1);
      return;
    }
    komorka.wejscie.value = "";
    pokazOcene(komorka);
  }

  /** Pole wpisywania w komórce wyniku: jeden znak, `0` albo `1`. */
  function zbudujWejscie(komorka) {
    const wejscie = element("input", "tt-wejscie");
    komorka.wejscie = wejscie; // ocena() czyta wartość tego pola
    /* Nie `type="number"`: przeglądarka dorzuca wtedy własne strzałki, a my chcemy
       zwykłe pole na jedną cyfrę (klawiaturę cyfrową daje `inputmode`). */
    wejscie.type = "text";
    wejscie.setAttribute("inputmode", "numeric");
    wejscie.setAttribute("maxlength", "1");
    wejscie.setAttribute("autocomplete", "off");
    wejscie.setAttribute("aria-label", opisKomorki(komorka));

    wejscie.addEventListener("input", () => pokazOcene(komorka));
    /* Kliknięcie w pole nie może wybierać całego wiersza ani go filtrować. */
    wejscie.addEventListener("click", (zdarzenie) => zdarzenie.stopPropagation());
    wejscie.addEventListener("keydown", (zdarzenie) => {
      /* Klawisze pola nie mogą dojść do wiersza: Enter wybiera tam całe ustawienie. */
      zdarzenie.stopPropagation();
      if (zdarzenie.key === "Enter") {
        zdarzenie.preventDefault();
        przejdzDo(komorka, 1);
        return;
      }
      if (zdarzenie.key === "Backspace") {
        zdarzenie.preventDefault();
        wyczysc(komorka);
      }
      /* Strzałki zostają polu: kursor chodzi po znaku, a krok się nie zmienia. */
    });
    return wejscie;
  }

  const podpowiedz = element("p", "tt-podpowiedz text-muted small mb-1", TEKSTY.podpowiedz);
  const legenda = element("p", "tt-legenda text-muted small mb-2", TEKSTY.legenda);

  const tabela = element("table", "tt-tabela table table-sm table-bordered align-middle mb-2");
  const podpis = element("caption", "tt-podpis visually-hidden", `Tablica prawdy formuły ${formula}.`);
  const thead = element("thead", null);
  const tbody = element("tbody", null);
  thead.append(zbudujNaglowek(zmienne, kolumny));
  for (const naglowek of thead.querySelectorAll(".tt-naglowek-podformuly")) {
    naglowkiWynikow.push(naglowek);
  }

  for (const [indeksWiersza, wiersz] of wiersze.entries()) {
    const tr = element("tr", "tt-wiersz");
    /* Wiersz jest klikalny, ale nie jest przyciskiem, więc musi być
       fokusowalny z klawiatury i mieć własną obsługę Enter oraz spacji. */
    tr.setAttribute("tabindex", "0");
    tr.setAttribute("aria-label", `${TEKSTY.wybierzWiersz}: ${indeksWiersza + 1}.`);

    const numer = element("th", "tt-numer", String(indeksWiersza + 1));
    numer.setAttribute("scope", "row");
    tr.append(numer);

    const wybierzWiersz = () => {
      for (const nazwa of zmienne) {
        ustawienie.set(nazwa, wiersz[nazwa]);
      }
      odswiez();
    };
    tr.addEventListener("click", wybierzWiersz);
    tr.addEventListener("keydown", (zdarzenie) => {
      if (zdarzenie.key === "Enter" || zdarzenie.key === " ") {
        zdarzenie.preventDefault();
        wybierzWiersz();
      }
    });

    for (const nazwa of zmienne) {
      const znak = wiersz[nazwa];
      const komorka = element("td", "tt-komorka-zmiennej");
      const przycisk = element("button", "tt-komorka");
      przycisk.type = "button";
      przycisk.setAttribute("aria-pressed", "false");
      przycisk.setAttribute("aria-label", `Ustaw ${nazwa} = ${znak}, czyli ${slownie(znak)}.`);
      przycisk.append(wartosc(znak));
      przycisk.addEventListener("click", (zdarzenie) => {
        zdarzenie.stopPropagation(); // ustawiamy jedną zmienną, nie cały wiersz
        ustawienie.set(nazwa, znak);
        odswiez();
      });
      przyciski.push({ przycisk, zmienna: nazwa, znak });
      komorka.append(przycisk);
      tr.append(komorka);
    }

    /* Kolumny zmiennych są odkryte od początku. Wyniki czekają na swoją kolej:
       zakryta komórka pokazuje pole, w które student sam wpisuje `0` albo `1`,
       a odkryta — gotową wartość z tabeli. Pole zostaje w komórce także po
       odkryciu (tyle że ukryte), żeby cofnięcie kroku nie gubiło odpowiedzi. */
    const rzad = [];
    for (const [kolumna, znak] of (wiersz[POLE_WARTOSCI] || []).entries()) {
      const komorka = element("td", `tt-komorka-wyniku tt-wynik-${znak}`);
      const pole = {
        element: komorka,
        kolumna,
        wiersz: indeksWiersza,
        numer: numerKomorki(kolumna, indeksWiersza),
        odkryta: false,
      };
      pole.znaczek = element("span", "tt-ocena");
      pole.znaczek.setAttribute("aria-hidden", "true");
      komorka.append(zbudujWejscie(pole), pole.znaczek, wartosc(znak));
      tr.append(komorka);
      rzad.push(pole);
      polaWynikow.push(pole);
      pokazOcene(pole);
    }
    komorkiWyniku.push(rzad);

    wierszeDOM.push(tr);
    tbody.append(tr);
  }

  tabela.append(podpis, thead, tbody);
  const przewijanie = element("div", "tt-przewijanie table-responsive mb-2");
  przewijanie.append(tabela);

  /* Pasek kroków (karta PRZ-072) stoi pod tabelą, a przyciski oceny — obok, ale poza
     kontenerem paska, bo `createStepper` podmienia zawartość swojego kontenera. */
  const pasek = element("div", "tt-kroki");
  const montazKrokow = element("div", "tt-kroki-pasek");
  montazKrokow.setAttribute("data-stepper", "");
  const przyciskiOceny = element("div", "tt-przyciski-oceny mb-2");

  const sprawdzTabele = element("button", "btn btn-primary btn-sm", TEKSTY.sprawdzTabele);
  sprawdzTabele.type = "button";
  const pokazOdpowiedz = element("button", "btn btn-outline-primary btn-sm", TEKSTY.pokazOdpowiedz);
  pokazOdpowiedz.type = "button";
  przyciskiOceny.append(sprawdzTabele, pokazOdpowiedz);

  /* Wynik sprawdzenia to zdanie po polsku — widoczne i ogłaszane przez `aria-live`. */
  const wynikSprawdzenia = element("p", "tt-wynik-sprawdzenia mb-0");
  wynikSprawdzenia.setAttribute("role", "status");
  wynikSprawdzenia.setAttribute("aria-live", "polite");

  /* Numer kroku chowamy przed wzrokiem, ale nie przed czytnikiem ekranu (karta PRZ-121). */
  const zdanieKroku = element("p", "tt-krok-opis visually-hidden");
  zdanieKroku.setAttribute("role", "status");
  zdanieKroku.setAttribute("aria-live", "polite");

  pasek.append(montazKrokow, przyciskiOceny, wynikSprawdzenia, zdanieKroku);

  const panel = element("div", "tt-panel alert alert-light border");
  const tytul = element("h3", "tt-tytul-ustawienia h6 mb-1", TEKSTY.ustawienie);
  const opisUstawienia = element("p", "tt-ustawienie mb-1");
  const opisWyniku = element("p", "tt-wynik-ustawienia small text-muted mb-1", TEKSTY.czekanie);
  const klasyfikacja =
    KLASYFIKACJE[dane.klasyfikacja] || `Odpowiedź serwera: ${dane.klasyfikacja}.`;
  const opisKlasyfikacji = element("p", "tt-klasyfikacja small mb-2", klasyfikacja);
  const czysc = element("button", "btn btn-outline-secondary btn-sm", TEKSTY.wyczysc);
  czysc.type = "button";
  czysc.addEventListener("click", () => {
    ustawienie.clear();
    odswiez();
  });
  panel.append(tytul, opisUstawienia, opisWyniku, opisKlasyfikacji, czysc);

  /** Przelicza widok po każdej zmianie ustawienia: filtry, podświetlenie i panel. */
  function odswiez() {
    const pelneUstawienie = zmienne.length > 0 && zmienne.length === ustawienie.size;
    let pasujace = 0;
    let wybrany = null;

    wierszeDOM.forEach((tr, indeks) => {
      const zgodny = zmienne.every(
        (nazwa) => !ustawienie.has(nazwa) || ustawienie.get(nazwa) === wiersze[indeks][nazwa],
      );
      const jestWybrany = pelneUstawienie && zgodny;
      /* Wiersze sprzeczne z ustawieniem wygaszamy, a nie ukrywamy: tabela zostaje
         kompletna dla czytnika ekranu, a użytkownik widzi, co odpadło. */
      tr.classList.toggle("tt-odfiltrowany", !zgodny);
      tr.classList.toggle("tt-wybrany", jestWybrany);
      if (zgodny) {
        pasujace += 1;
      }
      if (jestWybrany) {
        wybrany = indeks;
      }
    });

    for (const { przycisk, zmienna, znak } of przyciski) {
      const aktywny = ustawienie.get(zmienna) === znak;
      przycisk.setAttribute("aria-pressed", aktywny ? "true" : "false");
    }

    opisUstawienia.textContent = zmienne
      .map((nazwa) =>
        ustawienie.has(nazwa)
          ? `${nazwa} = ${ustawienie.get(nazwa)} (${slownie(ustawienie.get(nazwa))})`
          : `${nazwa} = ${TEKSTY.nieustawiona}`,
      )
      .join("   ·   ");

    const wartosci = wybrany === null ? [] : wiersze[wybrany][POLE_WARTOSCI] || [];
    /* Ostatnia kolumna to cała formuła — tak buduje tablicę `app/logic/truth.py`. */
    const wynik = wartosci.length > 0 ? wartosci[wartosci.length - 1] : null;

    if (wynik === 0 || wynik === 1) {
      opisWyniku.className = "tt-wynik-ustawienia alert alert-success py-1 px-2 mb-1";
      opisWyniku.textContent = `${TEKSTY.wynik}: ${wynik} (${slownie(wynik)}).`;
      status.textContent = `${TEKSTY.wynik}: ${slownie(wynik)}. Pasuje ${pasujace} z ${wiersze.length} wierszy.`;
    } else {
      opisWyniku.className = "tt-wynik-ustawienia small text-muted mb-1";
      opisWyniku.textContent = TEKSTY.czekanie;
      status.textContent = `Pasuje ${pasujace} z ${wiersze.length} wierszy.`;
    }

    czysc.disabled = ustawienie.size === 0;
  }

  /** „Sprawdź całą tabelę”: maluje wpisy i mówi słowami, ile z nich jest dobrych.
   *
   *  Liczą się komórki jeszcze zakryte, w które student wpisał `0` albo `1` — odkryte
   *  pokazują już wartość z tabeli, więc nie są jego odpowiedzią. */
  function sprawdzCalaTabele() {
    let dobre = 0;
    let wpisane = 0;
    for (const komorka of polaWynikow) {
      pokazOcene(komorka);
      const stan = komorka.odkryta ? null : ocena(komorka);
      if (stan === null) {
        continue;
      }
      wpisane += 1;
      if (stan === "dobrze") {
        dobre += 1;
      }
    }
    if (wpisane === 0) {
      wynikSprawdzenia.textContent = TEKSTY.brakWpisow;
    } else if (dobre === wpisane) {
      wynikSprawdzenia.textContent = TEKSTY.wszystkoDobrze;
    } else {
      wynikSprawdzenia.textContent = `${TEKSTY.wynikDobry} ${dobre} z ${wpisane}`;
    }
  }

  sprawdzTabele.addEventListener("click", sprawdzCalaTabele);

  const kroki = zbudujKroki(zmienne, kolumny, kolumnyKrokow, wiersze, dane.klasyfikacja);
  let stepper = null;

  /** Pokazuje stan po wejściu w krok o numerze `indeks` (liczonym od zera).
   *
   *  Numer kroku jest numerem komórki, więc komórka o numerze `n` jest odkryta, gdy
   *  `n <= indeks` — każde „›” odsłania dokładnie jedną. Komórki kolumn zmiennych
   *  nie mają numeru i są odkryte od początku. Krok podsumowania (numer równy liczbie
   *  komórek) pokazuje już całą tabelę i nie ma własnej kolumny. */
  function pokazKrok(indeks) {
    const krok = kroki[indeks] || {};
    const biezaca = krok.kolumna === null || krok.kolumna === undefined ? null : krok;

    for (const rzad of komorkiWyniku) {
      for (const komorka of rzad) {
        const odkryta = komorka.numer === null || komorka.numer <= indeks;
        const jestBiezaca = komorka.numer !== null && komorka.numer === indeks;
        komorka.odkryta = odkryta;
        komorka.element.classList.toggle("tt-odkryta", odkryta);
        komorka.element.classList.toggle("tt-biezaca", jestBiezaca);
        pokazOcene(komorka);
        if (jestBiezaca) {
          komorka.element.setAttribute("aria-current", "true");
        } else {
          komorka.element.removeAttribute("aria-current");
        }
      }
    }

    naglowkiWynikow.forEach((naglowek, kolumna) => {
      naglowek.classList.toggle("tt-biezaca-kolumna", biezaca !== null && kolumna === biezaca.kolumna);
    });

    /* Na ostatnim kroku nie ma czego odsłaniać — przycisk traci sens. */
    pokazOdpowiedz.disabled = indeks >= kroki.length - 1;

    zdanieKroku.textContent = `${TEKSTY.krok} ${indeks + 1} z ${kroki.length}. ${krok.opis || ""}`;
  }

  pokazOdpowiedz.addEventListener("click", () => {
    if (stepper) {
      stepper.go(stepper.length - 1);
    }
  });

  montaz.replaceChildren(podpowiedz, legenda, przewijanie, pasek, panel, status);
  odswiez();
  /* Pasek kroków to wspólny komponent (karty PRZ-072 i PRZ-124): dokładnie dwie
     strzałki „‹” i „›” i opis kroku między nimi, bez numerków i guzików. Karta nie
     nadpisuje napisów paska — numer kroku trafia tylko do czytnika ekranu
     (`zdanieKroku`). */
  stepper = createStepper({
    mount: montazKrokow,
    steps: kroki,
    onStep: (indeks) => pokazKrok(indeks),
  });
}

/** Wypełnia pojedynczy montaż: pobiera tablicę z API i rysuje widok. */
async function wypelnij(montaz) {
  const formula = montaz.dataset.formula || "";
  const adres = montaz.dataset.adres || ADRES_ZAPASOWY;

  montaz.replaceChildren();
  const status = element("p", "tt-status visually-hidden");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  const komunikat = element("p", "tt-ladowanie text-muted small mb-1", TEKSTY.ladowanie);
  montaz.append(komunikat, status);

  let dane;
  try {
    const odpowiedz = await fetch(adres, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ formula }),
    });
    dane = await odpowiedz.json();
  } catch (blad) {
    pokazBlad(komunikat, TEKSTY.siec);
    return;
  }

  if (!dane.ok) {
    pokazBlad(komunikat, dane.blad || TEKSTY.brakTablicy);
    return;
  }

  rysuj(montaz, formula, dane, status);
}

document.querySelectorAll(".truth-table-mount").forEach((montaz) => {
  wypelnij(montaz);
});
