"""Generator pytań quizu z praw rachunku zdań (PRZ-007).

Moduł zamienia treść praw (:mod:`app.logic.laws`) na gotowe pytania quizu i sprawdza
odpowiedź. Sprawdzenie liczy pytania od nowa, więc serwer nigdy nie wysyła rozwiązania
do przeglądarki: przeglądarka dostaje pytanie przez :meth:`Question.to_public_dict`,
a wybrany numer odpowiedzi oddaje do :func:`check`.

Cztery rodzaje pytań:

1. ``rozpoznanie`` — wskazać wzór prawa albo nazwę prawa o danym wzorze,
2. ``rownowaznosc`` — wskazać formułę równoważną; każdy dystraktor jest sprawdzony
   funkcją :func:`app.logic.truth.equivalent`, więc żaden nie jest poprawny,
3. ``blad`` — wskazać, co poszło nie tak w błędnym przekształceniu,
4. ``uzupelnienie`` — pytanie przygotowane ręcznie w polu ``quiz`` prawa.

Losowość: każdy zestaw liczy się z ``random.Random(seed)`` — moduł nigdy nie używa
globalnego ``random``. Ten sam ``seed`` daje ten sam zestaw pytań i tę samą kolejność
odpowiedzi. ``id`` pytania ma postać ``"<slug>-<rodzaj>-<numer>-<seed>"``, gdzie
``numer`` to pozycja pytania w zestawie danego prawa. Dzięki temu :func:`check` znajduje
pytanie w całym zestawie prawa — niezależnie od tego, ile pytań pobrała przeglądarka.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from app.logic import laws, truth
from app.logic.formula import (
    And,
    Iff,
    Imp,
    Node,
    Not,
    Or,
    Var,
    parse,
    replace,
    same,
    subformulas,
    to_text,
)
from app.logic.law_model import Law

__all__ = ["RODZAJE", "Question", "check", "generate"]

#: Rodzaje pytań. Wchodzą do ``Question.id``, więc widok i testy rozpoznają rodzaj
#: po samym identyfikatorze pytania.
RODZAJE = ("rozpoznanie", "rownowaznosc", "blad", "uzupelnienie")

#: Opisy błędów w pytaniu typu ``blad``. Dokładnie jeden z nich opisuje błąd z pytania;
#: reszta to dystraktory. Kolejność jest stała, więc opis nie zależy od losowania.
_OPISY_BLEDOW = (
    "Zamieniono spójnik ∧ na ∨.",
    "Zamieniono spójnik ∨ na ∧.",
    "Usunięto przeczenie przed całą formułą.",
    "Dodano przeczenie przed całą formułą.",
    "Usunięto przeczenie przed jednym ze zdań.",
    "Zamieniono strony implikacji.",
    "Zamieniono równoważność na implikację.",
    "Zamieniono jedną zmienną na inną.",
    "Nic — przekształcenie jest poprawne.",
)

#: Najmniejsza i największa liczba odpowiedzi w jednym pytaniu.
_MIN_OPCJI = 3
_MAX_OPCJI = 4


@dataclass(frozen=True)
class Question:
    """Jedno pytanie quizu wraz z rozwiązaniem.

    ``poprawna`` to numer odpowiedzi w ``opcje``. Pola ``poprawna`` i ``wyjasnienie``
    zostają na serwerze — :meth:`to_public_dict` ich nie wypuszcza.
    """

    id: str
    prawo: str
    pytanie: str
    opcje: list[str]
    poprawna: int
    podpowiedz: str
    wyjasnienie: str

    def to_public_dict(self) -> dict:
        """Zwraca dane dla przeglądarki: bez poprawnej odpowiedzi i bez wyjaśnienia."""
        return {
            "id": self.id,
            "prawo": self.prawo,
            "pytanie": self.pytanie,
            "opcje": list(self.opcje),
            "podpowiedz": self.podpowiedz,
        }


@dataclass(frozen=True)
class _Candidate:
    """Pytanie przed nadaniem numeru i przed przetasowaniem odpowiedzi."""

    rodzaj: str
    pytanie: str
    opcje: list[str]
    poprawna: int
    podpowiedz: str
    wyjasnienie: str


# ---------------------------------------------------------------------------
# Zestaw pytań
# ---------------------------------------------------------------------------


def generate(prawo: str | None = None, ile: int = 5, seed: int | None = None) -> list[Question]:
    """Buduje zestaw pytań quizu.

    ``prawo`` to slug prawa albo ``None`` (wszystkie prawa). Nieznany slug daje pustą
    listę. ``ile`` to liczba pytań — gdy zestaw prawa jest mniejszy, zwracamy go całego.
    ``seed=None`` losuje ziarno, ale nadal bez globalnego ``random``.
    """
    if ile <= 0:
        return []
    if seed is None:
        seed = random.Random().randrange(2**32)
    zestaw = _pool(prawo, seed)
    random.Random(_seed_for(seed, "kolejnosc")).shuffle(zestaw)
    return zestaw[:ile]


def check(prawo: str | None, seed: int, pytanie_id: str, odpowiedz: int) -> bool:
    """Sprawdza odpowiedź: liczy pytania od nowa i porównuje numer odpowiedzi.

    Szukamy w całym zestawie prawa, nie tylko w pierwszych ``ile`` pytaniach, bo
    przeglądarka mogła pobrać dłuższy zestaw. Nieznane ``pytanie_id`` oraz odpowiedź,
    która nie jest liczbą, dają ``False`` — bez wyjątku.
    """
    if not isinstance(odpowiedz, int) or isinstance(odpowiedz, bool):
        return False
    for pytanie in _pool(prawo, seed):
        if pytanie.id == pytanie_id:
            return odpowiedz == pytanie.poprawna
    return False


def _pool(prawo: str | None, seed: int) -> list[Question]:
    """Wszystkie pytania wybranych praw, w stałej kolejności."""
    if prawo is None:
        wybrane = laws.all_laws()
    else:
        znalezione = laws.get(prawo)
        wybrane = [] if znalezione is None else [znalezione]
    pytania: list[Question] = []
    for law in wybrane:
        pytania.extend(_questions_for(law, seed))
    return pytania


def _seed_for(seed: int, klucz: str) -> int:
    """Ziarno zależne tylko od ``seed`` i ``klucz`` — niezależne od kolejności praw."""
    skrot = hashlib.sha256(f"{seed}:{klucz}".encode()).digest()
    return int.from_bytes(skrot[:8], "big")


def _questions_for(law: Law, seed: int) -> list[Question]:
    """Pytania jednego prawa. Odpowiedzi tasuje osobne ziarno tego prawa."""
    rng = random.Random(_seed_for(seed, law.slug))
    kandydaci: list[_Candidate] = []
    kandydaci.extend(_rozpoznanie(law, rng))
    kandydaci.extend(_rownowaznosc(law, rng))
    kandydaci.extend(_blad(law, rng))
    kandydaci.extend(_uzupelnienie(law))

    pytania: list[Question] = []
    for numer, kandydat in enumerate(kandydaci, start=1):
        opcje, poprawna = _tasuj(rng, kandydat.opcje, kandydat.poprawna)
        pytania.append(
            Question(
                id=f"{law.slug}-{kandydat.rodzaj}-{numer}-{seed}",
                prawo=law.slug,
                pytanie=kandydat.pytanie,
                opcje=opcje,
                poprawna=poprawna,
                podpowiedz=kandydat.podpowiedz,
                wyjasnienie=kandydat.wyjasnienie,
            )
        )
    return pytania


# ---------------------------------------------------------------------------
# Rodzaje pytań
# ---------------------------------------------------------------------------


def _rozpoznanie(law: Law, rng: random.Random) -> list[_Candidate]:
    """Dwa pytania: „który wzór to to prawo?” oraz „jak nazywa się prawo o tym wzorze?”.

    Wzory bierzemy dosłownie z treści prawa (``law.formula``), a nie z wypisywania drzewa:
    ``to_text`` pomija nawiasy, które nie zmieniają sensu, ale początkującemu pomagają.
    """
    wzor = parse(law.formula)
    wzory: list[str] = []
    nazwy: list[str] = []
    for other in laws.all_laws():
        if other.slug == law.slug:
            continue
        nazwy.append(other.nazwa)
        inny_wzor = parse(other.formula)
        if same(inny_wzor, wzor) or _odbicie(inny_wzor, wzor):
            continue
        wzory.append(other.formula)

    pytania: list[_Candidate] = []
    opcje = _skladaj(rng, law.formula, wzory)
    if opcje is not None:
        pytania.append(
            _Candidate(
                rodzaj="rozpoznanie",
                pytanie=f"Który wzór to {law.nazwa}?",
                opcje=opcje[0],
                poprawna=opcje[1],
                podpowiedz="Popatrz na spójniki i przeczenia w każdym wzorze.",
                wyjasnienie=(
                    f"{law.nazwa} ma zapis {law.formula}. {_pierwsze_zdanie(law.po_ludzku)}"
                ),
            )
        )

    opcje = _skladaj(rng, law.nazwa, nazwy)
    if opcje is not None:
        pytania.append(
            _Candidate(
                rodzaj="rozpoznanie",
                pytanie=f"Jak nazywa się prawo o wzorze {law.formula}?",
                opcje=opcje[0],
                poprawna=opcje[1],
                podpowiedz="Pomyśl, jak ten wzór zmienia spójniki i przeczenia.",
                wyjasnienie=(
                    f"Wzór {law.formula} to {law.nazwa}. {_pierwsze_zdanie(law.po_ludzku)}"
                ),
            )
        )
    return pytania


def _rownowaznosc(law: Law, rng: random.Random) -> list[_Candidate]:
    """Pytania o formułę równoważną — w obie strony, gdy strony prawa się różnią.

    Prawo, którego obie strony zapisano tak samo (np. ``p ∨ ∼p``), nie daje tu pytania:
    nie ma drugiej strony, o którą można zapytać.
    """
    if law.lewa.strip() == law.prawa.strip():
        return []

    pytania: list[_Candidate] = []
    for tekst, cel in ((law.lewa, law.prawa), (law.prawa, law.lewa)):
        poprawna = parse(cel)
        dystraktory = [
            to_text(kandydat)
            for _, kandydat in _mutacje(poprawna)
            if not truth.equivalent(kandydat, poprawna)
        ]
        opcje = _skladaj(rng, cel, dystraktory)
        if opcje is None:
            continue
        pytania.append(
            _Candidate(
                rodzaj="rownowaznosc",
                pytanie=f"Która formuła jest równoważna formule {tekst}?",
                opcje=opcje[0],
                poprawna=opcje[1],
                podpowiedz="Policz obie formuły w tablicy prawdy.",
                wyjasnienie=(
                    f"Formuły {tekst} i {cel} mają tę samą wartość przy każdym wartościowaniu, "
                    f"więc są równoważne: {law.formula}."
                ),
            )
        )
    return pytania


def _blad(law: Law, rng: random.Random) -> list[_Candidate]:
    """Pytanie o błąd: pokazujemy błędny wynik przekształcenia lewej strony prawa.

    Bierzemy pierwszy błąd, po którym formuła przestaje być równoważna lewej stronie.
    To gwarantuje, że „nic — przekształcenie jest poprawne” nigdy nie jest odpowiedzią.
    """
    lewa = parse(law.lewa)
    for opis, zla in _mutacje(lewa):
        if truth.equivalent(zla, lewa):
            continue
        opcje = _skladaj(rng, opis, list(_OPISY_BLEDOW))
        if opcje is None:
            continue
        return [
            _Candidate(
                rodzaj="blad",
                pytanie=(
                    f"W przekształceniu formuły {law.lewa} w formułę {to_text(zla)} "
                    "jest błąd. Co poszło nie tak?"
                ),
                opcje=opcje[0],
                poprawna=opcje[1],
                podpowiedz="Porównaj obie formuły znak po znaku.",
                wyjasnienie=(
                    f"Formuły {law.lewa} i {to_text(zla)} nie mają tej samej wartości "
                    f"przy każdym wartościowaniu. {opis}"
                ),
            )
        ]
    return []


def _uzupelnienie(law: Law) -> list[_Candidate]:
    """Pytania przygotowane ręcznie w polu ``quiz`` prawa."""
    pytania: list[_Candidate] = []
    for wpis in law.quiz:
        if not isinstance(wpis, dict):
            continue
        opcje = wpis.get("opcje")
        poprawna = wpis.get("poprawna")
        pytanie = wpis.get("pytanie")
        podpowiedz = wpis.get("podpowiedz")
        wyjasnienie = wpis.get("wyjasnienie")
        if not _dobre_pytanie(pytanie, opcje, poprawna, podpowiedz, wyjasnienie):
            continue
        pytania.append(
            _Candidate(
                rodzaj="uzupelnienie",
                pytanie=pytanie,
                opcje=list(opcje),
                poprawna=poprawna,
                podpowiedz=podpowiedz,
                wyjasnienie=wyjasnienie,
            )
        )
    return pytania


# ---------------------------------------------------------------------------
# Błędne formuły i opisy błędów
# ---------------------------------------------------------------------------


def _mutacje(node: Node) -> list[tuple[str, Node]]:
    """Kandydaci na błędną formułę: pary ``(opis błędu, formuła po błędzie)``.

    Każdy opis mówi, co zrobiono z formułą ``node``. To ta sama lista dla dystraktorów
    pytania o równoważność i dla pytania o błąd w przekształceniu.
    """
    wynik: list[tuple[str, Node]] = []
    if isinstance(node, (And, Or)):
        inny = Or if isinstance(node, And) else And
        wynik.append(
            (
                f"Zamieniono spójnik {_znak(type(node))} na {_znak(inny)}.",
                inny(node.left, node.right),
            )
        )
    if isinstance(node, Not) and isinstance(node.child, (And, Or)):
        dziecko = node.child
        inny = Or if isinstance(dziecko, And) else And
        wynik.append(
            (
                f"Zamieniono spójnik {_znak(type(dziecko))} na {_znak(inny)}.",
                Not(inny(dziecko.left, dziecko.right)),
            )
        )
    if isinstance(node, Not):
        wynik.append(("Usunięto przeczenie przed całą formułą.", node.child))
    wynik.append(("Dodano przeczenie przed całą formułą.", Not(node)))
    if isinstance(node, Imp):
        wynik.append(("Zamieniono strony implikacji.", Imp(node.right, node.left)))
    if isinstance(node, Iff):
        wynik.append(("Zamieniono równoważność na implikację.", Imp(node.left, node.right)))
    negacja = _pierwsza_negacja_zmiennej(node)
    if negacja is not None:
        wynik.append(
            ("Usunięto przeczenie przed jednym ze zdań.", replace(node, negacja, negacja.child))
        )
    zmienna = _pierwsza_zmienna(node)
    if zmienna is not None:
        wynik.append(
            (
                "Zamieniono jedną zmienną na inną.",
                replace(node, zmienna, Var(_inna_nazwa(zmienna.name))),
            )
        )
    return _bez_powtorzen(wynik)


def _bez_powtorzen(mutacje: list[tuple[str, Node]]) -> list[tuple[str, Node]]:
    """Usuwa powtórzone formuły — ta sama błędna formuła ma jeden opis.

    Jedna błędna formuła może powstać na dwa sposoby (np. „∼(p ∧ q)” → „p ∧ q” to
    usunięcie przeczenia przed całą formułą, ale i przed jednym zdaniem). Bez tego
    dystraktory mogłyby się powtórzyć albo dwa opisy opisywałyby tę samą formułę.
    """
    wynik: list[tuple[str, Node]] = []
    for opis, kandydat in mutacje:
        if any(same(kandydat, juz) for _, juz in wynik):
            continue
        wynik.append((opis, kandydat))
    return wynik


def _znak(typ: type[And] | type[Or]) -> str:
    """Znak spójnika w notacji wykładu, np. ``∧`` (wyliczony z ``to_text``)."""
    return to_text(typ(Var("p"), Var("q"))).split()[1]


def _pierwsza_zmienna(node: Node) -> Var | None:
    """Pierwsza zmienna formuły albo ``None``, gdy formuła nie ma zmiennych."""
    for czesc in subformulas(node):
        if isinstance(czesc, Var):
            return czesc
    return None


def _pierwsza_negacja_zmiennej(node: Node) -> Not | None:
    """Pierwsze przeczenie stojące bezpośrednio przed zmienną, np. ``∼p``."""
    for czesc in subformulas(node):
        if isinstance(czesc, Not) and isinstance(czesc.child, Var):
            return czesc
    return None


def _inna_nazwa(nazwa: str) -> str:
    """Inna zmienna z tego samego zestawu liter — do błędu „zamieniono zmienną”."""
    for kandydat in ("p", "q", "r", "s"):
        if kandydat != nazwa:
            return kandydat
    return "q"


def _odbicie(inny: Node, wzor: Node) -> bool:
    """Czy ``inny`` to ``wzor`` z zamienionymi stronami równoważności.

    ``(q ∨ p) ≡ (p ∨ q)`` to zapis tego samego prawa przemienności, więc nie nadaje się
    na dystraktor pytania „który wzór to to prawo?”.
    """
    if isinstance(wzor, Iff) and isinstance(inny, Iff):
        return same(inny, Iff(wzor.right, wzor.left))
    return False


# ---------------------------------------------------------------------------
# Składanie opcji
# ---------------------------------------------------------------------------


def _skladaj(
    rng: random.Random, poprawna: str, dystraktory: list[str]
) -> tuple[list[str], int] | None:
    """Składa opcje: poprawna odpowiedź plus 2–3 różne dystraktory.

    Zwraca ``(opcje, numer poprawnej)`` albo ``None``, gdy dystraktorów jest za mało.
    Numer poprawnej to zawsze 0 — tasuje go dopiero :func:`_tasuj`.
    """
    wybrane = _wybierz(rng, [tekst for tekst in dystraktory if tekst != poprawna], _MAX_OPCJI - 1)
    if len(wybrane) < _MIN_OPCJI - 1:
        return None
    return [poprawna, *wybrane], 0


def _wybierz(rng: random.Random, kandydaci: list[str], ile: int) -> list[str]:
    """Losuje co najwyżej ``ile`` różnych kandydatów, w kolejności losowania."""
    unikalne = list(dict.fromkeys(kandydaci))
    if len(unikalne) <= ile:
        return unikalne
    return rng.sample(unikalne, ile)


def _tasuj(rng: random.Random, opcje: list[str], poprawna: int) -> tuple[list[str], int]:
    """Miesza odpowiedzi i zwraca nową listę opcji oraz nowy numer poprawnej."""
    kolejnosc = list(range(len(opcje)))
    rng.shuffle(kolejnosc)
    return [opcje[numer] for numer in kolejnosc], kolejnosc.index(poprawna)


def _dobre_pytanie(
    pytanie: object,
    opcje: object,
    poprawna: object,
    podpowiedz: object,
    wyjasnienie: object,
) -> bool:
    """Czy wpis z pola ``quiz`` nadaje się na pytanie: 3–4 różne opcje i wskazana poprawna."""
    for tekst in (pytanie, podpowiedz, wyjasnienie):
        if not isinstance(tekst, str) or not tekst.strip():
            return False
    if not isinstance(opcje, list) or not _MIN_OPCJI <= len(opcje) <= _MAX_OPCJI:
        return False
    if any(not isinstance(opcja, str) or not opcja.strip() for opcja in opcje):
        return False
    if len(set(opcje)) != len(opcje):
        return False
    if not isinstance(poprawna, int) or isinstance(poprawna, bool):
        return False
    return 0 <= poprawna < len(opcje)


def _pierwsze_zdanie(text: str) -> str:
    """Pierwsze zdanie tekstu — na wyjaśnienie pytania."""
    koniec = text.find(". ")
    return text if koniec < 0 else text[: koniec + 1]
