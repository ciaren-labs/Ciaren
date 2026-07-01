# SPDX-License-Identifier: AGPL-3.0-only
"""Optional confinement of connector-reachable filesystem paths.

``CIAREN_STORAGE_ALLOWED_ROOTS`` (empty by default — unrestricted, the
local-first posture) limits where connectors may touch the server's filesystem:
the Local Storage connector's root folder *and* the database file of file-based
SQL providers (SQLite / DuckDB). Confining only storage would leave a hole — a
"sqlite" connection pointing at an arbitrary server file reads and writes it
just as effectively as a storage connection would.
"""

from __future__ import annotations

from pathlib import Path

from app.connectors.base import ConnectorError


def _is_within(path: Path, base: Path) -> bool:
    """Whether *path* is contained in *base* (both already resolved)."""
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def allowed_roots() -> list[Path]:
    """Configured confinement directories, resolved absolute.
    Empty list means "no confinement" (the historical default)."""
    from app.core.config import get_settings

    roots: list[Path] = []
    for raw in get_settings().STORAGE_ALLOWED_ROOTS:
        raw = raw.strip()
        if raw:
            roots.append(Path(raw).expanduser().resolve())
    return roots


def ensure_allowed_path(path: Path, what: str, hint: str = "the connection folder") -> Path:
    """Resolve *path* and raise unless it falls inside an allowed root.

    No-op (beyond resolving) when no roots are configured. Returns the
    resolved path so callers can keep using the canonical form.
    """
    resolved = path.expanduser().resolve()
    roots = allowed_roots()
    if roots and not any(resolved == base or _is_within(resolved, base) for base in roots):
        raise ConnectorError(
            f"{what} {resolved} is outside the allowed roots "
            f"({', '.join(str(b) for b in roots)}). "
            f"Adjust CIAREN_STORAGE_ALLOWED_ROOTS or {hint}."
        )
    return resolved
