"""Test dymny: aplikacja startuje, a endpoint /zdrowie odpowiada."""

from __future__ import annotations

from app import create_app


def test_aplikacja_startuje():
    app = create_app({"TESTING": True})
    assert "core" in app.config["BLUEPRINTS"]


def test_zdrowie_odpowiada():
    client = create_app({"TESTING": True}).test_client()
    response = client.get("/zdrowie")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
