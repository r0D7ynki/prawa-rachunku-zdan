/* Interaktywna tablica prawdy (karta PRZ-011).
   Dla każdego elementu `.truth-table-mount` pobiera tablicę z endpointu podanego
   w atrybucie `data-adres` i dorysowuje tabelę, filtry oraz panel „Twoje ustawienie”.

   Skrypt nie liczy logiki: wartości bierze gotowe z pola `znaki` odpowiedzi API
   (`1` = PRAWDA, `0` = FAŁSZ). Całą treść wstawiamy przez `textContent`, nigdy przez
   `innerHTML` — dane z serwera nie trafiają do DOM jako kod.

   Nie ma tu podsłuchu na zdarzenia klawiatury dla przycisków: element `<button>`
   sam obsługuje Enter i spację (przeglądarka wysyła wtedy `click`). Własny `keydown`
   ma tylko klikalny wiersz tabeli, bo `<tr>` nie jest przyciskiem. */

const ADRES_ZAPASOWY = "/api/formula/table";

/* Słowa obok koloru — kolor nigdy nie jest jedynym nośnikiem informacji. */
const PRAWDA = "PRAWDA";
const FAŁSZ = "FAŁSZ";

const TEKSTY = {
  ladowanie: "Wczytuję tablicę prawdy…",
  siec: "Nie udało się połączyć z serwerem. Sprawdź połączenie i odśwież stronę.",
  brakTablicy: "Nie udało się wczytać tablicy prawdy.",
  podpowiedz: "Kliknij wartość zmiennej, żeby ją ustawić. Kliknij wiersz, żeby wybrać całe ustawienie.",
  legenda: "Jedynka znaczy PRAWDA, zero znaczy FAŁSZ. Ostatnia kolumna to cała formuła.",
  ustawienie: "Twoje ustawienie",
  nieustawiona: "?",
  wynik: "Wynik całej formuły",
  czekanie: "Ustaw wszystkie zmienne, żeby zobaczyć wynik całej formuły.",
  wyczysc: "Wyczyść wybór",
  wybierzWiersz: "Wybierz ustawienie z tego wiersza",
};

/* Nazwa klasyfikacji z API zamieniona na jedno zdanie po polsku. */
const KLASYFIKACJE = {
  tautologia: "Ta formuła jest tautologią — zawsze prawdziwa.",
  kontrtautologia: "Ta formuła jest kontrtautologią — zawsze fałszywa.",
  spełnialna: "Ta formuła jest spełnialna — bywa prawdziwa, bywa fałszywa.",
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

/** Rysuje gotową tablicę, panel „Twoje ustawienie” i sterowanie filtrami. */
function rysuj(montaz, formula, dane, status) {
  const zmienne = dane.tabela.variables || [];
  const kolumny = dane.tabela.columns || [];
  const wiersze = dane.znaki || [];

  /* Ustawienie użytkownika: nazwa zmiennej → `0` albo `1`. Zmienna nieobecna
     w mapie jest nieustawiona — pokazujemy wtedy znak zapytania. */
  const ustawienie = new Map();
  const przyciski = [];
  const wierszeDOM = [];

  const podpowiedz = element("p", "tt-podpowiedz text-muted small mb-1", TEKSTY.podpowiedz);
  const legenda = element("p", "tt-legenda text-muted small mb-2", TEKSTY.legenda);

  const tabela = element("table", "tt-tabela table table-sm table-bordered align-middle mb-2");
  const podpis = element("caption", "tt-podpis visually-hidden", `Tablica prawdy formuły ${formula}.`);
  const thead = element("thead", null);
  const tbody = element("tbody", null);
  thead.append(zbudujNaglowek(zmienne, kolumny));

  for (const [indeks, wiersz] of wiersze.entries()) {
    const tr = element("tr", "tt-wiersz");
    /* Wiersz jest klikalny, ale nie jest przyciskiem, więc musi być
       fokusowalny z klawiatury i mieć własną obsługę Enter oraz spacji. */
    tr.setAttribute("tabindex", "0");
    tr.setAttribute("aria-label", `${TEKSTY.wybierzWiersz}: ${indeks + 1}.`);

    const numer = element("th", "tt-numer", String(indeks + 1));
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

    for (const znak of wiersz[POLE_WARTOSCI] || []) {
      const komorka = element("td", `tt-komorka-wyniku tt-wynik-${znak}`);
      komorka.append(wartosc(znak));
      tr.append(komorka);
    }

    wierszeDOM.push(tr);
    tbody.append(tr);
  }

  tabela.append(podpis, thead, tbody);
  const przewijanie = element("div", "tt-przewijanie table-responsive mb-2");
  przewijanie.append(tabela);

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

  montaz.replaceChildren(podpowiedz, legenda, przewijanie, panel, status);
  odswiez();
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
