/* Quiz: pytanie jedno na ekran, odpowiedź sprawdza serwer (karta PRZ-015).
   Serwer nie wysyła poprawnej odpowiedzi — skrypt trzyma tylko identyfikator pytania
   i ziarno zestawu. Każdy tekst z API wstawiamy przez `textContent`, nigdy przez
   `innerHTML`, dzięki temu żadna treść nie trafia do DOM jako kod HTML.

   Obsługa klawiatury: klawisze 1–4 wybierają odpowiedź, Enter przechodzi dalej.
   Cyfry działają tylko wtedy, gdy pytanie nie jest jeszcze rozstrzygnięte.
*/

const ADRESY = {
  generate: "/api/quiz/generate",
  check: "/api/quiz/check",
};

const TEKSTY = {
  ladowanie: "Losuję pytania…",
  siec: "Nie udało się połączyć z serwerem. Sprawdź połączenie i spróbuj ponownie.",
  bladOgolny: "Nie udało się przygotować quizu.",
  brakPytan: "Dla tego zakresu nie ma pytań. Wybierz inny zakres.",
  dobrze: "Dobrze!",
  zle: "Źle.",
  poprawka: "Poprawna odpowiedź i wyjaśnienie:",
  podpowiedz: "Podpowiedź",
  ukryjPodpowiedz: "Ukryj podpowiedź",
  dalej: "Dalej",
  zakoncz: "Zobacz wynik",
  jeszczeRaz: "Jeszcze raz",
  wszystkiePoprawne: "Wszystkie odpowiedzi poprawne. Tak trzymaj!",
};

/** Cyfry wybierające odpowiedzi — numer odpowiedzi to cyfra minus jeden. */
const KLUCZE_ODPOWIEDZI = ["1", "2", "3", "4"];

const formularzStart = document.getElementById("formularz-quizu");
const poleZakres = document.getElementById("pole-zakres");
const poleIle = document.getElementById("pole-ile");
const komunikat = document.getElementById("komunikat-quizu");
const kontener = document.getElementById("kontener-pytan");

/** Nazwy praw z listy zakresu: slug → nazwa. Do odnośników w podsumowaniu. */
const NAZWY_PRAW = new Map();
if (poleZakres) {
  for (const opcja of poleZakres.options) {
    if (opcja.value) {
      NAZWY_PRAW.set(opcja.value, opcja.textContent.trim());
    }
  }
}

const stan = {
  prawo: null,
  ile: 5,
  seed: null,
  pytania: [],
  indeks: 0,
  poprawne: 0,
  bledy: [],
  odpowiedziano: false,
  trwa: false,
  zakonczony: false,
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

/** Wysyła JSON na endpoint i zwraca odpowiedź. Sieć sprawdza wywołujący. */
async function pobierz(adres, dane) {
  const odpowiedz = await fetch(adres, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dane),
  });
  return odpowiedz.json();
}

/** Pokazuje komunikat błędu po polsku; pusty tekst ukrywa pasek komunikatu. */
function pokazKomunikat(tekst) {
  if (!komunikat) {
    return;
  }
  komunikat.textContent = tekst || "";
  komunikat.hidden = !tekst;
}

/** Ustawia zakres z adresu, gdy parametr `?prawo=` wskazuje prawo z listy. */
function zakresZAdresu() {
  if (!poleZakres) {
    return null;
  }
  const slug = new URLSearchParams(window.location.search).get("prawo");
  if (!slug) {
    return null;
  }
  const znane = Array.from(poleZakres.options).some((opcja) => opcja.value === slug);
  if (!znane) {
    return null;
  }
  poleZakres.value = slug;
  return slug;
}

/** Losuje zestaw pytań i zaczyna od pierwszego. */
async function start() {
  stan.prawo = poleZakres && poleZakres.value ? poleZakres.value : null;
  stan.ile = poleIle ? Number(poleIle.value) : 5;
  pokazKomunikat("");
  kontener.replaceChildren(element("p", "text-muted mb-0", TEKSTY.ladowanie));

  let dane;
  try {
    dane = await pobierz(ADRESY.generate, { prawo: stan.prawo, ile: stan.ile });
  } catch (blad) {
    pokazKomunikat(TEKSTY.siec);
    kontener.replaceChildren(element("p", "text-muted mb-0", TEKSTY.siec));
    return;
  }

  if (!dane.ok) {
    const tresc = dane.blad || TEKSTY.bladOgolny;
    pokazKomunikat(tresc);
    kontener.replaceChildren(element("p", "text-muted mb-0", tresc));
    return;
  }

  if (!Array.isArray(dane.pytania) || dane.pytania.length === 0) {
    pokazKomunikat(TEKSTY.brakPytan);
    kontener.replaceChildren(element("p", "text-muted mb-0", TEKSTY.brakPytan));
    return;
  }

  /* Serwer mówi tu, gdy zakres ma mniej pytań, niż wybrano. Pokazujemy to od razu,
     żeby mniejszy zestaw nie wyglądał jak zgubione pytania. */
  if (typeof dane.komunikat === "string" && dane.komunikat) {
    pokazKomunikat(dane.komunikat);
  }

  stan.seed = dane.seed;
  stan.pytania = dane.pytania;
  stan.indeks = 0;
  stan.poprawne = 0;
  stan.bledy = [];
  stan.zakonczony = false;
  pokazPytanie();
}

/** Pasek postępu: „Pytanie 3 z 5” razem z paskiem Bootstrapa. */
function pasekPostepu() {
  const razem = stan.pytania.length;
  const numer = stan.indeks + 1;
  const opakowanie = element("div", "postep-blok mb-3");

  const pasek = element("div", "progress");
  pasek.setAttribute("role", "progressbar");
  pasek.setAttribute("aria-valuenow", String(numer));
  pasek.setAttribute("aria-valuemin", "1");
  pasek.setAttribute("aria-valuemax", String(razem));
  pasek.setAttribute("aria-label", `Pytanie ${numer} z ${razem}`);

  const wnetrze = element("div", "progress-bar");
  wnetrze.style.width = `${Math.round((numer / razem) * 100)}%`;
  pasek.append(wnetrze);

  opakowanie.append(
    element("p", "postep-tekst fw-bold mb-1", `Pytanie ${numer} z ${razem}`),
    pasek,
  );
  return opakowanie;
}

/** Lista odpowiedzi — każda to prawdziwy przycisk z numerem i etykietą. */
function listaOdpowiedzi(pytanie) {
  const lista = element("ul", "lista-odpowiedzi list-unstyled d-grid gap-2 mt-3");
  pytanie.opcje.forEach((tekst, indeks) => {
    const pozycja = element("li");
    const przycisk = element(
      "button",
      "btn btn-outline-primary btn-odpowiedz text-start",
      `${indeks + 1}. ${tekst}`,
    );
    przycisk.type = "button";
    przycisk.dataset.indeks = String(indeks);
    przycisk.setAttribute("aria-label", `Odpowiedź ${indeks + 1}: ${tekst}`);
    przycisk.addEventListener("click", () => wybierz(indeks));
    pozycja.append(przycisk);
    lista.append(pozycja);
  });
  return lista;
}

/** Przycisk podpowiedzi z tekstem podpowiedzi ukrytym do pierwszego kliknięcia. */
function blokPodpowiedzi(pytanie) {
  const blok = element("div", "podpowiedz-blok mt-2");
  const tekst = element("p", "podpowiedz alert alert-secondary mt-2 mb-0", pytanie.podpowiedz);
  tekst.hidden = true;

  const przycisk = element("button", "btn btn-sm btn-outline-secondary", TEKSTY.podpowiedz);
  przycisk.type = "button";
  przycisk.id = "przycisk-podpowiedzi";
  przycisk.setAttribute("aria-expanded", "false");
  przycisk.setAttribute("aria-controls", "tekst-podpowiedzi");
  tekst.id = "tekst-podpowiedzi";
  przycisk.addEventListener("click", () => {
    const pokazac = tekst.hidden;
    tekst.hidden = !pokazac;
    przycisk.textContent = pokazac ? TEKSTY.ukryjPodpowiedz : TEKSTY.podpowiedz;
    przycisk.setAttribute("aria-expanded", String(pokazac));
  });

  blok.append(przycisk, tekst);
  return blok;
}

/** Rysuje bieżące pytanie: postęp, treść, odpowiedzi, podpowiedź i miejsce na wynik. */
function pokazPytanie() {
  stan.odpowiedziano = false;
  const pytanie = stan.pytania[stan.indeks];

  /* Mianownik to liczba pytań już rozstrzygniętych. Przed pierwszą odpowiedzią nie ma
     czego porównywać, więc pokazujemy sam licznik — inaczej stałoby tam mylące „0 z 0”. */
  const licznik = element(
    "p",
    "licznik-poprawnych text-muted mb-3",
    stan.indeks === 0
      ? `Poprawne odpowiedzi: ${stan.poprawne}.`
      : `Poprawne odpowiedzi: ${stan.poprawne} z ${stan.indeks}.`,
  );
  const tresc = element("h3", "h4 pytanie-tresc", pytanie.pytanie);

  const wynik = element("div", "wynik-odpowiedzi mt-3");
  wynik.id = "wynik-odpowiedzi";
  wynik.setAttribute("role", "status");
  wynik.setAttribute("aria-live", "polite");

  const nawigacja = element("div", "nawigacja-pytania mt-3");
  nawigacja.id = "nawigacja-pytania";

  kontener.replaceChildren(
    pasekPostepu(),
    licznik,
    tresc,
    listaOdpowiedzi(pytanie),
    blokPodpowiedzi(pytanie),
    wynik,
    nawigacja,
  );
}

/** Blokuje przyciski odpowiedzi po rozstrzygnięciu pytania. */
function zablokujOdpowiedzi() {
  for (const przycisk of kontener.querySelectorAll(".btn-odpowiedz")) {
    przycisk.disabled = true;
  }
}

/** Podświetla wybraną odpowiedź; kolor to dodatek, wynik opisuje tekst obok. */
function oznaczWybor(wybrany, poprawna) {
  const przyciski = kontener.querySelectorAll(".btn-odpowiedz");
  const przycisk = przyciski[wybrany];
  if (!przycisk) {
    return;
  }
  przycisk.classList.remove("btn-outline-primary");
  przycisk.classList.add(poprawna ? "btn-success" : "btn-danger");
}

/** Pokazuje „Dobrze!” albo „Źle.” razem z wyjaśnieniem z serwera. */
function pokazWynik(wybrany, poprawna, wyjasnienie) {
  const wynik = document.getElementById("wynik-odpowiedzi");
  if (!wynik) {
    return;
  }
  const naglowek = element(
    "p",
    poprawna ? "alert alert-success mb-2" : "alert alert-danger mb-2",
    poprawna
      ? `${TEKSTY.dobrze} Twoja odpowiedź: ${wybrany + 1}.`
      : `${TEKSTY.zle} Twoja odpowiedź: ${wybrany + 1}.`,
  );
  wynik.replaceChildren(
    naglowek,
    element("p", "etykieta-poprawki text-muted small mb-1", TEKSTY.poprawka),
    element("p", "wyjasnienie mb-0", wyjasnienie || ""),
  );
}

/** Przycisk przejścia dalej — ostatnie pytanie prowadzi do wyniku. */
function pokazPrzyciskDalej() {
  const nawigacja = document.getElementById("nawigacja-pytania");
  if (!nawigacja) {
    return;
  }
  const ostatnie = stan.indeks + 1 >= stan.pytania.length;
  const przycisk = element("button", "btn btn-primary", ostatnie ? TEKSTY.zakoncz : TEKSTY.dalej);
  przycisk.type = "button";
  przycisk.id = "przycisk-dalej";
  przycisk.addEventListener("click", nastepne);
  nawigacja.replaceChildren(przycisk);
  przycisk.focus();
}

/** Sprawdza odpowiedź na serwerze i pokazuje wynik. */
async function wybierz(wybrany) {
  if (!stan.pytania.length || stan.odpowiedziano || stan.trwa || stan.zakonczony) {
    return;
  }
  const pytanie = stan.pytania[stan.indeks];
  if (!(wybrany >= 0 && wybrany < pytanie.opcje.length)) {
    return;
  }
  stan.trwa = true;

  let dane;
  try {
    dane = await pobierz(ADRESY.check, {
      prawo: stan.prawo,
      seed: stan.seed,
      id: pytanie.id,
      odpowiedz: wybrany,
    });
  } catch (blad) {
    stan.trwa = false;
    pokazKomunikat(TEKSTY.siec);
    return;
  }
  stan.trwa = false;

  if (!dane.ok) {
    pokazKomunikat(dane.blad || TEKSTY.bladOgolny);
    return;
  }

  stan.odpowiedziano = true;
  pokazKomunikat("");
  const poprawna = dane.poprawna === true;
  if (poprawna) {
    stan.poprawne += 1;
  } else {
    stan.bledy.push({ tresc: pytanie.pytanie, prawo: pytanie.prawo });
  }

  oznaczWybor(wybrany, poprawna);
  pokazWynik(wybrany, poprawna, dane.wyjasnienie);
  zablokujOdpowiedzi();
  pokazPrzyciskDalej();
}

/** Przechodzi do następnego pytania albo kończy quiz. */
function nastepne() {
  if (!stan.odpowiedziano || stan.zakonczony) {
    return;
  }
  if (stan.indeks + 1 < stan.pytania.length) {
    stan.indeks += 1;
    pokazPytanie();
    return;
  }
  pokazPodsumowanie();
}

/** Zdanie oceniające wynik — bez oceniania osoby, tylko opis wyniku. */
function opisWyniku(razem) {
  const udzial = razem ? stan.poprawne / razem : 0;
  if (udzial === 1) {
    return "Bezbłędnie. Możesz przejść do trudniejszych praw.";
  }
  if (udzial >= 0.7) {
    return "Dobry wynik. Zajrzyj do praw z listy poniżej.";
  }
  return "Warto powtórzyć prawa z listy poniżej i spróbować jeszcze raz.";
}

/** Podsumowanie: wynik, lista błędów z odnośnikami do praw i przycisk „Jeszcze raz”. */
function pokazPodsumowanie() {
  stan.zakonczony = true;
  const razem = stan.pytania.length;
  const sekcja = element("div", "podsumowanie");

  sekcja.append(
    element("h3", "h4", "Wynik quizu"),
    element("p", "wynik-liczbowy fw-bold", `Poprawne odpowiedzi: ${stan.poprawne} z ${razem}.`),
    element("p", "ocena-wyniku mb-3", opisWyniku(razem)),
  );

  if (stan.bledy.length) {
    sekcja.append(element("h4", "h5", `Do powtórki: ${stan.bledy.length}`));
    const lista = element("ul", "lista-bledow list-unstyled d-grid gap-2");
    for (const blad of stan.bledy) {
      const pozycja = element("li", "blad-pytania border rounded p-2");
      const link = element(
        "a",
        "btn btn-sm btn-outline-primary mt-2",
        `Powtórz prawo: ${NAZWY_PRAW.get(blad.prawo) || blad.prawo}`,
      );
      link.href = `/prawa/${blad.prawo}`;
      pozycja.append(element("p", "blad-tresc mb-0", blad.tresc), link);
      lista.append(pozycja);
    }
    sekcja.append(lista);
  } else {
    sekcja.append(element("p", "alert alert-success", TEKSTY.wszystkiePoprawne));
  }

  const jeszczeRaz = element("button", "btn btn-primary mt-3", TEKSTY.jeszczeRaz);
  jeszczeRaz.type = "button";
  jeszczeRaz.id = "przycisk-jeszcze-raz";
  jeszczeRaz.addEventListener("click", start);
  sekcja.append(jeszczeRaz);

  kontener.replaceChildren(sekcja);
}

/** Klawiatura: cyfry wybierają odpowiedź, Enter przechodzi dalej. */
function obsluzKlawiature(zdarzenie) {
  const cel = zdarzenie.target;
  const znacznik = cel && cel.tagName ? cel.tagName : "";
  if (znacznik === "INPUT" || znacznik === "SELECT" || znacznik === "TEXTAREA") {
    return;
  }
  if (zdarzenie.ctrlKey || zdarzenie.altKey || zdarzenie.metaKey) {
    return;
  }

  if (KLUCZE_ODPOWIEDZI.includes(zdarzenie.key)) {
    const numer = Number(zdarzenie.key) - 1;
    const pytanie = stan.pytania[stan.indeks];
    if (!stan.odpowiedziano && pytanie && numer < pytanie.opcje.length) {
      zdarzenie.preventDefault();
      wybierz(numer);
    }
    return;
  }

  if (zdarzenie.key === "Enter" && stan.odpowiedziano) {
    zdarzenie.preventDefault();
    nastepne();
  }
}

if (kontener) {
  if (formularzStart) {
    formularzStart.addEventListener("submit", (zdarzenie) => {
      zdarzenie.preventDefault();
      start();
    });
  }
  document.addEventListener("keydown", obsluzKlawiature);

  /* Zakres z adresu (`?prawo=<slug>`) zaznacza prawo na liście i od razu startuje,
     żeby odnośnik z prawej strony działał jednym kliknięciem. */
  if (zakresZAdresu()) {
    start();
  }
}
