/* Tablice dowodowe krok po kroku (karta PRZ-076).
   Strona `/tautologie` ma dwie tablice, które ujawniają się krok po kroku: dowód
   pełną tablicą i metodę skróconą. Kroki przychodzą gotowe z serwera — `data-kroki`
   na panelu `.tablica-krokowa` — a ten skrypt tylko pokazuje i ukrywa: kolumny,
   wiersze i strzałki. Żadnej logiki tu nie ma.

   Kształt kroku (to samo buduje `app/blueprints/tautologie.py`):
     tytul     — napis do paska kroków,
     opis      — zdanie po polsku pod tabelą,
     kolumny   — numery kolumn widocznych w tym kroku (liczone od zera),
     wiersze   — numery wierszy widocznych i czynnych; numer równy liczbie wierszy
                 ciała tabeli to wiersz wniosku ze stopki,
     odrzucone — numery wierszy odrzuconych: zostają widoczne, ale gasną,
     strzalki  — lista strzałek {"od": [...], "do": [...], "opis": ...,
                 "jednostka": "kolumna"|"wiersz"} rysowanych nad tabelą.

   Cała treść trafia do DOM przez `textContent`, nigdy przez `innerHTML` — ani dane
   z serwera, ani napisy z kroków nie stają się kodem. */

import { createStepper } from "/static/js/stepper.js";

/* Klasa zgaszonego wiersza — tak samo nazywa ją `tautologie.css`. */
const KLASA_ODRZUCONY = "wiersz-odrzucony";

const TEKSTY = {
  wiersz: "wiersz",
  wiersze: "wiersze",
};

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

/** Wypisuje elementy po polsku: „p”, „p i q”, „p, q i r”. */
function wymien(elementy) {
  if (elementy.length <= 1) {
    return elementy[0] ?? "";
  }
  return `${elementy.slice(0, -1).join(", ")} i ${elementy[elementy.length - 1]}`;
}

/** Kroki z atrybutu `data-kroki`. Błędny JSON to pusta lista — strona działa dalej. */
function czytajKroki(panel) {
  try {
    const kroki = JSON.parse(panel.dataset.kroki ?? "[]");
    return Array.isArray(kroki) ? kroki.filter((krok) => krok !== null) : [];
  } catch {
    return [];
  }
}

/** Etykiety kolumn z nagłówka tabeli; numer kolumny to pozycja na tej liście. */
function etykietyKolumn(tabela) {
  return lista(tabela, "thead th").map((komorka) => komorka.textContent.trim());
}

/** Odkrywa i ukrywa kolumny tabeli — po numerach kolumn z kroku. */
function ustawKolumny(tabela, kolumny) {
  const grupy = [
    lista(tabela, "thead th"),
    ...lista(tabela, "tbody tr").map((wiersz) => [...wiersz.children]),
  ];
  for (const grupa of grupy) {
    grupa.forEach((komorka, numer) => {
      komorka.hidden = !kolumny.includes(numer);
    });
  }
}

/** Gaszone i ukrywane wiersze. Odrzucone zostają na stronie, ale bez treści dla czytnika. */
function ustawWiersze(tabela, krok) {
  const wiersze = lista(tabela, "tbody tr");
  const widoczne = krok.wiersze ?? [];
  const odrzucone = krok.odrzucone ?? [];

  wiersze.forEach((wiersz, numer) => {
    const odrzucony = odrzucone.includes(numer);
    wiersz.hidden = !(widoczne.includes(numer) || odrzucony);
    wiersz.classList.toggle(KLASA_ODRZUCONY, odrzucony);
    if (odrzucony) {
      wiersz.setAttribute("aria-hidden", "true");
    } else {
      wiersz.removeAttribute("aria-hidden");
    }
  });

  //: Stopka to wiersz wniosku — pokazuje go krok, który ma jej numer na liście wierszy.
  const wniosek = tabela.querySelector("tfoot tr");
  if (wniosek) {
    wniosek.hidden = !widoczne.includes(wiersze.length);
  }
}

/** Nazwy jednej strony strzałki: etykiety kolumn albo numery wierszy liczone od 1. */
function nazwyStrony(numery, tabela, jednostka) {
  if (jednostka === "wiersz") {
    const slowo = numery.length === 1 ? TEKSTY.wiersz : TEKSTY.wiersze;
    return `${slowo} ${wymien(numery.map((numer) => String(numer + 1)))}`;
  }
  const etykiety = etykietyKolumn(tabela);
  return wymien(numery.map((numer) => etykiety[numer] ?? ""));
}

/** Buduje jedną strzałkę: skąd, dokąd i jaka operacja. */
function zbudujStrzalke(dane, tabela) {
  const jednostka = dane.jednostka === "wiersz" ? "wiersz" : "kolumna";
  const od = nazwyStrony(dane.od ?? [], tabela, jednostka);
  const cel = nazwyStrony(dane.do ?? [], tabela, jednostka);
  const opis = dane.opis ?? "";

  const linia = nowyElement("span", "strzalka-linia", "→");
  linia.setAttribute("aria-hidden", "true");

  const strzalka = nowyElement("span", "strzalka-tabeli");
  strzalka.append(
    nowyElement("span", "strzalka-zrodla", od),
    linia,
    nowyElement("span", "strzalka-cel", cel),
    nowyElement("span", "strzalka-operacja", opis),
  );
  strzalka.setAttribute("aria-label", `${od} → ${cel}: ${opis}`);
  return strzalka;
}

/** Rysuje nad tabelą strzałki bieżącego kroku. Brak strzałek czyści kontener. */
function narysujStrzalki(kontener, krok, tabela) {
  if (!kontener) {
    return;
  }
  kontener.replaceChildren(...(krok.strzalki ?? []).map((dane) => zbudujStrzalke(dane, tabela)));
}

/** Włącza kroki w jednym panelu `[data-krokowa]`. */
function uruchomPanel(panel) {
  const tabela = panel.querySelector("table");
  const kroki = czytajKroki(panel);
  if (!tabela || kroki.length === 0) {
    return; // bez kroków zostaje pełna tabela z HTML-a
  }
  const strzalki = panel.querySelector("[data-strzalki]");
  createStepper({
    mount: panel.querySelector("[data-stepper]"),
    steps: kroki,
    onStep: (_index, krok) => {
      ustawKolumny(tabela, krok.kolumny ?? []);
      ustawWiersze(tabela, krok);
      narysujStrzalki(strzalki, krok, tabela);
    },
  });
}

for (const panel of document.querySelectorAll("[data-krokowa]")) {
  uruchomPanel(panel);
}
