/* Krokowe przekształcenia formuł.
   Dla każdego elementu `.steps-mount` pobiera ślad z `/api/formula/simplify`
   i pokazuje kroki po kolei. Wszystkie teksty z API wstawiamy przez `textContent`,
   nigdy przez `innerHTML` — dzięki temu żadna treść nie trafia do DOM jako kod. */

const ADRES = "/api/formula/simplify";

const TEKSTY = {
  ladowanie: "Wczytuję kroki przekształcenia…",
  siec: "Nie udało się połączyć z serwerem. Sprawdź połączenie i kliknij „Od nowa”.",
  brakKrokow: "Ta formuła nie wymaga przekształcenia — jest już w żądanej postaci.",
  podpowiedz: "Kliknij krok, aby rozwinąć wyjaśnienie.",
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

/** Pasek z czterema przyciskami sterującymi. */
function zbudujSterowanie() {
  const pasek = element("div", "steps-sterowanie d-flex flex-wrap gap-2 mb-3");
  pasek.setAttribute("role", "group");
  pasek.setAttribute("aria-label", "Sterowanie krokami przekształcenia");

  const przyciski = {
    poprzedni: element("button", "btn btn-outline-secondary btn-sm", "Poprzedni krok"),
    nastepny: element("button", "btn btn-primary btn-sm", "Następny krok"),
    wszystkie: element("button", "btn btn-outline-secondary btn-sm", "Pokaż wszystkie"),
    odNowa: element("button", "btn btn-outline-secondary btn-sm", "Od nowa"),
  };
  for (const przycisk of Object.values(przyciski)) {
    przycisk.type = "button";
  }
  pasek.append(przyciski.poprzedni, przyciski.nastepny, przyciski.wszystkie, przyciski.odNowa);
  return { pasek, przyciski };
}

/** Jeden krok na liście: numer, przejście, nazwa prawa i rozwijane wyjaśnienie. */
function zbudujKrok(numer, krok) {
  const pozycja = element("li", "krok list-group-item");

  const naglowek = element("button", "krok-naglowek");
  naglowek.type = "button";
  naglowek.setAttribute("aria-expanded", "false");

  const identyfikator = `krok-tresc-${numer}`;
  naglowek.setAttribute("aria-controls", identyfikator);
  naglowek.append(
    element("span", "krok-numer", `Krok ${numer}`),
    element("span", "krok-przejscie", `${krok.przed}  →  ${krok.po}`),
    element("span", "krok-prawo", krok.nazwa),
  );

  const tresc = element("div", "krok-tresc");
  tresc.id = identyfikator;
  tresc.hidden = true;
  tresc.append(
    element("p", "krok-opis mb-1", krok.opis),
    element("p", "krok-wyjasnienie mb-1", krok.wyjaśnienie),
    element("p", "krok-pozycja small text-muted mb-0", `Miejsce w formule: ${krok.pozycja}`),
  );

  naglowek.addEventListener("click", () => {
    const otwarty = naglowek.getAttribute("aria-expanded") === "true";
    naglowek.setAttribute("aria-expanded", otwarty ? "false" : "true");
    tresc.hidden = otwarty;
  });

  pozycja.append(naglowek, tresc);
  return pozycja;
}

/** Wypełnia pojedynczy montaż: pobiera ślad i rysuje kroki, sterowanie i podsumowanie. */
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
    komunikat.textContent = dane.blad || "Nie udało się przekształcić tej formuły.";
    return;
  }

  rysujSklad(montaz, dane.slad, status);
}

/** Rysuje gotowy ślad: sterowanie, listę kroków i podsumowanie. */
function rysujSklad(montaz, slad, status) {
  const kroki = slad.kroki || [];
  const { pasek, przyciski } = zbudujSterowanie();
  const lista = element("ol", "steps-lista list-group list-group-flush mb-3");
  const podsumowanie = element("p", "steps-podsumowanie alert alert-success mb-0");

  let pokazane = 0;

  function odswiez() {
    lista.replaceChildren();
    kroki.forEach((krok, indeks) => {
      const pozycja = zbudujKrok(indeks + 1, krok);
      if (indeks >= pokazane) {
        pozycja.hidden = true;
        pozycja.classList.add("krok-ukryty");
      } else if (indeks === pokazane - 1) {
        pozycja.classList.add("krok-aktywny");
      } else {
        pozycja.classList.add("krok-widoczny");
      }
      lista.append(pozycja);
    });

    przyciski.poprzedni.disabled = pokazane === 0;
    przyciski.nastepny.disabled = pokazane >= kroki.length;
    przyciski.wszystkie.disabled = pokazane >= kroki.length;
    przyciski.odNowa.disabled = pokazane === 0;

    if (kroki.length === 0) {
      podsumowanie.textContent = `${TEKSTY.brakKrokow} Forma wynikowa: ${slad.forma}. Liczba kroków: 0.`;
      status.textContent = podsumowanie.textContent;
    } else {
      podsumowanie.textContent =
        `Widoczny krok ${pokazane} z ${kroki.length}. ` +
        `Forma wynikowa: ${slad.forma}. Liczba kroków: ${kroki.length}.`;
      status.textContent =
        pokazane === 0
          ? `Formuła wyjściowa: ${slad.start}. ${TEKSTY.podpowiedz}`
          : `Krok ${pokazane}: ${kroki[pokazane - 1].nazwa}.`;
    }
  }

  przyciski.nastepny.addEventListener("click", () => {
    pokazane = Math.min(pokazane + 1, kroki.length);
    odswiez();
  });
  przyciski.poprzedni.addEventListener("click", () => {
    pokazane = Math.max(pokazane - 1, 0);
    odswiez();
  });
  przyciski.wszystkie.addEventListener("click", () => {
    pokazane = kroki.length;
    odswiez();
  });
  przyciski.odNowa.addEventListener("click", () => {
    pokazane = 0;
    odswiez();
  });

  montaz.append(pasek, lista, podsumowanie);
  odswiez();
}

document.querySelectorAll(".steps-mount").forEach((montaz) => {
  wypelnij(montaz);
});
