"""Connection management endpoints.

GET/POST   /api/connections
GET        /api/connections/providers
GET/PATCH/DELETE /api/connections/{id}
POST       /api/connections/{id}/test
GET        /api/connections/{id}/tables
"""

import pandas as pd
import pytest
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
    r = await client.post("/api/connections", json={"name": "dup", "provider": "sqlite", "database": "/tmp/y.db"})
    assert r.status_code == 409


async def test_validation_requires_fields(client: AsyncClient):
    # SQLite needs a database path.
    r = await client.post("/api/connections", json={"name": "bad", "provider": "sqlite"})
    assert r.status_code == 400
    # Postgres needs a host.
    r2 = await client.post("/api/connections", json={"name": "pg", "provider": "postgresql", "database": "d"})
    assert r2.status_code == 400


async def test_unknown_provider_rejected(client: AsyncClient):
    r = await client.post("/api/connections", json={"name": "x", "provider": "oracle9000", "database": "d"})
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
    created = await _create(client, name="mysqlconn", provider="mysql", host="localhost", database="d")
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
    bad = await client.post("/api/connections/test-config", json={"name": "x", "provider": "sqlite"})
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
    patched = await client.patch(f"/api/connections/{created['id']}", json={"name": "renamed"})
    assert patched.status_code == 200
    assert patched.json()["name"] == "renamed"

    deleted = await client.delete(f"/api/connections/{created['id']}")
    assert deleted.status_code == 204
    missing = await client.get(f"/api/connections/{created['id']}")
    assert missing.status_code == 404


# -- password_env validation -----------------------------------------------


async def test_valid_password_env_names_are_accepted(client: AsyncClient):
    """Valid POSIX env var names (letters, digits, underscores) are accepted."""
    for name in ["DB_PASS", "db_password", "MY_SECRET_123", "_LEADING_UNDERSCORE"]:
        r = await client.post(
            "/api/connections",
            json={"name": f"conn_{name}", "provider": "sqlite", "database": "/tmp/x.db", "password_env": name},
        )
        assert r.status_code == 201, f"Expected 201 for password_env={name!r}, got {r.status_code}: {r.text}"


async def test_invalid_password_env_names_are_rejected(client: AsyncClient):
    """Env var names that start with a digit or contain special chars are rejected at the schema level."""
    for bad in ["1STARTS_WITH_DIGIT", "has space", "has-dash", "has$dollar", ""]:
        if not bad:
            continue  # None/empty means "no password" and is valid
        r = await client.post(
            "/api/connections",
            json={"name": "bad_conn", "provider": "sqlite", "database": "/tmp/x.db", "password_env": bad},
        )
        assert r.status_code == 422, f"Expected 422 for password_env={bad!r}, got {r.status_code}"


async def test_password_env_cannot_name_app_config(client: AsyncClient):
    """Ciaren's own config vars (API token, webhook secrets, …) are never usable
    as a connection secret — that would let a connection exfiltrate them to a
    user-chosen host."""
    r = await client.post(
        "/api/connections",
        json={
            "name": "sneaky",
            "provider": "sqlite",
            "database": "/tmp/x.db",
            "password_env": "CIAREN_API_TOKEN",
        },
    )
    assert r.status_code == 400
    assert "configuration" in r.json()["detail"].lower()


async def test_secret_env_allowlist_enforced(client: AsyncClient, monkeypatch):
    """With CIAREN_SECRET_ENV_ALLOWLIST set, only listed names (or `PREFIX*`
    entries) are accepted; anything else is refused at save time."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "SECRET_ENV_ALLOWLIST", ["PG_*", "MY_DB_PASSWORD"])
    denied = await client.post(
        "/api/connections",
        json={"name": "denied", "provider": "sqlite", "database": "/tmp/x.db", "password_env": "AWS_SECRET_KEY"},
    )
    assert denied.status_code == 400
    assert "allowlist" in denied.json()["detail"].lower()
    for ok_name in ("PG_PASSWORD", "MY_DB_PASSWORD"):
        r = await client.post(
            "/api/connections",
            json={"name": f"ok-{ok_name}", "provider": "sqlite", "database": "/tmp/x.db", "password_env": ok_name},
        )
        assert r.status_code == 201, r.text


async def test_keyring_and_file_secret_refs_accepted(client: AsyncClient, monkeypatch, tmp_path):
    """The new reference schemes save fine; file: refs are confined at save time."""
    from app.core.config import get_settings

    r = await client.post(
        "/api/connections",
        json={"name": "kr", "provider": "sqlite", "database": "/tmp/x.db", "password_env": "keyring:pg-main"},
    )
    assert r.status_code == 201, r.text

    monkeypatch.setattr(get_settings(), "SECRET_FILE_DIRS", [str(tmp_path / "secrets")])
    ok = await client.post(
        "/api/connections",
        json={
            "name": "file-ok",
            "provider": "sqlite",
            "database": "/tmp/x.db",
            "password_env": f"file:{tmp_path / 'secrets' / 'pg'}",
        },
    )
    assert ok.status_code == 201, ok.text
    outside = await client.post(
        "/api/connections",
        json={
            "name": "file-outside",
            "provider": "sqlite",
            "database": "/tmp/x.db",
            "password_env": f"file:{tmp_path / 'elsewhere' / 'pg'}",
        },
    )
    assert outside.status_code == 400
    assert "secrets folder" in outside.json()["detail"].lower()


async def test_unknown_secret_scheme_rejected(client: AsyncClient):
    r = await client.post(
        "/api/connections",
        json={"name": "bad-scheme", "provider": "sqlite", "database": "/tmp/x.db", "password_env": "vault:pg"},
    )
    assert r.status_code == 422


def test_sql_options_cannot_override_target():
    """Driver options that redirect the connection (host/odbc_connect/…) are
    refused — they would bypass the SSRF guard, which only checks spec.host."""
    from app.connectors.base import ConnectorError
    from app.connectors.sql import SqlConnector

    for options in (
        {"host": "internal-db"},
        {"ODBC_CONNECT": "DRIVER=x;SERVER=evil"},
        {"port": "9999"},
        {"service": "other-target"},  # psycopg: loads the target from pg_service.conf
        {"read_default_file": "/tmp/evil.cnf"},  # pymysql: option file with host/creds
    ):
        spec = ConnectionSpec(provider="postgresql", host="db.example.com", database="d", options=options)
        with pytest.raises(ConnectorError, match="not allowed"):
            SqlConnector()._url(spec)
    # Benign driver options still pass through.
    spec = ConnectionSpec(provider="postgresql", host="db.example.com", database="d", options={"sslmode": "require"})
    assert SqlConnector()._url(spec).query["sslmode"] == "require"


async def test_api_connection_rejects_secret_headers(client: AsyncClient):
    """A static Authorization/API-key header would store the credential in plain
    text — refused in favor of auth_style + the secret env var."""
    r = await client.post(
        "/api/connections",
        json={
            "name": "leaky-api",
            "provider": "rest_api",
            "host": "https://api.example.com",
            "options": {"headers": {"Authorization": "Bearer hardcoded-token"}},
        },
    )
    assert r.status_code == 400
    assert "authentication settings" in r.json()["detail"].lower()
    # Non-secret custom headers are fine.
    ok = await client.post(
        "/api/connections",
        json={
            "name": "ok-api",
            "provider": "rest_api",
            "host": "https://api.example.com",
            "options": {"headers": {"Accept-Language": "en"}},
        },
    )
    assert ok.status_code == 201, ok.text


# -- Delete-in-use guard ------------------------------------------------------


async def test_delete_connection_used_by_flow_conflicts(client: AsyncClient):
    created = await _create(client, name="in-use")
    graph = {
        "nodes": [
            {
                "id": "in1",
                "type": "sqlInput",
                "data": {"config": {"connection_id": created["id"], "mode": "table", "table": "t"}},
            },
            # A node with null data must not crash the reference scan.
            {"id": "odd", "type": "filterRows", "data": None},
        ],
        "edges": [],
    }
    flow = await client.post("/api/flows", json={"name": "uses-conn", "graph_json": graph})
    assert flow.status_code == 201, flow.text

    refused = await client.delete(f"/api/connections/{created['id']}")
    assert refused.status_code == 409
    assert "uses-conn" in refused.json()["detail"]
    # The connection is still there.
    assert (await client.get(f"/api/connections/{created['id']}")).status_code == 200

    forced = await client.delete(f"/api/connections/{created['id']}?force=true")
    assert forced.status_code == 204
    assert (await client.get(f"/api/connections/{created['id']}")).status_code == 404


async def test_delete_unused_connection_needs_no_force(client: AsyncClient):
    created = await _create(client, name="unused")
    r = await client.delete(f"/api/connections/{created['id']}")
    assert r.status_code == 204


# -- MLflow tracking connection ---------------------------------------------


async def test_mlflow_provider_listed(client: AsyncClient):
    r = await client.get("/api/connections/providers")
    providers = {p["name"]: p for p in r.json()}
    assert "mlflow" in providers
    assert providers["mlflow"]["kind"] == "mlflow"


async def test_mlflow_connection_requires_uri(client: AsyncClient):
    r = await client.post("/api/connections", json={"name": "ml-bad", "provider": "mlflow"})
    assert r.status_code == 400
    assert "tracking uri" in r.json()["detail"].lower()


async def test_mlflow_connection_type_is_mlflow(client: AsyncClient, tmp_path):
    created = await _create(client, name="ml-conn", provider="mlflow", database=str(tmp_path / "mlruns"))
    assert created["connection_type"] == "mlflow"


async def test_mlflow_connection_test_succeeds_for_local_store(client: AsyncClient, tmp_path):
    created = await _create(client, name="ml-local", provider="mlflow", database=str(tmp_path / "mlruns"))
    r = await client.post(f"/api/connections/{created['id']}/test")
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_test_records_last_tested_at(client: AsyncClient, tmp_path):
    db = str(tmp_path / "warehouse.db")
    _seed_sqlite(db)
    created = await _create(client, name="dated", database=db)
    assert created["last_tested_at"] is None
    await client.post(f"/api/connections/{created['id']}/test")
    after = (await client.get(f"/api/connections/{created['id']}")).json()
    assert after["last_tested_at"] is not None


async def test_mlflow_connection_is_source_of_truth(client: AsyncClient, db_session, tmp_path):
    """resolve_tracking_uri returns the connection's URI over the setting default."""
    from app.ml.tracking import resolve_tracking_uri

    uri = str(tmp_path / "custom_mlruns")
    await _create(client, name="ml-truth", provider="mlflow", database=uri)
    # db_session shares the test engine with the API client, so the row is visible.
    resolved = await resolve_tracking_uri(db_session)
    assert resolved.endswith("custom_mlruns")
