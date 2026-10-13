# Treść wykładu 2 — konsekwencja logiczna, dowody, rezolucja

Źródło: „Logika pragmatyczna 2026/2027”, prof. Adam Kasperski (PWr), wykład 2.
Ten plik jest **źródłem prawdy** dla stron wykładu 2. Nie zmieniaj oznaczeń ani numeracji.

## Notacja

Ta sama co w wykładzie 1: `∼`, `∧`, `∨`, `→`, `≡`. Zdania oznaczamy `p`, `q`, `r`, `s`, `t`.
W regułach używamy **metazmiennych** `Φ`, `Ψ`, `Θ` — to dowolne formuły, nie pojedyncze zdania.

## 1. Konsekwencja logiczna

Formuła `Ψ` **wynika logicznie** z formuł `Φ1, Φ2, …, Φn`, jeżeli

```
(Φ1 ∧ Φ2 ∧ … ∧ Φn) → Ψ
```

jest tautologią. Formuły `Φ1 … Φn` to **założenia**, `Ψ` to **teza** (wniosek, konsekwencja).

Znaczenie: nie istnieje wartościowanie, w którym wszystkie założenia są prawdziwe,
a teza fałszywa.

Ta sama własność zapisana inaczej (dowód na ćwiczeniach):

```
(Φ1 ∧ Φ2 ∧ … ∧ Φn) → Ψ   ≡   Φ1 → (Φ2 → (Φ3 → … → (Φn → Ψ)…))
```

### Przykłady z wykładu

| Rozumowanie | Zapis | Ocena |
|---|---|---|
| Azor jest psem → Azor jest zwierzęciem. Azor nie jest psem. Zatem Azor nie jest zwierzęciem. | `((p → q) ∧ ∼p) → ∼q` | **niepoprawne** — kontrprzykład: Azor-kot |
| Azor jest psem → Azor jest zwierzęciem. Azor nie jest zwierzęciem. Zatem Azor nie jest psem. | `((p → q) ∧ ∼q) → ∼p` | **poprawne** — tautologia |

### Założenia sprzeczne

Założenia `Φ1 … Φn` są **sprzeczne**, gdy `Φ1 ∧ … ∧ Φn` jest zawsze fałszywa.
Z założeń sprzecznych wynika logicznie **dowolna** teza.

Przykład z wykładu: „Pada deszcz i nie pada deszcz. Zatem Ziemia jest płaska.”

```
(p ∧ ∼p) → q
```

Rozumowanie jest formalnie poprawne, ale bezsensowne — nie istnieje świat, w którym
założenia są spełnione. **Tautologie określają formalną poprawność rozumowania, a nie jego sens.**

## 2. Reguły wnioskowania

### Pierwotne

| Kod | Nazwa | Zapis reguły | Tautologia | Przykład |
|---|---|---|---|---|
| **RO** | Reguła odrywania (Modus Ponens) | `Φ → Ψ`, `Φ` ⊢ `Ψ` | `((p → q) ∧ p) → q` | Jeżeli pada śnieg, to jest zimno. Pada śnieg. Zatem jest zimno. |
| **OK** | Opuszczanie koniunkcji | `Φ ∧ Ψ` ⊢ `Φ` oraz `Φ ∧ Ψ` ⊢ `Ψ` | `((p ∧ q) → p)`, `((p ∧ q) → q)` | Pada śnieg i jest zimno. Zatem pada śnieg. |
| **DK** | Dołączanie koniunkcji | `Φ`, `Ψ` ⊢ `Φ ∧ Ψ` | `(p → (q → (p ∧ q)))` | Pada śnieg. Jest zimno. Zatem pada śnieg i jest zimno. |
| **OA** | Opuszczanie alternatywy | `Φ ∨ Ψ`, `∼Φ` ⊢ `Ψ` | `((p ∨ q) ∧ ∼p) → q` | Pada śnieg lub jest zimno. Nie pada śnieg. Zatem jest zimno. |
| **DA** | Dołączanie alternatywy | `Φ` ⊢ `Φ ∨ Ψ` | `p → (p ∨ q)` | Pada śnieg. Zatem pada śnieg lub jest zimno. |
| **DR** | Dołączanie równoważności | `Φ → Ψ`, `Ψ → Φ` ⊢ `Φ ≡ Ψ` | `((p → q) ∧ (q → p)) → (p ≡ q)` | Jeżeli pada śnieg, to jest zimno, i odwrotnie. Zatem pada śnieg wtedy i tylko wtedy, gdy jest zimno. |
| **OR** | Opuszczanie równoważności | `Φ ≡ Ψ` ⊢ `Φ → Ψ` oraz `Ψ → Φ` | `(p ≡ q) → ((p → q) ∧ (q → p))` | Pada śnieg wtedy i tylko wtedy, gdy jest zimno. Zatem jeżeli pada śnieg, to jest zimno. |

### Dodatkowe

| Kod | Nazwa | Zapis reguły | Tautologia |
|---|---|---|---|
| **DM1** | I prawo de Morgana | `∼(Φ ∨ Ψ)` ⊢ `∼Φ ∧ ∼Ψ` | `∼(p ∨ q) → (∼p ∧ ∼q)` |
| **DM2** | II prawo de Morgana | `∼Φ ∧ ∼Ψ` ⊢ `∼(Φ ∨ Ψ)` | `(∼p ∧ ∼q) → ∼(p ∨ q)` |
| **KP** | Prawo kontrapozycji | `Φ → Ψ` ⊢ `∼Ψ → ∼Φ` | `(p → q) → (∼q → ∼p)` |

## 3. Dowód założeniowy wprost

W pierwszych wierszach wypisujemy założenia. Kolejne wiersze tworzymy z poprzednich znanymi
regułami. Dowód kończy się, gdy jednym z wierszy jest teza.

### Dowód A — `((p → q) ∧ (q → r)) → (p → r)`

| Nr | Formuła | Uzasadnienie |
|---|---|---|
| 1 | `(p → q) ∧ (q → r)` | Założenie |
| 2 | `p` | Założenie |
| 3 | `p → q` | OK 1 |
| 4 | `q → r` | OK 1 |
| 5 | `q` | RO 2, 3 |
| 6 | `r` | RO 4, 5 |

### Dowód B — `(((p ∨ q) → (r ∨ s)) ∧ (p → ∼s) ∧ p) → r`

| Nr | Formuła | Uzasadnienie |
|---|---|---|
| 1 | `(p ∨ q) → (r ∨ s)` | Założenie |
| 2 | `p → ∼s` | Założenie |
| 3 | `p` | Założenie |
| 4 | `∼s` | RO 2, 3 |
| 5 | `p ∨ q` | DA 3 |
| 6 | `r ∨ s` | RO 1, 5 |
| 7 | `r` | OA 4, 6 |

## 4. Dowód założeniowy nie wprost

Do założeń dokładamy **zanegowaną tezę**. Dowód kończy się, gdy otrzymamy dwa sprzeczne wiersze
postaci `Φ` i `∼Φ`.

### Dowód C — `((p ∧ q) → r) → ((p ∧ ∼r) → ∼q)`

| Nr | Formuła | Uzasadnienie |
|---|---|---|
| 1 | `(p ∧ q) → r` | Założenie |
| 2 | `p ∧ ∼r` | Założenie |
| 3 | `q` | Z dow. nie wprost |
| 4 | `p` | OK 2 |
| 5 | `∼r` | OK 2 |
| 6 | `p ∧ q` | DK 3, 4 |
| 7 | `r` | RO 1, 6 |
| 8 | `Sprzeczność 5, 7` | — |

### Dowód D — `((p → q) ∧ (r → s) ∧ (p ∨ r)) → (q ∨ s)`

| Nr | Formuła | Uzasadnienie |
|---|---|---|
| 1 | `p → q` | Założenie |
| 2 | `r → s` | Założenie |
| 3 | `p ∨ r` | Założenie |
| 4 | `∼(q ∨ s)` | Z dow. nie wprost |
| 5 | `∼q` | DM1 4 |
| 6 | `∼s` | DM1 4 |
| 7 | `∼q → ∼p` | KP 1 |
| 8 | `∼s → ∼r` | KP 2 |
| 9 | `∼p` | RO 5, 7 |
| 10 | `∼r` | RO 6, 8 |
| 11 | `∼p ∧ ∼r` | DK 9, 10 |
| 12 | `∼(p ∨ r)` | DM2 11 |
| 13 | `Sprzeczność 3, 12` | — |

### Dowód E — `(((p ∨ q) → r) ∧ (r → s) ∧ (p ∨ q ∨ s)) → (∼p → s)`

| Nr | Formuła | Uzasadnienie |
|---|---|---|
| 1 | `(p ∨ q) → r` | Założenie |
| 2 | `r → s` | Założenie |
| 3 | `p ∨ q ∨ s` | Założenie |
| 4 | `∼p` | Założenie |
| 5 | `∼s` | Z dow. nie wprost |
| 6 | `p ∨ q` | OA 3, 5 |
| 7 | `r` | RO 1, 6 |
| 8 | `∼s → ∼r` | KP 2 |
| 9 | `∼r` | RO 5, 8 |
| 10 | `Sprzeczność 7, 9` | — |

### Dowód F — wielokrotne założenia: `((p → (q ∧ r)) ∧ (∼p → (s ∧ t)) ∧ ∼t) → q`

| Nr | Formuła | Uzasadnienie |
|---|---|---|
| 1 | `p → (q ∧ r)` | Założenie |
| 2 | `∼p → (s ∧ t)` | Założenie |
| 3 | `∼t` | Założenie |
| 4 | `∼q` | Z dow. nie wprost |
| 4.1 | `p` | Dodatkowe założenie |
| 4.2 | `q ∧ r` | RO 1, 4.1 |
| 4.3 | `q` | OK 4.2 |
| 4.4 | `Sprzeczność 4.3, 4` | — |
| 5.1 | `∼p` | Dodatkowe założenie |
| 5.2 | `s ∧ t` | RO 2, 5.1 |
| 5.3 | `t` | OK 5.2 |
| 5.4 | `Sprzeczność 3, 5.3` | — |

## 5. Niepoprawne rozumowania i kontrprzykład

Gdy w dowodzie nie wprost nie da się dojść do sprzeczności, rozumowanie jest niepoprawne.
Z wierszy dowodu odczytujemy wtedy **kontrprzykład**.

| Rozumowanie | Wiersze | Kontrprzykład |
|---|---|---|
| Azor nie jest psem, zatem nie jest zwierzęciem | 1: `p → q`, 2: `∼p`, 3: `q` | `p = 0`, `q = 1` (Azor-kot) |
| Prawa moralne i niepostępowanie według nich → niekonsekwencja → postępowanie złe. Zatem uznaję prawa i postępuję według nich → nie postępuję źle | 1: `(p ∧ ∼q) → r`, 2: `r → t`, 3: `p ∧ q`, 4: `t` | `p = 1`, `q = 1`, `t = 1`, `r` dowolne |

## 6. Reguła rezolucji

```
l1 ∨ l2 ∨ … ∨ p ∨ … ∨ ln
k1 ∨ k2 ∨ … ∨ ∼p ∨ … ∨ km
─────────────────────────────
l1 ∨ l2 ∨ … ∨ ln ∨ k1 ∨ k2 ∨ … ∨ km
```

`li`, `ki` to **literały** (zmienna zdaniowa albo jej negacja). We wniosku usuwamy powtarzające
się literały. Przykład z wykładu:

```
 p ∨ ∼r ∨ q ∨ s
 p ∨ t ∨ ∼q
───────────────
 p ∨ ∼r ∨ s ∨ t
```

## 7. Algorytm rezolucji

Chcemy pokazać, że `Ψ` wynika logicznie z `Φ1 … Φn`:

1. Sprowadź `Φ1 ∧ … ∧ Φn` oraz `∼Ψ` do **koniunkcyjnej postaci normalnej** (KPN).
2. Wypisz wszystkie otrzymane klauzule w kolejnych wierszach.
3. Stosuj systematycznie regułę rezolucji — także do nowo utworzonych wierszy.
4. Dowód kończy się, gdy powstanie para wierszy sprzecznych (teza udowodniona) albo gdy nie da
   się utworzyć żadnej nowej klauzuli (teza nie wynika z założeń).

### Przykład 1 — pokaż, że `p ∨ s` wynika z `p → q`, `r → s`, `p ∨ r`

KPN założeń: `(∼p ∨ q) ∧ (∼r ∨ s) ∧ (p ∨ r)`. Negacja tezy: `∼(p ∨ s) ≡ ∼p ∧ ∼s`.

| Nr | Klauzula | Skąd |
|---|---|---|
| 1 | `∼p ∨ q` | założenie `p → q` |
| 2 | `∼r ∨ s` | założenie `r → s` |
| 3 | `p ∨ r` | założenie `p ∨ r` |
| 4 | `∼p` | negacja tezy |
| 5 | `∼s` | negacja tezy |
| 6 | `q ∨ r` | 1, 3 (na `p`) |
| 7 | `p ∨ s` | 2, 3 (na `r`) |
| 8 | `∼r` | 2, 5 (na `s`) |
| 9 | `r` | 3, 4 (na `p`) |
| 10 | `Sprzeczność 8, 9` | — |

### Przykład 2 — założenia `p ∨ q`, `p → q`, `∼q ∨ r`, `∼r` są sprzeczne

| Nr | Klauzula | Skąd |
|---|---|---|
| 1 | `p ∨ q` | założenie |
| 2 | `∼p ∨ q` | założenie `p → q` |
| 3 | `∼q ∨ r` | założenie `∼q ∨ r` |
| 4 | `∼r` | założenie `∼r` |
| 5 | `q` | 1, 2 (na `p`) |
| 6 | `∼q` | 3, 4 (na `r`) |
| 7 | `Sprzeczność 5, 6` | — |
