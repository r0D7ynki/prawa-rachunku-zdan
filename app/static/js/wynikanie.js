/* Test wynikania: założenia i teza → `POST /api/wynikanie`.
   Logika siedzi na serwerze — ten skrypt wysyła dane i pokazuje odpowiedź.
   Każdy tekst z API wstawiamy przez `textContent`, nigdy przez `innerHTML`,
   dzięki temu żadna treść nie trafia do DOM jako kod.

   Ten sam formularz działa bez JavaScriptu: wtedy wysyła się zwykłym POST-em
   na `/konsekwencja`, a wynik rysuje szablon `partials/_wynikanie.html`. */

import { pobierzJson } from "/static/js/api.js";

const ADRES = "/api/wynikanie";

const TEKSTY = {
  ladowanie: "Sprawdzam wynikanie…",
  siec: "Nie udało się połączyć z serwerem. Sprawdź połączenie i spróbuj ponownie.",
  bladOgolny: "Nie udało się sprawdzić wynikania.",
  wynika: "Teza wynika z założeń.",
  opisWynika: "Nie ma wartościowania, w którym założenia są prawdziwe, a teza fałszywa.",
  nieWynika: "Teza nie wynika z założeń.",
  kontrprzyklad: "Kontrprzyklad — założenia prawdziwe, teza fałszywa (1 to prawda, 0 to fałsz):",
  placZabaw: "Sprawdź tezę w placu zabaw",
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

/** Wysyła JSON na endpoint wspólnym klientem (karta PRZ-174).

    Wynik ma pola `ok` oraz `dane` albo `blad` — obsługę błędów sprawdza wywołujący. */
function pobierz(adres, dane) {
  return pobierzJson(adres, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dane),
  });
}

/** Bierze założenia z pola tekstowego: jedna formuła w wierszu, puste wiersze precz. */
function zalozeniaZPola(tekst) {
  return tekst
    .split("\n")
    .map((wiersz) => wiersz.trim())
    .filter((wiersz) => wiersz !== "");
}

/** Zdanie z kontrprzykładu: „p = 1, q = 0” — słownie, bez kolorów. */
function opisKontrprzykladu(kontrprzyklad) {
  return Object.keys(kontrprzyklad)
    .sort()
    .map((nazwa) => `${nazwa} = ${kontrprzyklad[nazwa]}`)
    .join(", ");
}

const formularz = document.getElementById("formularz-wynikania");
const poleZalozen = document.getElementById("pole-zalozenia");
const poleTezy = document.getElementById("pole-teza");
const komunikatBledu = document.getElementById("komunikat-bledu");
const wynik = document.getElementById("wynik-wynikanie");

if (formularz && poleZalozen && poleTezy) {
  formularz.addEventListener("submit", (zdarzenie) => {
    zdarzenie.preventDefault();
    sprawdz();
  });
}

/** Pokazuje wynik: „wynika” albo „nie wynika” z kontrprzykładem i odnośnikiem. */
function pokazWynik(dane) {
  komunikatBledu.hidden = true;

  if (dane.wynika) {
    wynik.replaceChildren(
      element("p", "alert alert-success mb-2", TEKSTY.wynika),
      element("p", "text-muted small mb-0", TEKSTY.opisWynika),
    );
    return;
  }

  const odnosnik = element("a", "btn btn-outline-primary btn-sm", TEKSTY.placZabaw);
  odnosnik.href = "/plac-zabaw";
  const akapit = element("p", "mb-0");
  akapit.append(odnosnik);
  wynik.replaceChildren(
    element("p", "alert alert-warning mb-2", TEKSTY.nieWynika),
    element("p", "text-muted small mb-1", TEKSTY.kontrprzyklad),
    element("p", "kontrprzyklad mb-2", opisKontrprzykladu(dane.kontrprzyklad || {})),
    akapit,
  );
}

/** Pokazuje komunikat błędu po polsku i czyści wynik.
 *  `role="alert"` sprawia, że czytnik ekranu ogłasza komunikat od razu. */
function pokazBlad(tekst) {
  wynik.replaceChildren();
  komunikatBledu.className = "wynikanie-blad alert alert-warning mt-3 mb-0";
  komunikatBledu.setAttribute("role", "alert");
  komunikatBledu.textContent = tekst;
  komunikatBledu.hidden = false;
}

/** Sprawdza wynikanie i pokazuje wynik bez przeładowania strony. */
async function sprawdz() {
  const zalozenia = zalozeniaZPola(poleZalozen.value);
  const teza = poleTezy.value;
  wynik.replaceChildren(element("p", "text-muted small mb-0", TEKSTY.ladowanie));

  const wynik = await pobierz(ADRES, { zalozenia, teza });
  if (!wynik.ok) {
    pokazBlad(wynik.blad || TEKSTY.siec);
    return;
  }
  const dane = wynik.dane;

  if (!dane.ok) {
    pokazBlad(dane.blad || TEKSTY.bladOgolny);
    return;
  }

  pokazWynik(dane);
}
