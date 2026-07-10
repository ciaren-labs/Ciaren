# SPDX-License-Identifier: AGPL-3.0-only
"""Core REST/HTTP API connector — read JSON/CSV endpoints like database tables.

Modeled on how commercial ETL tools connect to web APIs: a **base URL** plus a
set of connection-level options that cover the common API shapes without code:

- **Authentication** — none, API key header, bearer token, HTTP basic, or an
  API key in a query parameter (``auth_style: query_param`` + ``api_key_param``,
  for APIs like Google's that authenticate via ``?key=...``). The secret always
  comes from the connection's secret reference (never stored); the query-param
  style injects it at request time and scrubs it from every error message.
- **Custom headers** and **default query params** applied to every request.
- **Endpoints** declared on the connection appear as *tables* for SQL Input.
- **Response parsing** — auto/json/csv, with a ``records_path`` dot-path for
  APIs that wrap their rows (``{"data": {"items": [...]}}``).
- **Pagination** — page-number pagination (param names, page size, max pages),
  the most common commercial-API scheme; the connector loops pages until a
  short page, an empty page, or the page cap.
- **Timeout** and **TLS verification** toggles.

The connector implements the same :class:`DataConnector` surface as the SQL
connectors, so the connections API (test / list tables) and the SQL Input node
(read + parquet snapshot) work unchanged. Writing is refused — HTTP APIs have
no generic table-write semantics.

Security: the base URL must be http(s); the host passes the same SSRF guard as
every other connector (``CONNECTOR_BLOCK_PRIVATE_HOSTS``); errors are scrubbed
of the secret before they leave this module; responses are size-capped before
parsing — per request and cumulatively across the pages of a paginated read.
"""

from __future__ import annotations

import base64
import io
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import pandas as pd

from app.connectors.base import ConnectionSpec, ConnectorError, TableRef
from app.connectors.ssrf import guard_endpoint
from app.core.secrets import scrub

AUTH_STYLES = ("none", "api_key", "bearer", "basic", "query_param")
RESPONSE_FORMATS = ("auto", "json", "csv")

DEFAULT_API_KEY_HEADER = "X-API-Key"
DEFAULT_API_KEY_PARAM = "api_key"
DEFAULT_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 300
#: Response-size cap (before parsing) — a runaway endpoint must not exhaust
#: server memory. Applies to each request *and* cumulatively across the pages
#: of one paginated read (pages are held in memory until concatenated).
MAX_RESPONSE_BYTES = 256 * 1024 * 1024
#: Hard ceiling on pagination requests per read, whatever max_pages says.
MAX_PAGES_CEILING = 1000
#: JSON keys checked (in order) when the response wraps its rows and no
#: records_path is configured.
_COMMON_RECORD_KEYS = ("data", "items", "results", "records", "rows", "value")


def _options(spec: ConnectionSpec) -> dict[str, Any]:
    return dict(spec.options or {})


def _base_url(spec: ConnectionSpec) -> str:
    base = str(spec.host or "").strip()
    if not base:
        raise ConnectorError("REST API connection has no base URL.")
    if not base.startswith(("http://", "https://")):
        raise ConnectorError(f"The base URL must start with http:// or https:// (got {base!r}).")
    return base.rstrip("/")


def _endpoints(spec: ConnectionSpec) -> list[str]:
    raw = _options(spec).get("endpoints") or []
    if isinstance(raw, str):  # tolerate a comma-separated string
        raw = [p.strip() for p in raw.split(",")]
    return [str(e).strip().strip("/") for e in raw if str(e).strip()]


def _timeout(spec: ConnectionSpec) -> float:
    raw = _options(spec).get("timeout_seconds")
    try:
        value = float(raw) if raw is not None else DEFAULT_TIMEOUT_SECONDS
    except (TypeError, ValueError):
        raise ConnectorError(f"timeout_seconds must be a number (got {raw!r}).") from None
    return min(max(value, 1.0), MAX_TIMEOUT_SECONDS)


def _string_mapping(spec: ConnectionSpec, key: str) -> dict[str, str]:
    """A str->str mapping option (custom headers / default query params).
    Tolerates a JSON-encoded string; anything else non-dict is refused."""
    raw = _options(spec).get(key) or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else {}
        except ValueError:
            raise ConnectorError(f"{key} must be a JSON object of string values.") from None
    if not isinstance(raw, dict):
        raise ConnectorError(f"{key} must be an object mapping names to values.")
    return {str(k): str(v) for k, v in raw.items() if str(k).strip()}


def _auth_style(spec: ConnectionSpec) -> str:
    style = str(_options(spec).get("auth_style") or "none")
    if style not in AUTH_STYLES:
        raise ConnectorError(f"auth_style must be one of {AUTH_STYLES} (got {style!r}).")
    return style


def _require_secret(spec: ConnectionSpec, style: str) -> str:
    secret = spec.password
    if not secret:
        raise ConnectorError(
            f"{style} authentication needs the connection's secret env var to be set (password env var)."
        )
    return secret


def _auth_headers(spec: ConnectionSpec) -> dict[str, str]:
    style = _auth_style(spec)
    if style in ("none", "query_param"):
        return {}
    secret = _require_secret(spec, style)
    if style == "bearer":
        return {"Authorization": f"Bearer {secret}"}
    if style == "api_key":
        header = str(_options(spec).get("api_key_header") or DEFAULT_API_KEY_HEADER).strip()
        if not header or any(c in header for c in "\r\n:"):
            raise ConnectorError(f"api_key_header is not a valid header name: {header!r}.")
        return {header: secret}
    token = base64.b64encode(f"{spec.username or ''}:{secret}".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _auth_query_params(spec: ConnectionSpec) -> dict[str, str]:
    """Query-parameter authentication (``?api_key=...``), for APIs that only
    accept a key in the URL. The secret still comes from the connection's
    secret reference — never from the stored ``query_params`` option, which
    would persist it in plain text and echo it in API responses — and is
    injected per request, so error messages can scrub it reliably."""
    style = _auth_style(spec)
    if style != "query_param":
        return {}
    secret = _require_secret(spec, style)
    param = str(_options(spec).get("api_key_param") or DEFAULT_API_KEY_PARAM).strip()
    if not param or any(c in param for c in "&=#?/ \r\n"):
        raise ConnectorError(f"api_key_param is not a valid query parameter name: {param!r}.")
    return {param: secret}


def _build_url(spec: ConnectionSpec, path: str, extra_params: dict[str, str]) -> str:
    """Join the base URL, a relative path (which may carry its own query string),
    the connection's default query params, per-request params, and — always
    winning over every other source — the auth query param (if configured)."""
    base = _base_url(spec)
    path = path.strip()
    if path.startswith(("http://", "https://")):
        raise ConnectorError("Endpoints must be paths relative to the base URL, not absolute URLs.")
    url = base + ("/" + path.lstrip("/") if path else "")
    parsed = urllib.parse.urlsplit(url)
    params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    merged = list(params)
    seen = {k for k, _ in params}
    for key, value in {**_string_mapping(spec, "query_params"), **extra_params}.items():
        if key not in seen:
            merged.append((key, value))
    # The auth secret replaces any same-named param from the path or options: a
    # stale plaintext duplicate must never win over the resolved secret.
    for key, value in _auth_query_params(spec).items():
        merged = [(k, v) for k, v in merged if k != key]
        merged.append((key, value))
    query = urllib.parse.urlencode(merged)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))


def _resolve_records_path(payload: Any, records_path: str) -> Any:
    value = payload
    for part in [p for p in records_path.split(".") if p]:
        if not isinstance(value, dict) or part not in value:
            raise ConnectorError(f"records_path {records_path!r}: key {part!r} not found in the response.")
        value = value[part]
    return value


def _rows_from_json(payload: Any, records_path: str) -> list[dict[str, Any]]:
    """Extract a list of records from a JSON payload. An explicit ``records_path``
    wins; otherwise a bare list is used as-is and common wrapper keys are tried."""
    if records_path:
        payload = _resolve_records_path(payload, records_path)
    if isinstance(payload, dict) and not records_path:
        for key in _COMMON_RECORD_KEYS:
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if isinstance(payload, list):
        return [row if isinstance(row, dict) else {"value": row} for row in payload]
    if isinstance(payload, dict):
        return [payload]
    return [{"value": payload}]


class RestApiConnector:
    """Read-only :class:`DataConnector` for HTTP JSON/CSV APIs."""

    provider_kind = "api"

    # -- HTTP ------------------------------------------------------------------

    def _request(self, spec: ConnectionSpec, path: str, extra_params: dict[str, str]) -> tuple[bytes, str]:
        url = _build_url(spec, path, extra_params)  # injects the auth query param, if configured
        guard_endpoint(url)
        headers = {
            "Accept": "application/json, text/csv;q=0.9, */*;q=0.1",
            "User-Agent": "ciaren-rest-api-connector",
            **_string_mapping(spec, "headers"),
            **_auth_headers(spec),
        }
        request = urllib.request.Request(url, headers=headers)  # noqa: S310 - scheme enforced in _base_url
        context: ssl.SSLContext | None = None
        if _options(spec).get("verify_tls") is False:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(request, timeout=_timeout(spec), context=context) as response:  # noqa: S310
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ConnectorError(f"The response from {path or '/'} exceeds the {MAX_RESPONSE_BYTES} byte cap.")
                return body, response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            detail = ""
            if exc.code in (401, 403):
                detail = " — check the authentication settings and the secret env var"
            raise ConnectorError(scrub(f"HTTP {exc.code} {exc.reason} from {url}{detail}.", spec.password)) from None
        except urllib.error.URLError as exc:
            raise ConnectorError(scrub(f"Could not reach {url}: {exc.reason}.", spec.password)) from None
        except TimeoutError:
            # Scrubbed like the other error paths: with query_param auth the
            # URL itself carries the secret.
            raise ConnectorError(
                scrub(f"Request to {url} timed out after {_timeout(spec):g}s.", spec.password)
            ) from None

    def _to_frame(self, spec: ConnectionSpec, body: bytes, content_type: str) -> pd.DataFrame:
        fmt = str(_options(spec).get("response_format") or "auto")
        if fmt not in RESPONSE_FORMATS:
            raise ConnectorError(f"response_format must be one of {RESPONSE_FORMATS} (got {fmt!r}).")
        if fmt == "auto":
            fmt = "csv" if "csv" in content_type else "json"
        if fmt == "csv":
            try:
                return pd.read_csv(io.BytesIO(body))
            except Exception as exc:  # noqa: BLE001 - surfaced as a clear parse error
                raise ConnectorError(f"The endpoint did not return parsable CSV: {exc}") from None
        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ConnectorError(f"The endpoint did not return valid JSON: {exc}") from None
        return pd.DataFrame(_rows_from_json(payload, str(_options(spec).get("records_path") or "").strip()))

    # -- pagination --------------------------------------------------------------

    def _read_paginated(self, spec: ConnectionSpec, path: str, limit: int | None) -> pd.DataFrame:
        options = _options(spec)
        page_param = str(options.get("page_param") or "").strip()
        if not page_param:
            body, content_type = self._request(spec, path, {})
            frame = self._to_frame(spec, body, content_type)
            return frame.head(limit) if limit is not None else frame

        try:
            page_size = int(options.get("page_size") or 100)
            # `or 1` would also catch an explicit 0, which is the whole point of
            # this option for 0-indexed pagination APIs — only fall back to the
            # default when the option is genuinely absent.
            start_page_opt = options.get("start_page")
            start_page = int(start_page_opt) if start_page_opt is not None else 1
            max_pages = int(options.get("max_pages") or 100)
        except (TypeError, ValueError):
            raise ConnectorError("page_size, start_page, and max_pages must be integers.") from None
        if page_size < 1 or max_pages < 1:
            raise ConnectorError("page_size and max_pages must be at least 1.")
        max_pages = min(max_pages, MAX_PAGES_CEILING)
        page_size_param = str(options.get("page_size_param") or "").strip()

        pages: list[pd.DataFrame] = []
        total = 0
        total_bytes = 0
        for page in range(start_page, start_page + max_pages):
            params = {page_param: str(page)}
            if page_size_param:
                params[page_size_param] = str(page_size)
            body, content_type = self._request(spec, path, params)
            # Every page stays in memory until the final concat, so the size cap
            # is cumulative — max_pages alone must not let a read grow unbounded.
            total_bytes += len(body)
            if total_bytes > MAX_RESPONSE_BYTES:
                raise ConnectorError(
                    f"Paginated read of {path or '/'} exceeds the {MAX_RESPONSE_BYTES} byte cap "
                    "across pages — reduce max_pages/page_size or filter the endpoint."
                )
            frame = self._to_frame(spec, body, content_type)
            if len(frame):
                pages.append(frame)
                total += len(frame)
            # Stop on an empty or short page (the API ran out of rows) or once a
            # bounded read has enough.
            if len(frame) < page_size or (limit is not None and total >= limit):
                break
        result = pd.concat(pages, ignore_index=True) if pages else pd.DataFrame()
        return result.head(limit) if limit is not None else result

    # -- DataConnector surface -----------------------------------------------------

    def test_connection(self, spec: ConnectionSpec) -> None:
        endpoints = _endpoints(spec)
        self._request(spec, endpoints[0] if endpoints else "", {})

    def list_tables(self, spec: ConnectionSpec) -> list[TableRef]:
        return [TableRef(name=endpoint) for endpoint in _endpoints(spec)]

    def read_table(self, spec: ConnectionSpec, table: str, schema: str | None, limit: int | None) -> pd.DataFrame:
        path = str(table or "").strip()
        if not path:
            raise ConnectorError("Pick an endpoint to read (the node's table).")
        return self._read_paginated(spec, path, limit)

    def read_query(self, spec: ConnectionSpec, query: str) -> pd.DataFrame:
        """Custom-request mode: the "query" is a request path relative to the base
        URL, optionally with its own query string (e.g. ``users?active=true``)."""
        path = str(query or "").strip()
        if not path:
            raise ConnectorError("Enter a request path relative to the base URL (e.g. users?active=true).")
        return self._read_paginated(spec, path, None)

    def write_table(
        self, spec: ConnectionSpec, df: pd.DataFrame, table: str, schema: str | None, if_exists: str
    ) -> None:
        raise ConnectorError(
            "REST API connections are read-only — HTTP APIs have no generic table-write semantics. "
            "Write to a database or storage connection instead."
        )
