/* Rezolucja krok po kroku (karta PRZ-092). Strona `/rezolucja` ma dwa dowody;
   każdy ujawnia się wiersz po wierszu. Kroki przychodzą gotowe z serwera — atrybut
   `data-kroki` na sekcji dowodu — a ten skrypt tylko pokazuje i wyróżnia:

     nr       — numer wiersza w tabeli (atrybut `data-nr` wiersza),
     rodzaj   — "zalozenie" | "negacja-tezy" | "rezolucja" | "sprzecznosc",
     rodzice  — numery wierszy, z których powstała klauzula,
     literal  — literał sklejenia (pusty dla założeń i sprzeczności).

   Nad tabelą stoi strzałka „wiersze 1 i 3 → wiersz 6 · na p”: mówi, skąd bierze się
   nowa klauzula i na czym ją sklejono. Ostatni krok podświetla dwa sprzeczne wiersze.
   Żadnej logiki rezolucyjnej tu nie ma — wiersze są policzone w Pythonie i widoczne
   w HTML także bez JavaScriptu.

   Cała treść trafia do DOM przez `textContent`, nigdy przez `innerHTML`. */

import { createStepper } from "/static/js/stepper.js";

/* Klasy wyróżnień — tak samo nazywa je `rezolucja.css`. */
const KLASA_BIEZACY = "wiersz-biezacy";
const KLASA_RODZIC = "wiersz-rodzic";
const KLASA_PODSWIETLONY = "wiersz-podswietlony";
const KLASA_STRZALKI = "strzalka-rezolucji";

const RODZAJ_REZOLUCJA = "rezolucja";
const RODZAJ_SPRZECZNOSC = "sprzecznosc";

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

/** Wiersz tabeli o podanym numerze albo `null`. */
function wierszPoNumerze(tabela, nr) {
  return lista(tabela, "tbody tr").find((wiersz) => Number(wiersz.dataset.nr) === nr) ?? null;
}

/** Wypisuje numery po polsku: „1”, „1 i 3”. */
function wymien(numery) {
  if (numery.length <= 1) {
    return String(numery[0] ?? "");
  }
  return `${numery.slice(0, -1).join(", ")} i ${numery[numery.length - 1]}`;
}

/** Buduje strzałkę jednego kroku: od wierszy rodziców do nowej klauzuli. */
function zbudujStrzalke(krok) {
  const od = `wiersze ${wymien(krok.rodzice)}`;
  const cel = krok.rodzaj === RODZAJ_SPRZECZNOSC ? "sprzeczność" : `wiersz ${krok.nr}`;
  const opis = krok.literal ? `na ${krok.literal}` : "";

  const linia = nowyElement("span", "strzalka-linia", "→");
  linia.setAttribute("aria-hidden", "true");

  const strzalka = nowyElement("span", KLASA_STRZALKI);
  strzalka.append(
    nowyElement("span", "strzalka-zrodla", od),
    linia,
    nowyElement("span", "strzalka-cel", cel),
  );
  if (opis) {
    strzalka.append(nowyElement("span", "strzalka-operacja", opis));
  }
  strzalka.setAttribute("aria-label", `${od} do ${cel}${opis ? `: ${opis}` : ""}`);
  return strzalka;
}

/** Rysuje strzałkę bieżącego kroku. Krok bez rodziców czyści kontener. */
function narysujStrzalki(kontener, krok) {
  if (!kontener) {
    return;
  }
  const rysujemy = krok.rodzaj === RODZAJ_REZOLUCJA || krok.rodzaj === RODZAJ_SPRZECZNOSC;
  kontener.replaceChildren(...(rysujemy ? [zbudujStrzalke(krok)] : []));
}

/** Pokazuje wiersze do bieżącego kroku włącznie, resztę ukrywa atrybutem `hidden`. */
function ustawWiersze(tabela, kroki, indeks) {
  const widoczne = new Set(kroki.slice(0, indeks + 1).map((krok) => krok.nr));

  for (const wiersz of lista(tabela, "tbody tr")) {
    wiersz.hidden = !widoczne.has(Number(wiersz.dataset.nr));
  }
}

/** Wyróżnia bieżący wiersz i jego rodziców; przy sprzeczności rodzice świecą mocniej. */
function zaznaczWiersze(tabela, krok) {
  const sprzecznosc = krok.rodzaj === RODZAJ_SPRZECZNOSC;

  for (const wiersz of lista(tabela, "tbody tr")) {
    wiersz.classList.remove(KLASA_BIEZACY, KLASA_RODZIC, KLASA_PODSWIETLONY);
  }

  const biezacy = wierszPoNumerze(tabela, krok.nr);
  if (biezacy) {
    biezacy.classList.add(KLASA_BIEZACY);
  }

  for (const nr of krok.rodzice ?? []) {
    const wiersz = wierszPoNumerze(tabela, nr);
    if (wiersz) {
      wiersz.classList.add(sprzecznosc ? KLASA_PODSWIETLONY : KLASA_RODZIC);
    }
  }
}

/** Włącza kroki w jednej sekcji dowodu. */
function uruchomDowod(sekcja) {
  const tabela = sekcja.querySelector("[data-tabela-rezolucji]");
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

for (const sekcja of document.querySelectorAll("[data-dowod-rezolucji]")) {
  uruchomDowod(sekcja);
}
