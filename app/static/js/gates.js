/* Schemat bramek logicznych prowadzony krok po kroku (karty PRZ-012 i PRZ-074).

   Rysunek powstaje z drzewa `ast` z `POST /api/formula/parse` — struktury nie zgadujemy
   z tekstu formuły. Wartości podformuł bierzemy z `POST /api/formula/table` (pole `znaki`):
   dla wybranego wartościowania czytamy gotowe wyniki, zamiast liczyć logikę w przeglądarce.
   Każdy element SVG tworzymy przez `document.createElementNS`, a treść wstawiamy wyłącznie
   przez `textContent`. Dzięki temu napis z API (na przykład nazwa zmiennej) nigdy nie trafia
   do DOM jako kod.

   Każdy element rysunku dostaje potomka `<title>` z opisem po polsku. Także elementy
   `<text>`: przeglądarki nie pokazują `<title>` wewnątrz napisu, a dzięki temu każdy
   fragment schematu ma opis, gdy czytnik ekranu idzie po kolei po elementach.

   Przewody mają groty strzałek (`marker-end`), a wartości na nich są opisane słowami
   PRAWDA i FAŁSZ — kolor tylko wspiera tekst, nigdy nie jest jedynym nośnikiem informacji. */

import { pobierzJson } from "/static/js/api.js";
import { createStepper } from "/static/js/stepper.js";

const ADRES = "/api/formula/parse";
const ADRES_TABLICY = "/api/formula/table";
const NS_SVG = "http://www.w3.org/2000/svg";

/** Identyfikator grotu strzałki, którym kończy się każdy przewód. */
const ID_GROTU = "wiz-grot";
/** Pole z wynikami kolumn w wierszu tablicy prawdy (umowa z API). */
const POLE_WARTOSCI = "values";

const TEKSTY = {
  ladowanie: "Wczytuję schemat bramek…",
  siec: "Nie udało się połączyć z serwerem. Sprawdź połączenie i odśwież stronę.",
  blad: "Nie udało się narysować schematu dla tej formuły.",
  brakAst: "Serwer nie przysłał drzewa formuły, więc nie ma czego rysować.",
  zaDuze: "Ta formuła ma zbyt wiele części, żeby zmieścił się czytelny schemat.",
  brakTabeli: "Serwer nie przysłał wartości podformuł, więc nie ma z czego policzyć kroków.",
  opisRysunku: "Schemat bramek logicznych dla tej formuły",
  opisUkladu: "Rysunek czytamy od lewej: zmienne na wejściu, bramki liczą wynik.",
  wyjscie: "Wyjście układu. To jest wynik całej formuły.",
  przewod: "Przewód z wyjścia jednej bramki na wejście następnej.",
  zmienna: "Wejście układu — zmienna zdaniowa",
  opisLegendy: "Legenda bramek użytych na rysunku",
  strzalka: "Grot strzałki pokazuje kierunek przepływu sygnału.",
  wartoscNieznana: "Wartość jeszcze nieznana — przejdź kroki, żeby ją policzyć.",
  wejscia: "Wartości wejść układu",
  wejscie: "Wartość wejścia",
  prawda: "PRAWDA",
  falsz: "FAŁSZ",
  znakNieznany: "?",
  wynikCalkowity: "Cała formuła ma wartość",
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
/** Zapas po prawej stronie na przewód wyjściowy, strzałkę i napis „wynik”. */
const MIEJSCE_WYJSCIA = 116;
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

/** Podmienia opis `<title>` i `aria-label` elementu SVG (pierwsze dziecko tworzy `nowyElement`). */
function ustawTytul(element, opis) {
  const tytul = element.firstElementChild;
  if (tytul && tytul.tagName.toLowerCase() === "title") {
    tytul.textContent = opis;
  }
  if (element.hasAttribute("aria-label")) {
    element.setAttribute("aria-label", opis);
  }
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

/** Klucz strukturalny węzła.
 *
 *  Identyczne podformuły dostają jeden klucz — tak samo porównuje je serwer (po wartości,
 *  a nie po położeniu w drzewie). Dzięki temu wynik kolumny „p ∧ q” pasuje do każdego
 *  wystąpienia tej podformuły na rysunku. */
function kluczWezla(node) {
  if (node.typ === "Var") {
    return `Var:${node.nazwa}`;
  }
  if (node.typ === "Not") {
    return `Not(${kluczWezla(node.dziecko)})`;
  }
  return `${node.typ}(${kluczWezla(node.lewy)},${kluczWezla(node.prawy)})`;
}

/** Liczba wystąpień zmiennych w poddrzewie — tyle samo zwraca `formula.size` w Pythonie. */
function liczbaLisci(node) {
  if (node.typ === "Var") {
    return 1;
  }
  if (node.typ === "Not") {
    return liczbaLisci(node.dziecko);
  }
  return liczbaLisci(node.lewy) + liczbaLisci(node.prawy);
}

/** Podformuły bez powtórzeń, od najmniejszej — kolejność kolumn tablicy z API.
 *
 *  Kolejność musi zgadzać się z `truth.subformulas` w Pythonie: przejście dzieci przed
 *  rodzicem, bez powtórzeń, a potem stabilne sortowanie po liczbie liści (przy remisie
 *  decyduje kolejność przejścia). Dzięki temu indeks podformuły wskazuje jej kolumnę
 *  w `POST /api/formula/table`, więc wartości nie liczymy w przeglądarce. */
function zbierzPodformuly(ast) {
  const kolejnosc = [];
  const wezly = new Map();

  function idz(node) {
    if (node.typ === "Not") {
      idz(node.dziecko);
    } else if (node.typ !== "Var") {
      idz(node.lewy);
      idz(node.prawy);
    }
    const klucz = kluczWezla(node);
    if (!wezly.has(klucz)) {
      wezly.set(klucz, node);
      kolejnosc.push(klucz);
    }
  }

  idz(ast);

  const kolejnoscPrzejscia = new Map(kolejnosc.map((klucz, indeks) => [klucz, indeks]));
  kolejnosc.sort((a, b) => {
    const roznica = liczbaLisci(wezly.get(a)) - liczbaLisci(wezly.get(b));
    return roznica !== 0 ? roznica : kolejnoscPrzejscia.get(a) - kolejnoscPrzejscia.get(b);
  });
  return { kolejnosc, wezly };
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

/** Grot strzałki dokładany na końcu każdego przewodu (`marker-end`). */
function grotStrzalki() {
  const defs = nowyElement("defs");
  const marker = nowyElement("marker");
  marker.setAttribute("id", ID_GROTU);
  marker.setAttribute("viewBox", "0 0 10 10");
  marker.setAttribute("refX", "9");
  marker.setAttribute("refY", "5");
  marker.setAttribute("markerWidth", "6");
  marker.setAttribute("markerHeight", "6");
  marker.setAttribute("markerUnits", "strokeWidth");
  marker.setAttribute("orient", "auto");
  marker.setAttribute("aria-hidden", "true");
  const grot = nowyElement("path");
  grot.setAttribute("class", "wiz-grot");
  grot.setAttribute("d", "M 0 0 L 10 5 L 0 10 Z");
  marker.append(grot);
  defs.append(marker);
  return defs;
}

/** Przewód jako łamana linia: wyjście węzła, potem wejście następnego. */
function przewod(od, do_) {
  const linia = nowyElement("polyline", TEKSTY.przewod);
  linia.setAttribute("class", "wiz-przewod wiz-nieznane");
  linia.setAttribute("role", "img");
  linia.setAttribute("aria-label", TEKSTY.przewod);
  const srodek = (od.x + do_.x) / 2;
  linia.setAttribute(
    "points",
    `${od.x},${od.y} ${srodek},${od.y} ${srodek},${do_.y} ${do_.x},${do_.y}`,
  );
  // Groty pokazują kierunek przepływu sygnału — czytelnik widzi, co jest wejściem,
  // a co wyjściem, także po samym kształcie linii.
  linia.setAttribute("marker-end", `url(#${ID_GROTU})`);
  return linia;
}

/** Opis wartości przy przewodzie. Startuje jako znak zapytania — wartość nieznana. */
function etykietaPrzewodu(od) {
  const napis = nowyElement("text", TEKSTY.wartoscNieznana);
  napis.setAttribute("class", "wiz-wartosc");
  napis.setAttribute("x", String(od.x + 4));
  napis.setAttribute("y", String(od.y - 5));
  napis.setAttribute("text-anchor", "start");
  napis.textContent = TEKSTY.znakNieznany;
  return napis;
}

/** Buduje rysunek: przewody, bramki i przewód wyjściowy.
 *
 *  Zwraca `<svg>` oraz model węzłów — po każdym kroku wpisujemy w model wartości
 *  przewodów, zamiast przerysowywać cały schemat. */
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
  rysunek.append(grotStrzalki(), przewody, bramki);

  const elementy = [];

  /** Zapisuje węzeł w modelu, żeby dało się wpisać wartość na jego przewody. */
  function zapisz(node, grupa, nazwa) {
    const element = { klucz: kluczWezla(node), typ: node.typ, nazwa, grupa, przewody: [] };
    elementy.push(element);
    return element;
  }

  /** Dokłada przewód z wyjścia węzła na wejście następnego i wiąże go z modelem. */
  function polacz(od, do_, element) {
    const linia = przewod(od, do_);
    const etykieta = etykietaPrzewodu(od);
    przewody.append(linia, etykieta);
    element.przewody.push({ linia, etykieta });
  }

  function idz(node) {
    const srodek = punkt(uklad, node);
    if (node.typ === "Var") {
      const grupa = wezelZmiennej(node.nazwa, srodek);
      bramki.append(grupa);
      const element = zapisz(node, grupa, node.nazwa);
      return { x: srodek.x + SZEROKOSC_ZMIENNEJ / 2, y: srodek.y, element };
    }

    const dzieci = node.typ === "Not" ? [node.dziecko] : [node.lewy, node.prawy];
    const wyjscia = dzieci.map(idz);
    const grupa = ksztalt(node.typ, srodek);
    bramki.append(grupa);
    const element = zapisz(node, grupa, "");
    wyjscia.forEach((wyjscie, indeks) => {
      const wejscie = {
        x: srodek.x - POLOWA_BRAMY,
        y: dzieci.length === 1 ? srodek.y : srodek.y + (indeks === 0 ? -ODSTEP_WEJSC : ODSTEP_WEJSC),
      };
      polacz(wyjscie, wejscie, wyjscie.element);
    });
    return { x: srodek.x + (node.typ === "Not" ? 16 : POLOWA_BRAMY), y: srodek.y, element };
  }

  const wyjscie = idz(ast);
  const koniec = uklad.szerokosc - 62;
  polacz(wyjscie, { x: koniec, y: wyjscie.y }, wyjscie.element);

  const napis = nowyElement("text", TEKSTY.wyjscie);
  napis.setAttribute("class", "wiz-wynik");
  napis.setAttribute("x", String(koniec + 6));
  napis.setAttribute("y", String(wyjscie.y));
  napis.setAttribute("dominant-baseline", "central");
  napis.textContent = "wynik";
  rysunek.append(napis);
  return { svg: rysunek, elementy };
}

/** Wpisuje wartość na przewody węzła: `1`/`0` ze słowem albo `null` dla nieznanej.
 *
 *  Wartość `1` pogrubia przewód, `0` go pocienia, a nieznana jest kreskowana. Słowo
 *  PRAWDA/FAŁSZ stoi przy przewodzie, więc kolor tylko wspiera tekst. */
function ustawPrzewody(przewody, wartosc) {
  const znana = wartosc === 1 || wartosc === 0;
  for (const { linia, etykieta } of przewody) {
    linia.classList.remove("wiz-prawda", "wiz-falsz", "wiz-nieznane");
    etykieta.classList.remove("wiz-wartosc-prawda", "wiz-wartosc-falsz");

    if (!znana) {
      linia.classList.add("wiz-nieznane");
      etykieta.textContent = TEKSTY.znakNieznany;
      ustawTytul(linia, `${TEKSTY.przewod} ${TEKSTY.wartoscNieznana}`);
      ustawTytul(etykieta, TEKSTY.wartoscNieznana);
      continue;
    }

    const prawda = wartosc === 1;
    const opis = `${wartosc} ${prawda ? TEKSTY.prawda : TEKSTY.falsz}`;
    linia.classList.add(prawda ? "wiz-prawda" : "wiz-falsz");
    etykieta.classList.add(prawda ? "wiz-wartosc-prawda" : "wiz-wartosc-falsz");
    etykieta.textContent = opis;
    ustawTytul(linia, `${TEKSTY.przewod} Wartość na tym przewodzie: ${opis}.`);
    ustawTytul(etykieta, `Wartość na tym przewodzie: ${opis}.`);
  }
}

/** Wartość `1`/`0` jako słowo — kolor nigdy nie jest jedynym nośnikiem informacji. */
function slowoWartosci(wartosc) {
  return wartosc === 1 ? TEKSTY.prawda : TEKSTY.falsz;
}

/** Zdanie opisujące bramkę w kroku, np. „Bramka AND: 1 i 0 daje 0”. */
function opisBramki(node, wartosci) {
  const wynik = wartosci.get(kluczWezla(node));
  if (node.typ === "Not") {
    return `Bramka NOT: z ${wartosci.get(kluczWezla(node.dziecko))} daje ${wynik}`;
  }
  const lewy = wartosci.get(kluczWezla(node.lewy));
  const prawy = wartosci.get(kluczWezla(node.prawy));
  return `Bramka ${node.typ}: ${lewy} i ${prawy} daje ${wynik}`;
}

/** Kroki od liści do korzenia — po jednym na każdą bramkę.
 *
 *  Kolejność jest odwrotna do notacji polskiej: najpierw najmniejsze podformuły, na końcu
 *  cała formuła. Ostatni krok mówi wprost, jaką wartość ma cała formuła. Formuła bez
 *  bramek (sama zmienna) dostaje jeden krok z wynikiem. */
function zbudujKroki(ast, wartosci, kolejnosc, wezly) {
  const korzen = kluczWezla(ast);
  const kroki = kolejnosc
    .map((klucz) => wezly.get(klucz))
    .filter((node) => node && node.typ !== "Var")
    .map((node) => {
      const klucz = kluczWezla(node);
      let opis = opisBramki(node, wartosci);
      if (klucz === korzen) {
        opis += ` ${TEKSTY.wynikCalkowity} ${slowoWartosci(wartosci.get(klucz))}.`;
      }
      return { tytul: `Bramka ${node.typ}`, opis, klucz };
    });

  if (kroki.length === 0) {
    kroki.push({
      tytul: "Wynik",
      opis: `${TEKSTY.wynikCalkowity} ${slowoWartosci(wartosci.get(korzen))}.`,
      klucz: korzen,
    });
  }
  return kroki;
}

/** Przełączniki `0`/`1` nad rysunkiem — po jednej parze na każde wejście układu. */
function zbudujWejscia(zmienne, zmienWartosc) {
  const sekcja = elementHtml("div", "wiz-wejscia");
  if (zmienne.length === 0) {
    sekcja.classList.add("d-none");
    return { element: sekcja, ustaw: () => {} };
  }
  sekcja.setAttribute("role", "group");
  sekcja.setAttribute("aria-label", TEKSTY.wejscia);

  const przelaczniki = new Map();

  for (const nazwa of zmienne) {
    const grupa = elementHtml("span", "wiz-wejscie");
    grupa.setAttribute("role", "group");
    grupa.setAttribute("aria-label", `${TEKSTY.wejscie} „${nazwa}”`);
    grupa.append(elementHtml("span", "wiz-wejscie-nazwa", nazwa));

    const przyciski = new Map();
    for (const wartosc of [1, 0]) {
      const przycisk = elementHtml("button", "btn btn-sm wiz-przelacznik", String(wartosc));
      przycisk.type = "button";
      przycisk.setAttribute("aria-pressed", "false");
      przycisk.addEventListener("click", () => zmienWartosc(nazwa, wartosc));
      przyciski.set(wartosc, przycisk);
      grupa.append(przycisk);
    }

    przelaczniki.set(nazwa, przyciski);
    sekcja.append(grupa);
  }

  /** Odświeża stan przycisków — wciśnięta jest tylko wartość bieżąca. */
  function ustaw(env) {
    for (const [nazwa, przyciski] of przelaczniki) {
      for (const [wartosc, przycisk] of przyciski) {
        przycisk.setAttribute("aria-pressed", env[nazwa] === wartosc ? "true" : "false");
      }
    }
  }

  return { element: sekcja, ustaw };
}

/** Wiersz tablicy dla wybranego wartościowania (wartości wejść jako `1`/`0`). */
function znajdzWiersz(wiersze, zmienne, env) {
  return wiersze.find((wiersz) => zmienne.every((nazwa) => wiersz[nazwa] === env[nazwa]));
}

/** Wartości wszystkich podformuł z wiersza tablicy — kolumna po kolumnie. */
function wartosciZWiersza(kolejnosc, wiersz) {
  const wartosci = new Map();
  kolejnosc.forEach((klucz, indeks) => {
    wartosci.set(klucz, wiersz[POLE_WARTOSCI][indeks]);
  });
  return wartosci;
}

/** Rysuje wartości po kroku: odkryte bramki mają wynik, reszta czeka ze znakiem `?`. */
function pokazKrok(elementy, kroki, indeks, wartosci, status) {
  const odsloniete = new Set();
  for (let pozycja = 0; pozycja <= indeks && pozycja < kroki.length; pozycja += 1) {
    odsloniete.add(kroki[pozycja].klucz);
  }
  const biezacy = kroki[indeks] ? kroki[indeks].klucz : null;

  for (const element of elementy) {
    const znana = element.typ === "Var" || odsloniete.has(element.klucz);
    ustawPrzewody(element.przewody, znana ? wartosci.get(element.klucz) : null);

    if (element.typ === "Var") {
      continue;
    }
    element.grupa.classList.toggle("wiz-znana", odsloniete.has(element.klucz));
    if (element.klucz === biezacy) {
      element.grupa.classList.add("wiz-biezaca");
      element.grupa.setAttribute("aria-current", "true");
    } else {
      element.grupa.classList.remove("wiz-biezaca");
      element.grupa.removeAttribute("aria-current");
    }
  }

  const krok = kroki[indeks];
  if (krok) {
    status.textContent = `${krok.opis} Krok ${indeks + 1} z ${kroki.length}.`;
  }
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
    dokumentem — czytnik ekranu nie ogłosiłby wyniku. Sam komunikat ma `role="alert"`,
    więc czytnik ogłasza go od razu, bez szukania po stronie. */
function pokazKomunikat(montaz, tekst, status) {
  const komunikat = elementHtml("p", "wiz-blad alert alert-warning mb-0", tekst);
  komunikat.setAttribute("role", "alert");
  montaz.replaceChildren(komunikat, status);
  status.textContent = tekst;
}

/** Wysyła żądanie do API wspólnym klientem (karta PRZ-174).

    Wynik ma pola `ok` oraz `dane` albo `blad` — tak samo dla każdego komponentu. */
function pobierz(adres, tresc) {
  return pobierzJson(adres, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(tresc),
  });
}

/** Wypełnia jeden montaż: drzewo formuły, wartości podformuł, kroki i przełączniki. */
async function wypelnij(montaz) {
  const formula = montaz.dataset.formula || "";
  montaz.replaceChildren();

  const status = elementHtml("p", "wiz-status visually-hidden");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  montaz.append(elementHtml("p", "wiz-ladowanie text-muted small mb-1", TEKSTY.ladowanie), status);

  const wyniki = await Promise.all([
    pobierz(ADRES, { formula }),
    pobierz(ADRES_TABLICY, { formula, podformuly: true }),
  ]);
  const zly = wyniki.find((wynik) => !wynik.ok);
  if (zly) {
    pokazKomunikat(montaz, zly.blad || TEKSTY.siec, status);
    return;
  }
  const [dane, tabela] = wyniki.map((wynik) => wynik.dane);

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

  const zmienne = Array.isArray(dane.zmienne) ? dane.zmienne : [];
  const wiersze = tabela && tabela.ok && Array.isArray(tabela.znaki) ? tabela.znaki : [];
  const kolumny =
    tabela && tabela.ok && tabela.tabela && Array.isArray(tabela.tabela.columns)
      ? tabela.tabela.columns
      : [];
  const { kolejnosc, wezly } = zbierzPodformuly(dane.ast);

  // Kolumny tablicy i nasza kolejność podformuł muszą się zgadzać co do jednej.
  // Gdyby serwer zmienił kolejność albo nie przysłał wierszy, pokazujemy komunikat
  // zamiast zgadywać wartości. Formuła bez zmiennych nie potrzebuje zmiennych w tabeli,
  // ale nadal wymaga policzonych wartości podformuł z serwera.
  if (wiersze.length === 0 || kolumny.length !== kolejnosc.length) {
    pokazKomunikat(montaz, TEKSTY.brakTabeli, status);
    return;
  }

  const env = {};
  for (const nazwa of zmienne) {
    env[nazwa] = 1;
  }

  const rysunek = zbudujRysunek(dane.ast, uklad);

  const wejscia = zbudujWejscia(zmienne, zmienWartosc);

  const figura = elementHtml("div", "wiz-figura");
  figura.append(rysunek.svg);

  // Kontener paska kroków. Pasek powstaje w `createStepper`; przy zmianie wejść
  // podmieniamy tylko jego zawartość, żeby nie zgubić fokusu na przełącznikach.
  const montazKrokow = elementHtml("div", "wiz-kroki");
  montazKrokow.setAttribute("data-stepper", "");

  const sekcja = elementHtml("div", "wiz-rysunek d-flex flex-column gap-3");
  if (zmienne.length > 0) {
    sekcja.append(wejscia.element);
  }
  sekcja.append(figura, montazKrokow, zbudujLegende(zbierzTypy(dane.ast)));
  montaz.replaceChildren(sekcja, status);

  let stepper = null;

  /** Przelicza kroki dla bieżących wartości wejść i pokazuje pierwszy z nich.
   *
   *  Rysunek zostaje ten sam — zmieniają się tylko wartości na przewodach, więc po
   *  zmianie wejścia cała reszta wraca do stanu „nieznana”. */
  function odswiez() {
    if (stepper) {
      stepper.destroy();
      stepper = null;
    }

    const wiersz = znajdzWiersz(wiersze, zmienne, env);
    if (!wiersz || !Array.isArray(wiersz[POLE_WARTOSCI])) {
      pokazKomunikat(montaz, TEKSTY.brakTabeli, status);
      return;
    }

    const wartosci = wartosciZWiersza(kolejnosc, wiersz);
    const kroki = zbudujKroki(dane.ast, wartosci, kolejnosc, wezly);
    wejscia.ustaw(env);

    stepper = createStepper({
      mount: montazKrokow,
      steps: kroki,
      labels: {
        prev: "Wstecz",
        next: "Dalej",
        play: "Odtwórz",
        pause: "Pauza",
        reset: "Od nowa",
      },
      onStep: (indeks) => pokazKrok(rysunek.elementy, kroki, indeks, wartosci, status),
    });
  }

  /** Zmiana wartości wejścia: przelicza kroki i wraca do początku prowadzenia. */
  function zmienWartosc(nazwa, wartosc) {
    env[nazwa] = wartosc;
    odswiez();
  }

  odswiez();
}

document.querySelectorAll(".gates-mount").forEach((montaz) => {
  wypelnij(montaz);
});
