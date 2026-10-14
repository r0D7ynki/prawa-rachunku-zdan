/* Diagramy zbiorów prowadzone krok po kroku (karty PRZ-012 i PRZ-075).

   Dla każdej strony prawa pobieramy drzewo `ast` z `POST /api/formula/parse` i liczymy je
   **na obszarach**: prostokąt to cała przestrzeń, koła to zbiory zmiennych, a punkt należy
   do zbioru wtedy, gdy leży w jego kole.

   Obszary liczymy **na siatce próbek** (`KOLUMNY_SIATKI` × `WIERSZE_SIATKI`): dla środka
   każdej próbki sprawdzamy, w których kołach leży, i pytamy `ocena`, czy formuła jest tam
   prawdziwa. Przebiegi prawdziwych próbek składamy w jedną ścieżkę SVG (`<path>`). Dlatego
   rysunek jest poprawny także dla trzech zbiorów i nie potrzebuje analitycznej geometrii.

   Kroki bierzemy z pola `kroki` prawa — partial wpisuje je w liście `[data-kroki]`.
   Na kroku `i` zamalowany jest obszar formuły z tego kroku, a obszary kroków wcześniejszych
   zostają widoczne jako obrys: student widzi, że przekształcenie nie zmieniło obszaru.
   Gdy partial nie poda kroków (na przykład poza stroną prawa), kroki powstają z podformuł
   obu stron — od operacji najbardziej wewnętrznej do zewnętrznej.

   Każdy element SVG tworzymy przez `document.createElementNS`, a treść wstawiamy tylko
   przez `textContent` — napisy z API nie trafiają do DOM jako kod. */

import { pobierzJson } from "/static/js/api.js";
import { createStepper } from "/static/js/stepper.js";

const ADRES = "/api/formula/parse";
const NS_SVG = "http://www.w3.org/2000/svg";

/** Najwięcej kół, ile zmieści się na czytelnym diagramie. */
const MAKS_ZBIOROW = 3;

const SZEROKOSC = 220;
const WYSOKOSC = 180;
const PROMIEN = 46;

/** Gęstość siatki próbek: tyle punktów w poziomie i w pionie liczy jeden obszar.
 *  Siatka 440 × 360 daje schodek wielkości pół punktu, czyli około piksela na ekranie —
 *  dzięki temu skosy obszaru wyglądają gładko. Jeden obszar liczy się kilka milisekund. */
const KOLUMNY_SIATKI = 440;
const WIERSZE_SIATKI = 360;

/** Zakładka próbek: sąsiednie prostokąty zachodzą na siebie, żeby nie prześwitywało tło. */
const ZAKLADKA = 0.5;

const TEKSTY = {
  ladowanie: "Wczytuję diagramy zbiorów…",
  siec: "Nie udało się połączyć z serwerem. Sprawdź połączenie i odśwież stronę.",
  blad: "Nie udało się narysować diagramu dla tej formuły.",
  brakAst: "Serwer nie przysłał drzewa formuły, więc nie ma czego rysować.",
  przestrzen: "Cała przestrzeń — prostokąt obejmuje wszystkie możliwe przypadki.",
  takiSam:
    "Zamalowany obszar jest taki sam po obu stronach — dlatego wzory są równoważne.",
  rozny: "Zamalowane obszary różnią się, więc te wzory nie są równoważne.",
  bezSensu:
    "Tej formuły nie da się pokazać jako obszaru. Diagram zbiorów rysuje tylko negację (∼), " +
    "koniunkcję (∧) i alternatywę (∨).",
  legenda: "Legenda: cały prostokąt to przestrzeń, koła to zbiory zmiennych.",
  obszarPusty: "Formuła jest fałszywa przy każdym wartościowaniu, więc nic nie zamalowano.",
  obszarPelny: "Formuła jest prawdziwa przy każdym wartościowaniu, więc zamalowano całość.",
  obszarKroku: "Zamalowany obszar formuły z tego kroku.",
  obrysKroku: "Obrys obszaru z wcześniejszego kroku — przekształcenie go nie zmieniło.",
  pokazOba: "Pokaż oba naraz",
  pokazKrokami: "Pokaż krokami",
  oba: "Pokazuję oba docelowe obszary naraz: lewą i prawą stronę prawa.",
  strzalka:
    "Lewa strona jest równoważna prawej — po obu stronach zamalowany jest ten sam obszar.",
  krok: "Krok",
  tenSam: "Obszar jest taki sam jak w poprzednim kroku.",
};

/** Ustalone położenie kół dla jednej, dwóch i trzech zmiennych. */
const UKLADY = {
  1: [[110, 90]],
  2: [
    [86, 90],
    [134, 90],
  ],
  3: [
    [110, 62],
    [82, 108],
    [138, 108],
  ],
};

/** Zdejmuje z formuły pary przeczeń: `∼∼X` zamalowuje ten sam obszar co `X`.
 *
 *  Kroki przekształcenia dopisują i zdejmują przeczenia, więc bez tego kroku
 *  `∼∼(∼p ∧ ∼q)` nazywałby się „dopełnienie”, choć zamalowuje część wspólną. */
function bezParPrzeczen(node) {
  let biezacy = node;
  while (biezacy.typ === "Not" && biezacy.dziecko.typ === "Not") {
    biezacy = biezacy.dziecko.dziecko;
  }
  return biezacy;
}

/** Nazwa i wyjaśnienie operacji, którą wykonuje formuła danego kroku.
 *
 *  Dzięki temu nad diagramem stoi wprost napisane, co robimy: „suma”, „część wspólna”
 *  albo „dopełnienie sumy”. Nazwa zbioru pochodzi z API — trafia do DOM przez `textContent`.
 */
function operacja(formula) {
  const node = bezParPrzeczen(formula);
  if (node.typ === "Not") {
    if (node.dziecko.typ === "Or") {
      return { nazwa: "dopełnienie sumy", opis: "obszar poza sumą zbiorów" };
    }
    if (node.dziecko.typ === "And") {
      return { nazwa: "dopełnienie części wspólnej", opis: "obszar poza częścią wspólną" };
    }
    if (node.dziecko.typ === "Var") {
      return { nazwa: `dopełnienie zbioru ${node.dziecko.nazwa}`, opis: "obszar poza zbiorem" };
    }
    return { nazwa: "dopełnienie", opis: "obszar poza zaznaczonym obszarem" };
  }
  if (node.typ === "And") {
    return { nazwa: "część wspólna", opis: "obszar wspólny obu stron" };
  }
  if (node.typ === "Or") {
    return { nazwa: "suma", opis: "wszystko, co leży w którymkolwiek ze zbiorów" };
  }
  return { nazwa: "zbiór", opis: "obszar jednego zbioru" };
}

/** Tworzy element SVG i dokłada mu opis po polsku jako pierwsze dziecko. */
function nowyElement(znacznik, opis) {
  const element = document.createElementNS(NS_SVG, znacznik);
  if (opis !== undefined) {
    const tytul = document.createElementNS(NS_SVG, "title");
    tytul.textContent = opis;
    element.append(tytul);
  }
  return element;
}

/** Tworzy element HTML z klasą i tekstem (tekst zawsze przez `textContent`). */
function elementHtml(znacznik, klasa, tekst) {
  const element = document.createElement(znacznik);
  if (klasa) {
    element.className = klasa;
  }
  if (tekst !== undefined) {
    element.textContent = tekst;
  }
  return element;
}

/** Czy drzewo z API ma kształt, który umiemy policzyć. */
function maPoprawneDrzewo(node) {
  if (!node || typeof node !== "object") {
    return false;
  }
  if (node.typ === "Var") {
    return typeof node.nazwa === "string";
  }
  if (node.typ === "Not") {
    return maPoprawneDrzewo(node.dziecko);
  }
  if (["And", "Or", "Imp", "Iff"].includes(node.typ)) {
    return maPoprawneDrzewo(node.lewy) && maPoprawneDrzewo(node.prawy);
  }
  return false;
}

/** Czy formuła mówi tylko o zbiorach: negacja, koniunkcja i alternatywa.
 *
 *  Implikacja i równoważność nie mają odpowiednika w prostych operacjach na kołach,
 *  więc takich formuł nie rysujemy — pokazujemy komunikat.
 */
function sensZbiorowy(node) {
  if (node.typ === "Var") {
    return true;
  }
  if (node.typ === "Not") {
    return sensZbiorowy(node.dziecko);
  }
  if (node.typ === "And" || node.typ === "Or") {
    return sensZbiorowy(node.lewy) && sensZbiorowy(node.prawy);
  }
  return false;
}

/** Czy w formule jest choć jeden operator zbiorowy (∼, ∧, ∨). */
function maOperatorZbiorowy(node) {
  if (node.typ === "Not") {
    return true;
  }
  if (node.typ === "And" || node.typ === "Or") {
    return true;
  }
  if (node.typ === "Var") {
    return false;
  }
  return maOperatorZbiorowy(node.lewy) || maOperatorZbiorowy(node.prawy);
}

/** Nazwy zmiennych z drzewa — posortowane i bez powtórzeń. */
function zbierzZmienne(node, zmienne = new Set()) {
  if (node.typ === "Var") {
    zmienne.add(node.nazwa);
  } else if (node.typ === "Not") {
    zbierzZmienne(node.dziecko, zmienne);
  } else {
    zbierzZmienne(node.lewy, zmienne);
    zbierzZmienne(node.prawy, zmienne);
  }
  return zmienne;
}

/** Wartość formuły przy podanych wartościach zmiennych. */
function ocena(node, wartosci) {
  switch (node.typ) {
    case "Var":
      return Boolean(wartosci[node.nazwa]);
    case "Not":
      return !ocena(node.dziecko, wartosci);
    case "And":
      return ocena(node.lewy, wartosci) && ocena(node.prawy, wartosci);
    case "Or":
      return ocena(node.lewy, wartosci) || ocena(node.prawy, wartosci);
    case "Imp":
      return !ocena(node.lewy, wartosci) || ocena(node.prawy, wartosci);
    case "Iff":
      return ocena(node.lewy, wartosci) === ocena(node.prawy, wartosci);
    default:
      return false;
  }
}

/** Zamalowane obszary: liczby, których bity mówią, które zmienne są prawdziwe.
 *
 *  Dla dwóch zmiennych są cztery takie obszary, dla trzech — osiem.
 */
function obszary(node, zmienne) {
  const zamalowane = new Set();
  for (let maska = 0; maska < 1 << zmienne.length; maska += 1) {
    const wartosci = {};
    zmienne.forEach((nazwa, indeks) => {
      wartosci[nazwa] = Boolean(maska & (1 << indeks));
    });
    if (ocena(node, wartosci)) {
      zamalowane.add(maska);
    }
  }
  return zamalowane;
}

/** Podpis obszaru — ten sam dla formuł, które zamalowują ten sam obszar.
 *
 *  Dzięki podpisowi ścieżkę SVG liczymy raz na obszar, a nie raz na krok: kroki
 *  przekształcenia są równoważne, więc często pokazują ten sam obszar. */
function sygnatura(node, zmienne) {
  return [...obszary(node, zmienne)]
    .sort((a, b) => a - b)
    .join(",");
}

/** Opis obszaru po polsku, na przykład „Zamalowany obszar: p = 1, q = 0.”. */
function opisObszaru(zmienne, maska) {
  const czesci = zmienne.map(
    (nazwa, indeks) => `${nazwa} = ${maska & (1 << indeks) ? "1" : "0"}`,
  );
  return `Zamalowany obszar: ${czesci.join(", ")}.`;
}

/** Koło jako element SVG. */
function koloSvg(srodek, wypelnienie, opis) {
  const kolo = nowyElement("circle", opis);
  kolo.setAttribute("cx", String(srodek[0]));
  kolo.setAttribute("cy", String(srodek[1]));
  kolo.setAttribute("r", String(PROMIEN));
  kolo.setAttribute("fill", wypelnienie);
  return kolo;
}

/** Czy punkt leży w kole danego zbioru. */
function wKole(kola, indeks, x, y) {
  const srodek = kola[indeks];
  return (x - srodek[0]) ** 2 + (y - srodek[1]) ** 2 <= PROMIEN ** 2;
}

/** Ścieżka SVG zamalowanego obszaru, złożona z przebiegów próbek siatki.
 *
 *  Dla każdego wiersza szukamy spójnych odcinków, w których formuła jest prawdziwa,
 *  i zamieniamy każdy odcinek na prostokąt. Prostokąty zachodzą na siebie o `ZAKLADKA`,
 *  żeby między sąsiadami nie prześwitywało tło. */
function sciezkaObszaru(node, zmienne, kola) {
  const krokX = SZEROKOSC / KOLUMNY_SIATKI;
  const krokY = WYSOKOSC / WIERSZE_SIATKI;
  const wartosci = {};
  const prostokaty = [];

  for (let wiersz = 0; wiersz < WIERSZE_SIATKI; wiersz += 1) {
    const y = (wiersz + 0.5) * krokY;
    let start = -1;
    for (let kolumna = 0; kolumna <= KOLUMNY_SIATKI; kolumna += 1) {
      let prawda = false;
      if (kolumna < KOLUMNY_SIATKI) {
        const x = (kolumna + 0.5) * krokX;
        zmienne.forEach((nazwa, indeks) => {
          wartosci[nazwa] = wKole(kola, indeks, x, y);
        });
        prawda = ocena(node, wartosci);
      }
      if (prawda && start < 0) {
        start = kolumna;
      } else if (!prawda && start >= 0) {
        const lewa = (start * krokX).toFixed(1);
        const prawa = (kolumna * krokX + ZAKLADKA).toFixed(1);
        const gora = (wiersz * krokY).toFixed(1);
        const dol = ((wiersz + 1) * krokY + ZAKLADKA).toFixed(1);
        prostokaty.push(`M ${lewa} ${gora} H ${prawa} V ${dol} H ${lewa} Z`);
        start = -1;
      }
    }
  }
  return prostokaty.join(" ");
}

/** Buduje jeden diagram: przestrzeń, miejsce na obszary kroków i koła z nazwami.
 *
 *  Ścieżki obszarów dostają wszystkie kroki naraz, ale są ukryte — `ustawObszar`
 *  odkrywa tylko te, które należą do kroków już wykonanych. Dzięki temu przejście
 *  między krokami nie przebudowuje rysunku.
 *
 *  Kolejność dokładania ma znaczenie: SVG nie zna `z-index`, więc późniejszy element
 *  zasłania wcześniejszy. Wypełnienie bieżącego kroku powstaje **przed** obrysami, żeby
 *  obrys obszaru z wcześniejszego kroku leżał nad nim. Gdy kroki są równoważne (na przykład
 *  krok 3 i krok 1 w prawie de Morgana), oba obszary mają ten sam kształt — gdyby obrys
 *  powstał pierwszy, wypełnienie zasłoniłoby go i student nie zobaczyłby, że to ten sam
 *  obszar. */
function zbudujDiagram(zmienne, identyfikator, podpis, liczbaKrokow) {
  const kola = UKLADY[zmienne.length];

  const rysunek = nowyElement("svg", podpis);
  rysunek.setAttribute("viewBox", `0 0 ${SZEROKOSC} ${WYSOKOSC}`);
  rysunek.setAttribute("preserveAspectRatio", "xMidYMid meet");
  rysunek.setAttribute("class", "wiz-svg wiz-svg-zbiorow");
  rysunek.setAttribute("role", "img");
  rysunek.setAttribute("aria-label", podpis);
  rysunek.setAttribute("data-obszar", identyfikator);

  const przestrzen = nowyElement("rect", TEKSTY.przestrzen);
  przestrzen.setAttribute("x", "4");
  przestrzen.setAttribute("y", "4");
  przestrzen.setAttribute("width", String(SZEROKOSC - 8));
  przestrzen.setAttribute("height", String(WYSOKOSC - 8));
  przestrzen.setAttribute("rx", "8");
  przestrzen.setAttribute("class", "wiz-przestrzen");
  rysunek.append(przestrzen);

  const obrysy = nowyElement("g", TEKSTY.obrysKroku);
  obrysy.setAttribute("class", "wiz-obrysy-krokow");
  for (let numer = 0; numer < liczbaKrokow; numer += 1) {
    const obrys = nowyElement("path", TEKSTY.obrysKroku);
    obrys.setAttribute("class", "wiz-obrys-obszaru wiz-niewidoczny");
    obrysy.append(obrys);
  }

  const wypelnienie = nowyElement("path", TEKSTY.obszarKroku);
  wypelnienie.setAttribute("class", "wiz-obszar wiz-niewidoczny");
  // Najpierw wypełnienie, potem obrysy — inaczej wypełnienie zasłoniłoby obrys
  // obszaru o tym samym kształcie (patrz komentarz przy `zbudujDiagram`).
  rysunek.append(wypelnienie, obrysy);

  const obrysyKol = nowyElement("g", "Obrysy i nazwy zbiorów.");
  obrysyKol.setAttribute("class", "wiz-obrysy");
  kola.forEach((srodek, indeks) => {
    const obrys = koloSvg(srodek, "none", `Zbiór ${zmienne[indeks]}.`);
    obrys.setAttribute("class", "wiz-obrys");
    obrysyKol.append(obrys);

    const etykieta = nowyElement("text", `Nazwa zbioru: ${zmienne[indeks]}.`);
    etykieta.setAttribute("class", "wiz-napis");
    etykieta.setAttribute("x", String(srodek[0] - PROMIEN * 0.62));
    etykieta.setAttribute("y", String(srodek[1] - PROMIEN * 0.62));
    etykieta.setAttribute("text-anchor", "middle");
    etykieta.textContent = zmienne[indeks];
    obrysyKol.append(etykieta);
  });
  rysunek.append(obrysyKol);
  return { element: rysunek, wypelnienie, obrysy };
}

/** Rysuje obszar bieżącego kroku i obrysy obszarów z kroków wcześniejszych. */
function ustawObszar(diagram, sciezka, wczesniejsze) {
  diagram.wypelnienie.setAttribute("d", sciezka || "");
  diagram.wypelnienie.classList.toggle("wiz-niewidoczny", !sciezka);

  const sloty = diagram.obrysy.querySelectorAll("path");
  sloty.forEach((slot, numer) => {
    const wczesniejsza = wczesniejsze[numer];
    slot.setAttribute("d", wczesniejsza || "");
    slot.classList.toggle("wiz-niewidoczny", !wczesniejsza);
  });
}

/** Jedna strona prawa: nagłówek z formułą i diagram pod nim. */
function zbudujStrone(tytul, diagram) {
  const sekcja = elementHtml("div", "wiz-diagram");
  sekcja.append(elementHtml("h3", "h6 wiz-diagram-tytul", tytul), diagram.element);
  return sekcja;
}

/** Kroki przekazane przez partial: opis i formuła po kroku (pole `kroki` prawa). */
function krokiZMontazu(montaz) {
  const lista = montaz.querySelector("[data-kroki]");
  if (!lista) {
    return [];
  }
  return [...lista.querySelectorAll("li")].map((element) => ({
    opis: element.dataset.opis || "",
    po: element.dataset.po || "",
  }));
}

/** Kroki zapasowe: podformuły obu stron od najbardziej wewnętrznej do zewnętrznej.
 *
 *  Ta kolejność pokazuje, jak powstaje obszar: najpierw suma zbiorów, potem jej
 *  dopełnienie; najpierw dopełnienia, potem ich część wspólna. Używamy jej, gdy partial
 *  nie przekazał kroków prawa. */
function krokiZapasowe(lewa, prawa) {
  const kroki = [];
  const dodaj = (node, strona) => {
    if (node.typ === "Var") {
      return;
    }
    if (node.typ === "Not") {
      dodaj(node.dziecko, strona);
    } else {
      dodaj(node.lewy, strona);
      dodaj(node.prawy, strona);
    }
    const krok = operacja(node);
    kroki.push({
      tytul: krok.nazwa,
      opis: `${strona}: ${krok.nazwa} — ${krok.opis}.`,
      drzewo: node,
    });
  };
  dodaj(lewa, "Lewa strona");
  dodaj(prawa, "Prawa strona");
  return kroki;
}

/** Pokazuje komunikat zamiast diagramów.
 *
 *  Element `status` wraca do montażu razem z komunikatem. Bez tego `replaceChildren`
 *  odłączyłby go od dokumentu i `status.textContent` ustawiałby tekst na węźle poza
 *  dokumentem — czytnik ekranu nie ogłosiłby wyniku. */
function pokazKomunikat(montaz, tekst, status) {
  const komunikat = elementHtml("p", "wiz-blad alert alert-warning mb-0", tekst);
  komunikat.setAttribute("role", "alert");
  montaz.replaceChildren(komunikat, status);
  status.textContent = tekst;
}

/** Pobiera drzewo formuły z API wspólnym klientem (karta PRZ-174).

    Zwraca `{ ok, dane }` albo `{ ok: false, blad }` — nigdy nie rzuca, więc `wypelnij`
    sprawdza wynik zwykłym `if`, a nie `try/catch`. */
function pobierzAst(formula) {
  return pobierzJson(ADRES, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ formula }),
  });
}

/** Wypełnia jeden montaż: liczy obszary obu stron i prowadzi przez kroki prawa. */
async function wypelnij(montaz) {
  const formula = montaz.dataset.formula || "";
  const stronaLewa = montaz.dataset.lewa || formula;
  const stronaPrawa = montaz.dataset.prawa || formula;
  const krokiPrawa = krokiZMontazu(montaz);
  montaz.replaceChildren();

  const status = elementHtml("p", "wiz-status visually-hidden");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  montaz.append(elementHtml("p", "wiz-ladowanie text-muted small mb-1", TEKSTY.ladowanie), status);

  // Formuły do narysowania: obie strony prawa i formuła po każdym kroku. Powtarzające się
  // pobieramy raz — kroki przekształcenia często powtarzają formuły sąsiadów.
  const formuly = [...new Set([stronaLewa, stronaPrawa, ...krokiPrawa.map((krok) => krok.po)])]
    .filter((tekst) => tekst);
  const wyniki = await Promise.all(formuly.map(pobierzAst));
  const zly = wyniki.find((wynik) => !wynik.ok);
  if (zly) {
    pokazKomunikat(montaz, zly.blad || TEKSTY.siec, status);
    return;
  }
  const odpowiedzi = wyniki.map((wynik) => wynik.dane);

  for (const dane of odpowiedzi) {
    if (!dane.ok) {
      pokazKomunikat(montaz, dane.blad || TEKSTY.blad, status);
      return;
    }
    if (!dane.ast || !maPoprawneDrzewo(dane.ast)) {
      pokazKomunikat(montaz, TEKSTY.brakAst, status);
      return;
    }
  }

  const drzewa = new Map();
  formuly.forEach((tekst, indeks) => drzewa.set(tekst, odpowiedzi[indeks].ast));

  const zmienne = [
    ...new Set(formuly.flatMap((tekst) => [...zbierzZmienne(drzewa.get(tekst))])),
  ].sort();

  if (zmienne.length > MAKS_ZBIOROW) {
    pokazKomunikat(
      montaz,
      `Diagram zbiorów pokazuje co najwyżej ${MAKS_ZBIOROW} zmienne. ` +
        `Ta formuła ma ich ${zmienne.length} — nie zmieszczą się na rysunku.`,
      status,
    );
    return;
  }

  for (const tekst of formuly) {
    if (!sensZbiorowy(drzewa.get(tekst)) || !maOperatorZbiorowy(drzewa.get(tekst))) {
      pokazKomunikat(montaz, `${TEKSTY.bezSensu} (${tekst})`, status);
      return;
    }
  }

  // Krok bez formuły (puste `po`) nie ma czego narysować: `drzewa.get("")` jest `undefined`,
  // a `operacja` przewróciłaby się na odczycie `undefined.typ`. Gdy którykolwiek krok prawa
  // nie ma drzewa, wracamy do kroków z podformuł obu stron.
  const krokiPrawaMajaDrzewa =
    krokiPrawa.length > 0 && krokiPrawa.every((krok) => drzewa.has(krok.po));
  const kroki = krokiPrawaMajaDrzewa
    ? krokiPrawa.map((krok) => {
        const op = operacja(drzewa.get(krok.po));
        return { tytul: op.nazwa, opis: krok.opis, drzewo: drzewa.get(krok.po) };
      })
    : krokiZapasowe(drzewa.get(stronaLewa), drzewa.get(stronaPrawa));

  const kola = UKLADY[zmienne.length];
  const sciezkiObszarow = new Map();
  /** Ścieżka obszaru formuły — liczy się raz na obszar, nie raz na krok. */
  function sciezkaDla(drzewo) {
    const podpis = sygnatura(drzewo, zmienne);
    if (!sciezkiObszarow.has(podpis)) {
      sciezkiObszarow.set(podpis, sciezkaObszaru(drzewo, zmienne, kola));
    }
    return sciezkiObszarow.get(podpis);
  }

  const sciezkiKrokow = kroki.map((krok) => sciezkaDla(krok.drzewo));
  const sciezkaLewa = sciezkaDla(drzewa.get(stronaLewa));
  const sciezkaPrawa = sciezkaDla(drzewa.get(stronaPrawa));

  const diagramLewy = zbudujDiagram(
    zmienne,
    "lewa",
    `Diagram zbiorów dla lewej strony: ${stronaLewa}`,
    kroki.length,
  );
  const diagramPrawy = zbudujDiagram(
    zmienne,
    "prawa",
    `Diagram zbiorów dla prawej strony: ${stronaPrawa}`,
    kroki.length,
  );

  // Nazwa operacji stoi wprost nad diagramami, a opis bieżącego kroku — pod nimi.
  const operacjaEl = elementHtml("p", "wiz-operacja fw-semibold mb-2");
  operacjaEl.setAttribute("data-rola", "nazwa-operacji");
  const opisKroku = elementHtml("p", "wiz-krok-opis mb-0");
  opisKroku.setAttribute("data-rola", "opis-kroku");

  const strzalka = elementHtml("div", "wiz-strzalka", "≡");
  strzalka.setAttribute("data-rola", "strzalka-rownowaznosci");
  strzalka.setAttribute("role", "img");
  strzalka.setAttribute("aria-label", TEKSTY.strzalka);

  const diagramy = elementHtml("div", "wiz-diagramy");
  diagramy.append(
    zbudujStrone(`Lewa strona: ${stronaLewa}`, diagramLewy),
    strzalka,
    zbudujStrone(`Prawa strona: ${stronaPrawa}`, diagramPrawy),
  );

  const przyciskOba = elementHtml("button", "btn btn-sm btn-outline-primary", TEKSTY.pokazOba);
  przyciskOba.type = "button";
  przyciskOba.setAttribute("aria-pressed", "false");
  przyciskOba.setAttribute("data-rola", "pokaz-oba");

  // Pasek kroków powstaje w `createStepper`; ten kontener tylko go mieści.
  const montazKrokow = elementHtml("div", "wiz-kroki");
  montazKrokow.setAttribute("data-stepper", "");

  const obszaryLewe = obszary(drzewa.get(stronaLewa), zmienne);
  const obszaryPrawe = obszary(drzewa.get(stronaPrawa), zmienne);
  const takieSame =
    obszaryLewe.size === obszaryPrawe.size &&
    [...obszaryLewe].every((maska) => obszaryPrawe.has(maska));

  const podpis = elementHtml(
    "p",
    `wiz-podpis alert mb-0 ${takieSame ? "alert-success" : "alert-warning"}`,
    takieSame ? TEKSTY.takiSam : TEKSTY.rozny,
  );

  const uwagi = elementHtml("p", "wiz-legenda-opis small text-muted mb-0", TEKSTY.legenda);
  if (obszaryLewe.size === 0 && obszaryPrawe.size === 0) {
    uwagi.textContent = `${TEKSTY.legenda} ${TEKSTY.obszarPusty}`;
  } else if (obszaryLewe.size === 1 << zmienne.length && obszaryPrawe.size === 1 << zmienne.length) {
    uwagi.textContent = `${TEKSTY.legenda} ${TEKSTY.obszarPelny}`;
  }

  const sekcja = elementHtml("div", "wiz-rysunek d-flex flex-column gap-3");
  sekcja.append(operacjaEl, diagramy, przyciskOba, opisKroku, montazKrokow, podpis, uwagi);
  montaz.replaceChildren(sekcja, status);

  let widokOba = false;
  let stepper = null;

  /** Rysuje krok o podanym numerze: obszar kroku i obrysy kroków wcześniejszych. */
  function pokazKrok(numer) {
    const indeks = Math.min(Math.max(numer, 0), kroki.length - 1);
    widokOba = false;
    przyciskOba.setAttribute("aria-pressed", "false");
    przyciskOba.textContent = TEKSTY.pokazOba;

    const wczesniejsze = sciezkiKrokow.slice(0, indeks);
    ustawObszar(diagramLewy, sciezkiKrokow[indeks], wczesniejsze);
    ustawObszar(diagramPrawy, sciezkiKrokow[indeks], wczesniejsze);

    const krok = kroki[indeks];
    const op = operacja(krok.drzewo);
    operacjaEl.textContent = `${TEKSTY.krok} ${indeks + 1}: ${op.nazwa} — ${op.opis}`;
    const czyTenSam = indeks > 0 && sciezkiKrokow[indeks] === sciezkiKrokow[indeks - 1];
    opisKroku.textContent =
      `${TEKSTY.krok} ${indeks + 1} z ${kroki.length}: ${krok.opis}` +
      `${czyTenSam ? ` ${TEKSTY.tenSam}` : ""}`;
    status.textContent =
      `${krok.opis} Zamalowany obszar: ${op.nazwa}. ${TEKSTY.krok} ${indeks + 1} z ${kroki.length}.`;
  }

  /** Przełącza widok: kroki po kolei albo oba docelowe obszary naraz. */
  function przelaczOba() {
    widokOba = !widokOba;
    przyciskOba.setAttribute("aria-pressed", widokOba ? "true" : "false");
    przyciskOba.textContent = widokOba ? TEKSTY.pokazKrokami : TEKSTY.pokazOba;

    if (!widokOba) {
      pokazKrok(stepper ? stepper.index : 0);
      return;
    }
    ustawObszar(diagramLewy, sciezkaLewa, []);
    ustawObszar(diagramPrawy, sciezkaPrawa, []);
    operacjaEl.textContent = TEKSTY.oba;
    opisKroku.textContent = TEKSTY.oba;
    status.textContent = `${TEKSTY.oba} ${takieSame ? TEKSTY.takiSam : TEKSTY.rozny}`;
  }

  przyciskOba.addEventListener("click", przelaczOba);

  stepper = createStepper({
    mount: montazKrokow,
    steps: kroki.map((krok) => ({ tytul: krok.tytul, opis: krok.opis })),
    labels: {
      prev: "Wstecz",
      next: "Dalej",
      play: "Odtwórz",
      pause: "Pauza",
      reset: "Od nowa",
    },
    onStep: (indeks) => pokazKrok(indeks),
  });
}

document.querySelectorAll(".sets-mount").forEach((montaz) => {
  wypelnij(montaz);
});
