# Treść: 14 praw rachunku zdań (numeracja z wykładu)

Źródło: „Logika pragmatyczna 2026/2027”, prof. Adam Kasperski (PWr), wykład 1,
slajdy „Tautologie” (T1–T14). Ta numeracja i te wzory są **obowiązujące** na stronie.
Uwaga: numeracja z wykładu różni się od popularnej kolejności w podręcznikach —
nie zmieniaj jej.

Każde prawo ma osobny wpis w `app/logic/laws_data/`. Kolejność w `kolejnosc` ustala
kolejność nauki na stronie.

| # | `slug` | Nazwa z wykładu | Kategoria | Formuła (notacja wykładu) | Plik |
|---|---|---|---|---|---|
| 1 | `wylaczony-srodek` | Prawo wyłączonego środka | podstawowe | `p ∨ ∼p` | `podstawowe.py` |
| 2 | `identycznosci` | Prawo identyczności | podstawowe | `p → p` | `podstawowe.py` |
| 3 | `podwojne-przeczenie` | Prawo podwójnego przeczenia | podstawowe | `∼(∼p) ≡ p` | `podstawowe.py` |
| 4 | `definiowanie-implikacji` | Prawo definiowania implikacji | implikacja | `(p → q) ≡ (∼p ∨ q)` | `implikacja.py` |
| 5 | `kontrapozycji` | Prawo kontrapozycji | implikacja | `(p → q) ≡ (∼q → ∼p)` | `implikacja.py` |
| 6 | `lacznosc-alternatywy` | Prawo łączności alternatywy | algebra | `((p ∨ q) ∨ r) ≡ (p ∨ (q ∨ r))` | `algebra.py` |
| 7 | `lacznosc-koniunkcji` | Prawo łączności koniunkcji | algebra | `((p ∧ q) ∧ r) ≡ (p ∧ (q ∧ r))` | `algebra.py` |
| 8 | `rozdzielnosc-1` | I prawo rozdzielności | algebra | `((p ∨ q) ∧ r) ≡ ((p ∧ r) ∨ (q ∧ r))` | `algebra.py` |
| 9 | `rozdzielnosc-2` | II prawo rozdzielności | algebra | `((p ∧ q) ∨ r) ≡ ((p ∨ r) ∧ (q ∨ r))` | `algebra.py` |
| 10 | `przemiennosc-alternatywy` | Prawo przemienności alternatywy | algebra | `(p ∨ q) ≡ (q ∨ p)` | `algebra.py` |
| 11 | `przemiennosc-koniunkcji` | Prawo przemienności koniunkcji | algebra | `(p ∧ q) ≡ (q ∧ p)` | `algebra.py` |
| 12 | `de-morgan-1` | I prawo de Morgana | de Morgan | `∼(p ∨ q) ≡ (∼p ∧ ∼q)` | `de_morgan.py` |
| 13 | `de-morgan-2` | II prawo de Morgana | de Morgan | `∼(p ∧ q) ≡ (∼p ∨ ∼q)` | `de_morgan.py` |
| 14 | `zastepowanie-rownych` | Prawo zastępowania równ. | zastępowanie | `(p ≡ q) ≡ ((p → q) ∧ (q → p))` | `zastepowanie.py` |

## Notacja (wymóg z wykładu)

Na stronie **główna** jest notacja z wykładu. Obok pokazuj notację popularną.

| Znaczenie | Notacja wykładu (główna) | Notacja popularna |
|---|---|---|
| negacja | `∼p` | `¬p` |
| koniunkcja | `p ∧ q` | `p ∧ q` |
| alternatywa | `p ∨ q` | `p ∨ q` |
| implikacja | `p → q` | `p → q` |
| równoważność | `p ≡ q` | `p ↔ q` |
| prawda / fałsz | `1` / `0` | PRAWDA / FAŁSZ |

Czytanie spójników po polsku (tak samo jak na wykładzie):

- `∼p` — „nieprawda, że p” (nie p),
- `p ∧ q` — „p i q”,
- `p ∨ q` — „p lub q”,
- `p → q` — „jeżeli p, to q” (z p wynika q),
- `p ≡ q` — „p wtedy i tylko wtedy, gdy q”.

## Co musi mieć każde prawo

Wypełnij **wszystkie** pola `Law` z `docs/ARCHITEKTURA.md`.

1. **`po_ludzku`** — 2 do 4 zdań prostym językiem. Zasady:
   - zdanie ma najwyżej 15–20 słów,
   - strona czynna, czasowniki konkretne,
   - żadnego słowa, którego nie wyjaśnia sąsiednie zdanie,
   - najpierw obraz z życia, potem zapis symboliczny.
2. **`przyklad`** — konkretne zdanie z życia. Nie używaj `p` i `q` w przykładzie.
   Dla praw, które mają przykład na wykładzie, użyj **tego samego** przykładu:
   - kontrapozycja: „Jeżeli nauczę się, to zdam. Zatem jeżeli nie zdałem, to się nie nauczyłem.”,
   - de Morgan I: „Nie jest prawdą, że pójdę do kina lub do teatru. Zatem nie pójdę do kina i nie pójdę do teatru.”,
   - podwójne przeczenie: „Jeżeli nie jest prawdą, że nie zdam, to zdam.”,
3. **`kroki`** — od 3 do 6 kroków przejścia od `lewa` do `prawa`. Każdy krok ma jedno zdanie
   wyjaśnienia. Krok 1 ma `reguła: "założenie"`. Ostatni krok kończy się dokładnie na `prawa`.
4. **`czeste_bledy`** — 2 do 3 typowych pomyłek studenta. Pisz, co ktoś robi źle i dlaczego
   to błąd. Obowiązkowe wpisy:
   - kontrapozycja: „Ktoś uznaje `(p → q) ≡ (∼p → ∼q)` za tautologię. To błąd: z faktu, że się
     nie nauczyłem, nie wynika, że nie zdam.”,
   - de Morgan: „Ktoś neguje tylko pierwszy człon i nie odwraca spójnika.”,
   - rozdzielność: „Ktoś rozdziela `∧` po `∨` i zapomina rozdzielić oba składniki.”.
5. **`quiz`** — 2 do 3 pytań. Każde pytanie ma 3 lub 4 odpowiedzi, jedną poprawną,
   podpowiedź i wyjaśnienie. Odpowiedzi nie mogą być trywialne (nie „tak/nie”).
6. **`wizualizacja`** — dobierz do treści:
   - `switch` — prawo wyłączonego środka: dwa wyłączniki, zawsze jeden włączony,
   - `chain` — identyczność, podwójne przeczenie, zastępowanie równ.: łańcuch przekształceń,
   - `gates` — implikacja, algebra, przemienność: schemat bramek logicznych,
   - `sets` — oba prawa de Morgana, rozdzielność: diagramy zbiorów.

## Prawa dodatkowe (poza listą 14)

Wykład używa ich w przykładach przekształceń. Oznacz je jako „prawa dodatkowe” i nie numeruj
jako T1–T14. Mieszkają w `app/logic/laws_data/dodatkowe.py` (karta PRZ-024).

| `slug` | Nazwa | Formuła |
|---|---|---|
| `idempotencja-alternatywy` | Prawo idempotencji alternatywy | `(p ∨ p) ≡ p` |
| `idempotencja-koniunkcji` | Prawo idempotencji koniunkcji | `(p ∧ p) ≡ p` |
| `podstawianie` | Reguła podstawiania | jeśli `ϕ` jest tautologią, to `ϕ[p := ψ]` też jest tautologią |

## Sprawdzenie treści

`python3 -c "from app.logic.laws import validate; print(validate())"` ma wypisać pustą listę.
Test `tests/test_laws.py` sprawdza dodatkowo:

- 14 praw z listy T1–T14 i unikalne `slug`,
- każda formuła `lewa` i `prawa` parsuje się i są równoważne (`truth.equivalent`),
- każdy krok z `kroki` jest równoważny poprzedniemu,
- `quiz` ma poprawny indeks odpowiedzi,
- `po_ludzku` ma co najmniej 80 znaków.
