"""Connection management endpoints.

  GET/POST   /api/connections
  GET        /api/connections/providers
  GET/PATCH/DELETE /api/connections/{id}
  POST       /api/connections/{id}/test
  GET        /api/connections/{id}/tables
"""

import pandas as pd
from httpx import AsyncClient

from app.connectors import ConnectionSpec, get_connector, get_provider


def _seed_sqlite(path: str) -> None:
    """Create a SQLite file with one table so list/test have something to find."""
    conn = get_connector(get_provider("sqlite"))
    spec = ConnectionSpec(provider="sqlite", database=path)
    df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
    conn.write_table(spec, df, "users", None, "replace")


async def _create(client: AsyncClient, **overrides) -> dict:
    body = {"name": "wh", "provider": "sqlite", "database": "/tmp/x.db"}
    body.update(overrides)
    r = await client.post("/api/connections", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_and_list(client: AsyncClient):
    created = await _create(client, name="warehouse")
    assert created["provider"] == "sqlite"
    listed = await client.get("/api/connections")
    assert listed.status_code == 200
    assert any(c["id"] == created["id"] for c in listed.json())


async def test_response_never_exposes_a_password(client: AsyncClient):
    created = await _create(client, name="secretive", password_env="PG_PASSWORD")
    # Only the env-var NAME is returned — never a 'password' field/value.
    assert created["password_env"] == "PG_PASSWORD"
    assert "password" not in created


async def test_duplicate_name_conflicts(client: AsyncClient):
    await _create(client, name="dup")
    r = await client.post(
        "/api/connections", json={"name": "dup", "provider": "sqlite", "database": "/tmp/y.db"}
    )
    assert r.status_code == 409


async def test_validation_requires_fields(client: AsyncClient):
    # SQLite needs a database path.
    r = await client.post("/api/connections", json={"name": "bad", "provider": "sqlite"})
    assert r.status_code == 400
    # Postgres needs a host.
    r2 = await client.post(
        "/api/connections", json={"name": "pg", "provider": "postgresql", "database": "d"}
    )
    assert r2.status_code == 400


async def test_unknown_provider_rejected(client: AsyncClient):
    r = await client.post(
        "/api/connections", json={"name": "x", "provider": "oracle9000", "database": "d"}
    )
    assert r.status_code == 400


async def test_providers_endpoint_reports_availability(client: AsyncClient):
    r = await client.get("/api/connections/providers")
    assert r.status_code == 200
    providers = {p["name"]: p for p in r.json()}
    assert providers["sqlite"]["available"] is True
    assert "postgresql" in providers and "mongodb" in providers


async def test_test_endpoint_success_for_sqlite(client: AsyncClient, tmp_path):
    db = str(tmp_path / "warehouse.db")
    _seed_sqlite(db)
    created = await _create(client, name="real", database=db)
    r = await client.post(f"/api/connections/{created['id']}/test")
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_test_endpoint_reports_missing_driver(client: AsyncClient):
    # MySQL driver isn't installed in CI → ok=False with an install hint, not a crash.
    created = await _create(
        client, name="mysqlconn", provider="mysql", host="localhost", database="d"
    )
    r = await client.post(f"/api/connections/{created['id']}/test")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "driver" in body["message"].lower()


async def test_list_tables_for_sqlite(client: AsyncClient, tmp_path):
    db = str(tmp_path / "tables.db")
    _seed_sqlite(db)
    created = await _create(client, name="tbls", database=db)
    r = await client.get(f"/api/connections/{created['id']}/tables")
    assert r.status_code == 200
    assert any(t["name"] == "users" for t in r.json())


async def test_test_config_before_saving(client: AsyncClient, tmp_path):
    # A valid SQLite payload tests OK without being saved first.
    db = str(tmp_path / "probe.db")
    _seed_sqlite(db)
    r = await client.post(
        "/api/connections/test-config",
        json={"name": "x", "provider": "sqlite", "database": db},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # Nothing was persisted by a test.
    listed = await client.get("/api/connections")
    assert listed.json() == []


async def test_test_config_reports_problems(client: AsyncClient):
    # Missing required field → ok=False (not a 500).
    bad = await client.post(
        "/api/connections/test-config", json={"name": "x", "provider": "sqlite"}
    )
    assert bad.status_code == 200
    assert bad.json()["ok"] is False
    # Missing driver → ok=False with an install hint.
    mysql = await client.post(
        "/api/connections/test-config",
        json={"name": "x", "provider": "mysql", "host": "localhost", "database": "d"},
    )
    assert mysql.json()["ok"] is False
    assert "driver" in mysql.json()["message"].lower()


async def test_update_and_delete(client: AsyncClient):
    created = await _create(client, name="temp")
    patched = await client.patch(
        f"/api/connections/{created['id']}", json={"name": "renamed"}
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "renamed"

    deleted = await client.delete(f"/api/connections/{created['id']}")
    assert deleted.status_code == 204
    missing = await client.get(f"/api/connections/{created['id']}")
    assert missing.status_code == 404
