# Treść: 14 praw rachunku zdań

Wykaz praw. Każde prawo ma osobny wpis w `app/logic/laws_data/`. Ten plik mówi, co ma
zawierać wpis. Kolejność w `kolejnosc` ustala kolejność nauki na stronie.

| # | `slug` | Nazwa | Kategoria | Formuła | Plik |
|---|---|---|---|---|---|
| 1 | `wylaczony-srodek` | Prawo wyłączonego środka | podstawowe | `p ∨ ¬p` | `podstawowe.py` |
| 2 | `identycznosci` | Prawo identyczności | podstawowe | `p → p` | `podstawowe.py` |
| 3 | `podwojne-przeczenie` | Prawo podwójnego przeczenia | podstawowe | `¬¬p ↔ p` | `podstawowe.py` |
| 4 | `definiowanie-implikacji` | Prawo definiowania implikacji | implikacja | `(p → q) ↔ (¬p ∨ q)` | `implikacja.py` |
| 5 | `kontrapozycji` | Prawo kontrapozycji | implikacja | `(p → q) ↔ (¬q → ¬p)` | `implikacja.py` |
| 6 | `lacznosc-alternatywy` | Prawo łączności alternatywy | algebra | `(p ∨ q) ∨ r ↔ p ∨ (q ∨ r)` | `algebra.py` |
| 7 | `lacznosc-koniunkcji` | Prawo łączności koniunkcji | algebra | `(p ∧ q) ∧ r ↔ p ∧ (q ∧ r)` | `algebra.py` |
| 8 | `rozdzielnosc-1` | Pierwsze prawo rozdzielności | algebra | `p ∧ (q ∨ r) ↔ (p ∧ q) ∨ (p ∧ r)` | `algebra.py` |
| 9 | `rozdzielnosc-2` | Drugie prawo rozdzielności | algebra | `p ∨ (q ∧ r) ↔ (p ∨ q) ∧ (p ∨ r)` | `algebra.py` |
| 10 | `przemiennosc-alternatywy` | Prawo przemienności alternatywy | algebra | `p ∨ q ↔ q ∨ p` | `algebra.py` |
| 11 | `przemiennosc-koniunkcji` | Prawo przemienności koniunkcji | algebra | `p ∧ q ↔ q ∧ p` | `algebra.py` |
| 12 | `de-morgan-1` | Pierwsze prawo de Morgana | de Morgan | `¬(p ∧ q) ↔ (¬p ∨ ¬q)` | `de_morgan.py` |
| 13 | `de-morgan-2` | Drugie prawo de Morgana | de Morgan | `¬(p ∨ q) ↔ (¬p ∧ ¬q)` | `de_morgan.py` |
| 14 | `zastepowanie-rownych` | Prawo zastępowania równych | zastępowanie | `jeśli A ↔ B, to C[A] ↔ C[B]` | `zastepowanie.py` |

## Co musi mieć każde prawo

Wypełnij **wszystkie** pola `Law` z `docs/ARCHITEKTURA.md`.

1. **`po_ludzku`** — 2 do 4 zdań prostym językiem. Zasady:
   - zdanie ma najwyżej 15–20 słów,
   - strona czynna, czasowniki konkretne,
   - żadnego słowa, którego nie wyjaśnia sąsiednie zdanie,
   - najpierw obraz z życia, potem zapis symboliczny.
2. **`przyklad`** — jedno konkretne zdanie z życia, np. „Pada deszcz albo nie pada”.
   Nie używaj `p` i `q` w przykładzie.
3. **`kroki`** — od 3 do 6 kroków przejścia od `lewa` do `prawa`. Każdy krok ma jedno zdanie
   wyjaśnienia. Krok 1 ma `reguła: "założenie"`. Ostatni krok kończy się dokładnie na `prawa`.
4. **`czeste_bledy`** — 2 do 3 typowych pomyłek studenta. Pisz, co ktoś robi źle i dlaczego
   to błąd. Przykład dla de Morgana: „Ktoś zamienia ∧ na ∧ i zapomina odwrócić znak negacji”.
5. **`quiz`** — 2 do 3 pytań. Każde pytanie ma 3 lub 4 odpowiedzi, jedną poprawną,
   podpowiedź i wyjaśnienie. Odpowiedzi nie mogą być trywialne (nie „tak/nie”).
6. **`wizualizacja`** — dobierz do treści:
   - `switch` — prawo wyłączonego środka: dwa wyłączniki, zawsze jeden włączony,
   - `chain` — identyczność, podwójne przeczenie: łańcuch przekształceń,
   - `gates` — implikacja, algebra, przemienność: schemat bramek logicznych,
   - `sets` — oba prawa de Morgana, rozdzielność: diagramy zbiorów.

## Sprawdzenie treści

`python3 -c "from app.logic.laws import validate; print(validate())"` ma wypisać pustą listę.
Test `tests/test_laws.py` sprawdza dodatkowo:

- 14 praw i unikalne `slug`,
- każda formuła `lewa` i `prawa` parsuje się i są równoważne (`truth.equivalent`),
- każdy krok z `kroki` jest równoważny poprzedniemu,
- `quiz` ma poprawny indeks odpowiedzi,
- `po_ludzku` ma co najmniej 80 znaków.
