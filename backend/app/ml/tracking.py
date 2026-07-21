# SPDX-License-Identifier: AGPL-3.0-only
"""MLflow configuration shared by mlTrain (logging) and mlPredict/featureImportance
(loading). Centralizes the local-file-store opt-in and URI normalization so both
sides agree on where artifacts live."""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

# MLflow tracking targets that are not filesystem paths and must pass through as-is.
_BARE_MLFLOW_SCHEMES = {"databricks", "databricks-uc", "uc"}

# Hosts we treat as "local" when deciding whether to warn about a remote store.
_LOCAL_TRACKING_HOSTS = {"", "localhost", "127.0.0.1", "::1"}

# Serializes "configure_mlflow() + the fluent mlflow.* calls that follow it" as
# one atomic unit. configure_mlflow calls mlflow.set_tracking_uri, which mutates
# the SDK's process-global state; the default THREAD execution mode runs
# multiple flows concurrently in the same process, so two trainings racing on
# this window (e.g. Thread A configures URI A, Thread B configures URI B before
# A reaches mlflow.start_run()/log_model()) can log one run's params/model
# against the OTHER thread's tracking store. mlflow.tracking.MlflowClient(...)
# call sites that pass an explicit tracking_uri (see ml_service.py) don't need
# this — only code using the implicit-global fluent API (mlflow.start_run(),
# mlflow.log_params(), mlflow.sklearn.log_model(), ...) does. Held only for the
# configure-through-log critical section, not the (much slower) model fit.
_MLFLOW_GLOBAL_STATE_LOCK = threading.Lock()


def mlflow_tracking_lock() -> threading.Lock:
    """The lock guarding process-global MLflow SDK state. Acquire it around
    configure_mlflow() and every fluent mlflow.* call that follows, for the
    whole critical section."""
    return _MLFLOW_GLOBAL_STATE_LOCK


def _warn_if_remote_tracking(uri: str) -> None:
    """Warn when the MLflow tracking URI is a non-local http(s) host.

    Loading a model from a ``runs:/`` / ``models:/`` URI resolves against this
    store and deserializes with cloudpickle (code execution). A remote store is
    an accepted local-first tradeoff — the operator configured it — but it is
    worth an audit-trail warning so a surprising remote host doesn't go unnoticed.
    Never raises: URI parsing problems are ignored (MLflow will surface them).
    """
    from urllib.parse import urlparse

    try:
        parsed = urlparse(uri)
    except (ValueError, TypeError):
        return
    if parsed.scheme not in ("http", "https"):
        return
    host = (parsed.hostname or "").lower()
    if host in _LOCAL_TRACKING_HOSTS:
        return
    logger.warning(
        "MLflow tracking URI points at a remote host %r; loading a model from it runs code "
        "from that store (cloudpickle deserialization). Ensure the store is trusted.",
        host,
    )


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
    """Point the MLflow client at Ciaren's effective tracking/registry URIs and
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
    effective = normalize_tracking_uri(_effective_tracking_uri(tracking_uri))
    _warn_if_remote_tracking(effective)
    mlflow.set_tracking_uri(effective)
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
        # configure_mlflow() mutates process-global MLflow SDK state, and
        # mlflow.search_experiments() below reads it back implicitly (the
        # fluent API) — both must be atomic relative to any other thread's
        # configure-through-log critical section (see mlflow_tracking_lock's
        # docstring), or this connection test could run against a URI a
        # concurrent training run just set, and report a false pass/fail.
        with mlflow_tracking_lock():
            mlflow = configure_mlflow(tracking_uri=uri.strip())
            mlflow.search_experiments(max_results=1)
    except Exception as exc:  # noqa: BLE001 - surfaced as a friendly test result
        raise ValueError(f"Could not reach MLflow at {uri!r}: {exc}") from exc
