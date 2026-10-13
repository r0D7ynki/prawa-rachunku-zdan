"""Testy workflow GitHub Actions, który uruchamia bramkę projektu (karta PRZ-026).

PyYAML nie jest zależnością projektu (AGENTS.md: w `pyproject.toml` tylko `flask`),
więc plik czytamy jako tekst i sprawdzamy kształt bloków własnym czytnikiem.
Gdy PyYAML jest dostępny, dodatkowy test parsuje cały plik przez `yaml.safe_load`.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "gate.yml"
README = ROOT / "README.md"

#: Kroki, które workflow musi zawierać — w tej kolejności.
KROKI = (
    "uses: actions/checkout",
    "uses: astral-sh/setup-uv",
    "run: uv sync --frozen",
    "run: ./scripts/gate.sh",
)

#: Ciągi, których w workflow być nie może: sekrety, klucze i tokeny.
ZAKAZANE = ("secrets.", "password", "token", "api_key", "api-key", "private_key")

#: Adres repozytorium, do którego prowadzi znacznik w README.
REPOZYTORIUM = "github.com/r0D7ynki/prawa-rachunku-zdan"


def _workflow() -> str:
    """Treść pliku workflow; brak pliku to od razu błąd testu."""
    assert WORKFLOW.is_file(), f"brak pliku {WORKFLOW.relative_to(ROOT)}"
    return WORKFLOW.read_text(encoding="utf-8")


def _blok(tekst: str, klucz: str) -> str:
    """Blok YAML o kluczu `klucz`: linia klucza i wszystko głębiej wcięte."""
    linie = tekst.splitlines()
    for numer, linia in enumerate(linie):
        if linia.strip() != f"{klucz}:" and not linia.strip().startswith(f"{klucz}: "):
            continue
        wciecie = len(linia) - len(linia.lstrip(" "))
        blok = [linia]
        for dalsza in linie[numer + 1 :]:
            if dalsza.strip() and len(dalsza) - len(dalsza.lstrip(" ")) <= wciecie:
                break
            blok.append(dalsza)
        return "\n".join(blok)
    raise AssertionError(f"brak bloku „{klucz}:” w pliku")


def _sekcja_markdown(tekst: str, tytul: str) -> str:
    """Treść sekcji `## tytul` z README, bez nagłówka i bez następnej sekcji."""
    wzor = re.compile(rf"^## {re.escape(tytul)}\s*$(.*?)(?=^## |\Z)", re.M | re.S)
    trafienie = wzor.search(tekst)
    assert trafienie, f"README.md nie ma sekcji „{tytul}”"
    return trafienie.group(1).strip()


def _sprawdz_wyglad_yaml(tekst: str) -> None:
    """Sprawdza to, co widać bez parsera: brak tabulatorów, mapy i parzyste wcięcia."""
    for numer, linia in enumerate(tekst.splitlines(), start=1):
        if not linia.strip() or linia.lstrip().startswith("#"):
            continue
        assert "\t" not in linia, f"linia {numer}: tabulator zamiast spacji"
        wciecie = len(linia) - len(linia.lstrip(" "))
        assert wciecie % 2 == 0, f"linia {numer}: wcięcie {wciecie} nie jest parzyste"
        assert re.match(r"^-? ?[\w.-]+:", linia.strip()), f"linia {numer} nie jest mapą: {linia!r}"


def test_workflow_istnieje_i_parsuje_sie_jako_yaml():
    """Plik jest, ma postać YAML, a przy dostępnym PyYAML parsuje się w całości."""
    tekst = _workflow()
    _sprawdz_wyglad_yaml(tekst)
    try:
        import yaml
    except ModuleNotFoundError:
        # PyYAML nie jest zależnością projektu (AGENTS.md: tylko `flask`).
        # Zostaje sprawdzenie wyglądu pliku z góry tego testu.
        return
    dane = yaml.safe_load(tekst)
    assert isinstance(dane, dict)
    # PyYAML 1.1 czyta klucz `on:` jako wartość logiczną True.
    wyzwalacze = dane.get("on", dane.get(True))
    assert isinstance(wyzwalacze, dict)
    assert set(wyzwalacze) == {"push", "pull_request"}
    assert dane["jobs"]["gate"]["steps"]


def test_workflow_ma_wyzwalacze_push_i_pull_request():
    wyzwalacze = _blok(_workflow(), "on")
    assert re.search(r"^\s+push:", wyzwalacze, re.M), "brak wyzwalacza push"
    assert re.search(r"^\s+pull_request:", wyzwalacze, re.M), "brak wyzwalacza pull_request"
    assert "main" in wyzwalacze, "push nie obejmuje gałęzi main"
    assert "swarm/integration" in wyzwalacze, "push nie obejmuje swarm/integration"


def test_workflow_ma_uprawnienia_tylko_do_odczytu():
    uprawnienia = _blok(_workflow(), "permissions")
    assert re.search(r"^\s+contents: read$", uprawnienia, re.M), "brak `contents: read`"
    assert "write" not in uprawnienia, "workflow chce prawa zapisu"


def test_workflow_zawiera_wymagane_kroki_w_kolejnosci():
    kroki = _blok(_workflow(), "steps")
    pozycje = []
    for krok in KROKI:
        pozycja = kroki.find(krok)
        assert pozycja >= 0, f"brak kroku „{krok}”"
        pozycje.append(pozycja)
    assert pozycje == sorted(pozycje), f"kroki w złej kolejności: {KROKI}"


def test_workflow_nie_zawiera_sekretow_ani_kluczy():
    tekst = _workflow().lower()
    for slowo in ZAKAZANE:
        assert slowo not in tekst, f"workflow zawiera „{slowo}”"


def test_workflow_ma_limit_czasu_najwyzej_15_minut():
    tekst = _workflow()
    limity = [int(wartosc) for wartosc in re.findall(r"^\s*timeout-minutes: *(\d+)$", tekst, re.M)]
    assert limity, "workflow nie ustawia timeout-minutes"
    assert max(limity) <= 15, f"limit czasu {max(limity)} minut przekracza 15"


def test_readme_ma_sekcje_ci_z_jednym_zdaniem_i_znacznikiem():
    sekcja = _sekcja_markdown(README.read_text(encoding="utf-8"), "CI")
    assert f"{REPOZYTORIUM}/actions/workflows/gate.yml/badge.svg" in sekcja, "brak znacznika"
    zdania = [linia for linia in sekcja.splitlines() if linia.strip() and "badge.svg" not in linia]
    assert len(zdania) == 1, f"sekcja „CI” ma mieć jedno zdanie, a ma {len(zdania)} linii"
    zdanie = zdania[0].strip()
    assert zdanie.endswith("."), "zdanie w sekcji „CI” nie kończy się kropką"
    assert ". " not in zdanie, "sekcja „CI” ma mieć jedno zdanie"
