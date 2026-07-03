# SPDX-License-Identifier: AGPL-3.0-only
"""Catalog of supported model types and how to build each estimator.

Maps the ``model_type`` string from an ``mlTrain`` config to its learning task and
a builder that constructs the sklearn-compatible estimator with the user's
hyperparameters and the run seed. Everything imports lazily so the catalog can be
described (names, tasks) without importing scikit-learn / xgboost / lightgbm.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.ml.availability import LIGHTGBM, XGBOOST, MLLibrary, install_hint, library_available, require_library
from app.ml.security import sanitize_hyperparameters

CLASSIFICATION = "classification"
REGRESSION = "regression"
CLUSTERING = "clustering"
DIMENSIONALITY_REDUCTION = "dimensionality_reduction"
TIMESERIES = "timeseries"

#: Every learning task Ciaren models. ``timeseries`` is defined but has no
#: estimators yet (the Train Forecaster node is a scaffold — models land later).
TASKS = (CLASSIFICATION, REGRESSION, CLUSTERING, DIMENSIONALITY_REDUCTION, TIMESERIES)

#: Train node type → the tasks whose models it accepts. One node per task family
#: so the palette is self-explanatory and each picker only shows relevant models.
TRAIN_NODE_TASKS: dict[str, tuple[str, ...]] = {
    "mlTrainClassifier": (CLASSIFICATION,),
    "mlTrainRegressor": (REGRESSION,),
    "mlTrainClustering": (CLUSTERING,),
    "mlTrainForecaster": (TIMESERIES,),
    "mlTrainDimReduction": (DIMENSIONALITY_REDUCTION,),
}
TRAIN_NODE_TYPES: tuple[str, ...] = tuple(TRAIN_NODE_TASKS)


@dataclass(frozen=True)
class ModelSpec:
    task: str
    builder: Callable[[dict[str, Any], int | None], Any]
    supervised: bool
    requires: tuple[MLLibrary, ...] = field(default_factory=tuple)


def _with_seed(params: dict[str, Any], seed: int | None, key: str = "random_state") -> dict[str, Any]:
    """Inject the run seed under ``key`` unless the user set it explicitly."""
    merged = dict(params)
    if seed is not None and key not in merged:
        merged[key] = seed
    return merged


# -- builders (lazy imports keep the catalog import-light) -------------------


def _logistic_regression(p: dict[str, Any], seed: int | None) -> Any:
    from sklearn.linear_model import LogisticRegression

    return LogisticRegression(**_with_seed({"max_iter": 1000, **p}, seed))


def _random_forest_classifier(p: dict[str, Any], seed: int | None) -> Any:
    from sklearn.ensemble import RandomForestClassifier

    return RandomForestClassifier(**_with_seed(p, seed))


def _svm_classifier(p: dict[str, Any], seed: int | None) -> Any:
    from sklearn.svm import SVC

    # probability is left at sklearn's default (off); set it via hyperparameters if
    # class probabilities are needed. mlPredict degrades gracefully without it.
    return SVC(**_with_seed(p, seed))


def _knn_classifier(p: dict[str, Any], seed: int | None) -> Any:
    from sklearn.neighbors import KNeighborsClassifier

    return KNeighborsClassifier(**p)  # no random_state


def _xgboost_classifier(p: dict[str, Any], seed: int | None) -> Any:
    from xgboost import XGBClassifier

    return XGBClassifier(**_with_seed(p, seed))


def _lightgbm_classifier(p: dict[str, Any], seed: int | None) -> Any:
    from lightgbm import LGBMClassifier

    return LGBMClassifier(**_with_seed({"verbose": -1, **p}, seed))


def _linear_regression(p: dict[str, Any], seed: int | None) -> Any:
    from sklearn.linear_model import LinearRegression

    return LinearRegression(**p)  # no random_state


def _ridge(p: dict[str, Any], seed: int | None) -> Any:
    from sklearn.linear_model import Ridge

    return Ridge(**_with_seed(p, seed))


def _lasso(p: dict[str, Any], seed: int | None) -> Any:
    from sklearn.linear_model import Lasso

    return Lasso(**_with_seed(p, seed))


def _random_forest_regressor(p: dict[str, Any], seed: int | None) -> Any:
    from sklearn.ensemble import RandomForestRegressor

    return RandomForestRegressor(**_with_seed(p, seed))


def _svr(p: dict[str, Any], seed: int | None) -> Any:
    from sklearn.svm import SVR

    return SVR(**p)  # no random_state


def _xgboost_regressor(p: dict[str, Any], seed: int | None) -> Any:
    from xgboost import XGBRegressor

    return XGBRegressor(**_with_seed(p, seed))


def _lightgbm_regressor(p: dict[str, Any], seed: int | None) -> Any:
    from lightgbm import LGBMRegressor

    return LGBMRegressor(**_with_seed({"verbose": -1, **p}, seed))


def _kmeans(p: dict[str, Any], seed: int | None) -> Any:
    from sklearn.cluster import KMeans

    return KMeans(**_with_seed({"n_init": "auto", **p}, seed))


def _dbscan(p: dict[str, Any], seed: int | None) -> Any:
    from sklearn.cluster import DBSCAN

    return DBSCAN(**p)  # no random_state


def _agglomerative(p: dict[str, Any], seed: int | None) -> Any:
    from sklearn.cluster import AgglomerativeClustering

    return AgglomerativeClustering(**p)  # no random_state


def _pca_fit(p: dict[str, Any], seed: int | None) -> Any:
    from sklearn.decomposition import PCA

    return PCA(**_with_seed(p, seed))


MODEL_CATALOG: dict[str, ModelSpec] = {
    # classification
    "logistic_regression": ModelSpec(CLASSIFICATION, _logistic_regression, True),
    "random_forest_classifier": ModelSpec(CLASSIFICATION, _random_forest_classifier, True),
    "svm_classifier": ModelSpec(CLASSIFICATION, _svm_classifier, True),
    "knn_classifier": ModelSpec(CLASSIFICATION, _knn_classifier, True),
    "xgboost_classifier": ModelSpec(CLASSIFICATION, _xgboost_classifier, True, (XGBOOST,)),
    "lightgbm_classifier": ModelSpec(CLASSIFICATION, _lightgbm_classifier, True, (LIGHTGBM,)),
    # regression
    "linear_regression": ModelSpec(REGRESSION, _linear_regression, True),
    "ridge": ModelSpec(REGRESSION, _ridge, True),
    "lasso": ModelSpec(REGRESSION, _lasso, True),
    "random_forest_regressor": ModelSpec(REGRESSION, _random_forest_regressor, True),
    "svr": ModelSpec(REGRESSION, _svr, True),
    "xgboost_regressor": ModelSpec(REGRESSION, _xgboost_regressor, True, (XGBOOST,)),
    "lightgbm_regressor": ModelSpec(REGRESSION, _lightgbm_regressor, True, (LIGHTGBM,)),
    # clustering
    "kmeans": ModelSpec(CLUSTERING, _kmeans, False),
    "dbscan": ModelSpec(CLUSTERING, _dbscan, False),
    "agglomerative": ModelSpec(CLUSTERING, _agglomerative, False),
    # dimensionality reduction (fit)
    "pca_fit": ModelSpec(DIMENSIONALITY_REDUCTION, _pca_fit, False),
}


# -- plugin-contributed model types -------------------------------------------
# Plugins contribute model types through a ModelProvider (see app/plugin_api).
# They are consulted *after* the static catalog, synthesized into the same
# ModelSpec shape, and train through the identical pipeline — hyperparameter
# sanitization, seed injection by the plugin's builder, size limits, MLflow
# logging, and code export all apply unchanged.


def _plugin_registry() -> Any | None:
    """The process-wide plugin registry, or None when unavailable (e.g. during
    early bootstrap). Imported lazily: app.plugins depends on app.ml, not vice
    versa, so this back-reference must never be a module-level import."""
    try:
        from app.plugins import get_registry

        return get_registry()
    except Exception:  # noqa: BLE001 — the ML catalog must work without plugins
        return None


def _missing_plugin_modules(requires: tuple[str, ...]) -> list[str]:
    import importlib.util

    missing: list[str] = []
    for module in requires:
        try:
            if importlib.util.find_spec(module) is None:
                missing.append(module)
        except (ModuleNotFoundError, ValueError):
            missing.append(module)
    return missing


def _plugin_model_spec(model_type: str) -> ModelSpec | None:
    """Synthesize a :class:`ModelSpec` for a plugin-contributed model type."""
    registry = _plugin_registry()
    if registry is None:
        return None
    spec = registry.model_type_spec(model_type)
    builder = registry.model_builder(model_type)
    if spec is None or builder is None:
        return None

    def _build(params: dict[str, Any], seed: int | None, _spec: Any = spec, _builder: Any = builder) -> Any:
        missing = _missing_plugin_modules(tuple(_spec.requires))
        if missing:
            hint = _spec.install_hint or f"install the missing module(s): {', '.join(missing)}"
            raise RuntimeError(f"model_type {_spec.id!r} needs {', '.join(missing)} — {hint}")
        # The spec's declared defaults fill in under the user's values — the same
        # pattern core builders use ({"max_iter": 1000, **p}) — so an untouched
        # hyperparameter form trains with the defaults the catalog advertises.
        return _builder({**_spec.default_hyperparameters, **params}, seed)

    return ModelSpec(task=spec.task, builder=_build, supervised=spec.supervised)


def plugin_import_lines(model_type: str) -> tuple[str, ...]:
    """Import lines a plugin model type declares for exported training scripts
    (``()`` for core types or when the plugin declares none — the estimator
    import is then derived from the estimator's class module)."""
    spec = _plugin_model_types().get(model_type)
    return tuple(spec.import_lines) if spec is not None else ()


def _plugin_model_types() -> dict[str, Any]:
    """Plugin model-type specs by id (excluding ids shadowed by the core catalog,
    which the registry's duplicate guard should already prevent)."""
    registry = _plugin_registry()
    if registry is None:
        return {}
    return {s.id: s for s in registry.model_type_specs() if s.id not in MODEL_CATALOG}


def get_model_spec(model_type: str) -> ModelSpec:
    spec = MODEL_CATALOG.get(model_type)
    if spec is not None:
        return spec
    plugin_spec = _plugin_model_spec(model_type)
    if plugin_spec is not None:
        return plugin_spec
    supported = sorted([*MODEL_CATALOG, *_plugin_model_types()])
    raise ValueError(f"Unknown model_type {model_type!r}. Supported: {supported}.")


def models_for_tasks(tasks: tuple[str, ...]) -> list[str]:
    """Model-type names whose task is in ``tasks`` (sorted, stable), including
    plugin-contributed types."""
    names = [name for name, spec in MODEL_CATALOG.items() if spec.task in tasks]
    names += [name for name, spec in _plugin_model_types().items() if spec.task in tasks]
    return sorted(names)


def model_catalog_status() -> list[dict[str, Any]]:
    """Serializable model catalog annotated with optional-library availability.
    Core entries first, then plugin-contributed types (marked by ``provider``)."""
    rows: list[dict[str, Any]] = []
    for model_type, spec in sorted(MODEL_CATALOG.items()):
        missing = [lib for lib in spec.requires if not library_available(lib)]
        rows.append(
            {
                "model_type": model_type,
                "task": spec.task,
                "available": not missing,
                "requires": [lib.module for lib in spec.requires],
                "missing": [lib.module for lib in missing],
                "warning": "; ".join(install_hint(lib) for lib in missing) if missing else None,
                "provider": "ciaren.ml",
                "label": None,
            }
        )
    for model_type, spec in sorted(_plugin_model_types().items()):
        missing_modules = _missing_plugin_modules(tuple(spec.requires))
        rows.append(
            {
                "model_type": model_type,
                "task": spec.task,
                "available": not missing_modules,
                "requires": list(spec.requires),
                "missing": missing_modules,
                "warning": (spec.install_hint or f"missing: {', '.join(missing_modules)}") if missing_modules else None,
                "provider": spec.provider,
                "label": spec.label,
                "supervised": spec.supervised,
                "default_hyperparameters": dict(spec.default_hyperparameters),
                "hyperparameter_schema": dict(spec.hyperparameter_schema),
            }
        )
    return rows


def build_estimator(model_type: str, hyperparameters: dict[str, Any] | None, seed: int | None) -> Any:
    """Construct the estimator for ``model_type``.

    Validates library availability (clear install hint if xgboost/lightgbm is
    missing) and hyperparameters, then builds with the run seed injected. A bad
    hyperparameter name surfaces as a ValueError rather than a raw sklearn TypeError.
    """
    spec = get_model_spec(model_type)
    for lib in spec.requires:
        require_library(lib)
    params = sanitize_hyperparameters(hyperparameters)
    try:
        return spec.builder(params, seed)
    except TypeError as exc:
        raise ValueError(f"Invalid hyperparameters for {model_type!r}: {exc}") from exc
