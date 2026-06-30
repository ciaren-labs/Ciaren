# SPDX-License-Identifier: AGPL-3.0-only
"""Detect which ML libraries are installed and whether the ML extension is usable.

Mirrors ``app/connectors/providers.py``: an import-spec check (never importing the
heavy library itself) plus a pip install hint surfaced in errors and the UI. The
ML node registry and ML routes consult :func:`ml_extension_ready` so a base
install behaves exactly as before — ML simply stays invisible until both the
``[ml]`` extra is installed and ``ML_ENABLED`` is set.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass


@dataclass(frozen=True)
class MLLibrary:
    name: str  # distribution/display name (for messages)
    module: str  # importable module name (for the availability check)
    extra: str = "ml"  # pip extra that provides it


# Libraries that ship in the ``[ml]`` extra.
SKLEARN = MLLibrary("scikit-learn", "sklearn")
MLFLOW = MLLibrary("MLflow", "mlflow")
JOBLIB = MLLibrary("joblib", "joblib")
XGBOOST = MLLibrary("XGBoost", "xgboost")
LIGHTGBM = MLLibrary("LightGBM", "lightgbm")

# The minimum set every ML node needs (training/persistence/tracking).
CORE_LIBRARIES: tuple[MLLibrary, ...] = (SKLEARN, MLFLOW, JOBLIB)


def library_available(library: MLLibrary) -> bool:
    """True if the library can be imported, without importing it."""
    try:
        return importlib.util.find_spec(library.module) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def install_hint(library: MLLibrary) -> str:
    return f"{library.name} is not installed. Run: pip install flowframe[{library.extra}]"


def require_library(library: MLLibrary) -> None:
    """Raise a clear, install-hint error if ``library`` is missing."""
    if not library_available(library):
        raise RuntimeError(install_hint(library))


def ml_core_available() -> bool:
    """True if scikit-learn, MLflow, and joblib are all importable."""
    return all(library_available(lib) for lib in CORE_LIBRARIES)


def ml_enabled() -> bool:
    """True when the operator has switched the ML feature flag on."""
    from app.core.config import get_settings

    return get_settings().ML_ENABLED


def ml_extension_ready() -> bool:
    """True only when ML is both turned on (``ML_ENABLED``) and installable.

    The single gate for registering ML nodes and serving ML routes.
    """
    return ml_enabled() and ml_core_available()


def ml_status() -> dict[str, object]:
    """Diagnostic snapshot for the UI / CLI: per-library availability + the gate."""
    return {
        "enabled": ml_enabled(),
        "core_available": ml_core_available(),
        "ready": ml_extension_ready(),
        "libraries": {
            lib.module: {
                "name": lib.name,
                "available": library_available(lib),
                "extra": lib.extra,
            }
            for lib in (SKLEARN, MLFLOW, JOBLIB, XGBOOST, LIGHTGBM)
        },
    }
