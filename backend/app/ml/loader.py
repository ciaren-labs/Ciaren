"""Safe model loading for mlPredict / featureImportance.

Every load goes through the security checks in :mod:`app.ml.security`: the URI must
be an MLflow reference or a local path inside the artifact root, and a local file
must be a supported, non-pickle format. MLflow URIs are resolved by the MLflow
client (returns the logged sklearn Pipeline); local ``.joblib`` files load with
joblib. Pickles are refused before any code can run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.ml.security import (
    ModelSecurityError,
    validate_model_file_suffix,
    validate_model_uri,
)


def load_model(uri: str) -> Any:
    """Load and return a fitted model/pipeline from ``uri`` after validation."""
    settings = get_settings()
    safe = validate_model_uri(uri, settings.ml_artifact_path)

    if safe.startswith(("runs:/", "models:/")):
        from app.ml.tracking import configure_mlflow

        mlflow = configure_mlflow()
        import mlflow.sklearn  # type: ignore[no-redef, unused-ignore]  # noqa: F811 - load the submodule onto the configured client

        return mlflow.sklearn.load_model(safe)

    validate_model_file_suffix(safe)
    suffix = Path(safe).suffix.lower()
    if suffix == ".joblib":
        import joblib

        return joblib.load(safe)
    # .json passed the suffix allowlist but native loading needs the model class,
    # which a bare file doesn't carry — point users at the MLflow reference instead.
    raise ModelSecurityError(
        f"Loading {safe!r} directly is not supported; reference the model via its "
        f"MLflow 'models:/' or 'runs:/' URI (it loads the full pipeline safely)."
    )
