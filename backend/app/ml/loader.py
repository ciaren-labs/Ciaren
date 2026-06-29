"""Model loading for mlPredict / featureImportance.

Every load goes through the security checks in :mod:`app.ml.security`: the URI must
be an MLflow reference or a local path inside the artifact root, with a supported
suffix. MLflow URIs are resolved by the MLflow client (returns the logged sklearn
Pipeline); local ``.joblib`` files load with joblib.

Important: ``.joblib`` is **pickle-backed** — loading a malicious ``.joblib`` can
execute arbitrary code, exactly like a raw ``.pkl``. Rejecting ``.pkl``/``.pickle``
is only cosmetic defense-in-depth; the real protection is that the file must
already live under the trusted artifact root (``validate_model_uri``). A size cap
(``ML_MAX_MODEL_SIZE_MB``) bounds the obvious resource-exhaustion case before the
deserializer runs. See SECURITY-AUDIT.md (#3).
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
        # Bound resource use *before* the pickle-backed deserializer (or even the
        # joblib import) runs. This does not make joblib loading "safe" (see module
        # docstring) — confinement to the artifact root is the real control — but it
        # stops a huge artifact from exhausting memory on load.
        max_bytes = settings.ML_MAX_MODEL_SIZE_MB * 1024 * 1024
        size = Path(safe).stat().st_size
        if size > max_bytes:
            raise ModelSecurityError(
                f"Refusing to load {safe!r}: model file is {size} bytes, over the "
                f"{settings.ML_MAX_MODEL_SIZE_MB} MB limit (ML_MAX_MODEL_SIZE_MB)."
            )
        import joblib

        return joblib.load(safe)
    # .json passed the suffix allowlist but native loading needs the model class,
    # which a bare file doesn't carry — point users at the MLflow reference instead.
    raise ModelSecurityError(
        f"Loading {safe!r} directly is not supported; reference the model via its "
        f"MLflow 'models:/' or 'runs:/' URI (it loads the full pipeline safely)."
    )
