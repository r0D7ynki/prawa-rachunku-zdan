/* Krokowe przekształcenia formuł. Karty PRZ-013, PRZ-077 i PRZ-143.
   Skrypt obsługuje dwa rodzaje kroków:

   1. Montaże `.steps-mount` (strony przekształcania) — pobiera ślad
      z `/api/formula/simplify` i rysuje kroki od zera.
   2. Sekcję `.kroki-prawa` na stronie prawa — tam kroki rysuje serwer, a skrypt
      dokłada tylko pasek strzałek i pokazuje jeden krok naraz. Bez JavaScriptu
      czytelnik widzi całą listę kroków, więc nic nie ginie.

   Każdy krok to jedna linia: plakietka z nazwą użytego prawa, formuła **przed**,
   strzałka i formuła **po**. Fragment, który krok zmienia, jest wyróżniony
   znacznikiem `<mark>` z `aria-label`; gdy fragmentu nie ma w formule, krok
   pokazuje się bez wyróżnienia i bez błędu.

   Kroki prowadzi wspólny komponent `createStepper` (PRZ-072): bieżący krok jest
   rozwinięty z opisem, poprzednie są zwinięte do jednej linii, a kolejne czekają
   na wejście. Wszystkie teksty z API wstawiamy przez `textContent`, nigdy przez
   `innerHTML` — dzięki temu żadna treść nie trafia do DOM jako kod. */

import { createStepper } from "/static/js/stepper.js";

const ADRES = "/api/formula/simplify";

/** Selektory sekcji kroków rysowanej po stronie serwera (strona prawa). */
const SEKCJA_PRAW = "[data-kroki-prawa]";

const TEKSTY = {
  ladowanie: "Wczytuję kroki przekształcenia…",
  siec: "Nie udało się połączyć z serwerem. Sprawdź połączenie i odśwież stronę.",
  brakKrokow: "Ta formuła nie wymaga przekształcenia — jest już w żądanej postaci.",
  blad: "Nie udało się przekształcić tej formuły.",
  fragment: "ten fragment zastępujemy",
  strzalka: "daje w wyniku",
  legenda: "Fragment, który zmienia ten krok, jest wyróżniony tłem i opisany słowami.",
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

/**
 * Zwraca formułę jako element, w którym każdy fragment zmieniany przez krok
 * jest opakowany w `<mark>` z opisem zmiany.
 *
 * Pusty `fragment` albo fragment, którego nie ma w formule, daje zwykły tekst —
 * bez wyróżnienia i bez błędu.
 */
function zPodswietleniem(formula, fragment) {
  const opakowanie = element("span", "krok-wzor formula");
  const szukany = typeof fragment === "string" ? fragment : "";

  if (!szukany || !formula.includes(szukany)) {
    opakowanie.textContent = formula;
    return opakowanie;
  }

  formula.split(szukany).forEach((czesc, indeks) => {
    if (indeks > 0) {
      const wyrozniony = element("mark", "krok-fragment", szukany);
      wyrozniony.setAttribute("aria-label", TEKSTY.fragment);
      opakowanie.append(wyrozniony);
    }
    if (czesc) {
      opakowanie.append(document.createTextNode(czesc));
    }
  });
  return opakowanie;
}

/**
 * Jeden krok listy: linia przejścia (przed ⇒ plakietka z nazwą prawa ⇒ po)
 * oraz opis, pokazywany tylko w bieżącym kroku.
 */
function zbudujKrok(numer, krok) {
  const pozycja = element("li", "krok");
  const linia = element("p", "krok-linia mb-1");

  const strzalka = element("span", "krok-strzalka", "⇒");
  strzalka.setAttribute("aria-hidden", "true");

  linia.append(
    element("span", "krok-numer", `Krok ${numer}`),
    zPodswietleniem(krok.przed, krok.fragment),
    element("span", "visually-hidden", TEKSTY.strzalka),
    strzalka,
    element("span", "krok-plakietka badge text-bg-secondary", krok.nazwa),
    zPodswietleniem(krok.po, krok.fragment),
  );

  const tresc = element("div", "krok-tresc");
  tresc.append(
    element("p", "krok-opis mb-1", krok.opis || ""),
    element("p", "krok-wyjasnienie mb-1", krok.wyjaśnienie || ""),
    element("p", "krok-pozycja small text-muted mb-0", `Miejsce w formule: ${krok.pozycja}`),
  );

  pozycja.append(linia, tresc);
  return { pozycja, tresc };
}

/** Wypełnia pojedynczy montaż: pobiera ślad i rysuje kroki, pasek i podsumowanie. */
async function wypelnij(montaz) {
  const formula = montaz.dataset.formula || "";
  const cel = montaz.dataset.cel || "auto";

  montaz.replaceChildren();
  const status = element("p", "steps-status visually-hidden");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  const komunikat = element("p", "steps-ladowanie text-muted small mb-1", TEKSTY.ladowanie);
  montaz.append(komunikat, status);

  let dane;
  try {
    const odpowiedz = await fetch(ADRES, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ formula, cel }),
    });
    dane = await odpowiedz.json();
  } catch (blad) {
    komunikat.className = "steps-blad alert alert-warning mb-0";
    komunikat.textContent = TEKSTY.siec;
    return;
  }

  if (!dane.ok) {
    komunikat.className = "steps-blad alert alert-warning mb-0";
    komunikat.textContent = dane.blad || TEKSTY.blad;
    return;
  }

  rysujSklad(montaz, dane.slad, status);
}

/** Rysuje gotowy ślad: pasek kroków, listę przejść i podsumowanie. */
function rysujSklad(montaz, slad, status) {
  const kroki = Array.isArray(slad.kroki) ? slad.kroki : [];

  // Kontener paska kroków. Pasek powstaje w `createStepper`; sami rysujemy listę
  // przejść i podsumowanie.
  const montazKrokow = element("div", "steps-prowadzenie");
  montazKrokow.setAttribute("data-stepper", "");
  const legenda = element("p", "steps-legenda text-muted small mb-2", TEKSTY.legenda);
  const lista = element("ol", "steps-lista list-unstyled mb-3");
  const podsumowanie = element("p", "steps-podsumowanie alert alert-success mb-0");

  // Bez kroków nie ma czego prowadzić — zostaje samo podsumowanie.
  if (kroki.length === 0) {
    podsumowanie.className = "steps-podsumowanie alert alert-info mb-0";
    podsumowanie.textContent =
      `${TEKSTY.brakKrokow} Forma wynikowa: ${slad.forma}. Liczba kroków: 0.`;
    status.textContent = podsumowanie.textContent;
    montaz.replaceChildren(podsumowanie, status);
    return;
  }

  const pozycje = kroki.map((krok, indeks) => zbudujKrok(indeks + 1, krok));
  for (const { pozycja } of pozycje) {
    lista.append(pozycja);
  }

  podsumowanie.textContent = `Forma wynikowa: ${slad.forma}. Liczba kroków: ${kroki.length}.`;

  /** Pokazuje krok o indeksie od zera: bieżący rozwinięty, poprzednie zwinięte. */
  function pokazKrok(indeks) {
    pozycje.forEach(({ pozycja, tresc }, numer) => {
      const biezacy = numer === indeks;
      tresc.hidden = !biezacy;
      pozycja.hidden = numer > indeks;
      pozycja.classList.toggle("krok-aktywny", biezacy);
      pozycja.classList.toggle("krok-zwiniety", numer < indeks);
      pozycja.classList.toggle("krok-ukryty", numer > indeks);
    });
    // Numer kroku zostaje wyłącznie dla czytnika ekranu (`visually-hidden`);
    // widok pokazuje same strzałki paska (karta PRZ-124).
    status.textContent = `Krok ${indeks + 1} z ${kroki.length}: ${kroki[indeks].nazwa}.`;
  }

  montaz.replaceChildren(montazKrokow, legenda, lista, podsumowanie, status);

  createStepper({
    mount: montazKrokow,
    steps: kroki.map((krok) => ({
      tytul: krok.nazwa,
      opis: krok.wyjaśnienie || krok.opis || "",
    })),
    onStep: (indeks) => pokazKrok(indeks),
  });
}

/**
 * Prowadzi krok po kroku sekcję narysowaną przez serwer (strona prawa).
 *
 * Kroki są już w HTML — ten kod tylko pokazuje jeden z nich naraz i stawia pasek
 * ze strzałkami. Bez JavaScriptu cała lista kroków zostaje widoczna, więc
 * czytelnik nie traci treści.
 */
function prowadzKrokiPrawa(sekcja) {
  const pasek = sekcja.querySelector("[data-stepper]");
  const pozycje = Array.from(sekcja.querySelectorAll("li.krok"));
  if (!pasek || pozycje.length === 0) {
    return;
  }

  /** Tekst elementu wewnątrz kroku; brak elementu to pusty napis. */
  function tekst(pozycja, selektor) {
    const wewnatrz = pozycja.querySelector(selektor);
    return wewnatrz ? wewnatrz.textContent.trim() : "";
  }

  /** Pokazuje wyłącznie krok o tym numerze (liczonym od zera). */
  function pokazKrok(numer) {
    pozycje.forEach((pozycja, indeks) => {
      pozycja.hidden = indeks !== numer;
    });
  }

  createStepper({
    mount: pasek,
    steps: pozycje.map((pozycja) => ({
      tytul: tekst(pozycja, ".krok-plakietka"),
      opis: tekst(pozycja, ".krok-opis"),
    })),
    onStep: pokazKrok,
  });
}

document.querySelectorAll(".steps-mount").forEach((montaz) => {
  wypelnij(montaz);
});

document.querySelectorAll(SEKCJA_PRAW).forEach((sekcja) => {
  prowadzKrokiPrawa(sekcja);
});
