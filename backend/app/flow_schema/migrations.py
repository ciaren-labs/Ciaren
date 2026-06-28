"""A small forward-migration framework for ``.flow`` documents.

Migrations are registered as ``from_version -> (to_version, fn)`` and applied as a
chain until the document reaches the target version. There are no migrations yet
(the schema is at its first version), but the framework — and its tests — exist
from day one so a future breaking change has a non-destructive upgrade path. The
caller is responsible for backups; :func:`migrate` never writes to disk.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from packaging.version import InvalidVersion, Version

from app.flow_schema.document import CURRENT_SCHEMA_VERSION

Migration = Callable[[dict[str, Any]], dict[str, Any]]

#: from_version -> (to_version, migration function).
_MIGRATIONS: dict[str, tuple[str, Migration]] = {}


class MigrationError(ValueError):
    """Raised when a document cannot be migrated to the requested version."""


def register_migration(from_version: str, to_version: str, fn: Migration) -> None:
    if from_version in _MIGRATIONS:
        raise ValueError(f"a migration from {from_version!r} is already registered")
    _MIGRATIONS[from_version] = (to_version, fn)


def clear_migrations() -> None:
    """Drop all registered migrations (used by tests)."""
    _MIGRATIONS.clear()


def _document_version(data: dict[str, Any]) -> str:
    return str(data.get("schemaVersion") or data.get("schema_version") or CURRENT_SCHEMA_VERSION)


def _as_version(value: str) -> Version:
    try:
        return Version(value)
    except InvalidVersion as exc:
        raise MigrationError(f"invalid schema version {value!r}: {exc}") from exc


def migrate(data: dict[str, Any], *, target: str = CURRENT_SCHEMA_VERSION) -> dict[str, Any]:
    """Apply the migration chain to move ``data`` to ``target``.

    Walks ``from -> to`` edges until the target is reached. Raises
    :class:`MigrationError` if no path exists, if the document is already newer
    than the target, or if a loop is detected.
    """
    current = _document_version(data)
    target_v = _as_version(target)

    if _as_version(current) > target_v:
        raise MigrationError(f"document is at {current}, newer than target {target}; downgrade is not supported")

    visited: set[str] = set()
    while _as_version(current) < target_v:
        if current in visited:
            raise MigrationError(f"migration loop detected at {current!r}")
        visited.add(current)
        step = _MIGRATIONS.get(current)
        if step is None:
            raise MigrationError(f"no migration registered from {current!r} toward {target!r}")
        to_version, fn = step
        data = fn(data)
        data["schemaVersion"] = to_version
        current = to_version

    return data
