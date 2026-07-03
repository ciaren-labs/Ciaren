# SPDX-License-Identifier: AGPL-3.0-only
"""Bridge plugin-contributed connectors into the connections machinery.

The connection service and the SQL/storage node resolvers are hardwired to the
core provider table (``app/connectors/providers.py``); this module is their
fallback path for providers contributed by plugins. A plugin connector consists
of a :class:`ConnectorSpec` (catalog + form metadata) and a
:class:`ConnectorRuntime` (test / list / read / write) registered through
``ConnectorProvider.connector_implementations``.

Security notes:

- A runtime only exists here when its plugin is loaded — i.e. the user approved
  running its code and granted the manifest's permissions.
- Connection secrets keep the env-var-only rule: the resolved secret is passed
  into a single call's ``config`` mapping and never stored.
- The core-invoked ``host`` field — and any option that looks like a URL or a
  host (``base_url``, ``endpoint``, …) — goes through the same SSRF guard as
  built-in connectors before a plugin runtime is called (best-effort: a
  plugin's own network use is governed by the ``network`` permission
  disclosure, not a sandbox).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from app.connectors.ssrf import guard_endpoint, guard_host
from app.core.exceptions import ValidationError
from app.core.secrets import resolve_secret
from app.plugin_api import ConfigFieldSpec, ConnectorRuntime, ConnectorSpec

if TYPE_CHECKING:
    from app.db.models.connection import Connection

#: Provider ids whose connectors are core built-ins (execute through the core
#: connector classes, not a plugin runtime).
_CORE_PROVIDERS = ("ciaren.core", "ciaren.ml")


def plugin_connector_specs() -> list[ConnectorSpec]:
    """Connector specs contributed by plugins (excludes core built-ins)."""
    from app.plugins import get_registry

    return [s for s in get_registry().connector_specs() if s.provider not in _CORE_PROVIDERS]


def plugin_connector(name: str) -> tuple[ConnectorSpec, ConnectorRuntime] | None:
    """The (spec, runtime) pair for a plugin connector, or ``None`` when the name
    is unknown, is a core connector, or the plugin shipped no runtime."""
    from app.plugins import get_registry

    registry = get_registry()
    spec = registry.connector_spec(name)
    if spec is None or spec.provider in _CORE_PROVIDERS:
        return None
    impl = registry.connector_implementation(name)
    if not isinstance(impl, ConnectorRuntime):
        return None
    return spec, impl


def is_plugin_connector(name: str) -> bool:
    return plugin_connector(name) is not None


def plugin_connection_kind(name: str) -> str | None:
    """The high-level kind (``sql`` / ``storage`` / ``api`` / …) of a plugin
    connector, or ``None`` when ``name`` is not a plugin connector."""
    found = plugin_connector(name)
    return found[0].kind if found else None


# -- config assembly -----------------------------------------------------------


def connector_config(
    *,
    host: str | None,
    port: int | None,
    database: str | None,
    username: str | None,
    password_env: str | None,
    options: dict[str, Any] | None,
) -> dict[str, Any]:
    """Flatten connection fields into the plain mapping a ConnectorRuntime
    receives. Resolves the password from its env var for this one call."""
    return {
        "host": host,
        "port": port,
        "database": database,
        "username": username,
        "password": resolve_secret(password_env),
        "options": dict(options or {}),
    }


def connection_config(conn: Connection) -> dict[str, Any]:
    """The runtime config mapping for a saved Connection row."""
    return connector_config(
        host=conn.host,
        port=conn.port,
        database=conn.database,
        username=conn.username,
        password_env=conn.password_env,
        options=conn.options_json,
    )


# -- validation -----------------------------------------------------------------


def _fields(spec: ConnectorSpec) -> list[ConfigFieldSpec]:
    raw = spec.config_schema.get("fields", []) if spec.config_schema else []
    return [ConfigFieldSpec.model_validate(f) for f in raw]


def _is_missing(options: dict[str, Any], key: str) -> bool:
    """A required field is missing when absent, None, or a blank string —
    valid falsy values (``False`` for a boolean, ``0`` for a number) count as
    provided."""
    if key not in options:
        return True
    value = options[key]
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()


def validate_plugin_connection(spec: ConnectorSpec, host: str | None, options: dict[str, Any] | None) -> None:
    """Pre-save validation for a plugin connection: form-flag requirements from
    the spec metadata plus the required fields of its ``config_schema``."""
    if spec.metadata.get("needs_host") and not host:
        raise ValidationError(f"{spec.label} needs a host.")
    opts = options or {}
    missing = [f.label or f.key for f in _fields(spec) if f.required and _is_missing(opts, f.key)]
    if missing:
        raise ValidationError(f"{spec.label} requires: {', '.join(missing)}.")


#: Option-key substrings that name a network location even without a URL scheme.
_NETWORK_KEY_TOKENS = ("host", "url", "uri", "endpoint", "server", "address")


def _network_option_values(value: Any, key: str = "") -> Iterator[str]:
    """Yield every option value that plausibly names a network location: any
    string carrying a URL scheme, or any string under a host/url/endpoint-like
    key — recursing through nested dicts and lists."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _network_option_values(v, str(k))
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _network_option_values(item, key)
    elif isinstance(value, str) and value.strip():
        lowered = key.lower()
        if "://" in value or any(token in lowered for token in _NETWORK_KEY_TOKENS):
            yield value


def guard_plugin_connection(host: str | None, options: dict[str, Any] | None = None) -> None:
    """Apply the core SSRF guard to every network-reachable field of a plugin
    connection before its runtime is invoked: the ``host`` column plus any
    option that is a URL or sits under a host/url/endpoint-like key (a plugin
    connector may take its target from ``options.base_url`` instead of ``host``).
    No-op unless CONNECTOR_BLOCK_PRIVATE_HOSTS is enabled."""
    guard_host(host)
    for value in _network_option_values(dict(options or {})):
        guard_endpoint(value)


def provider_entry(spec: ConnectorSpec) -> dict[str, Any]:
    """A plugin connector as an entry of ``GET /api/connections/providers`` —
    the same dict shape as a core provider (so the existing form logic applies)
    plus ``plugin``/``plugin_id``/``config_schema`` for the dynamic parts."""
    meta = spec.metadata
    return {
        "name": spec.id,
        "label": spec.label,
        "kind": spec.kind,
        "available": spec.available,
        "driver_module": spec.driver_module,
        "extra": spec.extra,
        "default_port": meta.get("default_port"),
        "needs_host": bool(meta.get("needs_host", False)),
        "needs_auth": bool(meta.get("needs_auth", False)),
        "supports_query": bool(meta.get("supports_query", False)),
        "needs_bucket": bool(meta.get("needs_bucket", False)),
        "needs_region": bool(meta.get("needs_region", False)),
        "needs_endpoint": bool(meta.get("needs_endpoint", False)),
        "plugin": True,
        "plugin_id": spec.provider,
        "config_schema": dict(spec.config_schema),
    }
