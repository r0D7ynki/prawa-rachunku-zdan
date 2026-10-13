"""Fabryka aplikacji Flask.

Nowy widok dodajesz jako moduł w ``app/blueprints/``. Każdy moduł wystawia
zmienną ``bp`` (instancja ``flask.Blueprint``). Fabryka znajduje moduły sama,
więc nie edytujesz tego pliku.
"""

from __future__ import annotations

import importlib
import pkgutil

from flask import Flask

BLUEPRINTS_PACKAGE = "app.blueprints"


def _blueprint_module_names() -> list[str]:
    """Zwraca nazwy modułów z pakietu ``app.blueprints`` (bez podkreślonych)."""
    package = importlib.import_module(BLUEPRINTS_PACKAGE)
    names = [
        info.name
        for info in pkgutil.iter_modules(package.__path__)
        if not info.name.startswith("_")
    ]
    return sorted(names)


def create_app(config: dict | None = None) -> Flask:
    """Tworzy aplikację i rejestruje wszystkie widoki."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    # Flask 3 nie zna już klucza configu JSON_AS_ASCII — odpowiada za to app.json.
    # Bez tego polskie znaki w odpowiedziach JSON trafiają do przeglądarki jako \uXXXX.
    app.json.ensure_ascii = False
    if config:
        app.config.update(config)

    registered: list[str] = []
    for name in _blueprint_module_names():
        module = importlib.import_module(f"{BLUEPRINTS_PACKAGE}.{name}")
        blueprint = getattr(module, "bp", None)
        if blueprint is None:
            raise RuntimeError(f"Moduł {BLUEPRINTS_PACKAGE}.{name} nie wystawia 'bp'.")
        app.register_blueprint(blueprint)
        registered.append(name)
    app.config["BLUEPRINTS"] = registered
    return app
