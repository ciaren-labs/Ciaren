"""Example HTTPS CSV/JSON input connector.

The connector intentionally uses only Ciaren's public plugin API plus the Python
standard library for URL validation, downloads, and parsing. Pandas is imported
only at the boundary where the ConnectorRuntime contract returns a DataFrame.
"""

from __future__ import annotations

import csv
import ipaddress
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from io import StringIO
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

PLUGIN_ID = "community.https-input"
CONNECTOR_ID = "https-input"

DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_MAX_BYTES = 10 * 1024 * 1024
CHUNK_SIZE = 64 * 1024


class UnsafeUrlError(ValueError):
    """Raised when a URL is unsuitable for server-side fetching."""


class ResponseTooLargeError(ValueError):
    """Raised when the response exceeds the configured streamed limit."""


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None

    def http_error_301(self, req, fp, code, msg, headers):  # noqa: ANN001, ANN201
        return fp

    http_error_302 = http_error_303 = http_error_307 = http_error_308 = http_error_301


class _HttpsInputRuntime(ConnectorRuntime):
    def test(self, config: dict[str, Any]) -> ConnectorTestResult:
        try:
            url = _configured_url(config, {})
            _validate_https_public_url(url)
            return ConnectorTestResult(ok=True, message="HTTPS URL is allowed")
        except Exception as exc:
            return ConnectorTestResult(ok=False, message=str(exc))

    def list_tables(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"name": "download", "schema": None, "row_count": None}]

    def read(self, config: dict[str, Any], options: dict[str, Any]) -> Any:
        url = _configured_url(config, options)
        fmt = _configured_format(config, options)
        max_bytes = _configured_max_bytes(config)
        timeout = _configured_timeout(config)
        body = _download(url, max_bytes=max_bytes, timeout=timeout)
        rows = _parse_body(body, fmt)

        import pandas as pd

        return pd.DataFrame(rows)


class _HttpsConnectorProvider(ConnectorProvider):
    def connectors(self) -> list[ConnectorSpec]:
        return [
            ConnectorSpec(
                id=CONNECTOR_ID,
                label="HTTPS CSV/JSON",
                kind="api",
                provider=PLUGIN_ID,
                capabilities=("connector.https-input",),
                permissions=(Permission.network,),
                metadata={"needs_host": False, "needs_auth": False, "supports_query": False},
                config_schema={
                    "fields": [
                        {
                            "key": "url",
                            "label": "HTTPS URL",
                            "type": "string",
                            "required": True,
                            "placeholder": "https://example.com/data.csv",
                            "help": "Direct HTTPS URL for a CSV or JSON document.",
                        },
                        {
                            "key": "format",
                            "label": "Format",
                            "type": "select",
                            "default": "csv",
                            "options": ("csv", "json"),
                            "help": "How to parse the downloaded response.",
                        },
                        {
                            "key": "max_bytes",
                            "label": "Max bytes",
                            "type": "integer",
                            "default": DEFAULT_MAX_BYTES,
                            "min": 1,
                            "help": "Maximum streamed response size.",
                        },
                        {
                            "key": "timeout_seconds",
                            "label": "Timeout seconds",
                            "type": "integer",
                            "default": DEFAULT_TIMEOUT_SECONDS,
                            "min": 1,
                            "help": "Network timeout for the request.",
                        },
                    ]
                },
            )
        ]

    def connector_implementations(self) -> dict[str, Any]:
        return {CONNECTOR_ID: _HttpsInputRuntime()}


class HttpsInputPlugin(Plugin):
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id=PLUGIN_ID,
            name="HTTPS Input Connector",
            version="0.1.0-alpha.1",
            publisher="community",
            description="Example read-only connector for HTTPS CSV and JSON documents.",
            capabilities=("connector.https-input",),
            permissions=(Permission.network,),
        )

    def register(self, registry: ServiceRegistry) -> None:
        registry.register_connector_provider(_HttpsConnectorProvider())


def _configured_url(config: dict[str, Any], options: dict[str, Any]) -> str:
    raw_options = config.get("options") or {}
    url = options.get("url") or raw_options.get("url") or config.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("https-input requires a non-empty HTTPS URL")
    return url.strip()


def _configured_format(config: dict[str, Any], options: dict[str, Any]) -> str:
    raw_options = config.get("options") or {}
    fmt = str(options.get("format") or raw_options.get("format") or "csv").lower()
    if fmt not in {"csv", "json"}:
        raise ValueError("https-input format must be 'csv' or 'json'")
    return fmt


def _configured_max_bytes(config: dict[str, Any]) -> int:
    raw_options = config.get("options") or {}
    return _positive_int(raw_options.get("max_bytes"), DEFAULT_MAX_BYTES, "max_bytes")


def _configured_timeout(config: dict[str, Any]) -> int:
    raw_options = config.get("options") or {}
    return _positive_int(raw_options.get("timeout_seconds"), DEFAULT_TIMEOUT_SECONDS, "timeout_seconds")


def _positive_int(value: Any, default: int, label: str) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a positive integer") from exc
    if parsed < 1:
        raise ValueError(f"{label} must be a positive integer")
    return parsed


def _download(url: str, *, max_bytes: int, timeout: int) -> bytes:
    _validate_https_public_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "Ciaren HTTPS input example"})
    opener = urllib.request.build_opener(_NoRedirectHandler)
    try:
        with opener.open(request, timeout=timeout) as response:
            status = getattr(response, "status", response.getcode())
            if 300 <= int(status) < 400:
                location = response.headers.get("Location", "")
                if location:
                    redirected = urllib.parse.urljoin(url, location)
                    _validate_https_public_url(redirected)
                raise UnsafeUrlError("redirect responses are not followed")

            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise ResponseTooLargeError(f"response exceeds {max_bytes} bytes")

            return _read_limited(response, max_bytes)
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            location = exc.headers.get("Location", "")
            if location:
                redirected = urllib.parse.urljoin(url, location)
                _validate_https_public_url(redirected)
            raise UnsafeUrlError("redirect responses are not followed") from exc
        raise


def _read_limited(response: Any, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ResponseTooLargeError(f"response exceeds {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_https_public_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() != "https":
        raise UnsafeUrlError("only https:// URLs are allowed")
    if not parsed.hostname:
        raise UnsafeUrlError("URL must include a hostname")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("credentials in URLs are not allowed")

    try:
        resolved = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"could not resolve host {parsed.hostname!r}") from exc

    addresses = {entry[4][0] for entry in resolved}
    if not addresses:
        raise UnsafeUrlError(f"could not resolve host {parsed.hostname!r}")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise UnsafeUrlError(f"URL resolves to a disallowed address: {ip}")


def _parse_body(body: bytes, fmt: str) -> list[dict[str, Any]]:
    text = body.decode("utf-8-sig")
    if fmt == "csv":
        return list(csv.DictReader(StringIO(text)))

    parsed = json.loads(text)
    if isinstance(parsed, list):
        if not all(isinstance(row, dict) for row in parsed):
            raise ValueError("JSON arrays must contain objects")
        return parsed
    if isinstance(parsed, dict):
        return [parsed]
    raise ValueError("JSON response must be an object or an array of objects")
