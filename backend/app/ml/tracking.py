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


def configure_mlflow() -> Any:
    """Point the MLflow client at FlowFrame's configured tracking/registry URIs and
    return the imported ``mlflow`` module. Opts into the local file store so the
    zero-setup ``./mlruns`` default keeps working on MLflow 3.14+."""
    import os

    import mlflow

    from app.core.config import get_settings

    settings = get_settings()
    # MLflow 3.14 puts the file store in maintenance mode and raises without this.
    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    mlflow.set_tracking_uri(normalize_tracking_uri(settings.MLFLOW_TRACKING_URI))
    if settings.MLFLOW_REGISTRY_URI:
        mlflow.set_registry_uri(normalize_tracking_uri(settings.MLFLOW_REGISTRY_URI))
    return mlflow
