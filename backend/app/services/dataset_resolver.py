# SPDX-License-Identifier: AGPL-3.0-only
"""Shared resolution of input-node dataset references to concrete files.

Both the preview and execution services need to turn the ``dataset_id`` (and
optional pinned ``dataset_version``) on each input node into a real file path.
Keeping it here avoids drift between the two and keeps the ``dataset_ref_key``
contract (used by the engine) in one place.
"""

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.dataset_version import DatasetVersion
from app.engine.executor import dataset_ref_key

# File inputs only — SQL inputs carry no dataset_id and are resolved separately.
from app.engine.node_kinds import FILE_INPUT_TYPE
from app.engine.node_kinds import INPUT_SOURCE_TYPES as _LEGACY_FILE_INPUT_TYPES


async def resolve_version(
    db: AsyncSession, dataset_id: str, version: int | None, *, allow_unavailable: bool = False
) -> DatasetVersion:
    """Return the requested DatasetVersion, or the latest when ``version`` is None.

    The parent dataset is eager-loaded so callers can read ``source_type``
    without a lazy (and, under async, failing) relationship access.

    A disabled or soft-deleted dataset is refused (``ValidationError`` → 400):
    "disabled"/"deleted" must mean "do not use in new executions or previews".
    ``allow_unavailable=True`` bypasses that guard for paths that legitimately
    read a superseded dataset (e.g. inspecting history) — it is *not* meant for
    running a flow against it.
    """
    stmt = (
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id)
        .options(selectinload(DatasetVersion.dataset))
    )
    if version is not None:
        stmt = stmt.where(DatasetVersion.version_number == version)
    else:
        stmt = stmt.order_by(DatasetVersion.version_number.desc())
    result = await db.execute(stmt.limit(1))
    found = result.scalar_one_or_none()
    if found is None:
        label = f"{dataset_id}:{version if version is not None else 'latest'}"
        raise NotFoundError("Dataset version", label)
    if not allow_unavailable:
        _guard_dataset_available(found)
    return found


def _guard_dataset_available(ver: DatasetVersion) -> None:
    """Reject resolving a version whose parent dataset is soft-deleted or disabled.

    Soft-delete keeps files on disk, so without this guard a run could still read
    a dataset the user believes is out of use. Deleted is checked first because it
    is the stronger, more actionable state to report."""
    dataset = ver.dataset
    if dataset is None:
        return
    name = dataset.name or ver.dataset_id
    if dataset.deleted_at is not None:
        raise ValidationError(
            f"Dataset '{name}' was deleted on {dataset.deleted_at:%Y-%m-%d} and cannot be used "
            "as a flow input. Restore it to run this flow."
        )
    if dataset.is_disabled:
        raise ValidationError(
            f"Dataset '{name}' is disabled and cannot be used as a flow input. Re-enable it to run this flow."
        )


def _input_refs(graph: dict[str, Any]) -> set[tuple[str, int | None]]:
    refs: set[tuple[str, int | None]] = set()
    for node in graph.get("nodes", []):
        node_type = node.get("type")
        if node_type not in _LEGACY_FILE_INPUT_TYPES and node_type != FILE_INPUT_TYPE:
            continue
        config = node.get("data", {}).get("config", {})
        dataset_id = config.get("dataset_id")
        if not dataset_id:
            # E.g. a freshly imported flow whose bindings were stripped — surface a
            # clear message instead of a bare KeyError('dataset_id').
            raise ValidationError(
                f"Input node {node.get('id', '?')!r} has no dataset selected. "
                "Open the flow and choose a dataset for every input node."
            )
        refs.add((dataset_id, config.get("dataset_version")))
    return refs


async def build_dataset_paths(db: AsyncSession, graph: dict[str, Any]) -> tuple[dict[str, Path], list[dict[str, Any]]]:
    """Resolve every input node to a file path.

    Returns the ``dataset_paths`` map keyed by :func:`dataset_ref_key`, plus a
    list of the concrete versions resolved (for auditing on the FlowRun).
    """
    paths: dict[str, Path] = {}
    resolved: list[dict[str, Any]] = []
    for dataset_id, version in _input_refs(graph):
        ver = await resolve_version(db, dataset_id, version)
        location = Path(ver.location)
        if not location.exists():
            # The dataset was purged after its retention window: the row still
            # references the version, but the file is gone. Surface a clear error
            # instead of a cryptic file-not-found from the engine.
            name = ver.dataset.name if ver.dataset else dataset_id
            deleted = (
                f" (deleted on {ver.dataset.deleted_at:%Y-%m-%d})" if ver.dataset and ver.dataset.deleted_at else ""
            )
            raise ValidationError(
                f"Dataset version 'v{ver.version_number} of {name}'{deleted} is no longer "
                f"available — its file was purged. Re-upload the dataset to re-run this flow."
            )
        paths[dataset_ref_key(dataset_id, version)] = location
        resolved.append({"dataset_id": dataset_id, "version_number": ver.version_number})
    return paths, resolved
