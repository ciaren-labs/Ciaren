# SPDX-License-Identifier: AGPL-3.0-only
"""Detect which ML libraries are installed and whether the ML extension is usable.

Mirrors ``app/connectors/providers.py``: an import-spec check (never importing the
heavy library itself) plus a pip install hint surfaced in errors and the UI.
scikit-learn, MLflow, and joblib are core dependencies, so ``ml_core_available()``
is effectively always true on a normal install — the check mainly guards against a
broken/stripped-down environment. XGBoost and LightGBM remain behind the ``[ml]``
extra and are gated per-model (see ``ModelSpec.requires`` in ``app/ml/models.py``),
not by this module's overall gate. The ML node registry and ML routes consult
:func:`ml_extension_ready` as the single on/off switch for the feature as a whole.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MLLibrary:
    name: str  # distribution/display name (for messages)
    module: str  # importable module name (for the availability check)
    extra: str = "ml"  # pip extra that provides it (only meaningful for XGBoost/LightGBM)


SKLEARN = MLLibrary("scikit-learn", "sklearn")
MLFLOW = MLLibrary("MLflow", "mlflow")
JOBLIB = MLLibrary("joblib", "joblib")
# The two libraries actually gated behind the ``[ml]`` extra.
XGBOOST = MLLibrary("XGBoost", "xgboost")
LIGHTGBM = MLLibrary("LightGBM", "lightgbm")

# The minimum set every ML node needs (training/persistence/tracking) — all core
# dependencies now, kept as a group for the availability check below.
CORE_LIBRARIES: tuple[MLLibrary, ...] = (SKLEARN, MLFLOW, JOBLIB)


def library_available(library: MLLibrary) -> bool:
    """True if the library can be imported, without importing it."""
    try:
        return importlib.util.find_spec(library.module) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def install_hint(library: MLLibrary) -> str:
    return f"{library.name} is not installed. Run: pip install ciaren[{library.extra}]"


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


def guard_graph_ml_enabled(graph: dict[str, Any] | None) -> None:
    """Reject executing/previewing a graph that uses ML nodes when the ML
    extension is off.

    ML node types are registered whenever the [ml] libraries are importable, so
    without this a crafted graph could reach ML nodes even with ML_ENABLED false.
    Shared by run and preview so the feature flag is a real gate everywhere.
    """
    from app.core.exceptions import MLNotEnabledError
    from app.engine.registry import ml_node_types

    ml_types = ml_node_types()
    if not ml_types:
        return
    nodes = (graph or {}).get("nodes", [])
    graph_types = {n.get("type") for n in nodes if isinstance(n, dict)}
    if graph_types & ml_types and not ml_extension_ready():
        raise MLNotEnabledError(
            "This flow uses machine-learning nodes, but ML support is not enabled "
            "on this server (set ML_ENABLED and install the [ml] extra)."
        )


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
