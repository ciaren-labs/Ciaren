"""Guard: the plugin API must stay decoupled from the Ciaren app internals.

If this fails, a spec/provider/registry module grew a dependency on the engine,
API, ORM, or FastAPI — which would break the goal of publishing
``ciaren-plugin-api`` standalone and would let plugins reach into private
internals. Keep the contract pure.
"""

from __future__ import annotations

import ast
from pathlib import Path

import app.plugin_api as plugin_api

FORBIDDEN_PREFIXES = (
    "app.engine",
    "app.api",
    "app.services",
    "app.connectors",
    "app.db",
    "app.core",
    "app.ml",
    "app.schemas",
    "app.main",
    "fastapi",
    "sqlalchemy",
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def test_plugin_api_has_no_backend_imports():
    package_dir = Path(plugin_api.__file__).parent
    offenders: dict[str, set[str]] = {}
    for py in package_dir.glob("*.py"):
        bad = {
            mod for mod in _imported_modules(py) if any(mod == p or mod.startswith(p + ".") for p in FORBIDDEN_PREFIXES)
        }
        if bad:
            offenders[py.name] = bad
    assert not offenders, f"plugin_api leaked backend imports: {offenders}"
