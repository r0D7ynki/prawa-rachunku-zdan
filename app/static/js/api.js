/* Wspólny klient API (karta PRZ-174).
   Wszystkie komponenty JavaScript rozmawiają z serwerem przez `pobierzJson`. Dzięki
   temu każdy z nich zachowuje się tak samo, gdy coś pójdzie nie tak — zamiast pustki
   student widzi komunikat po polsku.

   Kontrakt (jedno miejsce na całą obsługę błędów):

     const wynik = await pobierzJson(adres, {
       method: "POST",
       headers: { "Content-Type": "application/json" },
       body: JSON.stringify({ formula }),
     });
     if (!wynik.ok) {
       pokazBlad(kontener, wynik.blad);   // napis po polsku, zawsze ten sam
       return;
     }
     const dane = wynik.dane;             // obiekt albo tablica z serwera

   Kiedy `wynik.ok` jest fałszem:

     - brak sieci albo zerwane połączenie   → „Nie udało się połączyć z serwerem. …”,
     - odpowiedź HTTP z kodem błędu         → „Serwer zwrócił błąd (kod N). Spróbuj ponownie.”,
     - treść, której nie da się sparsować   → „Serwer zwrócił nieprawidłową odpowiedź.”,
     - `ok: false` z API — komunikat z pola `blad` (albo zapasowy, gdy API go nie da),
     - brak odpowiedzi w 15 s               → „Serwer nie odpowiedział w porę.”.

   Funkcja nigdy nie rzuca: czekanie na wynik to jedna gałąź `if`, a nie `try/catch`
   w każdym komponencie. */

/* Po tylu milisekundach przerywamy żądanie i pokazujemy komunikat o czasie. */
const LIMIT_CZASU_MS = 15000;

const TEKSTY = {
  siec: "Nie udało się połączyć z serwerem. Sprawdź połączenie i spróbuj ponownie.",
  brakOdpowiedzi: "Serwer nie odpowiedział w porę.",
  zlaOdpowiedz: "Serwer zwrócił nieprawidłową odpowiedź.",
};

/** Komunikat dla kodu błędu HTTP, np. „Serwer zwrócił błąd (kod 500). Spróbuj ponownie.”. */
function komunikatKodu(kod) {
  return `Serwer zwrócił błąd (kod ${kod}). Spróbuj ponownie.`;
}

/** Czy wyjątek to przerwanie przez limit czasu, a nie zerwane połączenie? */
function przekroczonyCzas(blad) {
  return blad?.name === "AbortError";
}

/**
 * Pobiera JSON z API i zwraca `{ ok: true, dane }` albo `{ ok: false, blad }`.
 * `blad` to gotowy komunikat po polsku — komponent wstawia go przez `textContent`.
 */
export async function pobierzJson(adres, dane = {}) {
  const sterownik = new AbortController();
  const zegar = setTimeout(() => sterownik.abort(), LIMIT_CZASU_MS);
  try {
    const odpowiedz = await fetch(adres, { ...dane, signal: sterownik.signal });
    if (!odpowiedz.ok) {
      return { ok: false, blad: komunikatKodu(odpowiedz.status) };
    }

    let tresc;
    try {
      tresc = await odpowiedz.json();
    } catch (blad) {
      /* Przerwanie w trakcie czytania treści to wciąż przekroczony czas. */
      return { ok: false, blad: przekroczonyCzas(blad) ? TEKSTY.brakOdpowiedzi : TEKSTY.zlaOdpowiedz };
    }

    if (tresc && tresc.ok === false) {
      return { ok: false, blad: tresc.blad || TEKSTY.zlaOdpowiedz };
    }
    return { ok: true, dane: tresc };
  } catch (blad) {
    return { ok: false, blad: przekroczonyCzas(blad) ? TEKSTY.brakOdpowiedzi : TEKSTY.siec };
  } finally {
    clearTimeout(zegar);
  }
}
