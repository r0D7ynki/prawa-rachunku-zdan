/* Schemat bramek logicznych dla formuły (karta PRZ-012).

   Rysunek powstaje z drzewa `ast` z `POST /api/formula/parse` — struktury nie zgadujemy
   z tekstu formuły. Każdy element SVG tworzymy przez `document.createElementNS`, a treść
   wstawiamy wyłącznie przez `textContent`. Dzięki temu napis z API (na przykład nazwa
   zmiennej) nigdy nie trafia do DOM jako kod.

   Każdy element rysunku dostaje potomka `<title>` z opisem po polsku. Także elementy
   `<text>`: przeglądarki nie pokazują `<title>` wewnątrz napisu, a dzięki temu każdy
   fragment schematu ma opis, gdy czytnik ekranu idzie po kolei po elementach. */

const ADRES = "/api/formula/parse";
const NS_SVG = "http://www.w3.org/2000/svg";

const TEKSTY = {
  ladowanie: "Wczytuję schemat bramek…",
  siec: "Nie udało się połączyć z serwerem. Sprawdź połączenie i odśwież stronę.",
  blad: "Nie udało się narysować schematu dla tej formuły.",
  brakAst: "Serwer nie przysłał drzewa formuły, więc nie ma czego rysować.",
  zaDuze: "Ta formuła ma zbyt wiele części, żeby zmieścił się czytelny schemat.",
  opisRysunku: "Schemat bramek logicznych dla tej formuły",
  opisUkladu: "Rysunek czytamy od lewej: zmienne na wejściu, bramki liczą wynik.",
  wyjscie: "Wyjście układu. To jest wynik całej formuły.",
  przewod: "Przewód z wyjścia jednej bramki na wejście następnej.",
  zmienna: "Wejście układu — zmienna zdaniowa",
  opisLegendy: "Legenda bramek użytych na rysunku",
};

/** Nazwa, symbol i zdanie z życia dla każdego typu węzła drzewa. */
const BRAMKI = {
  Not: {
    symbol: "∼",
    nazwa: "Negacja (NIE)",
    zdanie: "Odwraca wartość: z prawdy robi fałsz, a z fałszu prawdę.",
    tytul: "Bramka negacji — odwraca wartość wejścia.",
  },
  And: {
    symbol: "∧",
    nazwa: "Koniunkcja (I)",
    zdanie: "Wynik jest prawdziwy tylko wtedy, gdy oba wejścia są prawdziwe.",
    tytul: "Bramka koniunkcji — wynik prawdziwy tylko przy dwóch prawdziwych wejściach.",
  },
  Or: {
    symbol: "∨",
    nazwa: "Alternatywa (LUB)",
    zdanie: "Wynik jest prawdziwy, gdy przynajmniej jedno wejście jest prawdziwe.",
    tytul: "Bramka alternatywy — wynik prawdziwy, gdy któreś wejście jest prawdziwe.",
  },
  Imp: {
    symbol: "→",
    nazwa: "Implikacja (JEŻELI… TO…)",
    zdanie: "Wynik jest fałszywy tylko wtedy, gdy z prawdy wynika fałsz.",
    tytul: "Bramka implikacji — fałsz tylko wtedy, gdy poprzednik prawdziwy, a następnik fałszywy.",
  },
  Iff: {
    symbol: "↔",
    nazwa: "Równoważność (… WTEDY I TYLKO WTEDY…)",
    zdanie: "Wynik jest prawdziwy, gdy oba wejścia mają tę samą wartość.",
    tytul: "Bramka równoważności — wynik prawdziwy, gdy wejścia są równe.",
  },
};

/** Kolejność, w jakiej typy węzłów trafiają do legendy. */
const KOLEJNOSC_TYPOW = ["Not", "And", "Or", "Imp", "Iff"];

const MARGINES_X = 56;
const ODSTEP_KOLUMN = 96;
const ODSTEP_WIERSZA = 62;
const WYSOKOSC_BRAMY = 34;
const POLOWA_BRAMY = 20;
const SZEROKOSC_ZMIENNEJ = 46;
const ODSTEP_WEJSC = 9;
/** Zapas po prawej stronie na przewód wyjściowy i napis „wynik”. */
const MIEJSCE_WYJSCIA = 96;
/** Największa liczba wejść, dla której schemat jest jeszcze czytelny. */
const MAKS_WEJSC = 10;

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

/** Czy drzewo z API ma kształt, który umiemy narysować. */
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

/** Typy węzłów użyte w drzewie — legenda pokazuje tylko je. */
function zbierzTypy(node, typy = new Set()) {
  typy.add(node.typ);
  if (node.typ === "Not") {
    zbierzTypy(node.dziecko, typy);
  } else if (node.typ !== "Var") {
    zbierzTypy(node.lewy, typy);
    zbierzTypy(node.prawy, typy);
  }
  return typy;
}

/** Liczy kolumnę i wiersz każdego węzła.
 *
 *  Kolumna rośnie od wejść (0) do wyjścia, wiersz to wysokość na rysunku. Liście
 *  dostają kolejne wiersze w kolejności czytania, a bramka — środek swoich wejść.
 *  Bez tego bramki zachodziłyby na siebie.
 */
function zaplanuj(ast) {
  const pozycje = new Map();
  let liscie = 0;
  let kolumny = 0;

  function policz(node) {
    if (node.typ === "Var") {
      const wynik = { kolumna: 0, wiersz: liscie };
      pozycje.set(node, wynik);
      liscie += 1;
      return wynik;
    }
    const dzieci = node.typ === "Not" ? [node.dziecko] : [node.lewy, node.prawy];
    const wyniki = dzieci.map(policz);
    const kolumna = Math.max(...wyniki.map((wynik) => wynik.kolumna)) + 1;
    const wiersz = wyniki.reduce((suma, wynik) => suma + wynik.wiersz, 0) / wyniki.length;
    const wynik = { kolumna, wiersz };
    pozycje.set(node, wynik);
    kolumny = Math.max(kolumny, kolumna);
    return wynik;
  }

  policz(ast);

  const wysokoscTresci = Math.max((liscie - 1) * ODSTEP_WIERSZA, 0);
  return {
    pozycje,
    liscie,
    szerokosc: MARGINES_X + kolumny * ODSTEP_KOLUMN + POLOWA_BRAMY + MIEJSCE_WYJSCIA,
    wysokosc: Math.max(wysokoscTresci + 2 * WYSOKOSC_BRAMY, 150),
    przesuniecie: Math.max(WYSOKOSC_BRAMY, (150 - wysokoscTresci) / 2),
  };
}

/** Środek bramki albo zmiennej na rysunku. */
function punkt(uklad, node) {
  const { kolumna, wiersz } = uklad.pozycje.get(node);
  return {
    x: MARGINES_X + kolumna * ODSTEP_KOLUMN,
    y: uklad.przesuniecie + wiersz * ODSTEP_WIERSZA,
  };
}

/** Kształt bramki w układzie lokalnym: środek bramki to punkt (0, 0). */
function ksztalt(typ, srodek) {
  const brama = nowyElement("g", BRAMKI[typ].tytul);
  brama.setAttribute("transform", `translate(${srodek.x} ${srodek.y})`);
  brama.setAttribute("class", `wiz-bramka wiz-bramka-${typ.toLowerCase()}`);

  const rysunek = nowyElement("path", BRAMKI[typ].tytul);
  rysunek.setAttribute("class", "wiz-kształt");
  if (typ === "Not") {
    rysunek.setAttribute("d", `M ${-POLOWA_BRAMY},-17 L 6,0 L ${-POLOWA_BRAMY},17 Z`);
    const kolko = nowyElement("circle", "Kółko na wyjściu bramki negacji.");
    kolko.setAttribute("cx", "11");
    kolko.setAttribute("cy", "0");
    kolko.setAttribute("r", "5");
    kolko.setAttribute("class", "wiz-kształt");
    brama.append(rysunek, kolko);
  } else if (typ === "And") {
    rysunek.setAttribute("d", `M ${-POLOWA_BRAMY},-17 L 0,-17 A 17,17 0 0 1 0,17 L ${-POLOWA_BRAMY},17 Z`);
    brama.append(rysunek);
  } else if (typ === "Or") {
    rysunek.setAttribute(
      "d",
      `M ${-POLOWA_BRAMY},-17 Q -4,-17 14,0 Q -4,17 ${-POLOWA_BRAMY},17 Q -9,0 ${-POLOWA_BRAMY},-17 Z`,
    );
    brama.append(rysunek);
  } else if (typ === "Imp") {
    rysunek.setAttribute("d", "M -13,-17 L 14,0 L -13,17 Z");
    const krawedz = nowyElement("path", "Krawędź wejściowa bramki implikacji.");
    krawedz.setAttribute("d", `M ${-POLOWA_BRAMY},-17 L ${-POLOWA_BRAMY},17`);
    krawedz.setAttribute("class", "wiz-kształt");
    brama.append(rysunek, krawedz);
  } else {
    rysunek.setAttribute("d", `M ${-POLOWA_BRAMY},-17 L 6,-17 L 6,17 L ${-POLOWA_BRAMY},17 Z`);
    brama.append(rysunek);
  }

  const napis = nowyElement("text", `${BRAMKI[typ].nazwa}. ${BRAMKI[typ].zdanie}`);
  napis.setAttribute("class", "wiz-symbol");
  napis.setAttribute("x", "0");
  napis.setAttribute("y", "0");
  napis.setAttribute("text-anchor", "middle");
  napis.setAttribute("dominant-baseline", "central");
  napis.textContent = BRAMKI[typ].symbol;
  brama.append(napis);
  return brama;
}

/** Prostokąt ze zmienną na wejściu układu. */
function wezelZmiennej(nazwa, srodek) {
  const grupa = nowyElement("g", `${TEKSTY.zmienna} „${nazwa}”.`);
  grupa.setAttribute("transform", `translate(${srodek.x} ${srodek.y})`);
  grupa.setAttribute("class", "wiz-zmienna");

  const tlo = nowyElement("rect", `${TEKSTY.zmienna} „${nazwa}”.`);
  tlo.setAttribute("x", String(-SZEROKOSC_ZMIENNEJ / 2));
  tlo.setAttribute("y", "-15");
  tlo.setAttribute("width", String(SZEROKOSC_ZMIENNEJ));
  tlo.setAttribute("height", "30");
  tlo.setAttribute("rx", "6");
  tlo.setAttribute("class", "wiz-kształt");
  grupa.append(tlo);

  const napis = nowyElement("text", `${TEKSTY.zmienna} „${nazwa}”.`);
  napis.setAttribute("class", "wiz-napis");
  napis.setAttribute("x", "0");
  napis.setAttribute("y", "0");
  napis.setAttribute("text-anchor", "middle");
  napis.setAttribute("dominant-baseline", "central");
  napis.textContent = nazwa;
  grupa.append(napis);
  return grupa;
}

/** Przewód jako łamana linia: wyjście bramki, potem wejście następnej. */
function przewod(od, do_) {
  const linia = nowyElement("polyline", TEKSTY.przewod);
  linia.setAttribute("class", "wiz-przewod");
  const srodek = (od.x + do_.x) / 2;
  linia.setAttribute(
    "points",
    `${od.x},${od.y} ${srodek},${od.y} ${srodek},${do_.y} ${do_.x},${do_.y}`,
  );
  return linia;
}

/** Buduje rysunek: przewody, bramki i przewód wyjściowy. Zwraca `<svg>`. */
function zbudujRysunek(ast, uklad) {
  const rysunek = nowyElement("svg", TEKSTY.opisRysunku);
  rysunek.setAttribute("viewBox", `0 0 ${uklad.szerokosc} ${uklad.wysokosc}`);
  rysunek.setAttribute("preserveAspectRatio", "xMidYMid meet");
  rysunek.setAttribute("class", "wiz-svg wiz-svg-bramki");
  rysunek.setAttribute("role", "img");
  rysunek.setAttribute("aria-label", TEKSTY.opisRysunku);

  const przewody = nowyElement("g", "Przewody układu.");
  przewody.setAttribute("class", "wiz-przewody");
  const bramki = nowyElement("g", TEKSTY.opisUkladu);
  bramki.setAttribute("class", "wiz-bramki");
  rysunek.append(przewody, bramki);

  function idz(node) {
    const srodek = punkt(uklad, node);
    if (node.typ === "Var") {
      bramki.append(wezelZmiennej(node.nazwa, srodek));
      return { x: srodek.x + SZEROKOSC_ZMIENNEJ / 2, y: srodek.y };
    }

    const dzieci = node.typ === "Not" ? [node.dziecko] : [node.lewy, node.prawy];
    const wyjscia = dzieci.map(idz);
    wyjscia.forEach((wyjscie, indeks) => {
      const wejscie = {
        x: srodek.x - POLOWA_BRAMY,
        y: dzieci.length === 1 ? srodek.y : srodek.y + (indeks === 0 ? -ODSTEP_WEJSC : ODSTEP_WEJSC),
      };
      przewody.append(przewod(wyjscie, wejscie));
    });
    bramki.append(ksztalt(node.typ, srodek));
    return { x: srodek.x + (node.typ === "Not" ? 16 : POLOWA_BRAMY), y: srodek.y };
  }

  const wyjscie = idz(ast);
  const koniec = uklad.szerokosc - 62;
  przewody.append(przewod(wyjscie, { x: koniec, y: wyjscie.y }));

  const napis = nowyElement("text", TEKSTY.wyjscie);
  napis.setAttribute("class", "wiz-wynik");
  napis.setAttribute("x", String(koniec + 6));
  napis.setAttribute("y", String(wyjscie.y));
  napis.setAttribute("dominant-baseline", "central");
  napis.textContent = "wynik";
  rysunek.append(napis);
  return rysunek;
}

/** Legenda: tylko bramki, które naprawdę występują na rysunku. */
function zbudujLegende(uzyte) {
  const sekcja = elementHtml("div", "wiz-legenda");
  sekcja.append(
    elementHtml("h3", "h6 wiz-legenda-tytul", "Legenda bramek na rysunku"),
    elementHtml("p", "wiz-legenda-opis small text-muted mb-2", TEKSTY.opisUkladu),
  );

  const lista = elementHtml("dl", "wiz-legenda-lista row mb-0");
  lista.setAttribute("aria-label", TEKSTY.opisLegendy);
  for (const typ of KOLEJNOSC_TYPOW) {
    if (!uzyte.has(typ)) {
      continue;
    }
    lista.append(
      elementHtml("dt", "col-sm-4", `${BRAMKI[typ].symbol} — ${BRAMKI[typ].nazwa}`),
      elementHtml("dd", "col-sm-8", BRAMKI[typ].zdanie),
    );
  }
  sekcja.append(lista);
  return sekcja;
}

/** Pokazuje komunikat zamiast rysunku.

    Element `status` wraca do montażu razem z komunikatem. Bez tego `replaceChildren`
    odłączyłby go od dokumentu i `status.textContent` ustawiałby tekst na węźle poza
    dokumentem — czytnik ekranu nie ogłosiłby wyniku. */
function pokazKomunikat(montaz, tekst, status) {
  montaz.replaceChildren(elementHtml("p", "wiz-blad alert alert-warning mb-0", tekst), status);
  status.textContent = tekst;
}

/** Wypełnia jeden montaż: pobiera drzewo formuły i rysuje z niego schemat. */
async function wypelnij(montaz) {
  const formula = montaz.dataset.formula || "";
  montaz.replaceChildren();

  const status = elementHtml("p", "wiz-status visually-hidden");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  montaz.append(elementHtml("p", "wiz-ladowanie text-muted small mb-1", TEKSTY.ladowanie), status);

  let dane;
  try {
    const odpowiedz = await fetch(ADRES, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ formula }),
    });
    dane = await odpowiedz.json();
  } catch (blad) {
    pokazKomunikat(montaz, TEKSTY.siec, status);
    return;
  }

  if (!dane.ok) {
    pokazKomunikat(montaz, dane.blad || TEKSTY.blad, status);
    return;
  }

  if (!dane.ast || !maPoprawneDrzewo(dane.ast)) {
    pokazKomunikat(montaz, TEKSTY.brakAst, status);
    return;
  }

  const uklad = zaplanuj(dane.ast);
  if (uklad.liscie > MAKS_WEJSC) {
    pokazKomunikat(montaz, TEKSTY.zaDuze, status);
    return;
  }

  const figura = elementHtml("div", "wiz-figura");
  figura.append(zbudujRysunek(dane.ast, uklad));
  montaz.replaceChildren(figura, zbudujLegende(zbierzTypy(dane.ast)), status);
  status.textContent = `${TEKSTY.opisRysunku}. Wykorzystane bramki: ${[...zbierzTypy(dane.ast)]
    .map((typ) => BRAMKI[typ].nazwa)
    .join(", ")}.`;
}

document.querySelectorAll(".gates-mount").forEach((montaz) => {
  wypelnij(montaz);
});
