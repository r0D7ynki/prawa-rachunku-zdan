"""Rysunki na stronach praw: schemat bramek i diagram zbiorów (karta PRZ-123).

Rysunek powstaje w Pythonie, a nie w przeglądarce. Dzięki temu działa bez
JavaScriptu i da się go sprawdzić testem w ``tests/test_diagrams.py``.

Moduł dostaje drzewo formuły z :mod:`app.logic.formula` i oddaje napis
z elementem ``<svg>``. Wynik wstawiamy do szablonu przez ``markupsafe.Markup``
— to nasz HTML, nie dane użytkownika. Nazwy zmiennych i wzory przechodzą przez
``escape``, bo pochodzą z tekstu.

Dwie listy kroków prowadzą czytelnika przez wzór:

* :func:`kroki_gates` — bramki w kolejności liczenia (od zmiennych do całości),
* :func:`kroki_sets` — operacje na zbiorach (zbiór, suma, część wspólna, dopełnienie).

Krok ``i`` (liczony od zera) pokazuje stan po ``i``-tej operacji, a ``krok=None``
znaczy „cała formuła”. Numer spoza listy jest przycinany do jej końców, tak jak
w komponencie kroków ``stepper.js``.
"""

from __future__ import annotations

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

#: Gęstość siatki próbek diagramu zbiorów (karta PRZ-123).
KOLUMNY_SIATKI = 44
WIERSZE_SIATKI = 36

#: Bok jednej próbki na rysunku, w jednostkach ``viewBox``.
BOK_PROBKI = 10

#: Rozmiar rysunku zbiorów: cała przestrzeń to ten prostokąt.
SZEROKOSC_ZBIOROW = KOLUMNY_SIATKI * BOK_PROBKI
WYSOKOSC_ZBIOROW = WIERSZE_SIATKI * BOK_PROBKI

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

#: Wartość logiczna słowem — kolor nigdy nie jest jedynym nośnikiem informacji.
PRAWDA = "PRAWDA"
FALSZ = "FAŁSZ"

# --- schemat bramek --------------------------------------------------------

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


def _uklad(node: Node) -> tuple[dict[Node, int], dict[Node, float]]:
    """Układa bramki: kolumna to głębokość w drzewie, wiersz — kolejność liści.

    Liście dostają kolejne wiersze od góry, a bramka stoi w środku swoich dzieci
    (średnia wierszy), więc przewody nie krzyżują się bez potrzeby.
    """
    kolumny: dict[Node, int] = {}
    rzedy: dict[Node, float] = {}
    kolejny = [0]

    def odwiedz(biezacy: Node) -> None:
        dzieci = _dzieci(biezacy)
        if not dzieci:
            kolumny[biezacy] = 0
            rzedy[biezacy] = float(kolejny[0])
            kolejny[0] += 1
            return
        for dziecko in dzieci:
            odwiedz(dziecko)
        kolumny[biezacy] = 1 + max(kolumny[dziecko] for dziecko in dzieci)
        rzedy[biezacy] = sum(rzedy[dziecko] for dziecko in dzieci) / len(dzieci)

    odwiedz(node)
    return kolumny, rzedy


def _srodek(kolumna: int, rzad: float) -> tuple[float, float]:
    """Środek prostokąta bramki na rysunku."""
    x = MARGINES + kolumna * ODSTEP_X + BRAMKA_SZEROKOSC / 2
    y = MARGINES + rzad * ODSTEP_Y + BRAMKA_WYSOKOSC / 2
    return x, y


def _prostokat(x: float, y: float, klasa: str, napis: str) -> str:
    """Prostokąt bramki albo zmiennej razem z jej napisem."""
    return (
        f'      <g class="{klasa}">\n'
        f'        <rect class="wiz-ksztalt" x="{x - BRAMKA_SZEROKOSC / 2:g}" '
        f'y="{y - BRAMKA_WYSOKOSC / 2:g}" width="{BRAMKA_SZEROKOSC}" '
        f'height="{BRAMKA_WYSOKOSC}" rx="6" />\n'
        f'        <text class="wiz-symbol" x="{x:g}" y="{y:g}" text-anchor="middle" '
        f'dominant-baseline="central">{napis}</text>\n'
        f"      </g>"
    )


def _przewod(
    od: tuple[float, float],
    do: tuple[float, float],
    wartosc: bool | None,
    opis: str,
    krok: int,
) -> str:
    """Przewód ze strzałką na końcu i wartością w ``<title>`` (słowami)."""
    x1 = od[0] + BRAMKA_SZEROKOSC / 2
    y1 = od[1]
    x2 = do[0] - BRAMKA_SZEROKOSC / 2
    y2 = do[1]
    srodek = (x1 + x2) / 2
    sciezka = f"M {x1:g} {y1:g} H {srodek:g} V {y2:g} H {x2:g}"
    if wartosc is None:
        klasa = "wiz-przewod wiz-nieznane"
        tytul = f"Przewód z {opis}: wartość jeszcze nieznana."
        znaczek = "?"
    else:
        klasa = "wiz-przewod " + ("wiz-prawda" if wartosc else "wiz-falsz")
        tytul = f"Przewód z {opis}: {_slowo(wartosc)} ({_cyfra(wartosc)})."
        znaczek = _cyfra(wartosc)
    return (
        f"      <g>\n"
        f'        <path class="{klasa}" d="{sciezka}" '
        f'marker-end="url(#{_id_grota(wartosc, krok)})"><title>{tytul}</title></path>\n'
        f'        <text class="wiz-wartosc" x="{srodek:g}" y="{(y1 + y2) / 2 - 6:g}" '
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
    for rodzic, dziecko in _krawedzie(node):
        wartosc = evaluate(dziecko, wartosci) if dziecko in znane else None
        elementy.append(
            _przewod(
                _srodek(kolumny[dziecko], rzedy[dziecko]),
                _srodek(kolumny[rodzic], rzedy[rodzic]),
                wartosc,
                to_text(dziecko),
                numer_kroku,
            )
        )

    for czesc in _wezly(node):
        x, y = _srodek(kolumny[czesc], rzedy[czesc])
        if isinstance(czesc, Var):
            klasa, napis = "wiz-bramka wiz-zmienna", escape(czesc.name)
        else:
            klasa = "wiz-bramka"
            klasa += " wiz-biezaca" if czesc == biezaca else ""
            klasa += " wiz-znana" if czesc in znane else ""
            napis = SYMBOLE[type(czesc)]
        elementy.append(_prostokat(x, y, klasa.strip(), napis))

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


def _wezly(node: Node) -> list[Node]:
    """Wszystkie węzły drzewa, dzieci przed rodzicem."""
    wynik: list[Node] = []
    for dziecko in _dzieci(node):
        wynik.extend(_wezly(dziecko))
    wynik.append(node)
    return wynik


def _krawedzie(node: Node) -> list[tuple[Node, Node]]:
    """Pary ``(rodzic, dziecko)`` — z nich powstają przewody."""
    wynik: list[tuple[Node, Node]] = []
    for rodzic in _wezly(node):
        wynik.extend((rodzic, dziecko) for dziecko in _dzieci(rodzic))
    return wynik


# --- diagram zbiorów -------------------------------------------------------


def kroki_sets(node: Node) -> list[dict]:
    """Kroki diagramu zbiorów: kolejne operacje na zbiorach.

    Jeden krok to jedna podformuła, tak samo jak w :func:`kroki_gates`.
    Pole ``operacja`` to nazwa operacji („suma”, „dopełnienie”, …).
    """
    return [
        {"opis": _opis_zbioru(czesc), "operacja": OPERACJE[type(czesc)]}
        for czesc in subformulas(node)
    ]


def _opis_zbioru(czesc: Node) -> str:
    """Zdanie po polsku opisujące operację na zbiorach."""
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


def _obszar(
    node: Node, zmienne: list[str], uklad: tuple[tuple[float, float, float], ...]
) -> list[list[bool]]:
    """Siatka próbek: dla każdej próbki mówi, czy formuła jest w niej prawdziwa.

    Przynależność próbki do koła to wartość zmiennej, więc formuła liczy się
    zwykłym :func:`app.logic.formula.evaluate` — ten sam kod co tablica prawdy.
    """
    siatka: list[list[bool]] = []
    for wiersz in range(WIERSZE_SIATKI):
        y = wiersz * BOK_PROBKI + BOK_PROBKI / 2
        linia: list[bool] = []
        for kolumna in range(KOLUMNY_SIATKI):
            x = kolumna * BOK_PROBKI + BOK_PROBKI / 2
            wartosci = {
                nazwa: _w_kole((x, y), uklad[indeks]) for indeks, nazwa in enumerate(zmienne)
            }
            linia.append(evaluate(node, wartosci))
        siatka.append(linia)
    return siatka


def _prostokaty(siatka: list[list[bool]]) -> list[str]:
    """Skleja prawdziwe próbki w wierszu w prostokąty i wypisuje je jako SVG."""
    prostokaty: list[str] = []
    for numer, linia in enumerate(siatka):
        kolumna = 0
        while kolumna < len(linia):
            if not linia[kolumna]:
                kolumna += 1
                continue
            start = kolumna
            while kolumna < len(linia) and linia[kolumna]:
                kolumna += 1
            prostokaty.append(
                f'          <rect class="wiz-probka" x="{start * BOK_PROBKI}" '
                f'y="{numer * BOK_PROBKI}" width="{(kolumna - start) * BOK_PROBKI}" '
                f'height="{BOK_PROBKI}" />'
            )
    return prostokaty


def _warstwa(siatka: list[list[bool]], klasa: str, tytul: str) -> str:
    """Warstwa obszaru: prostokąty próbek razem z opisem słownym."""
    wnetrze = "\n".join(_prostokaty(siatka))
    return (
        f'      <g class="{klasa}" role="img" aria-label="{escape(tytul)}">\n'
        f"        <title>{tytul}</title>\n{wnetrze}\n      </g>"
    )


def _rysunek_zbiorow(
    node: Node,
    zmienne: list[str],
    uklad: tuple[tuple[float, float, float], ...],
) -> str:
    """Prostokąt przestrzeni i koła zbiorów — tło każdego diagramu."""
    czesci = [
        f'      <rect class="wiz-przestrzen" x="0" y="0" width="{SZEROKOSC_ZBIOROW}" '
        f'height="{WYSOKOSC_ZBIOROW}" />'
    ]
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


def _warstwy_kroku(node: Node, krok: int) -> list[tuple[Node, str]]:
    """Formuły zamalowywane w danym kroku: ``(węzeł, klasa obszaru)``.

    Krok rysuje operandy bieżącej operacji — dwa koła dla sumy, części wspólnej
    i równoważności, a dla dopełnienia zbiór i wszystko poza nim. Dzięki temu
    widać, z czego powstaje wynik, a nie tylko sam gotowy obszar.
    """
    czesc = subformulas(node)[krok]
    if isinstance(czesc, Not):
        return [(czesc.child, "obszar-1"), (czesc, "obszar-2")]
    if isinstance(czesc, (And, Or, Imp, Iff)):
        return [(czesc.left, "obszar-1"), (czesc.right, "obszar-2")]
    return [(czesc, "obszar-1")]


def sets_svg(node: Node, krok: int | None = None) -> Markup:
    """Rysuje diagram zbiorów dla formuły.

    Prostokąt to cała przestrzeń, a koła — zbiory zmiennych (najwyżej trzy).
    Obszar zamalowany to próbki siatki, w których formuła jest prawdziwa.
    Bez ``krok`` rysujemy całą formułę, z ``krok`` — stan po tej operacji.
    """
    zmienne = variables(node)
    if len(zmienne) > MAX_ZBIOROW:
        return Markup(
            f'<p class="wiz-blad">Rysunek pokazuje co najwyżej trzy zbiory. '
            f"Ten wzór ma {len(zmienne)} zmiennych.</p>"
        )

    uklad = UKLADY[len(zmienne)]
    numer_kroku = _przytnij(krok, len(subformulas(node)))
    warstwy = [(node, "obszar-1")] if krok is None else _warstwy_kroku(node, numer_kroku)

    opis_kroku = "Cała formuła." if krok is None else _opis_zbioru(subformulas(node)[numer_kroku])
    elementy = [_rysunek_zbiorow(node, zmienne, uklad)]
    for czesc, klasa in warstwy:
        numer_obszaru = "pierwszy" if klasa.endswith("1") else "drugi"
        tytul = f"Obszar {numer_obszaru}: {_opis_zbioru(czesc)}"
        elementy.append(_warstwa(_obszar(czesc, zmienne, uklad), klasa, tytul))
    tytul = f"Diagram zbiorów dla wzoru {to_text(node)}. {opis_kroku}"
    return Markup(
        f'<svg class="wiz-svg wiz-svg-zbiory" viewBox="0 0 {SZEROKOSC_ZBIOROW} '
        f'{WYSOKOSC_ZBIOROW}" preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="{escape(tytul)}">\n'
        f"    <title>{tytul}</title>\n" + "\n".join(elementy) + "\n</svg>"
    )
