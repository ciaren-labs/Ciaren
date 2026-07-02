"""The REST API connector plugin: read HTTP JSON/CSV endpoints like a database.

This example demonstrates the connector extension point added in plugin API 1.1:
a :class:`ConnectorProvider` that ships an executable :class:`ConnectorRuntime`.
Once installed and approved, "REST API" appears on the Connections page (its
form is driven by the ``config_schema`` below), connections can be tested, the
declared endpoints list as *tables*, and a **SQL Input** node reads any endpoint
into a flow — Ciaren materializes the frame exactly as it does for a database.

Design notes:

- **stdlib only** (``urllib``): no extra dependencies to install.
- **Secrets follow Ciaren's env-var-only rule**: the bearer/basic credential is
  the connection's password env var, resolved by the host per call and never
  stored by this plugin.
- The manifest declares ``network`` + ``credentials``, so the user sees exactly
  what they are approving; the host additionally runs its SSRF guard on the
  configured host before this runtime is ever invoked.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from typing import Any

from app.plugin_api import (
    ConnectorProvider,
    ConnectorRuntime,
    ConnectorSpec,
    ConnectorTestResult,
    Permission,
    Plugin,
    PluginMetadata,
    ServiceRegistry,
)

PLUGIN_ID = "community.rest-connector"
CONNECTOR_ID = "rest-api"

AUTH_STYLES = ("none", "bearer", "basic")

CONFIG_SCHEMA: dict[str, Any] = {
    "fields": [
        {
            "key": "base_url",
            "label": "Base URL",
            "type": "string",
            "required": True,
            "placeholder": "https://api.example.com/v1",
            "help": "Endpoint paths are resolved against this URL.",
        },
        {
            "key": "endpoints",
            "label": "Endpoints",
            "type": "string_list",
            "help": "Relative paths (e.g. users, orders) listed as tables for SQL Input.",
        },
        {
            "key": "auth_style",
            "label": "Authentication",
            "type": "select",
            "options": list(AUTH_STYLES),
            "default": "none",
            "help": "bearer sends the password env var's value as a Bearer token; basic uses username + password.",
        },
        {
            "key": "response_format",
            "label": "Response format",
            "type": "select",
            "options": ["auto", "json", "csv"],
            "default": "auto",
        },
    ]
}


def _options(config: dict[str, Any]) -> dict[str, Any]:
    return dict(config.get("options") or {})


def _base_url(config: dict[str, Any]) -> str:
    base = str(_options(config).get("base_url") or "").strip()
    if not base:
        raise ValueError("rest-api: the connection has no base_url configured")
    if not base.startswith(("http://", "https://")):
        raise ValueError(f"rest-api: base_url must be http(s), got {base!r}")
    return base.rstrip("/")


def _endpoints(config: dict[str, Any]) -> list[str]:
    raw = _options(config).get("endpoints") or []
    if isinstance(raw, str):  # tolerate a comma-separated string
        raw = [p.strip() for p in raw.split(",")]
    return [str(e).strip().strip("/") for e in raw if str(e).strip()]


def _headers(config: dict[str, Any]) -> dict[str, str]:
    style = str(_options(config).get("auth_style") or "none")
    if style not in AUTH_STYLES:
        raise ValueError(f"rest-api: auth_style must be one of {AUTH_STYLES}, got {style!r}")
    headers = {"Accept": "application/json, text/csv;q=0.9, */*;q=0.1", "User-Agent": "ciaren-rest-connector"}
    secret = config.get("password")
    if style == "bearer":
        if not secret:
            raise ValueError("rest-api: bearer auth needs the connection's password env var to be set")
        headers["Authorization"] = f"Bearer {secret}"
    elif style == "basic":
        import base64

        user = config.get("username") or ""
        token = base64.b64encode(f"{user}:{secret or ''}".encode()).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def _fetch(config: dict[str, Any], path: str) -> tuple[bytes, str]:
    """GET ``base_url/path`` and return ``(body, content_type)``."""
    url = _base_url(config) + ("/" + path.lstrip("/") if path else "")
    request = urllib.request.Request(url, headers=_headers(config))  # noqa: S310 - http(s) enforced in _base_url
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            content_type = response.headers.get("Content-Type", "")
            return response.read(), content_type
    except urllib.error.HTTPError as exc:
        raise ValueError(f"rest-api: {url} answered HTTP {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"rest-api: could not reach {url}: {exc.reason}") from exc


def _rows_from_json(payload: Any) -> list[dict[str, Any]]:
    """Accept a bare list of records or the common ``{data|items|results: [...]}``
    wrappers; a single object becomes a one-row frame."""
    if isinstance(payload, list):
        return [row if isinstance(row, dict) else {"value": row} for row in payload]
    if isinstance(payload, dict):
        for key in ("data", "items", "results", "records"):
            if isinstance(payload.get(key), list):
                return _rows_from_json(payload[key])
        return [payload]
    return [{"value": payload}]


def _to_frame(body: bytes, content_type: str, response_format: str) -> Any:
    import pandas as pd

    fmt = response_format
    if fmt == "auto":
        fmt = "csv" if "csv" in content_type else "json"
    if fmt == "csv":
        return pd.read_csv(io.BytesIO(body))
    try:
        payload = json.loads(body.decode("utf-8"))
    except ValueError as exc:
        raise ValueError(f"rest-api: the endpoint did not return valid JSON ({exc})") from exc
    return pd.DataFrame(_rows_from_json(payload))


class RestApiRuntime(ConnectorRuntime):
    """test / list_tables / read against a configured HTTP API."""

    def test(self, config: dict[str, Any]) -> ConnectorTestResult:
        endpoints = _endpoints(config)
        try:
            _fetch(config, endpoints[0] if endpoints else "")
        except ValueError as exc:
            return ConnectorTestResult(ok=False, message=str(exc))
        return ConnectorTestResult(ok=True, message="API reachable.")

    def list_tables(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"name": endpoint, "schema": None, "row_count": None} for endpoint in _endpoints(config)]

    def read(self, config: dict[str, Any], options: dict[str, Any]) -> Any:
        if options.get("mode") == "query":
            raise ValueError("rest-api: this connector reads endpoints (tables), not SQL queries")
        path = str(options.get("table") or options.get("path") or "").strip()
        if not path:
            raise ValueError("rest-api: pick an endpoint to read (the node's 'table')")
        body, content_type = _fetch(config, path)
        frame = _to_frame(body, content_type, str(_options(config).get("response_format") or "auto"))
        limit = options.get("limit")
        return frame.head(limit) if isinstance(limit, int) else frame


class _RestConnectorProvider(ConnectorProvider):
    def connectors(self) -> list[ConnectorSpec]:
        return [
            ConnectorSpec(
                id=CONNECTOR_ID,
                label="REST API",
                kind="api",
                provider=PLUGIN_ID,
                capabilities=("connector.api", f"connector.{CONNECTOR_ID}"),
                permissions=(Permission.network, Permission.credentials),
                metadata={
                    "needs_host": False,
                    "needs_auth": True,
                    "supports_query": False,
                    "default_port": None,
                },
                config_schema=CONFIG_SCHEMA,
            )
        ]

    def connector_implementations(self) -> dict[str, Any]:
        return {CONNECTOR_ID: RestApiRuntime()}


class RestConnectorPlugin(Plugin):
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id=PLUGIN_ID,
            name="REST API Connector",
            version="0.1.0",
            publisher="community",
            description="Read HTTP JSON/CSV API endpoints into flows through SQL Input, like a database.",
            permissions=(Permission.network, Permission.credentials),
        )

    def register(self, registry: ServiceRegistry) -> None:
        registry.register_connector_provider(_RestConnectorProvider())
