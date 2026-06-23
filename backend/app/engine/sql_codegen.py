"""Helpers for emitting SQL source/sink code in the exported scripts.

The generated code reads the password from ``os.environ`` (matching FlowFrame's
"never store secrets" model), so exported scripts are runnable and safe to share.
"""

from __future__ import annotations

from typing import Any

_DRIVERNAMES = {
    "postgresql": "postgresql+psycopg",
    "mysql": "mysql+pymysql",
    "sqlite": "sqlite",
    "mssql": "mssql+pyodbc",
}

SQL_NODE_TYPES = ("sqlInput", "sqlOutput")


def graph_has_sql(graph: dict[str, Any]) -> bool:
    return any(n.get("type") in SQL_NODE_TYPES for n in graph.get("nodes", []))


def engine_url_expr(info: dict[str, Any]) -> str:
    """Return the *text* of a Python URL expression for ``create_engine``.

    The password is interpolated from ``os.environ`` at runtime, never embedded.
    """
    provider = info.get("provider", "")
    database = info.get("database") or ""
    if provider == "sqlite":
        return f'"sqlite:///{database}"'
    drivername = _DRIVERNAMES.get(provider, provider)
    host = info.get("host") or "localhost"
    user = info.get("username") or ""
    pw_env = info.get("password_env")
    if pw_env:
        # Produces the literal:  user:{os.environ['ENV_VAR']}@
        auth = f"{user}:{{os.environ[{pw_env!r}]}}@"
    elif user:
        auth = f"{user}@"
    else:
        auth = ""
    port = info.get("port")
    port_part = f":{port}" if port else ""
    return f'f"{drivername}://{auth}{host}{port_part}/{database}"'
