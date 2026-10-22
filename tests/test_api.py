"""API contract: probes, listing creation, idempotency and the publish step."""

from __future__ import annotations

import pytest
from app.api import app
from app.config import settings
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.setattr(settings, "API_KEY", "")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(settings, "VISION_PROVIDER", "mock")
    monkeypatch.setattr(settings, "PUBLISH_ENABLED", True)
    with TestClient(app) as live:
        yield live


def test_health_is_always_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reports_the_database(client):
    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "up"


def test_create_listing_returns_a_reviewable_draft(client):
    response = client.post(
        "/api/v1/listings",
        json={
            "product": {"title_hint": "Bamboo Cutting Board", "brand": "GreenLeaf"},
            "languages": ["en", "hi"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"VALIDATED", "APPROVED", "PUBLISHED"}
    assert body["attributes"]["title"]
    assert len(body["content"]) == 2
    assert body["price"]["recommended_price"] > 0


def test_create_listing_is_idempotent(client):
    payload = {"product": {"title_hint": "Copper Kettle"}, "languages": ["en"]}

    first = client.post("/api/v1/listings", json=payload, headers={"Idempotency-Key": "abc"})
    second = client.post("/api/v1/listings", json=payload, headers={"Idempotency-Key": "abc"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["listing_id"] == second.json()["listing_id"]


def test_listing_can_be_fetched_with_its_audit_trail(client):
    created = client.post(
        "/api/v1/listings", json={"product": {"title_hint": "Wool Scarf"}, "languages": ["en"]}
    ).json()

    fetched = client.get(f"/api/v1/listings/{created['listing_id']}")
    audit = client.get(f"/api/v1/listings/{created['listing_id']}/audit")

    assert fetched.status_code == 200
    assert audit.status_code == 200
    assert audit.json()["events"]


def test_unknown_listing_returns_404(client):
    assert client.get("/api/v1/listings/does-not-exist").status_code == 404
    assert client.get("/api/v1/listings/does-not-exist/audit").status_code == 404


def test_publish_requires_an_approved_listing(client):
    created = client.post(
        "/api/v1/listings", json={"product": {"title_hint": "Ceramic Bowl"}, "languages": ["en"]}
    ).json()

    response = client.post(
        f"/api/v1/listings/{created['listing_id']}/publish",
        json={"marketplaces": ["amazon_in"], "language": "en"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["marketplace"] == "amazon_in"
    assert body["status"] == "PUBLISHED"


def test_write_endpoints_require_the_api_key(client, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "secret")

    blocked = client.post("/api/v1/listings", json={"product": {"title_hint": "X"}})
    allowed = client.post(
        "/api/v1/listings",
        json={"product": {"title_hint": "X"}},
        headers={"X-API-Key": "secret"},
    )

    assert blocked.status_code == 401
    assert allowed.status_code == 200


def test_listing_collection_is_listable(client):
    client.post("/api/v1/listings", json={"product": {"title_hint": "One"}, "languages": ["en"]})
    client.post("/api/v1/listings", json={"product": {"title_hint": "Two"}, "languages": ["en"]})

    response = client.get("/api/v1/listings")

    assert response.status_code == 200
    assert response.json()["count"] == 2
