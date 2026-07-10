"""The core REST API connector: auth styles, headers/params, response parsing,
pagination, limits, SSRF/TLS/read-only guarantees, and the connections API +
SQL Input integration."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

from app.connectors.base import ConnectionSpec, ConnectorError
from app.connectors.rest_api import RestApiConnector
from app.core.config import get_settings

USERS = [
    {"id": 1, "name": "ada", "active": True},
    {"id": 2, "name": "bo", "active": False},
    {"id": 3, "name": "cy", "active": True},
]
# 25 rows for pagination tests.
ORDERS = [{"order_id": i, "total": float(i)} for i in range(1, 26)]


class _Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype: str = "application/json", status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - http.server API
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        if url.path == "/users":
            self._send(json.dumps(USERS).encode())
        elif url.path == "/users/active":
            if qs.get("active") != ["true"]:
                self._send(b"[]", status=200)
            else:
                self._send(json.dumps([u for u in USERS if u["active"]]).encode())
        elif url.path == "/wrapped":
            self._send(json.dumps({"meta": {}, "data": {"items": USERS}}).encode())
        elif url.path == "/report.csv":
            self._send(b"id,total\n1,9.5\n2,12.0\n", ctype="text/csv")
        elif url.path == "/orders":
            page = int(qs.get("page", ["1"])[0])
            size = int(qs.get("per_page", ["10"])[0])
            start = (page - 1) * size
            self._send(json.dumps(ORDERS[start : start + size]).encode())
        elif url.path == "/private/bearer":
            if self.headers.get("Authorization") != "Bearer sesame":
                self._send(b"{}", status=401)
            else:
                self._send(json.dumps([{"ok": 1}]).encode())
        elif url.path == "/private/key":
            if self.headers.get("X-Custom-Key") != "sesame":
                self._send(b"{}", status=403)
            else:
                self._send(json.dumps([{"ok": 1}]).encode())
        elif url.path == "/private/basic":
            if self.headers.get("Authorization") != "Basic YWRhOnNlc2FtZQ==":  # ada:sesame
                self._send(b"{}", status=401)
            else:
                self._send(json.dumps([{"ok": 1}]).encode())
        elif url.path == "/private/query-key":
            if qs.get("api_key") != ["sesame"]:
                self._send(b"{}", status=401)
            else:
                self._send(json.dumps([{"ok": 1}]).encode())
        elif url.path == "/private/gkey":
            if qs.get("key") != ["sesame"]:
                self._send(b"{}", status=401)
            else:
                self._send(json.dumps([{"ok": 1}]).encode())
        elif url.path == "/echo-headers":
            self._send(json.dumps([{"tenant": self.headers.get("X-Tenant", "")}]).encode())
        elif url.path == "/echo-page":
            self._send(json.dumps([{"page": qs.get("page", [""])[0]}]).encode())
        else:
            self._send(b"{}", status=404)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def api():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _spec(base_url: str, password: str | None = None, username: str | None = None, **options) -> ConnectionSpec:
    return ConnectionSpec(provider="rest_api", host=base_url, username=username, password=password, options=options)


connector = RestApiConnector()


# -- reading ------------------------------------------------------------------------


def test_read_table_json(api):
    df = connector.read_table(_spec(api), "users", None, None)
    assert list(df["name"]) == ["ada", "bo", "cy"]


def test_read_table_applies_limit(api):
    assert len(connector.read_table(_spec(api), "users", None, 2)) == 2


def test_read_csv_by_content_type(api):
    df = connector.read_table(_spec(api), "report.csv", None, None)
    assert list(df["total"]) == [9.5, 12.0]


def test_records_path_unwraps_nested_payloads(api):
    df = connector.read_table(_spec(api, records_path="data.items"), "wrapped", None, None)
    assert len(df) == 3
    with pytest.raises(ConnectorError, match="records_path"):
        connector.read_table(_spec(api, records_path="data.nope"), "wrapped", None, None)


def test_common_wrappers_unwrap_without_a_records_path(api):
    # /wrapped nests under data.items — "data" alone isn't a list, so this needs
    # the explicit path; but a top-level {"data": [...]} style works out of the box.
    df = connector.read_query(_spec(api), "users")
    assert len(df) == 3


def test_default_query_params_apply(api):
    df = connector.read_table(_spec(api, query_params={"active": "true"}), "users/active", None, None)
    assert list(df["name"]) == ["ada", "cy"]


def test_read_query_is_a_custom_request_path(api):
    df = connector.read_query(_spec(api), "users/active?active=true")
    assert list(df["name"]) == ["ada", "cy"]


def test_custom_headers_are_sent(api):
    df = connector.read_table(_spec(api, headers={"X-Tenant": "acme"}), "echo-headers", None, None)
    assert df["tenant"].iloc[0] == "acme"


# -- authentication -------------------------------------------------------------------


def test_bearer_auth(api):
    with pytest.raises(ConnectorError, match="401"):
        connector.read_table(_spec(api, password="wrong", auth_style="bearer"), "private/bearer", None, None)
    df = connector.read_table(_spec(api, password="sesame", auth_style="bearer"), "private/bearer", None, None)
    assert df["ok"].iloc[0] == 1


def test_api_key_auth_with_custom_header(api):
    spec = _spec(api, password="sesame", auth_style="api_key", api_key_header="X-Custom-Key")
    assert connector.read_table(spec, "private/key", None, None)["ok"].iloc[0] == 1


def test_basic_auth(api):
    spec = _spec(api, password="sesame", username="ada", auth_style="basic")
    assert connector.read_table(spec, "private/basic", None, None)["ok"].iloc[0] == 1


def test_auth_without_secret_is_a_clear_error(api):
    with pytest.raises(ConnectorError, match="secret env var"):
        connector.read_table(_spec(api, auth_style="bearer"), "users", None, None)


def test_errors_never_leak_the_secret(api):
    spec = _spec(api, password="super-secret-token", auth_style="bearer")
    with pytest.raises(ConnectorError) as err:
        connector.read_table(spec, "private/bearer", None, None)
    assert "super-secret-token" not in str(err.value)


def test_query_param_auth(api):
    spec = _spec(api, password="sesame", auth_style="query_param")  # default param: api_key
    assert connector.read_table(spec, "private/query-key", None, None)["ok"].iloc[0] == 1


def test_query_param_auth_with_custom_param_name(api):
    spec = _spec(api, password="sesame", auth_style="query_param", api_key_param="key")
    assert connector.read_table(spec, "private/gkey", None, None)["ok"].iloc[0] == 1


def test_query_param_auth_requires_secret(api):
    with pytest.raises(ConnectorError, match="secret env var"):
        connector.read_table(_spec(api, auth_style="query_param"), "private/query-key", None, None)


def test_query_param_auth_rejects_bad_param_name(api):
    spec = _spec(api, password="sesame", auth_style="query_param", api_key_param="a&b=c")
    with pytest.raises(ConnectorError, match="api_key_param"):
        connector.read_table(spec, "private/query-key", None, None)


def test_query_param_auth_overrides_plaintext_duplicates(api):
    """The resolved secret must win over a stale plaintext duplicate in the
    endpoint path or in the stored query_params option."""
    spec = _spec(api, password="sesame", auth_style="query_param", query_params={"api_key": "stale-stored"})
    df = connector.read_query(spec, "private/query-key?api_key=stale-in-path")
    assert df["ok"].iloc[0] == 1  # the real secret was sent, not either duplicate


def test_query_param_secret_never_leaks_in_error_urls(api):
    """The URL embedded in HTTP error messages carries the auth query param —
    it must be scrubbed like every other error path."""
    spec = _spec(api, password="wrong-but-still-secret", auth_style="query_param")
    with pytest.raises(ConnectorError) as err:
        connector.read_table(spec, "private/query-key", None, None)
    assert "401" in str(err.value)
    assert "wrong-but-still-secret" not in str(err.value)


# -- pagination -----------------------------------------------------------------------


def test_page_number_pagination_collects_all_pages(api):
    spec = _spec(api, page_param="page", page_size_param="per_page", page_size=10, max_pages=10)
    df = connector.read_table(spec, "orders", None, None)
    assert list(df["order_id"]) == list(range(1, 26))


def test_pagination_respects_max_pages_and_limit(api):
    spec = _spec(api, page_param="page", page_size_param="per_page", page_size=10, max_pages=1)
    assert len(connector.read_table(spec, "orders", None, None)) == 10

    spec = _spec(api, page_param="page", page_size_param="per_page", page_size=10, max_pages=10)
    assert len(connector.read_table(spec, "orders", None, 12)) == 12


def test_start_page_zero_is_respected_for_zero_indexed_apis(api):
    # `start_page=0` must request page "0" first, not silently fall back to 1 —
    # that fallback is only meant to kick in when the option is absent.
    spec = _spec(api, page_param="page", page_size_param="per_page", page_size=10, max_pages=1, start_page=0)
    df = connector.read_table(spec, "echo-page", None, None)
    assert df["page"].iloc[0] == "0"


def test_start_page_defaults_to_one_when_absent(api):
    spec = _spec(api, page_param="page", page_size_param="per_page", page_size=10, max_pages=1)
    df = connector.read_table(spec, "echo-page", None, None)
    assert df["page"].iloc[0] == "1"


def test_pagination_size_cap_is_cumulative(api, monkeypatch):
    """Each page can be under the per-request cap while the read as a whole
    grows unbounded — the cap must apply across pages too."""
    from app.connectors import rest_api as rest_api_mod

    # The first "orders" page is ~400 bytes; a 500-byte cap admits one page but
    # must refuse the read once the second page arrives.
    monkeypatch.setattr(rest_api_mod, "MAX_RESPONSE_BYTES", 500)
    spec = _spec(api, page_param="page", page_size_param="per_page", page_size=10, max_pages=10)
    with pytest.raises(ConnectorError, match="across pages"):
        connector.read_table(spec, "orders", None, None)


# -- connection surface -----------------------------------------------------------------


def test_test_connection_and_list_tables(api):
    spec = _spec(api, endpoints=["users", "orders"])
    connector.test_connection(spec)  # does not raise
    assert [t.name for t in connector.list_tables(spec)] == ["users", "orders"]


def test_test_connection_fails_cleanly(api):
    with pytest.raises(ConnectorError, match="404"):
        connector.test_connection(_spec(api, endpoints=["missing"]))


def test_writes_are_refused(api):
    with pytest.raises(ConnectorError, match="read-only"):
        connector.write_table(_spec(api), pd.DataFrame({"a": [1]}), "users", None, "replace")


def test_base_url_must_be_http(api):
    with pytest.raises(ConnectorError, match="http"):
        connector.read_table(_spec("file:///etc"), "users", None, None)
    with pytest.raises(ConnectorError, match="base URL"):
        connector.read_table(_spec(""), "users", None, None)


def test_absolute_endpoint_urls_are_refused(api):
    with pytest.raises(ConnectorError, match="relative"):
        connector.read_table(_spec(api), "https://evil.example/exfil", None, None)


def test_ssrf_guard_blocks_private_hosts(api, monkeypatch):
    monkeypatch.setenv("CIAREN_CONNECTOR_BLOCK_PRIVATE_HOSTS", "true")
    get_settings.cache_clear()
    try:
        with pytest.raises(ConnectorError, match="blocked"):
            connector.read_table(_spec(api), "users", None, None)
    finally:
        get_settings.cache_clear()


# -- API + SQL Input integration -----------------------------------------------------------


async def _create_connection(client, api, **overrides):
    body = {
        "name": "demo-api",
        "provider": "rest_api",
        "host": api,
        "options": {"endpoints": ["users", "orders"]},
    }
    body.update(overrides)
    r = await client.post("/api/connections", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def test_api_connection_crud_test_and_tables(client, api):
    created = await _create_connection(client, api)
    assert created["connection_type"] == "api"

    t = await client.post(f"/api/connections/{created['id']}/test")
    assert t.status_code == 200 and t.json()["ok"] is True, t.text

    tables = await client.get(f"/api/connections/{created['id']}/tables")
    assert {x["name"] for x in tables.json()} == {"users", "orders"}


async def test_api_connection_rejects_credential_query_params(client, api):
    """A credential-looking key in the stored query_params must be refused at
    save time — it would persist the secret in plain text and echo it back in
    every API response."""
    for key in ("api_key", "token", "ACCESS_TOKEN", "key", "client_secret"):
        r = await client.post(
            "/api/connections",
            json={
                "name": f"leaky-{key}",
                "provider": "rest_api",
                "host": api,
                "options": {"query_params": {key: "plaintext-secret"}},
            },
        )
        assert r.status_code == 400, f"{key}: {r.text}"
        assert "plain text" in r.json()["detail"]


async def test_api_connection_rejects_credential_query_params_on_update(client, api):
    created = await _create_connection(client, api)
    r = await client.patch(
        f"/api/connections/{created['id']}",
        json={"options": {"query_params": {"api_key": "plaintext-secret"}}},
    )
    assert r.status_code == 400, r.text


async def test_api_connection_allows_benign_query_params(client, api):
    created = await _create_connection(
        client, api, name="benign-params", options={"endpoints": ["users"], "query_params": {"active": "true"}}
    )
    assert created["options"]["query_params"] == {"active": "true"}


async def test_api_connection_requires_a_base_url(client):
    r = await client.post("/api/connections", json={"name": "bad", "provider": "rest_api"})
    assert r.status_code == 400
    assert "base URL" in r.json()["detail"]


async def test_providers_list_includes_rest_api(client):
    r = await client.get("/api/connections/providers")
    entry = next(p for p in r.json() if p["name"] == "rest_api")
    assert entry["kind"] == "api"
    assert entry["available"] is True
    assert entry["supports_query"] is True


async def test_sql_input_materializes_an_api_endpoint(db_session, api, tmp_path):
    from app.db.models.connection import Connection
    from app.services.sql_resolver import materialize_sql_inputs

    conn = Connection(name="api", provider="rest_api", host=api, options_json={})
    db_session.add(conn)
    await db_session.commit()

    graph = {
        "nodes": [
            {
                "id": "sq1",
                "type": "sqlInput",
                "data": {"config": {"connection_id": conn.id, "mode": "table", "table": "users"}},
            }
        ],
        "edges": [],
    }
    paths = await materialize_sql_inputs(db_session, graph, tmp_path)
    assert list(pd.read_parquet(paths["sq1"])["name"]) == ["ada", "bo", "cy"]
