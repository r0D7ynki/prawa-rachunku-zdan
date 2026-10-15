/* Plac zabaw: formuła użytkownika i cztery widoki wyniku.
   Logika siedzi na serwerze — ten skrypt wysyła formułę i pokazuje odpowiedź.
   Każdy tekst z API wstawiamy przez `textContent`, nigdy przez `innerHTML`,
   dzięki temu żadna treść nie trafia do DOM jako kod. */

import { pobierzJson } from "/static/js/api.js";

const ADRESY = {
  parse: "/api/formula/parse",
  table: "/api/formula/table",
  simplify: "/api/formula/simplify",
  equivalence: "/api/equivalence",
};

const TEKSTY = {
  ladowanie: "Sprawdzam formułę…",
  siec: "Nie udało się połączyć z serwerem. Sprawdź połączenie i spróbuj ponownie.",
  bladOgolny: "Nie udało się przeliczyć tej formuły.",
  prawda: "PRAWDA",
  falsz: "FAŁSZ",
  rownowazne: "Formuły są równoważne — mają tę samą wartość w każdym wierszu tablicy.",
  nierownowazne: "Formuły nie są równoważne.",
  kontrprzyklad: "Kontrprzyklad (wartościowanie, przy którym wyniki się różnią):",
  brakKrokow: "Ta formuła nie wymaga przekształcenia — jest już w żądanej postaci.",
};

/** Opisy klasyfikacji zwracanej przez API, po polsku. */
const OPISY_KLASYFIKACJI = {
  tautologia: "Formuła prawdziwa przy każdym wartościowaniu zmiennych.",
  kontrtautologia: "Formuła fałszywa przy każdym wartościowaniu zmiennych.",
  spełnialna: "Formuła prawdziwa przy niektórych wartościowaniach, a fałszywa przy innych.",
};

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

/** Komórka z wartością 1/0; kolor to dodatek, nośnikiem informacji jest liczba. */
function komorkaWartosci(wartosc) {
  const prawda = wartosc === true || wartosc === 1;
  return element("td", prawda ? "prawda" : "falsz", prawda ? "1" : "0");
}

/** Wysyła JSON na endpoint wspólnym klientem (karta PRZ-174).

    Wynik ma pola `ok` oraz `dane` albo `blad` — obsługę błędów sprawdza wywołujący. */
function pobierz(adres, dane) {
  return pobierzJson(adres, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dane),
  });
}

/** Wstawia symbol w miejscu kursora i zostawia kursor zaraz za nim. */
function wstawSymbol(pole, symbol) {
  const start = pole.selectionStart ?? pole.value.length;
  const koniec = pole.selectionEnd ?? pole.value.length;
  pole.value = pole.value.slice(0, start) + symbol + pole.value.slice(koniec);
  const pozycja = start + symbol.length;
  pole.focus();
  pole.setSelectionRange(pozycja, pozycja);
}

/** Zapisuje formułę w adresie, żeby wynik dało się wysłać linkiem. */
function aktualizujAdres(formula) {
  const adres = new URL(window.location.href);
  adres.searchParams.set("formula", formula);
  window.history.replaceState({}, "", adres);
}

/** Zdanie z kontrprzykładu: „p = PRAWDA, q = FAŁSZ”. */
function opisKontrprzykladu(kontrprzyklad) {
  return Object.keys(kontrprzyklad)
    .sort()
    .map((nazwa) => `${nazwa} = ${kontrprzyklad[nazwa] ? TEKSTY.prawda : TEKSTY.falsz}`)
    .join(", ");
}

/**
 * Pole z wynikami kolumn w wierszu tablicy prawdy (kontrakt z docs/ARCHITEKTURA.md).
 * Wiersze tablicy z POST /api/formula/table zawierają wartościowania zmiennych
 * oraz listę booleanów pod kluczem POLE_WARTOSCI ("values").
 */
const POLE_WARTOSCI = "values";

/**
 * Struktura danych tabeli prawdy z POST /api/formula/table:
 * @typedef {Object} TabelaPrawdy
 * @property {string[]} variables - nazwy zmiennych (np. ["p", "q"])
 * @property {string[]} columns - etykiety kolumn (zmienne i podformuły)
 * @property {Array<Record<string, boolean> & { values: boolean[] }>} rows - wiersze wartościowań
 * @property {string} classification - "tautologia" | "kontrtautologia" | "spełnialna"
 */

/**
 * Rysuje tabelę prawdy: kolumny zmiennych, potem kolumny podformuł.
 * @param {HTMLElement} kontener - element docelowy tabeli
 * @param {TabelaPrawdy} tabela - dane tablicy z API
 * @param {string} formula - zapis formuły w nagłówku
 */
function rysujTablice(kontener, tabela, formula) {
  if (
    !tabela ||
    !Array.isArray(tabela.variables) ||
    !Array.isArray(tabela.columns) ||
    !Array.isArray(tabela.rows)
  ) {
    kontener.replaceChildren(
      element("p", "alert alert-warning mb-0", "Niepoprawna struktura tablicy prawdy z API."),
    );
    return;
  }
  const tabelaEl = element("table", "table table-sm table-bordered tablica-prawdy align-middle");
  tabelaEl.append(element("caption", "tablica-podpis", `Tablica prawdy dla formuły: ${formula}`));

  const naglowki = [...tabela.variables];
  const podformuly = tabela.columns
    .map((etykieta, indeks) => ({ etykieta, indeks }))
    .filter((kolumna) => !tabela.variables.includes(kolumna.etykieta));

  const wierszNaglowkow = element("tr");
  for (const naglowek of naglowki) {
    const komorka = element("th", undefined, naglowek);
    komorka.scope = "col";
    wierszNaglowkow.append(komorka);
  }
  for (const kolumna of podformuly) {
    const komorka = element("th", undefined, kolumna.etykieta);
    komorka.scope = "col";
    wierszNaglowkow.append(komorka);
  }

  const thead = element("thead");
  thead.append(wierszNaglowkow);

  const tbody = element("tbody");
  for (const wiersz of tabela.rows) {
    const tr = element("tr");
    for (const nazwa of tabela.variables) {
      tr.append(komorkaWartosci(wiersz[nazwa]));
    }
    const wartosci = wiersz[POLE_WARTOSCI] ?? wiersz.values ?? [];
    for (const kolumna of podformuly) {
      tr.append(komorkaWartosci(wartosci[kolumna.indeks]));
    }
    tbody.append(tr);
  }

  tabelaEl.append(thead, tbody);
  kontener.replaceChildren(element("h3", "h5 mt-4", "Tablica prawdy"), tabelaEl);
}

/** Rysuje klasyfikację formuły razem z jednozdaniowym wyjaśnieniem. */
function rysujKlasyfikacje(kontener, klasyfikacja) {
  const opis = OPISY_KLASYFIKACJI[klasyfikacja] || "";
  kontener.replaceChildren(
    element("p", "klasyfikacja-nazwa alert alert-info mb-1", `Formuła jest: ${klasyfikacja}.`),
    element("p", "klasyfikacja-opis text-muted small mb-0", opis),
  );
}

/** Rysuje formę wykładową formuły i listę jej zmiennych. */
function rysujFormule(kontener, wyklad, zmienne) {
  const lista = zmienne.length ? zmienne.join(", ") : "brak";
  kontener.replaceChildren(
    element("p", "formula-mount mb-1", `Zapis z wykładu: ${wyklad}`),
    element("p", "text-muted small mb-0", `Zmienne w formule: ${lista}`),
  );
}

/** Rysuje krokowe uproszczenie jako listę przejść. */
function rysujKroki(kontener, slad) {
  const naglowek = element("h3", "h5 mt-4", "Krokowe uproszczenie");
  const kroki = slad.kroki || [];
  const lista = element("ol", "lista-krokow list-group list-group-flush mb-2");

  for (const [indeks, krok] of kroki.entries()) {
    const pozycja = element("li", "krok list-group-item");
    pozycja.append(
      element("span", "krok-numer", `Krok ${indeks + 1}`),
      element("span", "krok-przejscie", `${krok.przed}  →  ${krok.po}`),
      element("p", "krok-prawo small text-muted mb-1", krok.nazwa),
      element("p", "krok-opis mb-0", krok.wyjaśnienie),
    );
    lista.append(pozycja);
  }

  const podsumowanie = element(
    "p",
    "slad-podsumowanie alert alert-success mb-0",
    kroki.length === 0
      ? `${TEKSTY.brakKrokow} Forma wynikowa: ${slad.forma}.`
      : `Forma wynikowa: ${slad.forma}. Liczba kroków: ${kroki.length}.`,
  );

  kontener.replaceChildren(naglowek, podsumowanie, lista);
}

/** Rysuje wynik porównania: równoważne albo kontrprzykład zdaniem. */
function rysujRownowaznosc(kontener, dane) {
  if (dane.rownowazne) {
    kontener.replaceChildren(element("p", "alert alert-success mb-0", TEKSTY.rownowazne));
    return;
  }

  const zdanie = opisKontrprzykladu(dane.kontrprzyklad || {});
  kontener.replaceChildren(
    element("p", "alert alert-warning mb-2", TEKSTY.nierownowazne),
    element("p", "text-muted small mb-1", TEKSTY.kontrprzyklad),
    element("p", "kontrprzyklad mb-0", zdanie),
  );
}

const formularz = document.getElementById("formularz-formuly");
const poleFormuly = document.getElementById("pole-formula");
const poleCel = document.getElementById("pole-cel");
const komunikatBledu = document.getElementById("komunikat-bledu");
const wynikKlasyfikacja = document.getElementById("wynik-klasyfikacja");
const wynikFormula = document.getElementById("wynik-formula");
const wynikTablica = document.getElementById("wynik-tablica");
const wynikKroki = document.getElementById("wynik-kroki");

if (formularz && poleFormuly) {
  formularz.addEventListener("submit", (zdarzenie) => {
    zdarzenie.preventDefault();
    sprawdz();
  });
}

/** Sprawdza formułę: pobiera zapis, tablicę prawdy i ślad uproszczenia. */
async function sprawdz() {
  const formula = poleFormuly.value;
  aktualizujAdres(formula);
  komunikatBledu.hidden = true;
  wynikKlasyfikacja.replaceChildren(
    element("p", "text-muted small mb-0", TEKSTY.ladowanie),
  );

  const wyniki = await Promise.all([
    pobierz(ADRESY.parse, { formula }),
    pobierz(ADRESY.table, { formula, podformuly: true }),
    pobierz(ADRESY.simplify, { formula, cel: poleCel ? poleCel.value : "auto" }),
  ]);
  const zlyWynik = wyniki.find((wynik) => !wynik.ok);
  if (zlyWynik) {
    pokazBlad(zlyWynik.blad || TEKSTY.siec);
    return;
  }
  const [zapis, tablica, slad] = wyniki.map((wynik) => wynik.dane);

  const zly = [zapis, tablica, slad].find((dane) => !dane.ok);
  if (zly) {
    pokazBlad(zly.blad || TEKSTY.bladOgolny);
    return;
  }

  rysujFormule(wynikFormula, zapis.wyklad, zapis.zmienne || []);
  rysujKlasyfikacje(wynikKlasyfikacja, tablica.klasyfikacja);
  rysujTablice(wynikTablica, tablica.tabela, zapis.wyklad);
  rysujKroki(wynikKroki, slad.slad);
}

/** Pokazuje komunikat błędu po polsku i czyści wyniki.
 *  `role="alert"` sprawia, że czytnik ekranu ogłasza komunikat od razu. */
function pokazBlad(tekst) {
  wynikKlasyfikacja.replaceChildren();
  wynikFormula.replaceChildren();
  wynikTablica.replaceChildren();
  wynikKroki.replaceChildren();
  komunikatBledu.className = "komunikat-bledu alert alert-warning mt-3 mb-0";
  komunikatBledu.setAttribute("role", "alert");
  komunikatBledu.textContent = tekst;
  komunikatBledu.hidden = false;
}

const formularzPorownania = document.getElementById("formularz-porownania");
const poleDruga = document.getElementById("pole-druga");
const wynikRownowaznosc = document.getElementById("wynik-rownowaznosc");

if (formularzPorownania && poleDruga) {
  formularzPorownania.addEventListener("submit", (zdarzenie) => {
    zdarzenie.preventDefault();
    porownaj();
  });
}

/** Porównuje dwie formuły i pokazuje wynik — bez przeładowania strony. */
async function porownaj() {
  const lewa = poleFormuly.value;
  const prawa = poleDruga.value;
  wynikRownowaznosc.replaceChildren(
    element("p", "text-muted small mb-0", TEKSTY.ladowanie),
  );

  const wynik = await pobierz(ADRESY.equivalence, { lewa, prawa });
  if (!wynik.ok) {
    pokazBladPorownania(wynik.blad || TEKSTY.siec);
    return;
  }
  const dane = wynik.dane;

  if (!dane.ok) {
    pokazBladPorownania(dane.blad || TEKSTY.bladOgolny);
    return;
  }

  rysujRownowaznosc(wynikRownowaznosc, dane);
}

/** Pokazuje komunikat błędu pod polem porównania — z `role="alert"`. */
function pokazBladPorownania(tekst) {
  const komunikat = element("p", "alert alert-warning mb-0", tekst);
  komunikat.setAttribute("role", "alert");
  wynikRownowaznosc.replaceChildren(komunikat);
}

/** Czyści pole i zostawia w nim kursor. */
function wyczyscPole(pole) {
  pole.value = "";
  pole.focus();
}

/** Podłącza jeden panel znaków do pola wskazanego w jego atrybucie `data-pole`. */
function podepnijKlawiature(panel) {
  const pole = document.getElementById(panel.dataset.pole);
  if (!pole) {
    return;
  }

  panel.querySelectorAll("[data-symbol]").forEach((przycisk) => {
    przycisk.addEventListener("click", () => wstawSymbol(pole, przycisk.dataset.symbol));
  });

  const przyciskCzysc = panel.querySelector("[data-czysc]");
  if (przyciskCzysc) {
    przyciskCzysc.addEventListener("click", () => wyczyscPole(pole));
  }
}

/* Każdy panel znaków mówi w `data-pole`, do którego pola wstawia znaki — dzięki temu
   ten sam kod obsługuje pole pierwszej i drugiej formuły. Przyciski to prawdziwe
   <button>, więc działają z klawiatury (Enter i spacja) bez dodatkowego kodu. */
document.querySelectorAll(".klawiatura-symboli[data-pole]").forEach(podepnijKlawiature);

/* Przykłady: kliknięcie wypełnia pole i od razu liczy wynik.
   Bez JavaScriptu ten sam odnośnik prowadzi do /plac-zabaw?formula=... . */
document.querySelectorAll("[data-przyklad]").forEach((odnosnik) => {
  odnosnik.addEventListener("click", (zdarzenie) => {
    zdarzenie.preventDefault();
    poleFormuly.value = odnosnik.dataset.przyklad;
    poleFormuly.focus();
    sprawdz();
  });
});
