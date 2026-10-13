/* Diagramy zbiorów dla lewej i prawej strony prawa (karta PRZ-012).

   Dla każdej strony pobieramy drzewo `ast` z `POST /api/formula/parse` i liczymy je
   **na obszarach**: prostokąt to cała przestrzeń, koła to zbiory zmiennych, a każdy
   najmniejszy obszar (pole, na którym wartości zmiennych są ustalone) jest zamalowany
   wtedy, gdy formuła jest w nim prawdziwa.

   Zamalowanie rysujemy bez liczenia krzywych: najmniejszy obszar to część wspólna kół
   zmiennych prawdziwych (`clipPath` jeden na drugim) bez kół zmiennych fałszywych
   (`mask` — czarne koła zasłaniają). Dzięki temu kształt jest gładki, a nie schodkowy.

   Każdy element SVG tworzymy przez `document.createElementNS`, a treść wstawiamy tylko
   przez `textContent` — napisy z API nie trafiają do DOM jako kod. */

const ADRES = "/api/formula/parse";
const NS_SVG = "http://www.w3.org/2000/svg";

/** Najwięcej kół, ile zmieści się na czytelnym diagramie. */
const MAKS_ZBIOROW = 3;

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
};

const SZEROKOSC = 220;
const WYSOKOSC = 180;
const PROMIEN = 46;

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

/** Rysuje jeden najmniejszy obszar: część wspólna kół prawdziwych bez kół fałszywych. */
function zbudujObszar(kola, zmienne, maska, identyfikator, numer, definicje) {
  const opis = opisObszaru(zmienne, maska);
  const prawdziwe = [];
  const falszywe = [];
  zmienne.forEach((nazwa, indeks) => {
    if (maska & (1 << indeks)) {
      prawdziwe.push(indeks);
    } else {
      falszywe.push(indeks);
    }
  });

  const maskaEl = nowyElement("mask", `Maska obszaru: ${opis}`);
  maskaEl.setAttribute("id", `wiz-maska-${identyfikator}-${numer}`);
  maskaEl.setAttribute("maskUnits", "userSpaceOnUse");
  maskaEl.setAttribute("x", "0");
  maskaEl.setAttribute("y", "0");
  maskaEl.setAttribute("width", String(SZEROKOSC));
  maskaEl.setAttribute("height", String(WYSOKOSC));
  const widoczne = nowyElement("rect", "Obszar widoczny dla maski.");
  widoczne.setAttribute("width", String(SZEROKOSC));
  widoczne.setAttribute("height", String(WYSOKOSC));
  widoczne.setAttribute("fill", "#ffffff");
  maskaEl.append(widoczne);
  falszywe.forEach((indeks) => {
    maskaEl.append(koloSvg(kola[indeks], "#000000", opis));
  });
  definicje.append(maskaEl);

  const grupa = nowyElement("g", opis);
  grupa.setAttribute("mask", `url(#wiz-maska-${identyfikator}-${numer})`);
  let wezel = grupa;
  prawdziwe.forEach((indeks) => {
    const przyciete = nowyElement("g", opis);
    przyciete.setAttribute("clip-path", `url(#wiz-klip-${identyfikator}-${indeks})`);
    wezel.append(przyciete);
    wezel = przyciete;
  });

  const zamalowanie = nowyElement("rect", opis);
  zamalowanie.setAttribute("width", String(SZEROKOSC));
  zamalowanie.setAttribute("height", String(WYSOKOSC));
  zamalowanie.setAttribute("class", "wiz-obszar");
  wezel.append(zamalowanie);
  return grupa;
}

/** Buduje jeden diagram: przestrzeń, zamalowane obszary i obrysy kół. */
function zbudujDiagram(node, zmienne, identyfikator) {
  const kola = UKLADY[zmienne.length];
  const podpisRysunku = `Diagram zbiorów dla formuły o zbiorach ${zmienne.join(", ")}`;

  const rysunek = nowyElement("svg", podpisRysunku);
  rysunek.setAttribute("viewBox", `0 0 ${SZEROKOSC} ${WYSOKOSC}`);
  rysunek.setAttribute("preserveAspectRatio", "xMidYMid meet");
  rysunek.setAttribute("class", "wiz-svg wiz-svg-zbiorow");
  rysunek.setAttribute("role", "img");
  rysunek.setAttribute("aria-label", podpisRysunku);

  const definicje = nowyElement("defs", "Przycięcia i maski obszarów tego diagramu.");
  kola.forEach((srodek, indeks) => {
    const przyciecie = nowyElement("clipPath", `Zbiór ${zmienne[indeks]}.`);
    przyciecie.setAttribute("id", `wiz-klip-${identyfikator}-${indeks}`);
    przyciecie.append(koloSvg(srodek, "#ffffff", `Zbiór ${zmienne[indeks]}.`));
    definicje.append(przyciecie);
  });
  rysunek.append(definicje);

  const przestrzen = nowyElement("rect", TEKSTY.przestrzen);
  przestrzen.setAttribute("x", "4");
  przestrzen.setAttribute("y", "4");
  przestrzen.setAttribute("width", String(SZEROKOSC - 8));
  przestrzen.setAttribute("height", String(WYSOKOSC - 8));
  przestrzen.setAttribute("rx", "8");
  przestrzen.setAttribute("class", "wiz-przestrzen");
  rysunek.append(przestrzen);

  const warstwa = nowyElement("g", "Zamalowane obszary tej strony formuły.");
  warstwa.setAttribute("class", "wiz-obszary");
  [...obszary(node, zmienne)]
    .sort((a, b) => a - b)
    .forEach((maska, numer) => {
      warstwa.append(zbudujObszar(kola, zmienne, maska, identyfikator, numer, definicje));
    });
  rysunek.append(warstwa);

  const obrysy = nowyElement("g", "Obrysy i nazwy zbiorów.");
  obrysy.setAttribute("class", "wiz-obrysy");
  kola.forEach((srodek, indeks) => {
    const obrys = koloSvg(srodek, "none", `Zbiór ${zmienne[indeks]}.`);
    obrys.setAttribute("class", "wiz-obrys");
    obrysy.append(obrys);

    const etykieta = nowyElement("text", `Nazwa zbioru: ${zmienne[indeks]}.`);
    etykieta.setAttribute("class", "wiz-napis");
    etykieta.setAttribute("x", String(srodek[0] - PROMIEN * 0.62));
    etykieta.setAttribute("y", String(srodek[1] - PROMIEN * 0.62));
    etykieta.setAttribute("text-anchor", "middle");
    etykieta.textContent = zmienne[indeks];
    obrysy.append(etykieta);
  });
  rysunek.append(obrysy);
  return rysunek;
}

/** Jedna strona prawa: nagłówek z formułą i diagram pod nim. */
function zbudujStrone(tytul, node, zmienne, identyfikator) {
  const sekcja = elementHtml("div", "wiz-diagram");
  sekcja.append(
    elementHtml("h3", "h6 wiz-diagram-tytul", tytul),
    zbudujDiagram(node, zmienne, identyfikator),
  );
  return sekcja;
}

/** Pokazuje komunikat zamiast diagramów.

    Element `status` wraca do montażu razem z komunikatem. Bez tego `replaceChildren`
    odłączyłby go od dokumentu i `status.textContent` ustawiałby tekst na węźle poza
    dokumentem — czytnik ekranu nie ogłosiłby wyniku. */
function pokazKomunikat(montaz, tekst, status) {
  montaz.replaceChildren(elementHtml("p", "wiz-blad alert alert-warning mb-0", tekst), status);
  status.textContent = tekst;
}

/** Pobiera drzewo formuły z API. Rzuca, gdy sieć zawiedzie — łapie to `wypelnij`. */
async function pobierzAst(formula) {
  const odpowiedz = await fetch(ADRES, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ formula }),
  });
  return odpowiedz.json();
}

/** Wypełnia jeden montaż: liczy obszary obu stron i rysuje je obok siebie. */
async function wypelnij(montaz) {
  const formula = montaz.dataset.formula || "";
  const stronaLewa = montaz.dataset.lewa || formula;
  const stronaPrawa = montaz.dataset.prawa || formula;
  montaz.replaceChildren();

  const status = elementHtml("p", "wiz-status visually-hidden");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  montaz.append(elementHtml("p", "wiz-ladowanie text-muted small mb-1", TEKSTY.ladowanie), status);

  let daneLewa;
  let danePrawa;
  try {
    [daneLewa, danePrawa] = await Promise.all([pobierzAst(stronaLewa), pobierzAst(stronaPrawa)]);
  } catch (blad) {
    pokazKomunikat(montaz, TEKSTY.siec, status);
    return;
  }

  for (const dane of [daneLewa, danePrawa]) {
    if (!dane.ok) {
      pokazKomunikat(montaz, dane.blad || TEKSTY.blad, status);
      return;
    }
    if (!dane.ast || !maPoprawneDrzewo(dane.ast)) {
      pokazKomunikat(montaz, TEKSTY.brakAst, status);
      return;
    }
  }

  const zmienne = [...zbierzZmienne(daneLewa.ast)]
    .concat([...zbierzZmienne(danePrawa.ast)])
    .filter((nazwa, indeks, wszystkie) => wszystkie.indexOf(nazwa) === indeks)
    .sort();

  if (zmienne.length > MAKS_ZBIOROW) {
    pokazKomunikat(
      montaz,
      `Diagram zbiorów pokazuje co najwyżej ${MAKS_ZBIOROW} zmienne. ` +
        `Ta formuła ma ich ${zmienne.length} — nie zmieszczą się na rysunku.`,
      status,
    );
    return;
  }

  for (const [etykieta, dane] of [
    ["lewa strona", daneLewa],
    ["prawa strona", danePrawa],
  ]) {
    if (!sensZbiorowy(dane.ast) || !maOperatorZbiorowy(dane.ast)) {
      pokazKomunikat(montaz, `${TEKSTY.bezSensu} (${etykieta})`, status);
      return;
    }
  }

  const obszaryLewe = obszary(daneLewa.ast, zmienne);
  const obszaryPrawe = obszary(danePrawa.ast, zmienne);
  const takieSame =
    obszaryLewe.size === obszaryPrawe.size &&
    [...obszaryLewe].every((maska) => obszaryPrawe.has(maska));

  const diagramy = elementHtml("div", "wiz-diagramy");
  diagramy.append(
    zbudujStrone(`Lewa strona: ${stronaLewa}`, daneLewa.ast, zmienne, "lewa"),
    zbudujStrone(`Prawa strona: ${stronaPrawa}`, danePrawa.ast, zmienne, "prawa"),
  );

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

  montaz.replaceChildren(diagramy, podpis, uwagi, status);
  status.textContent = `${takieSame ? TEKSTY.takiSam : TEKSTY.rozny} Zamalowanych obszarów: ${
    obszaryLewe.size
  } po lewej i ${obszaryPrawe.size} po prawej.`;
}

document.querySelectorAll(".sets-mount").forEach((montaz) => {
  wypelnij(montaz);
});
