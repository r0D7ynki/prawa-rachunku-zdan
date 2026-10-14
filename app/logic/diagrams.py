"""Rysunki na stronach praw: schemat bramek i diagram zbiorów (karta PRZ-123).

Rysunek powstaje w Pythonie, a nie w przeglądarce. Dzięki temu działa bez
JavaScriptu i da się go sprawdzić testem w ``tests/test_diagrams.py``.

Moduł dostaje drzewo formuły z :mod:`app.logic.formula` i oddaje napis
z elementem ``<svg>``. Wynik wstawiamy do szablonu przez ``markupsafe.Markup``
— to nasz HTML, nie dane użytkownika. Nazwy zmiennych i wzory przechodzą przez
``escape``, bo pochodzą z tekstu.

Dwie listy kroków prowadzą czytelnika przez wzór:

* :func:`kroki_gates` — bramki w kolejności liczenia (od zmiennych do całości),
* :func:`kroki_sets` — operacje na zbiorach: najpierw lewa strona prawa, potem
  prawa (karta PRZ-172).

Krok ``i`` (liczony od zera) pokazuje stan po ``i``-tej operacji, a ``krok=None``
znaczy „cała formuła”. Numer spoza listy jest przycinany do jej końców, tak jak
w komponencie kroków ``stepper.js``.

Karta PRZ-172 zmieniła rysunek zbiorów: zamiast jednego diagramu całego wzoru są
**dwa** — lewa i prawa strona prawa obok siebie, a lista kroków pod nimi nazywa
operację każdego kroku („Suma — p ∨ q — obszar, który pokrywa p albo q.”). Same
zmienne nie są już krokami: zbiór ``p`` nie jest operacją, tylko punktem wyjścia,
więc nie ma go ani na liście, ani w numeracji kroków.

Od karty PRZ-141 każdy krok rysunku zbiorów jest **widocznie inny** od poprzedniego:
obszar bieżącego kroku dzielimy na dwa kolory. Mocnym akcentem (``obszar-nowy``)
malujemy to, co dokłada bieżąca operacja, a słabym (``obszar-poprzedni``) — część,
która przyszła z kroku wcześniej. Suma obu warstw to zawsze obszar bieżącego kroku.
Nad rysunkiem stoi etykieta operacji („Suma — obszar, który pokrywa p albo q.”),
a schemat bramek zapala bramkę bieżącego kroku klasą ``bramka-aktywna``.

Karta PRZ-182 zmieniła kształt obszaru: zamiast dziesiątek prostokątów próbek jest
**jeden kontur** na obszar. Maskę próbkujemy gęsto (``KOLUMNY_SIATKI`` ×
``WIERSZE_SIATKI``), granicę wyznaczamy metodą marching squares, upraszczamy punkty
(Douglas–Peucker) i wygładzamy je krzywymi Béziera (Catmull–Rom). Krawędzie obszaru
są wtedy gładkie, a nie schodkowe.

Diagram zbiorów to teraz **dwa niezależne rysunki** — lewa i prawa strona prawa —
a każdy z nich ``wizualizacje.js`` prowadzi własnymi strzałkami (karta PRZ-182).
Funkcja :func:`sets_svg` rysuje jedną stronę; oba rysunki stawia partial
``_sets.html`` w osobnych figurach.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from markupsafe import Markup, escape

from app.logic.formula import (
    And,
    FormulaError,
    Iff,
    Imp,
    Node,
    Not,
    Or,
    Var,
    evaluate,
    subformulas,
    to_text,
    variables,
)

#: Najwięcej zbiorów, ile zmieści się na diagramie zbiorów.
MAX_ZBIOROW = 3

#: Gęstość siatki próbek diagramu zbiorów (karty PRZ-123 i PRZ-182).
#: Gęsta siatka daje kontur blisko prawdziwej granicy — patrz :func:`_kontury`.
KOLUMNY_SIATKI = 200
WIERSZE_SIATKI = 160

#: Rozmiar rysunku zbiorów w jednostkach ``viewBox``: cała przestrzeń to ten prostokąt.
SZEROKOSC_ZBIOROW = 440.0
WYSOKOSC_ZBIOROW = 360.0

#: Bok jednej komórki siatki próbek — siatka dzieli równo cały rysunek.
KROK_X = SZEROKOSC_ZBIOROW / KOLUMNY_SIATKI
KROK_Y = WYSOKOSC_ZBIOROW / WIERSZE_SIATKI

#: Ile jednostek ``viewBox`` wolno odchylić kontur przy upraszczaniu punktów (PRZ-182).
TOLERANCJA_KONTURU = 0.6

#: Ile razy dzielimy odcinek siatki, szukając miejsca przecięcia granicy (PRZ-182).
#: Cztery kroki bisekcji to dokładność lepsza niż 0,2 jednostki ``viewBox``, czyli
#: trzy razy lepsza niż tolerancja upraszczania konturu (``TOLERANCJA_KONTURU``).
KROKI_BISEKCJI = 4

#: Wysokość pasa nad rysunkiem zbiorów: mieści etykietę operacji (karta PRZ-141).
WYSOKOSC_ETYKIETY = 34

#: Układy kół dla jednego, dwóch i trzech zbiorów: ``(środek x, środek y, promień)``.
UKLADY: dict[int, tuple[tuple[float, float, float], ...]] = {
    1: ((SZEROKOSC_ZBIOROW / 2, WYSOKOSC_ZBIOROW / 2, 120.0),),
    2: ((160.0, 180.0, 110.0), (280.0, 180.0, 110.0)),
    3: ((160.0, 140.0, 100.0), (280.0, 140.0, 100.0), (220.0, 240.0, 100.0)),
}

#: Symbol operatora w prostokącie bramki (notacja z wykładu).
SYMBOLE: dict[type, str] = {Not: "∼", And: "∧", Or: "∨", Imp: "→", Iff: "≡"}

#: Nazwa operacji na zbiorach; trafia do opisu kroku i do słownika kroków.
OPERACJE: dict[type, str] = {
    Var: "zbiór",
    Not: "dopełnienie",
    And: "część wspólna",
    Or: "suma",
    Imp: "implikacja",
    Iff: "równoważność",
}

#: Strony prawa na diagramie zbiorów (karta PRZ-172). Pole ``strona`` kroku mówi,
#: na którym diagramie ten krok się dzieje.
LEWA = "lewa"
PRAWA = "prawa"

#: Nagłówki obu diagramów zbiorów (karta PRZ-172).
TYTUL_LEWEJ = "Lewa strona"
TYTUL_PRAWEJ = "Prawa strona"

#: Wartość logiczna słowem — kolor nigdy nie jest jedynym nośnikiem informacji.
PRAWDA = "PRAWDA"
FALSZ = "FAŁSZ"

# --- schemat bramek --------------------------------------------------------

#: Ścieżka w drzewie formuły: numery dzieci od korzenia, np. ``(0, 1)``.
#: Ścieżka mówi, o które **wystąpienie** wzoru chodzi — te same wzory mogą stać
#: w drzewie dwa razy („p ∨ p”), a każde wystąpienie ma własne miejsce (PRZ-182).
Sciezka = tuple[int, ...]

#: Bok prostokąta bramki i odstępy siatki układu (jednostki ``viewBox``).
BRAMKA_SZEROKOSC = 52
BRAMKA_WYSOKOSC = 32
ODSTEP_X = 96
ODSTEP_Y = 64
MARGINES = 24


def _dzieci(node: Node) -> tuple[Node, ...]:
    """Dzieci węzła; ``Var`` nie ma dzieci (tak samo jak w ``formula``)."""
    if isinstance(node, Var):
        return ()
    if isinstance(node, Not):
        return (node.child,)
    return (node.left, node.right)


def _slowo(wartosc: bool) -> str:
    """Wartość logiczna słowem: ``PRAWDA`` albo ``FAŁSZ``."""
    return PRAWDA if wartosc else FALSZ


def _cyfra(wartosc: bool) -> str:
    """Wartość logiczna cyfrą z wykładu: ``1`` albo ``0``."""
    return "1" if wartosc else "0"


def _sprawdz_wartosci(node: Node, wartosci: dict[str, bool]) -> None:
    """Sprawdza, że wartościowanie opisuje wszystkie zmienne formuły."""
    brakujace = [nazwa for nazwa in variables(node) if nazwa not in wartosci]
    if brakujace:
        raise FormulaError("Brakuje wartości zmiennych: " + ", ".join(brakujace) + ".")


def _uklad(node: Node) -> tuple[dict[Sciezka, int], dict[Sciezka, float]]:
    """Układa bramki: kolumna to głębokość w drzewie, wiersz — kolejność liści.

    Liście dostają kolejne wiersze od góry, a bramka stoi w środku swoich dzieci
    (średnia wierszy), więc przewody nie krzyżują się bez potrzeby.

    Kluczem jest **wystąpienie** w drzewie (``Sciezka``), a nie sam węzeł: gdy ten
    sam wzór stoi w drzewie dwa razy („p ∨ p”), każde wystąpienie ma własny wiersz
    i własny prostokąt. Bez tego oba przewody i oba napisy trafiłyby w to samo
    miejsce (karta PRZ-182).
    """
    kolumny: dict[Sciezka, int] = {}
    rzedy: dict[Sciezka, float] = {}
    kolejny = [0]

    def odwiedz(biezacy: Node, sciezka: Sciezka) -> None:
        dzieci = _dzieci(biezacy)
        if not dzieci:
            kolumny[sciezka] = 0
            rzedy[sciezka] = float(kolejny[0])
            kolejny[0] += 1
            return
        for numer, dziecko in enumerate(dzieci):
            odwiedz(dziecko, (*sciezka, numer))
        podsciezki = [(*sciezka, numer) for numer in range(len(dzieci))]
        kolumny[sciezka] = 1 + max(kolumny[podsciezka] for podsciezka in podsciezki)
        rzedy[sciezka] = sum(rzedy[podsciezka] for podsciezka in podsciezki) / len(dzieci)

    odwiedz(node, ())
    return kolumny, rzedy


def _srodek(kolumna: int, rzad: float) -> tuple[float, float]:
    """Środek prostokąta bramki na rysunku."""
    x = MARGINES + kolumna * ODSTEP_X + BRAMKA_SZEROKOSC / 2
    y = MARGINES + rzad * ODSTEP_Y + BRAMKA_WYSOKOSC / 2
    return x, y


def _prostokat(x: float, y: float, klasa: str, napis: str, tytul: str) -> str:
    """Prostokąt bramki albo zmiennej razem z jej napisem i opisem słownym.

    ``<title>`` niesie wartość słowami, więc kolor i grubość krawędzi nigdy nie
    są jedynym nośnikiem informacji (karta PRZ-141).
    """
    return (
        f'      <g class="{klasa}">\n'
        f"        <title>{tytul}</title>\n"
        f'        <rect class="wiz-ksztalt" x="{x - BRAMKA_SZEROKOSC / 2:g}" '
        f'y="{y - BRAMKA_WYSOKOSC / 2:g}" width="{BRAMKA_SZEROKOSC}" '
        f'height="{BRAMKA_WYSOKOSC}" rx="6" />\n'
        f'        <text class="wiz-symbol" x="{x:g}" y="{y:g}" text-anchor="middle" '
        f'dominant-baseline="central">{napis}</text>\n'
        f"      </g>"
    )


def _opis_prostokata(czesc: Node, wartosc: bool | None) -> str:
    """Opis bramki słowami: co to za bramka i jaką ma wartość."""
    nazwa = (
        f"Zmienna {czesc.name}"
        if isinstance(czesc, Var)
        else f"Bramka {SYMBOLE[type(czesc)]} dla {to_text(czesc)}"
    )
    if wartosc is None:
        return f"{nazwa}: wartość jeszcze nieznana."
    return f"{nazwa}: {_slowo(wartosc)} ({_cyfra(wartosc)})."


def _przewod(
    od: tuple[float, float],
    do: tuple[float, float],
    wartosc: bool | None,
    opis: str,
    krok: int,
    aktywny: bool = False,
) -> str:
    """Przewód ze strzałką na końcu i wartością w ``<title>`` (słowami).

    ``aktywny`` znaczy „to przewód wejściowy bramki bieżącego kroku”: taki
    przewód dostaje klasę ``przewod-aktywny``, a jego wartość piszemy słowami,
    nie cyfrą — widać, co zasila bramkę, którą właśnie liczymy (karta PRZ-141).

    Przewód idzie prosto, potem **między kolumnami bramek** („przejazd”), a nie
    środkiem odcinka: inaczej długi przewód — od liścia do bramki o dwie kolumny
    dalej — przecinałby bramki stojące po drodze, a jego napis lądowałby
    w prostokącie bramki (karta PRZ-182).
    """
    x1 = od[0] + BRAMKA_SZEROKOSC / 2
    y1 = od[1]
    x2 = do[0] - BRAMKA_SZEROKOSC / 2
    y2 = do[1]
    przejazd = do[0] - ODSTEP_X / 2
    sciezka = f"M {x1:g} {y1:g} H {przejazd:g} V {y2:g} H {x2:g}"
    if wartosc is None:
        klasa = "wiz-przewod wiz-nieznane"
        tytul = f"Przewód z {opis}: wartość jeszcze nieznana."
        znaczek = "?"
    else:
        klasa = "wiz-przewod " + ("wiz-prawda" if wartosc else "wiz-falsz")
        tytul = f"Przewód z {opis}: {_slowo(wartosc)} ({_cyfra(wartosc)})."
        znaczek = _slowo(wartosc) if aktywny else _cyfra(wartosc)
    if aktywny:
        klasa += " przewod-aktywny"
    klasa_znaczka = "wiz-wartosc" + (" wiz-wartosc-slownie" if aktywny else "")
    return (
        f"      <g>\n"
        f'        <path class="{klasa}" d="{sciezka}" '
        f'marker-end="url(#{_id_grota(wartosc, krok)})"><title>{tytul}</title></path>\n'
        f'        <text class="{klasa_znaczka}" x="{przejazd:g}" y="{(y1 + y2) / 2 - 6:g}" '
        f'text-anchor="middle">{znaczek}</text>\n'
        f"      </g>"
    )


def _id_grota(wartosc: bool | None, krok: int) -> str:
    """Identyfikator grota strzałki; wartość nieznana ma własny, wygaszony grot.

    Numer kroku w nazwie sprawia, że każdy rysunek na stronie ma własne
    identyfikatory — powtórzone ``id`` myliłyby przeglądarkę i test.
    """
    if wartosc is None:
        return f"wiz-grot-nieznany-{krok}"
    return f"wiz-grot-{'prawda' if wartosc else 'falsz'}-{krok}"


def _defs(krok: int) -> str:
    """Groty strzałek: po jednym na wartość przewodu."""
    groty = ""
    for nazwa in ("prawda", "falsz", "nieznany"):
        identyfikator = f"wiz-grot-{nazwa}-{krok}"
        groty += (
            f'      <marker id="{identyfikator}" markerWidth="9" markerHeight="9" refX="8" '
            f'refY="4.5" orient="auto" markerUnits="strokeWidth">\n'
            f'        <path class="wiz-grot {identyfikator}" d="M 0 0 L 9 4.5 L 0 9 z" />\n'
            f"      </marker>\n"
        )
    return "    <defs>\n" + groty + "    </defs>"


def kroki_gates(node: Node) -> list[dict]:
    """Kroki schematu bramek: od zmiennych do całej formuły.

    Jeden krok to jedna podformuła (``formula.subformulas``), więc kolejność jest
    kolejnością liczenia. Pole ``bramka`` to numer kroku liczony od jednego.
    """
    return [
        {"opis": _opis_bramki(czesc), "bramka": numer}
        for numer, czesc in enumerate(subformulas(node), start=1)
    ]


def _opis_bramki(czesc: Node) -> str:
    """Zdanie po polsku opisujące bramkę tego kroku."""
    wzor = to_text(czesc)
    if isinstance(czesc, Var):
        return f"Zapisujemy wartość zmiennej {czesc.name}."
    if isinstance(czesc, Not):
        return f"Negacja: {wzor} jest prawdziwe, gdy {to_text(czesc.child)} jest fałszywe."
    if isinstance(czesc, And):
        return f"Koniunkcja: {wzor} jest prawdziwa tylko wtedy, gdy oba zdania są prawdziwe."
    if isinstance(czesc, Or):
        return f"Alternatywa: {wzor} jest prawdziwa, gdy choć jedno zdanie jest prawdziwe."
    if isinstance(czesc, Imp):
        return f"Implikacja: {wzor} jest fałszywa tylko wtedy, gdy zachodzi 1 → 0."
    return f"Równoważność: {wzor} jest prawdziwa, gdy obie strony mają tę samą wartość."


def gates_svg(node: Node, wartosci: dict[str, bool], krok: int | None = None) -> Markup:
    """Rysuje schemat bramek dla wartościowania ``wartosci``.

    Wartości podformuł liczy :func:`app.logic.formula.evaluate`. Gdy podano ``krok``
    (indeks w :func:`kroki_gates`), bramki policzone później pokazują ``?`` i mają
    przecięty przewód — widać, że wynik jeszcze nie zapadł.

    Krok ``i`` zapala bramki swojego wzoru: prostokąt ma klasę ``bramka-aktywna``,
    a przewody wejściowe ``przewod-aktywny``. Bramki policzone wcześniej mają
    ``bramka-policzona``, więc różnica między krokami jest widoczna bez czytania
    opisu (karta PRZ-141). Gdy ten sam wzór stoi w drzewie dwa razy („p ∨ p”),
    zapalają się oba jego prostokąty — to ten sam krok liczenia (karta PRZ-182).
    """
    _sprawdz_wartosci(node, wartosci)
    kolumny, rzedy = _uklad(node)
    czesci = subformulas(node)
    numer_kroku = _przytnij(krok, len(czesci))
    znane = set(czesci[: numer_kroku + 1])
    biezaca = czesci[numer_kroku]

    szerokosc = MARGINES * 2 + max(kolumny.values()) * ODSTEP_X + BRAMKA_SZEROKOSC
    wysokosc = MARGINES * 2 + max(rzedy.values()) * ODSTEP_Y + BRAMKA_WYSOKOSC

    elementy: list[str] = []
    for (sciezka_rodzica, rodzic), (sciezka_dziecka, dziecko) in _krawedzie(node):
        wartosc = evaluate(dziecko, wartosci) if dziecko in znane else None
        elementy.append(
            _przewod(
                _srodek(kolumny[sciezka_dziecka], rzedy[sciezka_dziecka]),
                _srodek(kolumny[sciezka_rodzica], rzedy[sciezka_rodzica]),
                wartosc,
                to_text(dziecko),
                numer_kroku,
                aktywny=rodzic == biezaca,
            )
        )

    for sciezka, czesc in _wezly(node):
        x, y = _srodek(kolumny[sciezka], rzedy[sciezka])
        klasa = "wiz-bramka"
        if isinstance(czesc, Var):
            klasa += " wiz-zmienna"
            napis = escape(czesc.name)
        else:
            napis = SYMBOLE[type(czesc)]
        if czesc == biezaca:
            klasa += " wiz-biezaca bramka-aktywna"
        elif czesc in znane:
            klasa += " wiz-znana bramka-policzona"
        wartosc = evaluate(czesc, wartosci) if czesc in znane else None
        elementy.append(_prostokat(x, y, klasa, napis, _opis_prostokata(czesc, wartosc)))

    tytul = f"Schemat bramek dla wzoru {to_text(node)}. Krok {numer_kroku + 1}: {to_text(biezaca)}."
    return Markup(
        f'<svg class="wiz-svg wiz-svg-bramki" viewBox="0 0 {szerokosc:g} {wysokosc:g}" '
        f'preserveAspectRatio="xMidYMid meet" role="img" aria-label="{escape(tytul)}">\n'
        f"    <title>{tytul}</title>\n"
        f"{_defs(numer_kroku)}\n"
        + "\n".join(elementy)
        + f'\n    <text class="wiz-wartosc wiz-legenda-svg" x="{MARGINES}" y="{wysokosc - 6:g}">'
        f"{PRAWDA} = 1, {FALSZ} = 0</text>\n</svg>"
    )


def _przytnij(krok: int | None, ile: int) -> int:
    """Zamienia ``krok`` na poprawny indeks listy kroków (``None`` = ostatni)."""
    if krok is None:
        return ile - 1
    return max(0, min(krok, ile - 1))


def _wezly(node: Node, sciezka: Sciezka = ()) -> list[tuple[Sciezka, Node]]:
    """Wszystkie wystąpienia węzłów drzewa, dzieci przed rodzicem."""
    wynik: list[tuple[Sciezka, Node]] = []
    for numer, dziecko in enumerate(_dzieci(node)):
        wynik.extend(_wezly(dziecko, (*sciezka, numer)))
    wynik.append((sciezka, node))
    return wynik


def _krawedzie(
    node: Node, sciezka: Sciezka = ()
) -> list[tuple[tuple[Sciezka, Node], tuple[Sciezka, Node]]]:
    """Pary ``(rodzic, dziecko)`` — z nich powstają przewody."""
    wynik: list[tuple[tuple[Sciezka, Node], tuple[Sciezka, Node]]] = []
    for numer, dziecko in enumerate(_dzieci(node)):
        podsciezka = (*sciezka, numer)
        wynik.append(((sciezka, node), (podsciezka, dziecko)))
        wynik.extend(_krawedzie(dziecko, podsciezka))
    return wynik


# --- diagram zbiorów -------------------------------------------------------


def strony(node: Node) -> tuple[Node, Node]:
    """Lewa i prawa strona prawa (karta PRZ-172).

    Równoważność ma je jako dzieci. Wzór, który nią nie jest, stoi po obu
    stronach — dzięki temu sekcja rysunków nie znika z nietypowej treści.
    """
    if isinstance(node, Iff):
        return node.left, node.right
    return node, node


def operacje_zbiorow(node: Node) -> list[Node]:
    """Podformuły będące operacją na zbiorach — bez samych zmiennych.

    Karta PRZ-172: punkt listy kroków nazywa operację, a zbiór ``p`` nie jest
    operacją, tylko punktem wyjścia. Krok ``i`` rysunku to ``i``-ta operacja
    z tej listy, więc numer kroku znaczy to samo na liście i na rysunku.
    """
    return [czesc for czesc in subformulas(node) if not isinstance(czesc, Var)]


def kroki_sets(node: Node) -> list[dict]:
    """Kroki obu diagramów zbiorów: operacje lewej strony, potem prawej (PRZ-172).

    Jeden krok to jedna operacja na zbiorach (:func:`operacje_zbiorow`). Kolejność
    jest kolejnością nauki: czytelnik przechodzi najpierw lewą stronę prawa, potem
    prawą, a ostatni krok domyka obie. Pola kroku: ``operacja`` („suma”,
    „dopełnienie”, …), ``wzor`` (tekst formuły po kroku), ``opis`` (co obejmuje
    obszar) i ``strona`` (``LEWA`` albo ``PRAWA``).
    """
    lewa, prawa = strony(node)
    grupy = [(LEWA, operacje_zbiorow(lewa))]
    if prawa is not lewa:
        grupy.append((PRAWA, operacje_zbiorow(prawa)))
    return [
        {
            "operacja": OPERACJE[type(czesc)],
            "wzor": to_text(czesc),
            "opis": _opis_obszaru(czesc),
            "strona": strona,
        }
        for strona, czesci in grupy
        for czesc in czesci
    ]


def krok_punktu_wyjscia(node: Node) -> dict:
    """Jeden krok dla strony prawa bez operacji — sam zbiór jako punkt wyjścia.

    Prawa strona prawa bywa pojedynczą zmienną („∼∼p ≡ p”), a wtedy nie ma czego
    liczyć. Taki diagram dostaje jeden krok z całym wzorem, żeby **każdy** diagram
    miał własne strzałki i własną listę kroków (karta PRZ-182).
    """
    return {
        "operacja": OPERACJE[type(node)],
        "wzor": to_text(node),
        "opis": _opis_obszaru(node),
    }


def _opis_obszaru(czesc: Node) -> str:
    """Co obejmuje obszar tego kroku — zdanie bez nazwy operacji.

    Nazwę operacji i wzór dokłada punkt listy kroków (``laws._punkt_kroku``),
    żeby napis brzmiał „Dopełnienie — ∼(p ∨ q) — obszar poza zbiorem p ∨ q.”
    (karta PRZ-172).
    """
    if isinstance(czesc, Var):
        return f"całe koło zbioru {czesc.name}."
    if isinstance(czesc, Not):
        return f"obszar poza zbiorem {to_text(czesc.child)}."
    if isinstance(czesc, And):
        return f"obszar wspólny zbiorów {to_text(czesc.left)} i {to_text(czesc.right)}."
    if isinstance(czesc, Or):
        return f"obszar, który pokrywa {to_text(czesc.left)} albo {to_text(czesc.right)}."
    if isinstance(czesc, Imp):
        lewa, prawa = to_text(czesc.left), to_text(czesc.right)
        return f"obszar {lewa} mieści się w obszarze {prawa}."
    return f"oba obszary wzoru {to_text(czesc)} pokrywają się."


def _opis_zbioru(czesc: Node) -> str:
    """Zdanie po polsku opisujące operację na zbiorach — opis rysunku dla czytnika."""
    wzor = to_text(czesc)
    if isinstance(czesc, Var):
        return f"Zaznaczamy zbiór {czesc.name}."
    if isinstance(czesc, Not):
        return f"Dopełnienie: bierzemy wszystko poza zbiorem {to_text(czesc.child)}."
    if isinstance(czesc, And):
        return f"Część wspólna zbiorów {to_text(czesc.left)} i {to_text(czesc.right)}."
    if isinstance(czesc, Or):
        return f"Suma zbiorów {to_text(czesc.left)} i {to_text(czesc.right)}."
    if isinstance(czesc, Imp):
        lewa, prawa = to_text(czesc.left), to_text(czesc.right)
        return f"Implikacja: obszar {lewa} mieści się w obszarze {prawa}."
    return f"Równoważność: obie strony wzoru {wzor} wskazują ten sam obszar."


def _w_kole(probka: tuple[float, float], kolo: tuple[float, float, float]) -> bool:
    """Czy próbka leży w kole zbioru."""
    odleglosc = (probka[0] - kolo[0]) ** 2 + (probka[1] - kolo[1]) ** 2
    return odleglosc <= kolo[2] ** 2


def _srodek_probki(wiersz: float, kolumna: float) -> tuple[float, float]:
    """Punkt rysunku o zadanych współrzędnych siatki (środek próbki).

    Próbki spoza siatki ścinamy do krawędzi rysunku — są tam puste (patrz
    ``_przynaleznosc``), więc kontur dopełnienia domyka się wzdłuż prostokąta,
    a nie wychodzi poza rysunek.
    """
    x = min(max((kolumna + 0.5) * KROK_X, 0.0), SZEROKOSC_ZBIOROW)
    y = min(max((wiersz + 0.5) * KROK_Y, 0.0), WYSOKOSC_ZBIOROW)
    return x, y


def _bity_probki(punkt: tuple[float, float], uklad: tuple[tuple[float, float, float], ...]) -> int:
    """Które koła pokrywają ten punkt — jeden bit na zmienną."""
    return sum(1 << indeks for indeks, kolo in enumerate(uklad) if _w_kole(punkt, kolo))


def _wartosci_z_bitow(bity: int, zmienne: tuple[str, ...]) -> dict[str, bool]:
    """Zamienia bity przynależności na wartościowanie dla ``formula.evaluate``."""
    return {nazwa: bool(bity & (1 << indeks)) for indeks, nazwa in enumerate(zmienne)}


@lru_cache(maxsize=4)
def _przynaleznosc(
    zmienne: tuple[str, ...], uklad: tuple[tuple[float, float, float], ...]
) -> tuple[tuple[int, ...], ...]:
    """Dla każdej próbki siatki mówi, które koła ją pokrywają (bity po zmiennych).

    Siatka zależy tylko od układu kół, a nie od wzoru, więc liczymy ją raz i wracamy
    do niej po wynik dla każdej formuły (karta PRZ-182).
    """
    return tuple(
        tuple(
            _bity_probki(_srodek_probki(wiersz, kolumna), uklad)
            for kolumna in range(KOLUMNY_SIATKI)
        )
        for wiersz in range(WIERSZE_SIATKI)
    )


@lru_cache(maxsize=16)
def _obszar(
    node: Node, zmienne: tuple[str, ...], uklad: tuple[tuple[float, float, float], ...]
) -> tuple[tuple[bool, ...], ...]:
    """Siatka próbek: dla każdej próbki mówi, czy formuła jest w niej prawdziwa.

    Przynależność próbki do koła to wartość zmiennej, więc formuła liczy się
    zwykłym :func:`app.logic.formula.evaluate` — ten sam kod co tablica prawdy.
    Wynik zależy tylko od tego, które koła pokrywają próbkę, więc dla każdej
    kombinacji kół liczymy formułę **raz**, a nie dla każdej z 32000 próbek
    (karta PRZ-182).
    """
    tabela: dict[int, bool] = {}
    wynik: list[tuple[bool, ...]] = []
    for linia in _przynaleznosc(zmienne, uklad):
        for bity in linia:
            if bity not in tabela:
                tabela[bity] = evaluate(node, _wartosci_z_bitow(bity, zmienne))
        wynik.append(tuple(tabela[bity] for bity in linia))
    return tuple(wynik)


def _roznica(
    siatka: tuple[tuple[bool, ...], ...], odjac: tuple[tuple[bool, ...], ...]
) -> tuple[tuple[bool, ...], ...]:
    """Próbki prawdziwe w pierwszej siatce, a fałszywe w drugiej."""
    return tuple(
        tuple(wartosc and not odjeta for wartosc, odjeta in zip(linia, odjac_linia, strict=True))
        for linia, odjac_linia in zip(siatka, odjac, strict=True)
    )


def _czesc_wspolna(
    a: tuple[tuple[bool, ...], ...], b: tuple[tuple[bool, ...], ...]
) -> tuple[tuple[bool, ...], ...]:
    """Próbki prawdziwe w obu siatkach."""
    return tuple(
        tuple(x and y for x, y in zip(linia_a, linia_b, strict=True))
        for linia_a, linia_b in zip(a, b, strict=True)
    )


def _nalezy_do(
    node: Node, zmienne: tuple[str, ...], uklad: tuple[tuple[float, float, float], ...]
) -> Callable[[tuple[float, float]], bool]:
    """Funkcja mówiąca, czy formuła jest prawdziwa w dowolnym punkcie rysunku.

    Przydaje się między próbkami: kontur trafia w prawdziwą granicę obszaru dzięki
    bisekcji (``_przejscie``), a do tego trzeba umieć policzyć formułę w środku
    odcinka siatki (karta PRZ-182).
    """

    def nalezy(punkt: tuple[float, float]) -> bool:
        wartosci = {nazwa: _w_kole(punkt, uklad[indeks]) for indeks, nazwa in enumerate(zmienne)}
        return evaluate(node, wartosci)

    return nalezy


# --- kontur obszaru: marching squares, upraszczanie i wygładzanie (PRZ-182) --


def _przejscie(
    od: tuple[float, float],
    do: tuple[float, float],
    wartosc_od: bool,
    wartosc_do: bool,
    nalezy: Callable[[tuple[float, float]], bool],
) -> tuple[float, float]:
    """Punkt na odcinku między próbkami, w którym zmienia się przynależność.

    Różnica wartości na końcach mówi, że granica przechodzi przez ten odcinek.
    Miejsce przecięcia liczymy bisekcją, żeby kontur szedł po prawdziwej granicy,
    a nie po schodkach siatki.

    ``wartosc_od`` i ``wartosc_do`` to znane wartości próbek. Dla próbek spoza
    siatki są one z góry ustalone (``False``), więc bisekcja prowadzi punkt do
    krawędzi rysunku — tam obszar się kończy.
    """
    for _ in range(KROKI_BISEKCJI):
        srodek = ((od[0] + do[0]) / 2, (od[1] + do[1]) / 2)
        if nalezy(srodek) == wartosc_do:
            do = srodek
        else:
            od = srodek
    return ((od[0] + do[0]) / 2, (od[1] + do[1]) / 2)


def _odleglosc_od_odcinka(
    punkt: tuple[float, float], poczatek: tuple[float, float], koniec: tuple[float, float]
) -> float:
    """Odległość punktu od odcinka — miara błędu przy upraszczaniu konturu."""
    dlugosc = (koniec[0] - poczatek[0]) ** 2 + (koniec[1] - poczatek[1]) ** 2
    if dlugosc == 0:
        return ((punkt[0] - poczatek[0]) ** 2 + (punkt[1] - poczatek[1]) ** 2) ** 0.5
    udzial = (
        (punkt[0] - poczatek[0]) * (koniec[0] - poczatek[0])
        + (punkt[1] - poczatek[1]) * (koniec[1] - poczatek[1])
    ) / dlugosc
    udzial = min(max(udzial, 0.0), 1.0)
    rzut = (
        poczatek[0] + udzial * (koniec[0] - poczatek[0]),
        poczatek[1] + udzial * (koniec[1] - poczatek[1]),
    )
    return ((punkt[0] - rzut[0]) ** 2 + (punkt[1] - rzut[1]) ** 2) ** 0.5


def _uprosc_lamana(
    punkty: list[tuple[float, float]], tolerancja: float
) -> list[tuple[float, float]]:
    """Douglas–Peucker dla otwartej łamanej: zostawia punkty wyznaczające kształt."""
    if len(punkty) < 3:
        return punkty
    zostaje = {0, len(punkty) - 1}
    stos = [(0, len(punkty) - 1)]
    while stos:
        poczatek, koniec = stos.pop()
        najgorszy, najdalszy = tolerancja, None
        for indeks in range(poczatek + 1, koniec):
            odleglosc = _odleglosc_od_odcinka(punkty[indeks], punkty[poczatek], punkty[koniec])
            if odleglosc > najgorszy:
                najgorszy, najdalszy = odleglosc, indeks
        if najdalszy is not None:
            zostaje.add(najdalszy)
            stos.append((poczatek, najdalszy))
            stos.append((najdalszy, koniec))
    return [punkt for indeks, punkt in enumerate(punkty) if indeks in zostaje]


def _uprosc_kontur(
    punkty: list[tuple[float, float]], tolerancja: float
) -> list[tuple[float, float]]:
    """Upraszcza **zamknięty** kontur: dzieli go na dwie łamane i upraszcza obie.

    Kontur nie ma początku ani końca, więc za punkty zaczepienia bierzemy pierwszy
    punkt i ten leżący najdalej od niego. Inaczej upraszczanie przyciskałoby cały
    kontur do pierwszego punktu (karta PRZ-182).
    """
    if len(punkty) < 4:
        return punkty
    poczatek = punkty[0]
    najdalszy = max(
        range(1, len(punkty)),
        key=lambda indeks: (
            (punkty[indeks][0] - poczatek[0]) ** 2 + (punkty[indeks][1] - poczatek[1]) ** 2
        ),
    )
    pierwsza = _uprosc_lamana(punkty[: najdalszy + 1], tolerancja)
    druga = _uprosc_lamana(punkty[najdalszy:] + [poczatek], tolerancja)
    return pierwsza[:-1] + druga[:-1]


def _krzywa(
    sterujacy_1: tuple[float, float],
    sterujacy_2: tuple[float, float],
    koniec: tuple[float, float],
) -> str:
    """Polecenie ``C`` SVG: krzywa Béziera przez dwa punkty sterujące do końca.

    Współrzędne zaokrąglamy do jednego miejsca po kropce — ścieżka jest wtedy
    krótsza, a różnicy nie widać w skali rysunku (karta PRZ-182).
    """
    punkty = (sterujacy_1, sterujacy_2, koniec)
    return "C " + " ".join("{:.1f} {:.1f}".format(*punkt) for punkt in punkty)


def _sciezka(punkty: list[tuple[float, float]]) -> str:
    """Ścieżka SVG przez kontur: łuki Béziera z punktów Catmull–Rom, domknięte ``Z``.

    Krzywe przechodzą dokładnie przez punkty konturu, a wygładzają kąty między
    nimi — dlatego obszar nie ma już schodków (karta PRZ-182).
    """
    if len(punkty) < 3:
        return ""
    ile = len(punkty)
    czesci = ["M {:.1f} {:.1f}".format(*punkty[0])]
    for indeks in range(ile):
        poprzedni = punkty[indeks - 1]
        nastepny = punkty[(indeks + 1) % ile]
        dalszy = punkty[(indeks + 2) % ile]
        sterujacy_1 = (
            punkty[indeks][0] + (nastepny[0] - poprzedni[0]) / 6,
            punkty[indeks][1] + (nastepny[1] - poprzedni[1]) / 6,
        )
        sterujacy_2 = (
            nastepny[0] - (dalszy[0] - punkty[indeks][0]) / 6,
            nastepny[1] - (dalszy[1] - punkty[indeks][1]) / 6,
        )
        czesci.append(_krzywa(sterujacy_1, sterujacy_2, nastepny))
    czesci.append("Z")
    return " ".join(czesci)


#: Dwa narożniki każdej krawędzi komórki — przesunięcia względem jej narożnika
#: północno-zachodniego. Wspólna krawędź dwóch komórek ma jedno miejsce przecięcia.
KRAWEDZIE_KOMORKI: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "polnocna": ((0, 0), (0, 1)),
    "wschodnia": ((0, 1), (1, 1)),
    "poludniowa": ((1, 0), (1, 1)),
    "zachodnia": ((0, 0), (1, 0)),
}

#: Przypadki marching squares (bity narożników: 1 = północno-zachodni, 2 = północno-wschodni,
#: 4 = południowo-wschodni, 8 = południowo-zachodni): odcinki konturu w tej komórce.
#: Przypadki 0 i 15 nie mają odcinków, a 5 i 10 rozstrzyga środek komórki (``KONTUR_SIODLO``).
KONTUR_KOMORKI: dict[int, tuple[tuple[str, str], ...]] = {
    1: (("zachodnia", "polnocna"),),
    2: (("polnocna", "wschodnia"),),
    3: (("zachodnia", "wschodnia"),),
    4: (("wschodnia", "poludniowa"),),
    6: (("polnocna", "poludniowa"),),
    7: (("zachodnia", "poludniowa"),),
    8: (("poludniowa", "zachodnia"),),
    9: (("polnocna", "poludniowa"),),
    11: (("wschodnia", "poludniowa"),),
    12: (("wschodnia", "zachodnia"),),
    13: (("polnocna", "wschodnia"),),
    14: (("zachodnia", "polnocna"),),
}

#: Przypadki niejednoznaczne: dwa narożniki po przekątnej należą do obszaru, a dwa nie.
#: O tym, które narożniki łączy kontur, mówi wartość formuły w środku komórki.
KONTUR_SIODLO: dict[tuple[int, bool], tuple[tuple[str, str], ...]] = {
    (5, True): (("polnocna", "wschodnia"), ("poludniowa", "zachodnia")),
    (5, False): (("polnocna", "zachodnia"), ("wschodnia", "poludniowa")),
    (10, True): (("polnocna", "zachodnia"), ("wschodnia", "poludniowa")),
    (10, False): (("polnocna", "wschodnia"), ("poludniowa", "zachodnia")),
}


def _probka_wewnatrz(wiersz: int, kolumna: int, siatka: tuple[tuple[bool, ...], ...]) -> bool:
    """Czy próbka o tych współrzędnych siatki należy do obszaru.

    Próbki spoza siatki są puste: obszar kończy się na krawędzi rysunku, więc
    kontur dopełnienia („wszystko poza zbiorem p”) domyka się wzdłuż prostokąta.
    """
    if _w_siatce(wiersz, kolumna):
        return siatka[wiersz][kolumna]
    return False


def _w_siatce(wiersz: int, kolumna: int) -> bool:
    """Czy próbka leży na siatce — próbki spoza siatki są puste (karta PRZ-182)."""
    return 0 <= wiersz < WIERSZE_SIATKI and 0 <= kolumna < KOLUMNY_SIATKI


def _petle(
    odcinki: list[tuple[tuple[float, float], tuple[float, float]]],
) -> list[list[tuple[float, float]]]:
    """Składa odcinki konturu w zamknięte pętle.

    Każde miejsce przecięcia jest końcem dokładnie dwóch odcinków, więc wystarczy
    przejść z odcinka na odcinek, aż wrócimy do punktu startowego (karta PRZ-182).
    """
    sasiedzi: dict[tuple[float, float], list[tuple[float, float]]] = {}
    for punkt, drugi in odcinki:
        sasiedzi.setdefault(punkt, []).append(drugi)
        sasiedzi.setdefault(drugi, []).append(punkt)

    zuzyte: set[frozenset[tuple[float, float]]] = set()
    petle: list[list[tuple[float, float]]] = []
    for odcinek in odcinki:
        if frozenset(odcinek) in zuzyte:
            continue
        zuzyte.add(frozenset(odcinek))
        petla = [odcinek[0], odcinek[1]]
        while True:
            biezacy = petla[-1]
            nastepny = next(
                (
                    sasiad
                    for sasiad in sasiedzi[biezacy]
                    if frozenset((biezacy, sasiad)) not in zuzyte
                ),
                None,
            )
            if nastepny is None:
                break
            zuzyte.add(frozenset((biezacy, nastepny)))
            if nastepny == petla[0]:
                # Wróciliśmy do początku — pętla się domknęła i nie dokładamy
                # punktu początkowego drugi raz (karta PRZ-182).
                break
            petla.append(nastepny)
        petle.append(petla)
    return petle


def _kontury(
    siatka: tuple[tuple[bool, ...], ...], nalezy: Callable[[tuple[float, float]], bool]
) -> list[list[tuple[float, float]]]:
    """Granica obszaru: zamknięte kontury wyznaczone metodą marching squares.

    Dla każdej komórki siatki patrzymy na jej cztery narożniki. Gdy część z nich
    należy do obszaru, a część nie, przez komórkę przechodzi kontur — zbieramy te
    odcinki i składamy z nich pętle. Miejsce przecięcia na każdej krawędzi liczymy
    raz (``_przejscie``), więc sąsiednie komórki trafiają w ten sam punkt.

    Pusty obszar nie ma żadnej komórki z odcinkiem, więc zwracamy pustą listę.
    """
    granice = _granice_obszaru(siatka)
    if granice is None:
        return []
    od_wiersza, do_wiersza, od_kolumny, do_kolumny = granice
    ramka = _siatka_z_ramka(siatka)
    przejscia: dict[frozenset[tuple[int, int]], tuple[float, float]] = {}
    odcinki: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for wiersz in range(od_wiersza, do_wiersza + 1):
        gora = ramka[wiersz + 1]
        dol = ramka[wiersz + 2]
        for kolumna in range(od_kolumny, do_kolumny + 1):
            przypadek = (
                gora[kolumna + 1]
                | (gora[kolumna + 2] << 1)
                | (dol[kolumna + 2] << 2)
                | (dol[kolumna + 1] << 3)
            )
            if przypadek in (0, 15):
                continue
            if przypadek in (5, 10):
                srodek_wewnatrz = nalezy(_srodek_probki(wiersz + 0.5, kolumna + 0.5))
                pary = KONTUR_SIODLO[(przypadek, srodek_wewnatrz)]
            else:
                pary = KONTUR_KOMORKI[przypadek]
            punkty = {
                nazwa: _punkt_krawedzi(wiersz, kolumna, nazwa, siatka, przejscia, nalezy)
                for para in pary
                for nazwa in para
            }
            odcinki.extend((punkty[lewa], punkty[prawa]) for lewa, prawa in pary)
    return _petle(odcinki)


def _siatka_z_ramka(
    siatka: tuple[tuple[bool, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    """Siatka próbek otoczona ramką zer, z wartościami jako ``0``/``1``.

    Ramka to próbki spoza siatki: są puste, więc kontur obszaru domyka się na
    krawędzi rysunku. Jedna ramka wokół całej siatki pozwala czytać cztery
    narożniki komórki zwykłym indeksem, bez sprawdzania zakresu (karta PRZ-182).
    """
    szerokosc = len(siatka[0]) + 2
    pusta = (0,) * szerokosc
    return (pusta, *((0, *(1 if probka else 0 for probka in linia), 0) for linia in siatka), pusta)


def _granice_obszaru(
    siatka: tuple[tuple[bool, ...], ...],
) -> tuple[int, int, int, int] | None:
    """Zakres komórek, które może przecinać kontur: ``(od_w, do_w, od_k, do_k)``.

    Kontur przechodzi tylko przez komórki przy zamalowanych próbkach, więc nie ma
    po co przeglądać całej siatki. ``None`` znaczy „obszar jest pusty”. Zakres
    obejmuje jedną komórkę zapasu, bo kontur idzie też między próbką a jej pustym
    sąsiadem (karta PRZ-182).
    """
    wiersze = [numer for numer, linia in enumerate(siatka) if any(linia)]
    if not wiersze:
        return None
    poczatki = []
    konce = []
    for numer in wiersze:
        linia = siatka[numer]
        poczatki.append(linia.index(True))
        konce.append(len(linia) - 1 - linia[::-1].index(True))
    return wiersze[0] - 1, wiersze[-1], min(poczatki) - 1, max(konce)


def _punkt_krawedzi(
    wiersz: int,
    kolumna: int,
    nazwa: str,
    siatka: tuple[tuple[bool, ...], ...],
    przejscia: dict[frozenset[tuple[int, int]], tuple[float, float]],
    nalezy: Callable[[tuple[float, float]], bool],
) -> tuple[float, float]:
    """Miejsce przecięcia granicy na zadanej krawędzi komórki (liczone raz)."""
    (wiersz_a, kolumna_a), (wiersz_b, kolumna_b) = KRAWEDZIE_KOMORKI[nazwa]
    probka_a = (wiersz + wiersz_a, kolumna + kolumna_a)
    probka_b = (wiersz + wiersz_b, kolumna + kolumna_b)
    klucz = frozenset((probka_a, probka_b))
    if klucz not in przejscia:
        # Krawędź rysunku: próbka spoza siatki leży dokładnie na brzegu (średnia
        # z jej współrzędnych wchodzi w ``_srodek_probki`` przez ściecie do brzegu).
        # Obszar kończy się tam, gdzie brzeg rysunku, więc nie ma czego szukać
        # bisekcją (karta PRZ-182).
        if not _w_siatce(*probka_a):
            przejscia[klucz] = _srodek_probki(*probka_a)
        elif not _w_siatce(*probka_b):
            przejscia[klucz] = _srodek_probki(*probka_b)
        else:
            przejscia[klucz] = _przejscie(
                _srodek_probki(*probka_a),
                _srodek_probki(*probka_b),
                _probka_wewnatrz(*probka_a, siatka),
                _probka_wewnatrz(*probka_b, siatka),
                nalezy,
            )
    return przejscia[klucz]


def _warstwa(
    siatka: tuple[tuple[bool, ...], ...],
    klasa: str,
    tytul: str,
    nalezy: Callable[[tuple[float, float]], bool],
) -> str:
    """Warstwa obszaru: jedna ścieżka na kontur, razem z opisem słownym.

    Kontur upraszczamy (Douglas–Peucker) i wygładzamy krzywymi Béziera, więc
    krawędź obszaru jest gładka, a nie schodkowa (karta PRZ-182).

    Pusta warstwa zostaje bez ``role="img"`` — nie ma czego pokazywać, a czytnik
    ekranu nie powinien zapowiadać obrazka bez treści. Klasa i ``<title>``
    zostają, żeby krok zawsze miał obie warstwy (karta PRZ-141).
    """
    sciezki = [
        sciezka
        for sciezka in (
            _sciezka(_uprosc_kontur(petla, TOLERANCJA_KONTURU))
            for petla in _kontury(siatka, nalezy)
        )
        if sciezka
    ]
    atrybuty = ' role="img"' if sciezki else ""
    wnetrze = "\n".join(
        f'          <path class="wiz-obszar" d="{sciezka}" '
        f'shape-rendering="geometricPrecision" stroke-linejoin="round" />'
        for sciezka in sciezki
    )
    return (
        f'      <g class="{klasa}"{atrybuty} aria-label="{escape(tytul)}">\n'
        f"        <title>{tytul}</title>\n{wnetrze}\n      </g>"
    )


def _przestrzen_zbiorow() -> str:
    """Prostokąt całej przestrzeni — tło diagramu zbiorów."""
    return (
        f'      <rect class="wiz-przestrzen" x="0" y="0" width="{SZEROKOSC_ZBIOROW:g}" '
        f'height="{WYSOKOSC_ZBIOROW:g}" />'
    )


def _kola_zbiorow(zmienne: list[str], uklad: tuple[tuple[float, float, float], ...]) -> str:
    """Koła zbiorów z cienkim obrysem — rysowane **nad** obszarem (karta PRZ-182).

    Dzięki temu obrys koła widać nawet pod zamalowanym obszarem, a student
    sprawdza, który kawałek koła obejmuje bieżąca operacja.
    """
    czesci = []
    for indeks, nazwa in enumerate(zmienne):
        x, y, promien = uklad[indeks]
        czesci.append(
            f'      <g class="wiz-zbior">\n'
            f"        <title>Zbiór {escape(nazwa)}</title>\n"
            f'        <circle class="wiz-obrys" cx="{x:g}" cy="{y:g}" r="{promien:g}" />\n'
            f'        <text class="wiz-napis" x="{x:g}" y="{y - promien + 18:g}" '
            f'text-anchor="middle">{escape(nazwa)}</text>\n'
            f"      </g>"
        )
    return "\n".join(czesci)


def _etykieta_zbioru(czesc: Node) -> str:
    """Etykieta operacji nad rysunkiem: nazwa operacji i obszar, którego dotyczy.

    Nazwy są te same co w :func:`kroki_sets` („suma”, „dopełnienie”, „część
    wspólna”), więc etykieta nad rysunkiem i punkt listy mówią o tym samym
    (karty PRZ-141 i PRZ-172).
    """
    if isinstance(czesc, Var):
        return f"Zbiór {czesc.name} — całe koło tej zmiennej."
    return f"{OPERACJE[type(czesc)].capitalize()} — {_opis_obszaru(czesc)}"


def _etykieta_svg(tekst: str) -> str:
    """Etykieta operacji w pasie nad rysunkiem zbiorów (karta PRZ-141)."""
    return (
        f'      <text class="wiz-etykieta-kroku" x="{SZEROKOSC_ZBIOROW / 2:g}" '
        f'y="{-WYSOKOSC_ETYKIETY / 2:g}" text-anchor="middle" dominant-baseline="central">'
        f"{escape(tekst)}</text>"
    )


def _warstwy_kroku(
    node: Node, krok: int, zmienne: tuple[str, ...], uklad: tuple[tuple[float, float, float], ...]
) -> list[tuple[tuple[tuple[bool, ...], ...], str, str, Callable[[tuple[float, float]], bool]]]:
    """Warstwy jednego kroku: ``(siatka próbek, klasy CSS, opis słowny, przynależność)``.

    Obszar bieżącego kroku dzielimy na dwie rozłączne części: mocny akcent
    (``obszar-nowy``) to to, co dokłada bieżąca operacja, a słaby
    (``obszar-poprzedni``) — część, która przyszła z poprzedniego kroku.
    Ich suma to zawsze cały obszar kroku, więc widać, co się właśnie zmieniło.

    Kroki liczymy po operacjach (:func:`operacje_zbiorow`), tak samo jak lista
    pod rysunkiem (karta PRZ-172); krok ``0`` to pierwsza operacja, więc warstwa
    poprzednia jest przy nim pusta.

    Ostatni element warstwy to funkcja mówiąca, czy formuła **tej warstwy** jest
    prawdziwa w danym punkcie: kontur liczy nią dokładne miejsce przecięcia
    granicy (karta PRZ-182), a nie tylko wartości próbek.
    """
    czesci = operacje_zbiorow(node)
    biezaca = czesci[krok]
    nalezy_biezaca = _nalezy_do(biezaca, zmienne, uklad)
    siatka = _obszar(biezaca, zmienne, uklad)
    nowy = (
        siatka,
        "obszar-1 obszar-nowy",
        f"Nowy obszar: {_etykieta_zbioru(biezaca)}",
        nalezy_biezaca,
    )
    if krok == 0:
        return [
            (
                (),
                "obszar-2 obszar-poprzedni",
                "Pierwszy krok — nie ma poprzedniego obszaru.",
                lambda punkt: False,
            ),
            nowy,
        ]
    poprzednia = czesci[krok - 1]
    nalezy_poprzednia = _nalezy_do(poprzednia, zmienne, uklad)
    siatka_poprzednia = _obszar(poprzednia, zmienne, uklad)
    wspolna = _czesc_wspolna(siatka, siatka_poprzednia)
    tytul = (
        f"Obszar z poprzedniego kroku: {_etykieta_zbioru(poprzednia)}"
        if any(any(linia) for linia in wspolna)
        else "Obszar z poprzedniego kroku: brak części wspólnej z bieżącym."
    )
    return [
        (
            wspolna,
            "obszar-2 obszar-poprzedni",
            tytul,
            lambda punkt: nalezy_biezaca(punkt) and nalezy_poprzednia(punkt),
        ),
        (
            _roznica(siatka, siatka_poprzednia),
            "obszar-1 obszar-nowy",
            nowy[2],
            lambda punkt: nalezy_biezaca(punkt) and not nalezy_poprzednia(punkt),
        ),
    ]


def _warstwy_calej_formuly(
    node: Node, zmienne: tuple[str, ...], uklad: tuple[tuple[float, float, float], ...]
) -> list[tuple[tuple[tuple[bool, ...], ...], str, str, Callable[[tuple[float, float]], bool]]]:
    """Warstwy rysunku bez wybranego kroku: cały obszar wzoru i pusta warstwa poprzednia.

    Pusta warstwa jest po to, żeby **każdy** rysunek — także ten bez wybranego
    kroku — miał obie warstwy obszaru, tak samo jak pierwszy krok (PRZ-141, PRZ-172).
    """
    return [
        (
            (),
            "obszar-2 obszar-poprzedni",
            "Nie ma poprzedniego kroku — to cały obszar wzoru.",
            lambda punkt: False,
        ),
        (
            _obszar(node, zmienne, uklad),
            "obszar-1 obszar-nowy",
            "Obszar całej formuły.",
            _nalezy_do(node, zmienne, uklad),
        ),
    ]


def sets_svg(node: Node, krok: int | None = None) -> Markup:
    """Rysuje diagram zbiorów **jednej strony prawa** (karty PRZ-172 i PRZ-182).

    Prostokąt to cała przestrzeń, a koła — zbiory zmiennych (najwyżej trzy).
    Obszar zamalowany to próbki siatki, w których formuła ``node`` jest prawdziwa;
    jego krawędź to gładki kontur (marching squares + wygładzanie Béziera), a nie
    zbiór prostokątów próbek (karta PRZ-182).

    Bez ``krok`` rysujemy cały wzór, z ``krok`` — stan po tej operacji: mocnym
    akcentem to, co dokłada operacja, słabym — część z poprzedniego kroku, a nad
    rysunkiem stoi etykieta operacji (karta PRZ-141). Kroki liczymy po operacjach
    na zbiorach (:func:`operacje_zbiorow`) — sam zbiór ``p`` nie jest krokiem
    (karta PRZ-172). Wzór bez operacji (na przykład sama zmienna) rysujemy w całości.

    Drugą stronę prawa rysuje osobne wywołanie: oba diagramy są teraz niezależne
    i każdy ma własne strzałki (karta PRZ-182, partial ``_sets.html``).
    """
    zmienne = variables(node)
    if len(zmienne) > MAX_ZBIOROW:
        return Markup(
            f'<p class="wiz-blad">Rysunek pokazuje co najwyżej trzy zbiory. '
            f"Ten wzór ma {len(zmienne)} zmiennych.</p>"
        )

    uklad = UKLADY[len(zmienne)]
    czesci = operacje_zbiorow(node)
    if krok is None or not czesci:
        warstwy = _warstwy_calej_formuly(node, tuple(zmienne), uklad)
        opis_kroku, etykieta = "Cała formuła.", None
    else:
        numer_kroku = _przytnij(krok, len(czesci))
        warstwy = _warstwy_kroku(node, numer_kroku, tuple(zmienne), uklad)
        czesc = czesci[numer_kroku]
        opis_kroku, etykieta = _opis_zbioru(czesc), _etykieta_zbioru(czesc)

    elementy = [_przestrzen_zbiorow()]
    elementy.extend(
        _warstwa(siatka, klasa, tytul_warstwy, nalezy)
        for siatka, klasa, tytul_warstwy, nalezy in warstwy
    )
    elementy.append(_kola_zbiorow(zmienne, uklad))
    tytul = f"Diagram zbiorów dla wzoru {to_text(node)}. {opis_kroku}"
    gora = -WYSOKOSC_ETYKIETY if etykieta else 0
    wysokosc = WYSOKOSC_ZBIOROW - gora
    return Markup(
        f'<svg class="wiz-svg wiz-svg-zbiory" viewBox="0 {gora} {SZEROKOSC_ZBIOROW:g} '
        f'{wysokosc:g}" preserveAspectRatio="xMidYMid meet" role="img" '
        f'shape-rendering="geometricPrecision" aria-label="{escape(tytul)}">\n'
        f"    <title>{tytul}</title>\n"
        + ("\n".join([_etykieta_svg(etykieta)] + elementy) if etykieta else "\n".join(elementy))
        + "\n</svg>"
    )
