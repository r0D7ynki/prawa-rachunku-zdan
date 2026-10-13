"""Rejestr praw rachunku zdań.

Moduł sam znajduje treść praw w pakiecie :mod:`app.logic.laws_data` i składa z niej
jedną listę w kolejności nauki. Nie importuje żadnego pliku treści po nazwie — nowy
plik w ``laws_data`` wystarczy dodać, żeby pojawił się na stronie.

Konwencja dla pliku treści
--------------------------
Każdy moduł w ``app/logic/laws_data/`` wystawia:

- ``LAWS: list[Law]`` — prawa w kolejności, w jakiej mają wystąpić na stronie,
- ``kolejnosc: int`` — liczba porządkująca **moduły**, żeby prawa jednego pliku
  trzymały się razem (np. ``kolejnosc = 1``). Brak atrybutu znaczy 100,
  a przy równej wartości decyduje nazwa modułu.

``all_laws()`` sortuje moduły po ``kolejnosc``, a w obrębie modułu zachowuje
kolejność z ``LAWS``.

Wynik ``all_laws()`` czytamy od nowa przy każdym wywołaniu. Importy są już
w pamięci Pythona, więc koszt jest znikomy, a testy mogą podmienić treść modułu
i od razu zobaczyć zmianę.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from pathlib import Path
from types import ModuleType

from app.logic.law_model import Law, Step

__all__ = ["all_laws", "by_category", "categories", "get", "validate"]

#: Pakiet z treścią praw.
DATA_PACKAGE = "app.logic.laws_data"

#: Kolejność modułu, który nie ma atrybutu ``kolejnosc``.
DEFAULT_ORDER = 100

#: Dozwolone rysunki (patrz ``docs/ARCHITEKTURA.md``).
WIZUALIZACJE = ("gates", "sets", "switch", "chain")

#: Poprawny ``slug``: małe litery, cyfry i myślniki, bez myślnika na końcach.
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: Pola ``Law``, które muszą być niepustymi napisami.
_REQUIRED_TEXT = (
    "slug",
    "nazwa",
    "kategoria",
    "formula",
    "formula_ascii",
    "lewa",
    "prawa",
    "po_ludzku",
    "przyklad",
    "wizualizacja",
)

#: Pola ``Step``, które muszą być niepustymi napisami.
_REQUIRED_STEP_TEXT = ("opis", "reguła", "przed", "po")

#: Pola pytania quizu, które muszą być niepustymi napisami.
_REQUIRED_QUIZ_TEXT = ("pytanie", "podpowiedz", "wyjasnienie")


# ---------------------------------------------------------------------------
# Odnajdywanie treści
# ---------------------------------------------------------------------------


def _module_order(module: ModuleType) -> int:
    """Zwraca ``kolejnosc`` modułu, a gdy jej nie ma albo jest błędna — 100."""
    order = getattr(module, "kolejnosc", DEFAULT_ORDER)
    return order if isinstance(order, int) else DEFAULT_ORDER


def _content_modules() -> list[ModuleType]:
    """Importuje moduły treści i zwraca je w kolejności nauki.

    Nazwy plików bierzemy z katalogu pakietu, więc ``laws.py`` nie zna żadnej
    z nich z góry.
    """
    package = importlib.import_module(DATA_PACKAGE)
    directory = Path(package.__file__).parent
    names = [
        found.name
        for found in pkgutil.iter_modules([str(directory)])
        if not found.name.startswith("_")
    ]
    modules = [importlib.import_module(f"{DATA_PACKAGE}.{name}") for name in names]
    modules.sort(key=lambda module: (_module_order(module), module.__name__))
    return modules


def all_laws() -> list[Law]:
    """Zwraca wszystkie prawa w kolejności nauki."""
    laws: list[Law] = []
    for module in _content_modules():
        laws.extend(getattr(module, "LAWS", ()))
    return laws


def get(slug: str) -> Law | None:
    """Zwraca prawo o podanym ``slug`` albo ``None``, gdy go nie ma."""
    for law in all_laws():
        if law.slug == slug:
            return law
    return None


def by_category() -> dict[str, list[Law]]:
    """Grupuje prawa po kategorii, w kolejności pierwszego wystąpienia."""
    grouped: dict[str, list[Law]] = {}
    for law in all_laws():
        grouped.setdefault(law.kategoria, []).append(law)
    return grouped


def categories() -> list[str]:
    """Zwraca nazwy kategorii w kolejności pierwszego wystąpienia."""
    return list(by_category())


# ---------------------------------------------------------------------------
# Sprawdzanie treści
# ---------------------------------------------------------------------------


def validate() -> list[str]:
    """Zwraca listę problemów w treści praw; pusta lista znaczy treść poprawną.

    Sprawdzamy tylko to, co da się ocenić bez znajomości logiki: obecność pól,
    wzorzec ``slug``, znany rysunek, liczbę kroków i indeks poprawnej odpowiedzi.
    Listy dozwolonych kategorii **nie** ma — nowa kategoria to decyzja autora
    treści, a nie błąd rejestru.
    """
    problems: list[str] = []
    seen_slugs: set[str] = set()
    for law in all_laws():
        if not isinstance(law, Law):
            problems.append(f"treść prawa nie jest obiektem Law: {law!r}")
            continue
        problems.extend(_validate_law_text(law))
        if law.slug in seen_slugs:
            problems.append(f"{law.slug}: powtórzony slug")
        seen_slugs.add(law.slug)
        problems.extend(_validate_steps(law))
        problems.extend(_validate_quiz(law))
    return problems


def _validate_law_text(law: Law) -> list[str]:
    """Sprawdza napisy i rysunek jednego prawa."""
    problems: list[str] = []
    where = law.slug or "<bez slug>"
    for field in _REQUIRED_TEXT:
        value = getattr(law, field, None)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{where}: pole '{field}' musi być niepustym napisem")
    if isinstance(law.slug, str) and not SLUG_PATTERN.match(law.slug):
        problems.append(f"{where}: slug nie pasuje do wzorca (małe litery, cyfry i myślniki)")
    if law.wizualizacja not in WIZUALIZACJE:
        allowed = ", ".join(WIZUALIZACJE)
        problems.append(f"{where}: nieznany rysunek '{law.wizualizacja}' (dozwolone: {allowed})")
    return problems


def _validate_steps(law: Law) -> list[str]:
    """Sprawdza liczbę kroków i ich pola."""
    problems: list[str] = []
    if not isinstance(law.kroki, (list, tuple)):
        return [f"{law.slug}: pole 'kroki' musi być listą"]
    if len(law.kroki) < 2:
        problems.append(f"{law.slug}: 'kroki' ma {len(law.kroki)} kroki, a musi mieć co najmniej 2")
    for number, step in enumerate(law.kroki, start=1):
        if not isinstance(step, Step):
            problems.append(f"{law.slug}: krok {number} nie jest obiektem Step")
            continue
        for field in _REQUIRED_STEP_TEXT:
            value = getattr(step, field, None)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{law.slug}: krok {number} ma puste pole '{field}'")
    return problems


def _validate_quiz(law: Law) -> list[str]:
    """Sprawdza pytania quizu: treść, liczbę odpowiedzi i indeks poprawnej."""
    problems: list[str] = []
    if not isinstance(law.quiz, (list, tuple)):
        return [f"{law.slug}: pole 'quiz' musi być listą"]
    for number, question in enumerate(law.quiz, start=1):
        where = f"{law.slug}: pytanie {number}"
        if not isinstance(question, dict):
            problems.append(f"{where} nie jest słownikiem")
            continue
        for field in _REQUIRED_QUIZ_TEXT:
            value = question.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{where}: puste pole '{field}'")
        options = question.get("opcje")
        if not isinstance(options, list) or not options:
            problems.append(f"{where}: pole 'opcje' musi być niepustą listą")
            continue
        correct = question.get("poprawna")
        is_index = isinstance(correct, int) and not isinstance(correct, bool)
        if not is_index or not 0 <= correct < len(options):
            problems.append(
                f"{where}: 'poprawna' musi być numerem odpowiedzi z zakresu 0..{len(options) - 1}"
            )
    return problems
