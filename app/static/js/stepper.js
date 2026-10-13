/* Wspólny komponent kroków (stepper) dla wizualizacji. Karty PRZ-072 i PRZ-124.
   Jeden pasek prowadzi użytkownika krok po kroku: tablicę prawdy, bramki,
   diagramy zbiorów i dowód tautologii.

   Pasek ma dokładnie dwa elementy interaktywne: okrągłą strzałkę „‹” (poprzedni krok)
   i okrągłą strzałkę „›” (następny krok). Między nimi stoi tekstowe opisanie bieżącego
   kroku. Numerków, kropek i przycisków odtwarzania nie ma — zniknęły w karcie PRZ-124.

   Kontrakt (opisany też w `docs/ARCHITEKTURA.md`):

     import { createStepper } from "/static/js/stepper.js";

     const stepper = createStepper({
       mount: document.querySelector("#kroki"),   // element, w którym powstaje pasek
       steps: [{ tytul: "...", opis: "..." }],    // co najmniej 1 krok
       onStep: (index, step) => { ... },          // co pokazać po wejściu w krok
     });

   Komponent pisze wyłącznie do własnego kontenera `mount` i do elementu opisu.
   Resztę rysunku robi karta, która go używa — w wywołaniu `onStep(index, step)`.

   Numeracja: `index`, `go(index)` i `onStep(index, ...)` liczą kroki od zera
   (jak tablice w JavaScripcie); widok nie pokazuje żadnego numeru kroku.
   Wszystkie teksty trafiają do DOM przez `textContent`, nigdy przez `innerHTML`. */

/** Widoczny znak przycisku: sama strzałka, bez podpisu. */
const GLYPHS = Object.freeze({
  prev: "‹",
  next: "›",
});

/** Nazwa przycisku dla czytnika ekranu — widok pokazuje tylko strzałkę. */
const LABELS = Object.freeze({
  prev: "Poprzedni krok",
  next: "Następny krok",
});

const MESSAGES = Object.freeze({
  group: "Sterowanie krokami",
  empty:
    "Ten komponent nie ma jeszcze kroków. Uzupełnij listę kroków, " +
    "aby prowadzić użytkownika krok po kroku.",
});

/** Tworzy element z klasą i tekstem (tekst zawsze bezpiecznie, przez `textContent`). */
function createElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

/** Zaślepka: brak kontenera albo brak kroków nie może wywrócić strony. */
function inertStepper() {
  const noop = () => {};
  return {
    index: -1,
    length: 0,
    go: noop,
    next: noop,
    prev: noop,
    destroy: noop,
  };
}

/** Komunikat po polsku, gdy montaż nie dostał żadnego kroku. */
function showEmptyMessage(mount) {
  const message = createElement("p", "stepper-blad alert alert-info mb-0", MESSAGES.empty);
  mount.replaceChildren(message);
}

/** Buduje pasek kroków w kontenerze `mount`. */
function buildStepper(mount, steps, settings) {
  const { onStep } = settings;

  let index = 0;

  const bar = createElement("div", "stepper");
  bar.tabIndex = 0; // cały pasek da się wziąć fokusem i obsłużyć strzałkami
  bar.setAttribute("role", "group");
  bar.setAttribute("aria-label", MESSAGES.group);

  // Dokładnie dwa elementy interaktywne: „‹” i „›”. Nic więcej.
  const previous = createElement("button", "stepper-strzalka", GLYPHS.prev);
  const following = createElement("button", "stepper-strzalka", GLYPHS.next);
  previous.type = "button";
  following.type = "button";
  previous.setAttribute("aria-label", LABELS.prev);
  following.setAttribute("aria-label", LABELS.next);

  // Element opisu to jedyne miejsce poza paskiem, do którego komponent pisze.
  // Stoi **między** strzałkami i nie zawiera numeru kroku.
  const description = createElement("div", "stepper-opis");
  description.setAttribute("aria-live", "polite");
  const title = createElement("p", "stepper-tytul");
  const body = createElement("p", "stepper-tresc");
  description.append(title, body);

  const controls = createElement("div", "stepper-pasek");
  controls.append(previous, description, following);

  /** Odświeża opis kroku i stan obu strzałek. */
  function draw() {
    const step = steps[index] || {};
    title.textContent = step.tytul || "";
    body.textContent = step.opis || "";

    // Na krańcach listy strzałka jest wyłączona — i po polu `disabled`,
    // i po `aria-disabled`, żeby czytnik ekranu też o tym wiedział.
    const pierwszy = index <= 0;
    const ostatni = index >= steps.length - 1;
    previous.disabled = pierwszy;
    following.disabled = ostatni;
    previous.setAttribute("aria-disabled", String(pierwszy));
    following.setAttribute("aria-disabled", String(ostatni));
  }

  /** Mówi karcie, która używa komponentu, co pokazać dla bieżącego kroku. */
  function notify() {
    if (typeof onStep === "function") {
      onStep(index, steps[index]);
    }
  }

  /** Przechodzi do kroku o podanym indeksie (liczonym od zera). */
  function go(target) {
    const position = Number(target);
    if (!Number.isFinite(position)) {
      return index;
    }
    const poprzedni = index;
    index = Math.min(Math.max(Math.trunc(position), 0), steps.length - 1);
    draw();
    if (index !== poprzedni) {
      notify();
    }
    return index;
  }

  function next() {
    return go(index + 1);
  }

  function prev() {
    return go(index - 1);
  }

  /** Strzałki, `Home` i `End` — cały pasek działa z klawiatury. */
  function handleKeydown(event) {
    const key = event.key;
    if (key === "ArrowLeft") {
      event.preventDefault();
      prev();
      return;
    }
    if (key === "ArrowRight") {
      event.preventDefault();
      next();
      return;
    }
    if (key === "Home") {
      event.preventDefault();
      go(0);
      return;
    }
    if (key === "End") {
      event.preventDefault();
      go(steps.length - 1);
    }
  }

  previous.addEventListener("click", prev);
  following.addEventListener("click", next);
  bar.addEventListener("keydown", handleKeydown);

  bar.append(controls);
  mount.replaceChildren(bar);
  draw();
  notify();

  /** Zdejmuje nasłuchy i usuwa pasek z kontenera. */
  function destroy() {
    bar.removeEventListener("keydown", handleKeydown);
    previous.removeEventListener("click", prev);
    following.removeEventListener("click", next);
    mount.replaceChildren();
  }

  return {
    get index() {
      return index;
    },
    get length() {
      return steps.length;
    },
    go,
    next,
    prev,
    destroy,
  };
}

/**
 * Tworzy pasek kroków w kontenerze `mount`.
 *
 * Brak kontenera albo brak kroków nie rzuca błędu. Bez `steps` komponent pokazuje
 * w kontenerze komunikat po polsku; bez `mount` nie dotyka dokumentu. W obu razach
 * zwrócony obiekt ma te same metody (nic nie robią).
 */
export function createStepper(options = {}) {
  const { mount, steps, onStep = null } = options;
  const list = Array.isArray(steps) ? steps.filter((step) => step != null) : [];

  if (!mount) {
    return inertStepper();
  }
  if (list.length === 0) {
    showEmptyMessage(mount);
    return inertStepper();
  }
  return buildStepper(mount, list, { onStep });
}
