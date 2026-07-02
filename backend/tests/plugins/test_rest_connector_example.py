"""The REST API connector example plugin: runtime behavior against a real local
HTTP server, plus discovery/bridging through the loader and the connections
service + SQL-node resolver."""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = REPO_ROOT / "examples" / "plugins" / "rest-connector-plugin"

USERS = [
    {"id": 1, "name": "ada", "active": True},
    {"id": 2, "name": "bo", "active": False},
    {"id": 3, "name": "cy", "active": True},
]


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server API
        if self.path == "/users":
            body = json.dumps(USERS).encode()
            ctype = "application/json"
        elif self.path == "/wrapped":
            body = json.dumps({"data": USERS, "next": None}).encode()
            ctype = "application/json"
        elif self.path == "/report.csv":
            body = b"id,total\n1,9.5\n2,12.0\n"
            ctype = "text/csv"
        elif self.path == "/private":
            if self.headers.get("Authorization") != "Bearer sesame":
                self.send_response(401)
                self.end_headers()
                return
            body = json.dumps([{"secret": 42}]).encode()
            ctype = "application/json"
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep test output clean
        pass


@pytest.fixture(scope="module")
def api_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="module")
def runtime():
    if str(PLUGIN_DIR) not in sys.path:
        sys.path.append(str(PLUGIN_DIR))
    from ciaren_rest.plugin import RestApiRuntime

    return RestApiRuntime()


def _config(base_url: str, **options):
    return {
        "host": None,
        "port": None,
        "database": None,
        "username": None,
        "password": options.pop("password", None),
        "options": {"base_url": base_url, **options},
    }


# -- runtime -----------------------------------------------------------------------


def test_test_reaches_the_api(runtime, api_server):
    result = runtime.test(_config(api_server, endpoints=["users"]))
    assert result.ok is True


def test_test_reports_unreachable_and_missing_config(runtime, api_server):
    assert runtime.test(_config(api_server, endpoints=["nope"])).ok is False
    assert "base_url" in runtime.test({"options": {}}).message


def test_list_tables_lists_declared_endpoints(runtime, api_server):
    tables = runtime.list_tables(_config(api_server, endpoints=["users", "report.csv"]))
    assert [t["name"] for t in tables] == ["users", "report.csv"]


def test_read_json_endpoint(runtime, api_server):
    df = runtime.read(_config(api_server), {"mode": "table", "table": "users", "limit": None})
    assert list(df["name"]) == ["ada", "bo", "cy"]
    assert list(df.columns) == ["id", "name", "active"]


def test_read_unwraps_common_json_envelopes(runtime, api_server):
    df = runtime.read(_config(api_server), {"table": "wrapped"})
    assert len(df) == 3


def test_read_csv_endpoint_by_content_type(runtime, api_server):
    df = runtime.read(_config(api_server), {"table": "report.csv"})
    assert list(df["total"]) == [9.5, 12.0]


def test_read_applies_the_preview_limit(runtime, api_server):
    df = runtime.read(_config(api_server), {"table": "users", "limit": 2})
    assert len(df) == 2


def test_bearer_auth_sends_the_resolved_secret(runtime, api_server):
    unauthorized = _config(api_server, auth_style="bearer", password=None)
    with pytest.raises(ValueError, match="password env var"):
        runtime.read(unauthorized, {"table": "private"})

    authorized = _config(api_server, auth_style="bearer", password="sesame")
    df = runtime.read(authorized, {"table": "private"})
    assert df["secret"].iloc[0] == 42


def test_read_rejects_query_mode_with_a_clear_error(runtime, api_server):
    with pytest.raises(ValueError, match="endpoints"):
        runtime.read(_config(api_server), {"mode": "query", "query": "SELECT 1"})


def test_non_http_base_url_is_refused(runtime):
    with pytest.raises(ValueError, match="http"):
        runtime.read(_config("file:///etc"), {"table": "users"})


# -- through the loader, connections service, and SQL resolver ----------------------


@pytest.fixture
def _loaded_plugin(monkeypatch):
    from app.plugins import get_registry, reset_registry
    from app.plugins.state import PluginStateStore

    monkeypatch.setenv("CIAREN_PLUGINS_DIR", str(PLUGIN_DIR.parent))
    state = PluginStateStore()
    state.set_approved("community.rest-connector", True)
    state.grant("community.rest-connector", ["network", "credentials"])
    state.save()
    reset_registry()
    get_registry()
    yield
    reset_registry()


def test_connector_registers_with_schema(_loaded_plugin):
    from app.plugins import get_registry

    spec = get_registry().connector_spec("rest-api")
    assert spec is not None
    assert spec.kind == "api"
    keys = [f["key"] for f in spec.config_schema["fields"]]
    assert "base_url" in keys and "endpoints" in keys


async def test_service_tests_and_lists_tables(_loaded_plugin, db_session, api_server):
    from app.db.models.connection import Connection
    from app.services.connection_service import ConnectionService

    conn = Connection(
        name="demo-api",
        provider="rest-api",
        options_json={"base_url": api_server, "endpoints": ["users", "report.csv"]},
    )
    db_session.add(conn)
    await db_session.commit()

    service = ConnectionService(db_session)
    result = await service.test(conn.id)
    assert result.ok is True

    tables = await service.list_tables(conn.id)
    assert {t.name for t in tables} == {"users", "report.csv"}


async def test_sql_input_materializes_an_endpoint(_loaded_plugin, db_session, api_server, tmp_path):
    from app.db.models.connection import Connection
    from app.services.sql_resolver import materialize_sql_inputs

    conn = Connection(name="demo-api", provider="rest-api", options_json={"base_url": api_server})
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
    df = pd.read_parquet(paths["sq1"])
    assert list(df["name"]) == ["ada", "bo", "cy"]


def test_signed_package_is_bundled_in_catalog():
    from app.plugins.package import read_manifest, verify_package

    bundled = REPO_ROOT / "backend" / "app" / "bundled_plugins"
    pkg = bundled / "community.rest-connector-0.1.0.ciarenplugin"
    assert pkg.is_file(), "run examples/plugins/build_rest_connector_ciarenplugin.py"
    manifest = read_manifest(pkg)
    assert manifest.id == "community.rest-connector"
    assert set(manifest.permissions) >= {"network", "credentials"}

    demo_key = {"ciaren-demo": "b827f3795467a701b018a0d57ab5900af43669d3622340905559d86ae2ec4bdd"}
    assert verify_package(pkg, trusted_keys=demo_key).outcome == "trusted"
