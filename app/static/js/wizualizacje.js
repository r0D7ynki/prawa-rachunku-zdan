/* Rysunki na stronie prawa: dwie strzałki prowadzą przez kroki (karta PRZ-123).

   Rysunki liczy serwer (``app/logic/diagrams.py``), więc ten skrypt nic nie pobiera:
   podmienia gotowy krok czekający w ``<template>``. Bez JavaScriptu widać pierwszy
   krok i całą listę opisów, więc strona działa dalej.

   Użycie: sekcja rysunku ma ``[data-wiz-kroki]``, a w niej kontener ``[data-wiz-rysunek]``,
   opis ``[data-wiz-opis]``, strzałki ``[data-wiz-poprzedni]`` i ``[data-wiz-nastepny]``
   oraz szablony kroków ``template[data-wiz-krok]``. Szablony **muszą leżeć w tej samej
   sekcji** — szukamy ich przez ``panel.querySelectorAll``. */

const RYSUNEK = ".wiz-rysunek";
const OPIS = ".wiz-krok-opis";
const ODNOSNIK_OPISU = ".wiz-opisy li";

/** Pokazuje krok o numerze `indeks` (liczonym od zera) i zwraca numer po przycięciu. */
function pokazKrok(panel, indeks) {
  const kroki = Array.from(panel.querySelectorAll("template[data-wiz-krok]"));
  if (kroki.length === 0) return 0;

  const numer = Math.max(0, Math.min(indeks, kroki.length - 1));
  const zrodlo = kroki[numer].content;

  panel.querySelector(RYSUNEK).replaceWith(zrodlo.querySelector(RYSUNEK).cloneNode(true));
  panel.querySelector(OPIS).replaceWith(zrodlo.querySelector(OPIS).cloneNode(true));

  panel.querySelectorAll(ODNOSNIK_OPISU).forEach((element, pozycja) => {
    const biezacy = pozycja === numer;
    element.classList.toggle("wiz-opis-biezacy", biezacy);
    if (biezacy) element.setAttribute("aria-current", "step");
    else element.removeAttribute("aria-current");
  });

  const naPoczatku = numer === 0;
  const naKoncu = numer === kroki.length - 1;
  for (const [wybor, nieaktywny] of [
    ["[data-wiz-poprzedni]", naPoczatku],
    ["[data-wiz-nastepny]", naKoncu],
  ]) {
    const przycisk = panel.querySelector(wybor);
    przycisk.disabled = nieaktywny;
    przycisk.setAttribute("aria-disabled", nieaktywny ? "true" : "false");
  }
  return numer;
}

/** Podłącza strzałki i klawiaturę do jednej sekcji rysunku. */
function uruchomPanel(panel) {
  let indeks = 0;
  const idz = (krok) => {
    indeks = pokazKrok(panel, indeks + krok);
  };

  panel.querySelector("[data-wiz-poprzedni]").addEventListener("click", () => idz(-1));
  panel.querySelector("[data-wiz-nastepny]").addEventListener("click", () => idz(1));
  panel.addEventListener("keydown", (zdarzenie) => {
    if (zdarzenie.key === "ArrowLeft") {
      idz(-1);
      zdarzenie.preventDefault();
    } else if (zdarzenie.key === "ArrowRight") {
      idz(1);
      zdarzenie.preventDefault();
    }
  });

  // Pierwsze ustawienie wyłącza „poprzedni” na starcie.
  indeks = pokazKrok(panel, 0);
}

document.querySelectorAll("[data-wiz-kroki]").forEach(uruchomPanel);
