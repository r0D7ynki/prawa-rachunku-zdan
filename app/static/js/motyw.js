/**
 * Przełącznik motywu: jeden suwak jasny/ciemny (karta PRZ-155).
 *
 * Atrybuty `data-theme` i `data-bs-theme` na `<html>` ustawia już skrypt inline
 * w `<head>` (żeby strona nie mignęła jasnym tłem), więc ten moduł tylko:
 *
 *   * ustawia suwak tak, żeby pokazywał motyw, który właśnie działa,
 *   * po przełączeniu zapisuje wybór w `localStorage["motyw"]` i zmienia atrybuty,
 *   * dopóki nikt nic nie wybrał, idzie za `prefers-color-scheme`; po zapisanym
 *     wyborze system przestaje zmieniać motyw.
 *
 * Opcji „Auto” nie ma — brak klucza w localStorage znaczy „jak w systemie”, a każde
 * przełączenie zapisuje `"light"` albo `"dark"`. Warstwą bez JavaScriptu zajmuje się
 * `@media (prefers-color-scheme: dark)` w `app.css`; tam suwak jest ukryty klasą
 * `bez-js` na `<html>`.
 */

const KLUCZ = "motyw";
const SUWAK = document.querySelector(".przelacznik-motywu");
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

/** Motyw, który podpowiada system — używany, gdy nikt nic nie wybrał. */
function motywSystemu() {
  return SYSTEM_CIEMNY.matches ? "dark" : "light";
}

let wybor = zapisanyWybor();

/** Ustawia motyw na `<html>` i przestawia suwak na ten motyw. */
function zastosujMotyw() {
  const motyw = wybor ?? motywSystemu();
  document.documentElement.setAttribute("data-theme", motyw);
  document.documentElement.setAttribute("data-bs-theme", motyw);

  if (SUWAK) {
    SUWAK.checked = motyw === "dark";
  }
}

// Motyw stosujemy od razu przy wczytaniu modułu: skrypt jest odroczony, więc suwak już
// istnieje, a skrypt inline w `<head>` zdążył ustawić atrybuty.
zastosujMotyw();

if (SUWAK) {
  SUWAK.addEventListener("change", () => {
    wybor = SUWAK.checked ? "dark" : "light";
    try {
      localStorage.setItem(KLUCZ, wybor);
    } catch (blad) {
      // Brak zapisu nie może zepsuć samego przełączania.
    }
    zastosujMotyw();
  });
}

// Zmiana ustawienia systemu działa tylko dopóki użytkownik niczego nie wybrał.
SYSTEM_CIEMNY.addEventListener("change", () => {
  if (wybor === null) {
    zastosujMotyw();
  }
});
