"""Authenticated watchlists with migration, ownership and signed JWT boundaries."""
from __future__ import annotations
import time
from pathlib import Path

import jwt
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from apps.api.main import app
from apps.api.storage import _engine

SECRET = "ci-only-secret-never-use-outside-ci-1234567"
client = TestClient(app)

@pytest.fixture
def configured(monkeypatch, tmp_path):
    url = "sqlite:///" + str(tmp_path / "research.db")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("QUANTEDGE_ALLOW_SQLITE_TEST_DB", "1")
    monkeypatch.setenv("QUANTEDGE_API_JWT_SECRET", SECRET)
    config = Config("apps/api/alembic.ini")
    command.upgrade(config, "head")
    yield
    command.downgrade(config, "base")
    assert "qe_users" not in inspect(_engine(url)).get_table_names()
    _engine(url).dispose()

def bearer(subject="github:100"):
    return {"Authorization": "Bearer " + jwt.encode(
        {"sub": subject, "iss": "quantedge-next", "aud": "quantedge-api",
         "iat": int(time.time()), "exp": int(time.time()) + 60}, SECRET, algorithm="HS256")}

def test_missing_bearer_and_bad_signature(configured):
    assert client.get("/api/v1/watchlists").status_code == 401
    assert client.get("/api/v1/watchlists", headers={"Authorization": "Bearer xyz"}).status_code == 401
    assert client.get("/api/v1/watchlists", headers=bearer("email:100")).status_code == 401

def test_isolation_writes_duplicate_validation_and_remove(configured):
    a, b = bearer("github:101"), bearer("github:202")
    created = client.post("/api/v1/watchlists", json={"name": " Quant "}, headers=a)
    assert created.status_code == 201, created.text
    wid = created.json()["id"]
    assert created.json()["name"] == "Quant"
    assert client.post("/api/v1/watchlists", json={"name": "Quant"}, headers=a).status_code == 409
    assert client.post("/api/v1/watchlists", json={"name": " "}, headers=a).status_code == 422
    assert client.post("/api/v1/watchlists", json={"name": "Other"}, headers=b).status_code == 201
    added = client.post(f"/api/v1/watchlists/{wid}/symbols", json={"symbol": "msft"}, headers=a)
    assert added.status_code == 201, added.text
    assert client.post(f"/api/v1/watchlists/{wid}/symbols", json={"symbol": "MSFT"}, headers=a).status_code == 409
    assert client.post(f"/api/v1/watchlists/{wid}/symbols", json={"symbol": "invalid!"}, headers=a).status_code == 422
    mine = client.get("/api/v1/watchlists", headers=a).json()["watchlists"]
    other = client.get("/api/v1/watchlists", headers=b).json()["watchlists"]
    assert len(mine) == len(other) == 1
    assert mine[0]["symbols"] == ["MSFT"]
    assert other[0]["symbols"] == []
    assert client.delete(f"/api/v1/watchlists/{wid}", headers=b).status_code == 404
    assert client.post(f"/api/v1/watchlists/{wid}/symbols", json={"symbol": "AAPL"}, headers=b).status_code == 404
    assert client.delete(f"/api/v1/watchlists/{wid}/symbols/MSFT", headers=b).status_code == 404
    assert client.delete(f"/api/v1/watchlists/{wid}/symbols/MSFT", headers=a).status_code == 200
    assert client.delete(f"/api/v1/watchlists/{wid}", headers=a).status_code == 200
    assert client.get("/api/v1/watchlists", headers=a).json()["watchlists"] == []

def test_reject_cross_tenant_invalid_token_claims(configured):
    now = int(time.time())
    for claims in (
        {"sub": "github:101", "iss": "attacker", "aud": "quantedge-api"},
        {"sub": "github:101", "iss": "quantedge-next", "aud": "attacker"},
        {"sub": "github:101", "iss": "quantedge-next", "aud": "quantedge-api", "exp": now - 600},
    ):
        payload = {"iat": now, "exp": now + 60, **claims}
        token = jwt.encode(payload, SECRET, algorithm="HS256")
        assert client.get("/api/v1/watchlists", headers={"Authorization": "Bearer " + token}).status_code == 401
