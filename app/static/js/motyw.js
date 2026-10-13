/**
 * Przełącznik motywu: „Auto” (jak w systemie), „Jasny” i „Ciemny” (karta PRZ-138).
 *
 * Atrybuty `data-theme` i `data-bs-theme` na `<html>` ustawia już skrypt inline
 * w `<head>` (żeby strona nie mignęła jasnym tłem), więc ten moduł tylko:
 *
 *   * zaznacza wybrany przycisk (`aria-pressed`),
 *   * zapisuje wybór w `localStorage["motyw"]`, a dla „Auto” usuwa klucz,
 *   * przełącza motyw, gdy system zmieni `prefers-color-scheme`, a wyborem jest „Auto”.
 *
 * Warstwą bez JavaScriptu zajmuje się `@media (prefers-color-scheme: dark)`
 * w `app.css` — wtedy przełącznik jest ukryty klasą `bez-js` na `<html>`.
 */

const KLUCZ = "motyw";
const PRZYCISKI = document.querySelectorAll("[data-motyw]");
const SYSTEM_CIEMNY = window.matchMedia("(prefers-color-scheme: dark)");

/** Zwraca zapisany wybór: `"light"`, `"dark"` albo `null`, gdy motyw idzie za systemem. */
function zapisanyWybor() {
  try {
    const wybor = localStorage.getItem(KLUCZ);
    return wybor === "light" || wybor === "dark" ? wybor : null;
  } catch (blad) {
    // Brak dostępu do localStorage (np. tryb prywatny) — motyw działa do końca wizyty.
    return null;
  }
}

/** Zapisuje wybór użytkownika; „Auto” (null) usuwa klucz i wraca do ustawienia systemu. */
function zapiszWybor(wybor) {
  try {
    if (wybor === null) {
      localStorage.removeItem(KLUCZ);
    } else {
      localStorage.setItem(KLUCZ, wybor);
    }
  } catch (blad) {
    // Jak wyżej: brak zapisu nie może zepsuć samego przełączania.
  }
}

let wybor = zapisanyWybor();

/** Ustawia motyw na `<html>` i zaznacza odpowiedni przycisk. */
function zastosujMotyw() {
  const motyw = wybor ?? (SYSTEM_CIEMNY.matches ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", motyw);
  document.documentElement.setAttribute("data-bs-theme", motyw);

  for (const przycisk of PRZYCISKI) {
    const wybrany = przycisk.dataset.motyw === (wybor ?? "auto");
    przycisk.setAttribute("aria-pressed", wybrany ? "true" : "false");
  }
}

// Motyw stosujemy od razu przy wczytaniu modułu: skrypt jest odroczony, więc przyciski
// już istnieją, a skrypt inline w `<head>` zdążył ustawić atrybuty.
zastosujMotyw();

for (const przycisk of PRZYCISKI) {
  przycisk.addEventListener("click", () => {
    const wartosc = przycisk.dataset.motyw;
    wybor = wartosc === "auto" ? null : wartosc;
    zapiszWybor(wybor);
    zastosujMotyw();
  });
}

SYSTEM_CIEMNY.addEventListener("change", () => {
  if (wybor === null) {
    zastosujMotyw();
  }
});
