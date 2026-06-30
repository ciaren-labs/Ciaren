# SPDX-License-Identifier: AGPL-3.0-only
"""MLflow configuration shared by mlTrain (logging) and mlPredict/featureImportance
(loading). Centralizes the local-file-store opt-in and URI normalization so both
sides agree on where artifacts live."""

from __future__ import annotations

from typing import Any

# MLflow tracking targets that are not filesystem paths and must pass through as-is.
_BARE_MLFLOW_SCHEMES = {"databricks", "databricks-uc", "uc"}


def normalize_tracking_uri(uri: str) -> str:
    """Make a local filesystem path a valid MLflow URI.

    MLflow accepts ``scheme://...`` URIs (file/http/sqlite/...) and a few bare
    words (``databricks``), but a bare absolute Windows path (``C:\\...``) is
    misparsed as a ``c:`` scheme. Convert any plain path to an absolute
    ``file://`` URI so the same config works on Windows and POSIX.
    """
    from pathlib import Path

    if "://" in uri or uri in _BARE_MLFLOW_SCHEMES:
        return uri
    return Path(uri).resolve().as_uri()


def _effective_tracking_uri(explicit: str | None) -> str:
    """Resolve the tracking URI to use, in precedence order:

    explicit argument > the run context (set by the executor from the MLflow
    *connection*, the source of truth) > the ``MLFLOW_TRACKING_URI`` setting.
    """
    if explicit:
        return explicit
    from app.engine.run_context import current_run_context

    ctx = current_run_context()
    if ctx and ctx.get("tracking_uri"):
        return str(ctx["tracking_uri"])
    from app.core.config import get_settings

    return get_settings().MLFLOW_TRACKING_URI


def configure_mlflow(tracking_uri: str | None = None) -> Any:
    """Point the MLflow client at FlowFrame's effective tracking/registry URIs and
    return the imported ``mlflow`` module. Opts into the local file store so the
    zero-setup ``./mlruns`` default keeps working on MLflow 3.14+.

    The effective tracking URI comes from the MLflow *connection* (resolved into
    the run context, or passed explicitly by API callers) and falls back to the
    ``MLFLOW_TRACKING_URI`` setting — so editing the connection re-points MLflow."""
    import os

    import mlflow

    from app.core.config import get_settings

    settings = get_settings()
    # MLflow 3.14 puts the file store in maintenance mode and raises without this.
    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    mlflow.set_tracking_uri(normalize_tracking_uri(_effective_tracking_uri(tracking_uri)))
    if settings.MLFLOW_REGISTRY_URI:
        mlflow.set_registry_uri(normalize_tracking_uri(settings.MLFLOW_REGISTRY_URI))
    return mlflow


async def resolve_tracking_uri(db: Any) -> str:
    """The effective tracking URI from the DB: the MLflow connection's URI (the
    source of truth) when one exists, else the ``MLFLOW_TRACKING_URI`` setting.

    Used by the execution service (to seed the run context) and the ML API routes
    (which load/list/register models)."""
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.models.connection import Connection

    result = await db.execute(select(Connection).where(Connection.provider == "mlflow").limit(1))
    conn = result.scalars().first()
    if conn is not None and conn.database:
        return str(conn.database)
    return get_settings().MLFLOW_TRACKING_URI


def test_tracking_uri(uri: str) -> None:
    """Verify an MLflow tracking URI is usable. Raises ValueError on failure.

    Runs a lightweight read (list a single experiment) against the resolved store.
    Designed to be called in a worker thread by the connection service."""
    if not uri or not uri.strip():
        raise ValueError("MLflow tracking URI is required (a folder path or a tracking server URI).")
    try:
        mlflow = configure_mlflow(tracking_uri=uri.strip())
        mlflow.search_experiments(max_results=1)
    except Exception as exc:  # noqa: BLE001 - surfaced as a friendly test result
        raise ValueError(f"Could not reach MLflow at {uri!r}: {exc}") from exc
