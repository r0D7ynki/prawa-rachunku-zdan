/* Wspólny komponent kroków (stepper) dla wizualizacji. Karta PRZ-072.
   Jeden pasek prowadzi użytkownika krok po kroku: tablicę prawdy, bramki,
   diagramy zbiorów i dowód tautologii.

   Kontrakt (opisany też w `docs/ARCHITEKTURA.md`):

     import { createStepper } from "/static/js/stepper.js";

     const stepper = createStepper({
       mount: document.querySelector("#kroki"),   // element, w którym powstaje pasek
       steps: [{ tytul: "...", opis: "..." }],    // co najmniej 1 krok
       onStep: (index, step) => { ... },          // co pokazać po wejściu w krok
       autoMs: 1500,                              // tempo odtwarzania
       labels: { prev: "Wstecz", next: "Dalej", play: "Odtwórz", pause: "Pauza", reset: "Od nowa" }
     });

   Komponent pisze wyłącznie do własnego kontenera `mount` i do elementu opisu.
   Resztę rysunku robi karta, która go używa — w wywołaniu `onStep(index, step)`.

   Numeracja: `index`, `go(index)` i `onStep(index, ...)` liczą kroki od zera
   (jak tablice w JavaScripcie), a widoczny wskaźnik pokazuje numer od jednego.
   Wszystkie teksty trafiają do DOM przez `textContent`, nigdy przez `innerHTML`. */

/** Domyślne napisy przycisków. Strona może je nadpisać przez `labels`. */
export const DEFAULT_LABELS = Object.freeze({
  prev: "Wstecz",
  next: "Dalej",
  play: "Odtwórz",
  pause: "Pauza",
  reset: "Od nowa",
});

const MESSAGES = Object.freeze({
  group: "Sterowanie krokami",
  dot: "Krok",
  progress: "Krok",
  empty:
    "Ten komponent nie ma jeszcze kroków. Uzupełnij listę kroków, " +
    "aby prowadzić użytkownika krok po kroku.",
});

/** Tempo odtwarzania, gdy strona nie poda własnego. */
const DEFAULT_AUTO_MS = 1500;

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
    playing: false,
    go: noop,
    next: noop,
    prev: noop,
    play: noop,
    pause: noop,
    reset: noop,
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
  const labels = { ...DEFAULT_LABELS, ...settings.labels };
  const autoMs =
    Number.isFinite(settings.autoMs) && settings.autoMs > 0
      ? Math.trunc(settings.autoMs)
      : DEFAULT_AUTO_MS;

  let index = 0;
  let timer = null;

  const bar = createElement("div", "stepper");
  bar.tabIndex = 0; // cały pasek da się wziąć fokusem i obsłużyć strzałkami
  bar.setAttribute("role", "group");
  bar.setAttribute("aria-label", MESSAGES.group);

  const controls = createElement(
    "div",
    "stepper-pasek d-flex flex-wrap gap-2 align-items-center mb-2",
  );
  const buttons = {
    prev: createElement("button", "btn btn-outline-secondary btn-sm", labels.prev),
    next: createElement("button", "btn btn-primary btn-sm", labels.next),
    play: createElement("button", "btn btn-outline-secondary btn-sm", labels.play),
    reset: createElement("button", "btn btn-outline-secondary btn-sm", labels.reset),
  };
  for (const button of Object.values(buttons)) {
    button.type = "button";
  }
  buttons.play.setAttribute("aria-pressed", "false");

  const indicator = createElement("span", "stepper-wskaznik text-muted small ms-auto");

  const dotsList = createElement("ol", "stepper-kropki list-unstyled d-flex flex-wrap gap-2 mb-2");
  const dots = steps.map((step, position) => {
    const item = createElement("li");
    const dot = createElement("button", "stepper-kropka", String(position + 1));
    dot.type = "button";
    dot.setAttribute("aria-label", `${MESSAGES.dot} ${position + 1}: ${step.tytul || ""}`);
    dot.addEventListener("click", () => go(position));
    item.append(dot);
    dotsList.append(item);
    return dot;
  });

  // Element opisu to jedyne miejsce poza paskiem, do którego komponent pisze.
  const description = createElement("div", "stepper-opis");
  description.setAttribute("aria-live", "polite");
  const title = createElement("p", "stepper-tytul fw-semibold mb-1");
  const body = createElement("p", "stepper-tresc mb-1");
  description.append(title, body);

  /** Odświeża pasek: kropki, wskaźnik, opis i stan przycisków. */
  function draw() {
    dots.forEach((dot, position) => {
      if (position === index) {
        dot.setAttribute("aria-current", "step");
      } else {
        dot.removeAttribute("aria-current");
      }
    });

    const step = steps[index] || {};
    indicator.textContent = `${MESSAGES.progress} ${index + 1} z ${steps.length}`;
    title.textContent = step.tytul || "";
    body.textContent = step.opis || "";

    buttons.prev.disabled = index <= 0;
    buttons.next.disabled = index >= steps.length - 1;
    buttons.reset.disabled = index <= 0 && timer === null;
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

  /** Odtwarza kroki po kolei w tempie `autoMs`. */
  function play() {
    if (timer !== null) {
      return; // już odtwarza
    }
    if (index >= steps.length - 1) {
      go(0); // z ostatniego kroku wracamy na początek
    }
    buttons.play.textContent = labels.pause;
    buttons.play.setAttribute("aria-pressed", "true");
    timer = window.setInterval(() => {
      if (index >= steps.length - 1) {
        pause(); // koniec listy zatrzymuje odtwarzanie
        return;
      }
      go(index + 1);
    }, autoMs);
    draw();
  }

  /** Zatrzymuje odtwarzanie i przywraca napis „Odtwórz”. */
  function pause() {
    if (timer !== null) {
      window.clearInterval(timer);
      timer = null;
    }
    buttons.play.textContent = labels.play;
    buttons.play.setAttribute("aria-pressed", "false");
    draw();
  }

  /** Zatrzymuje odtwarzanie i wraca do pierwszego kroku. */
  function reset() {
    pause();
    go(0);
  }

  function togglePlay() {
    if (timer === null) {
      play();
    } else {
      pause();
    }
  }

  /** Strzałki, `Home`, `End` i spacja — cały pasek działa z klawiatury. */
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
      return;
    }
    if (key === " " || key === "Spacebar") {
      // Spacja na przycisku ma już swoje znaczenie (klik), więc jej nie dublujemy.
      if (event.target instanceof HTMLButtonElement) {
        return;
      }
      event.preventDefault();
      togglePlay();
    }
  }

  buttons.prev.addEventListener("click", prev);
  buttons.next.addEventListener("click", next);
  buttons.play.addEventListener("click", togglePlay);
  buttons.reset.addEventListener("click", reset);
  bar.addEventListener("keydown", handleKeydown);

  controls.append(buttons.prev, buttons.next, buttons.play, buttons.reset, indicator);
  bar.append(controls, dotsList, description);
  mount.replaceChildren(bar);
  draw();
  notify();

  /** Zatrzymuje odtwarzanie, zdejmuje nasłuchy i usuwa pasek z kontenera. */
  function destroy() {
    pause();
    bar.removeEventListener("keydown", handleKeydown);
    buttons.prev.removeEventListener("click", prev);
    buttons.next.removeEventListener("click", next);
    buttons.play.removeEventListener("click", togglePlay);
    buttons.reset.removeEventListener("click", reset);
    mount.replaceChildren();
  }

  return {
    get index() {
      return index;
    },
    get length() {
      return steps.length;
    },
    get playing() {
      return timer !== null;
    },
    go,
    next,
    prev,
    play,
    pause,
    reset,
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
  const { mount, steps, onStep = null, autoMs = DEFAULT_AUTO_MS, labels = {} } = options;
  const list = Array.isArray(steps) ? steps.filter((step) => step != null) : [];

  if (!mount) {
    return inertStepper();
  }
  if (list.length === 0) {
    showEmptyMessage(mount);
    return inertStepper();
  }
  return buildStepper(mount, list, { onStep, autoMs, labels });
}
