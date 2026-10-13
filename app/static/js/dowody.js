/* Dowody założeniowe krok po kroku (karta PRZ-091). Strona `/dowody` ma sześć dowodów;
   każdy ujawnia się wiersz po wierszu. Kroki przychodzą gotowe z serwera — atrybut
   `data-kroki` na sekcji dowodu — a ten skrypt tylko pokazuje i wyróżnia:

     nr            — numer wiersza w tabeli (atrybut `data-nr` wiersza),
     z             — numery wierszy, z których powstał ten wiersz (puste przy założeniach),
     regula        — kod reguły, np. "RO" (pusty przy założeniach i sprzeczności),
     regula_nazwa  — pełna nazwa reguły, np. "Reguła odrywania",
     sprzecznosc   — czy wiersz zamyka dowód nie wprost.

   Nad tabelą stoi strzałka „wiersze 2 i 3 → wiersz 5 · RO”: mówi, z których wierszy
   powstał nowy wiersz i jaka reguła go wyprodukowała. Ostatni krok podświetla na
   czerwono oba wiersze sprzeczne i dokłada im podpis słowny, więc kolor nigdy nie jest
   jedynym nośnikiem informacji. Żadnej logiki dowodzenia tu nie ma — wiersze są
   policzone w Pythonie i widoczne w HTML także bez JavaScriptu.

   Cała treść trafia do DOM przez `textContent`, nigdy przez `innerHTML`. */

import { createStepper } from "/static/js/stepper.js";

/* Klasy wyróżnień — tak samo nazywa je `dowody.css`. */
const KLASA_BIEZACY = "wiersz-biezacy";
const KLASA_ZRODLO = "wiersz-zrodlo";
const KLASA_SPRZECZNY = "wiersz-sprzeczny";
const KLASA_ODZNAKA = "odznaka-sprzeczny";
const KLASA_STRZALKI = "strzalka-dowodu";

/* Napis dokładany wierszom sprzecznym: kolor ma swój odpowiednik słowny. */
const TEKST_SPRZECZNY = "sprzeczny";

/** Tworzy element z klasą i tekstem. */
function nowyElement(tag, klasa, tekst) {
  const element = document.createElement(tag);
  if (klasa) {
    element.className = klasa;
  }
  if (tekst !== undefined) {
    element.textContent = tekst;
  }
  return element;
}

/** Elementy pasujące do selektora jako zwykła lista — łatwiej o metody tablicowe. */
function lista(wezel, selektor) {
  return [...wezel.querySelectorAll(selektor)];
}

/** Kroki z atrybutu `data-kroki`. Błędny JSON to pusta lista — zostaje pełna tabela. */
function czytajKroki(sekcja) {
  try {
    const kroki = JSON.parse(sekcja.dataset.kroki ?? "[]");
    return Array.isArray(kroki) ? kroki.filter((krok) => krok !== null) : [];
  } catch {
    return [];
  }
}

/** Wiersz tabeli o podanym numerze albo `null`. Numery są napisami: „1”, „4.1”. */
function wierszPoNumerze(tabela, nr) {
  return lista(tabela, "tbody tr").find((wiersz) => wiersz.dataset.nr === String(nr)) ?? null;
}

/** Wypisuje numery po polsku: „3”, „2 i 3”, „1, 2 i 3”. */
function wymien(numery) {
  if (numery.length <= 1) {
    return String(numery[0] ?? "");
  }
  return `${numery.slice(0, -1).join(", ")} i ${numery[numery.length - 1]}`;
}

/** Źródła strzałki z odmianą: „wiersz 3” albo „wiersze 2 i 3”. */
function opisZrodel(numery) {
  return numery.length === 1 ? `wiersz ${numery[0]}` : `wiersze ${wymien(numery)}`;
}

/** Buduje strzałkę jednego kroku: od wierszy z listy `z` do nowego wiersza. */
function zbudujStrzalke(krok) {
  const od = opisZrodel(krok.z);
  const cel = krok.sprzecznosc ? "sprzeczność" : `wiersz ${krok.nr}`;
  // W zdaniu „do …” potrzebny jest dopełniacz: „do wiersza 9”, „do sprzeczności”.
  const celWZdaniu = krok.sprzecznosc ? "sprzeczności" : `wiersza ${krok.nr}`;

  const linia = nowyElement("span", "strzalka-linia", "→");
  linia.setAttribute("aria-hidden", "true");

  const strzalka = nowyElement("span", KLASA_STRZALKI);
  strzalka.append(
    nowyElement("span", "strzalka-zrodla", od),
    linia,
    nowyElement("span", "strzalka-cel", cel),
  );

  if (krok.regula) {
    strzalka.append(nowyElement("span", "strzalka-regula", krok.regula));
    if (krok.regula_nazwa) {
      strzalka.append(nowyElement("span", "strzalka-regula-nazwa", krok.regula_nazwa));
    }
  }

  const opisReguly = krok.regula
    ? `, reguła ${krok.regula}${krok.regula_nazwa ? ` (${krok.regula_nazwa})` : ""}`
    : "";
  strzalka.setAttribute("aria-label", `${od} do ${celWZdaniu}${opisReguly}`);
  return strzalka;
}

/** Rysuje strzałkę bieżącego kroku. Krok bez źródeł czyści kontener. */
function narysujStrzalki(kontener, krok) {
  if (!kontener) {
    return;
  }
  const zrodla = krok.z ?? [];
  kontener.replaceChildren(...(zrodla.length > 0 ? [zbudujStrzalke(krok)] : []));
}

/** Pokazuje wiersze do bieżącego kroku włącznie, resztę ukrywa atrybutem `hidden`. */
function ustawWiersze(tabela, kroki, indeks) {
  const widoczne = new Set(kroki.slice(0, indeks + 1).map((krok) => String(krok.nr)));

  for (const wiersz of lista(tabela, "tbody tr")) {
    wiersz.hidden = !widoczne.has(wiersz.dataset.nr);
  }
}

/** Wyróżnia bieżący wiersz i jego źródła; przy sprzeczności źródła świecą mocniej. */
function zaznaczWiersze(tabela, krok) {
  const sprzecznosc = krok.sprzecznosc === true;

  for (const odznaka of lista(tabela, `.${KLASA_ODZNAKA}`)) {
    odznaka.remove();
  }
  for (const wiersz of lista(tabela, "tbody tr")) {
    wiersz.classList.remove(KLASA_BIEZACY, KLASA_ZRODLO, KLASA_SPRZECZNY);
  }

  const biezacy = wierszPoNumerze(tabela, krok.nr);
  if (biezacy) {
    biezacy.classList.add(KLASA_BIEZACY);
  }

  for (const nr of krok.z ?? []) {
    const wiersz = wierszPoNumerze(tabela, nr);
    if (!wiersz) {
      continue;
    }
    wiersz.classList.add(sprzecznosc ? KLASA_SPRZECZNY : KLASA_ZRODLO);
    if (sprzecznosc) {
      // Podpis słowny przy wierszu: to samo, co mówi czerwone tło.
      wiersz.append(nowyElement("span", KLASA_ODZNAKA, TEKST_SPRZECZNY));
    }
  }
}

/** Włącza kroki w jednej sekcji dowodu. */
function uruchomDowod(sekcja) {
  const tabela = sekcja.querySelector("[data-tabela-dowodu]");
  const kroki = czytajKroki(sekcja);
  if (!tabela || kroki.length === 0) {
    return; // bez kroków zostaje pełna tabela z HTML-a
  }

  const strzalki = sekcja.querySelector("[data-strzalki]");
  createStepper({
    mount: sekcja.querySelector("[data-stepper]"),
    steps: kroki,
    onStep: (indeks, krok) => {
      ustawWiersze(tabela, kroki, indeks);
      zaznaczWiersze(tabela, krok);
      narysujStrzalki(strzalki, krok);
    },
  });
}

for (const sekcja of document.querySelectorAll("[data-dowod]")) {
  uruchomDowod(sekcja);
}
