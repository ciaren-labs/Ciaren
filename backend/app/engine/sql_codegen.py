# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers for emitting SQL source/sink code in the exported scripts.

The generated code fetches the password from the connection's secret reference
at runtime — ``os.environ``, the OS keychain (``keyring:``), or a secret file
(``file:``) — matching Ciaren's "never store secrets" model, so exported
scripts are runnable and safe to share.
"""

from __future__ import annotations

import re
from typing import Any

# Must stay in sync with app/connectors/sql.py _DRIVERNAMES.
_DRIVERNAMES = {
    "postgresql": "postgresql+psycopg",
    "mysql": "mysql+pymysql",
    "sqlite": "sqlite",
    "mssql": "mssql+pyodbc",
    "duckdb": "duckdb",
    "snowflake": "snowflake",
}

SQL_NODE_TYPES = ("sqlInput", "sqlOutput")

_ENV_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Must stay in sync with app/core/secrets.py KEYRING_SERVICE.
_KEYRING_SERVICE = "ciaren"


def graph_has_sql(graph: dict[str, Any]) -> bool:
    return any(n.get("type") in SQL_NODE_TYPES for n in graph.get("nodes", []))


def _split_secret_ref(ref: str) -> tuple[str, str]:
    """(scheme, value) for a secret reference; bare names are the env scheme.
    Mirrors app/core/secrets.py parse_secret_ref, but raises ValueError (this
    module stays importable in exported-code contexts without app exceptions)."""
    scheme, sep, rest = ref.partition(":")
    if sep and scheme in ("env", "file", "keyring"):
        value = rest.strip()
        if not value:
            raise ValueError(f"password_env {ref!r} is missing its {scheme}: value.")
        return scheme, value
    if _ENV_VAR_RE.match(ref):
        return "env", ref
    raise ValueError(f"password_env {ref!r} is not a valid secret reference.")


def _inline_secret_expr(scheme: str, value: str) -> str:
    """A Python expression fetching an env/keyring secret at script runtime.
    Both grammars are quote- and backslash-free, so the expression may sit
    inside an f-string on any Python version. ``file:`` paths may not
    (backslashes / nested quotes need PEP 701, Python 3.12+) — those are
    emitted as a named prelude statement by :func:`engine_url_parts`."""
    if scheme == "env":
        if not _ENV_VAR_RE.match(value):
            raise ValueError(f"password_env {value!r} is not a valid environment variable name.")
        return f"os.environ[{value!r}]"
    return f"keyring.get_password({_KEYRING_SERVICE!r}, {value!r})"


def sql_secret_imports(connections: dict[str, dict[str, Any]]) -> list[str]:
    """Extra import lines the connections' secret references need (beyond the
    ``import os`` the SQL header always carries for env references)."""
    refs = [str(info.get("password_env") or "") for info in connections.values()]
    imports = []
    if any(r.startswith("keyring:") for r in refs):
        imports.append("import keyring")
    if any(r.startswith("file:") for r in refs):
        imports.append("from pathlib import Path")
    return imports


def engine_url_parts(info: dict[str, Any], secret_var: str = "_secret") -> tuple[list[str], str]:
    """``(prelude_lines, url_expr_text)`` for ``create_engine``.

    The password is fetched at script runtime from the connection's secret
    reference, never embedded. env/keyring fetches are inlined in the URL
    f-string; a ``file:`` fetch is emitted as a prelude statement assigning
    ``secret_var`` (its path may carry backslashes or quotes, which are illegal
    inside f-string expressions before Python 3.12 — and a named statement
    reads better anyway).
    """
    provider = info.get("provider", "")
    database = info.get("database") or ""
    if provider in ("sqlite", "duckdb"):
        drivername = _DRIVERNAMES.get(provider, provider)
        return [], f'"{drivername}:///{database}"'
    drivername = _DRIVERNAMES.get(provider, provider)
    host = info.get("host") or "localhost"
    user = info.get("username") or ""
    pw_ref = info.get("password_env")
    prelude: list[str] = []
    if pw_ref:
        scheme, value = _split_secret_ref(str(pw_ref))
        if scheme == "file":
            # Forward slashes work on every OS and keep the repr backslash-free.
            # .strip() drops the trailing newline Docker/K8s secrets carry.
            path = value.replace("\\", "/")
            prelude.append(f"{secret_var} = Path({path!r}).read_text(encoding='utf-8').strip()")
            secret_expr = secret_var
        else:
            secret_expr = _inline_secret_expr(scheme, value)
        # Produces the literal:  user:{os.environ['ENV_VAR']}@  (or the
        # keyring/file-variable equivalent), interpolated when the script runs.
        auth = f"{user}:{{{secret_expr}}}@"
    elif user:
        auth = f"{user}@"
    else:
        auth = ""
    port = info.get("port")
    port_part = f":{port}" if port else ""
    return prelude, f'f"{drivername}://{auth}{host}{port_part}/{database}"'


def engine_url_expr(info: dict[str, Any]) -> str:
    """The URL expression alone. For ``file:`` references the expression names
    the ``_secret`` variable a prelude line defines — callers emitting full
    scripts should use :func:`engine_url_parts` and include that prelude."""
    return engine_url_parts(info)[1]
