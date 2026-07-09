"""Executable architecture boundaries.

These encode the layering rules from app/README.md as tests, so
a violation fails CI instead of silently eroding the structure. They parse each
module's imports with the ``ast`` module (not text matching, so comments/strings
never trigger a false positive).

If one of these fails, the fix is almost always to move logic to the correct layer
— not to relax the rule.
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def _module_dotted(path: Path) -> str:
    """The absolute dotted module name for a file under ``backend/`` (e.g.
    ``app.engine.backends.pandas_engine``)."""
    rel = path.relative_to(APP.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _module_imports(path: Path) -> set[str]:
    """Every imported dotted name in a file, resolved to absolute names.

    Handles ``import x``, ``from x import y``, AND relative imports
    (``from ..api import z``) — the last resolved against the file's own package so
    a cross-layer relative import can't slip past the boundary rules.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package_parts = _module_dotted(path).split(".")[:-1]  # drop the module itself
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            else:
                # level=1 → current package, level=2 → parent, …
                resolved = package_parts[: len(package_parts) - (node.level - 1)]
                base = ".".join([*resolved, node.module] if node.module else resolved)
            if base:
                names.add(base)
                names.update(f"{base}.{alias.name}" for alias in node.names)
    return names


def _py_files(*parts: str) -> list[Path]:
    root = APP.joinpath(*parts)
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def _violations(files: list[Path], forbidden: tuple[str, ...]) -> dict[str, list[str]]:
    """Map each file (that violates) to the forbidden prefixes it imports."""
    out: dict[str, list[str]] = {}
    for path in files:
        imports = _module_imports(path)
        hit = sorted({f for f in forbidden if any(imp == f or imp.startswith(f + ".") for imp in imports)})
        if hit:
            out[str(path.relative_to(APP.parent))] = hit
    return out


# -- engine: pure compute, no web/service/schema layers ---------------------


def test_engine_does_not_import_web_or_service_layers() -> None:
    bad = _violations(_py_files("engine"), ("fastapi", "app.api", "app.services", "app.schemas"))
    assert not bad, f"engine must stay below the API/service layers: {bad}"


# -- connectors: integrations only, no web/db-model/schema knowledge --------


def test_connectors_do_not_import_web_or_db_models() -> None:
    bad = _violations(_py_files("connectors"), ("fastapi", "app.api", "app.db", "app.schemas"))
    assert not bad, f"connectors must not know web or DB-model layers: {bad}"


# -- services: below the API layer ------------------------------------------


def test_services_do_not_import_the_api_layer() -> None:
    bad = _violations(_py_files("services"), ("app.api",))
    assert not bad, f"services must not depend on the API/routing layer: {bad}"


# -- routes: thin HTTP adapters, no raw DB session --------------------------

# /ready is a readiness probe whose whole job is to check DB connectivity, so it
# legitimately takes a raw session. Every other route must go through a service.
_ASYNC_SESSION_ALLOWED = {"api/routes/health.py"}


def test_routes_do_not_take_a_raw_db_session() -> None:
    # Catch both the typed form (`AsyncSession`) and the untyped one (`db=Depends(get_db)`)
    # by forbidding either symbol in a route module — a route needing a session is the
    # smell we're guarding against.
    markers = ("AsyncSession", "app.core.database.get_db")
    offenders: dict[str, list[str]] = {}
    for path in _py_files("api", "routes"):
        rel = str(path.relative_to(APP)).replace("\\", "/")
        if rel in _ASYNC_SESSION_ALLOWED:
            continue
        imports = _module_imports(path)
        hit = sorted(imp for imp in imports if any(m in imp for m in markers))
        if hit:
            offenders[rel] = hit
    assert not offenders, (
        f"routes must delegate DB work to a service (via *ServiceDep), not take an "
        f"AsyncSession / get_db directly: {offenders}"
    )
