# SPDX-License-Identifier: AGPL-3.0-only
"""Shared base classes for ML nodes.

``MLTransformation`` bridges FlowFrame's engine-agnostic frame world to sklearn,
which only speaks pandas/numpy: subclasses work in pandas via ``engine.to_pandas``
and hand results back with ``engine.from_pandas`` (Arrow-backed for polars), so an
ML node can sit inside a polars flow and still return a frame of the active engine.

``MetadataMLTransformation`` adds the metadata side-channel for nodes that surface
metrics / a model URI (mlTrain, mlEvaluate, featureImportance) onto their
``NodeResult`` — see :class:`app.engine.transformations.base.EmitsNodeMetadata`.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import (
    BaseTransformation,
    EmitsNodeMetadata,
    NodeMetadata,
)


class MLSchema:
    """The minimal, data-free description an ML node's ``validate_with_schema`` sees
    during preview: column names and an optional row count (from the previewed
    dataset). Kept tiny on purpose — full data is not loaded just to validate
    config."""

    def __init__(self, columns: list[str], row_count: int | None = None) -> None:
        self.columns = columns
        self.row_count = row_count


class MLTransformation(BaseTransformation):
    """Base for ML nodes. Provides the pandas boundary, pandas-based codegen, and a
    data-aware validation hook. Subclasses implement :meth:`validate_config`,
    :meth:`execute`, and :meth:`to_python_code`."""

    # sklearn operations have no lazy-polars equivalent; the polars code generator
    # must materialize around them.
    polars_lazy_safe = False

    # to_polars_code emits pandas (scikit-learn speaks pandas/numpy), so the polars
    # code generator converts frames to/from pandas around these nodes and collects
    # their sklearn imports — see BaseTransformation.emits_pandas_code.
    emits_pandas_code = True

    def validate_with_schema(self, config: dict[str, Any], schema: MLSchema) -> None:
        """Optional data-aware validation run during node preview, once the upstream
        column names / row count are known (see
        :meth:`app.services.preview_service.PreviewService.preview_transformation`).
        Cheap, config-only checks stay in :meth:`validate_config` so they surface
        without a dataset; :meth:`execute` re-enforces the same guardrails at run
        time (preview is best-effort, not the only gate). Default: no extra checks."""
        return None

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        """ML steps use scikit-learn (pandas/numpy); there is no native polars
        equivalent, so emit the same pandas body on either engine. The polars code
        generator materializes around it (``polars_lazy_safe = False``)."""
        return self.to_python_code(input_vars, output_vars, config)

    # -- helpers for subclasses ----------------------------------------------

    @staticmethod
    def _to_pandas(engine: EngineBackend, frame: AnyFrame) -> Any:
        return engine.to_pandas(frame)

    @staticmethod
    def _from_pandas(engine: EngineBackend, pdf: Any) -> AnyFrame:
        return engine.from_pandas(pdf)


class SklearnPipelineMixin:
    """Builds an sklearn ``Pipeline`` (preprocessing + estimator) from a node config,
    plus the matching code generation and imports.

    Shared by the train nodes (:class:`BaseTrainTransformation`) and the
    cross-validation node so the exact preprocessing applied at fit time is
    identical in both — no train/eval skew, no leakage from upstream nodes fitting
    on the full dataset. The preprocessing (imputation / scaling / one-hot
    encoding) is bundled *into* the pipeline so it is refit per CV fold.
    """

    _SCALER_CLASSES = {
        "standard_scaler": "StandardScaler",
        "minmax_scaler": "MinMaxScaler",
        "robust_scaler": "RobustScaler",
    }

    # -- runtime pipeline build ----------------------------------------------

    def _resolve_features(
        self, config: dict[str, Any], columns: list[str], supervised: bool, target: str | None
    ) -> list[str]:
        features = config.get("feature_columns")
        if features:
            return list(features)
        return [c for c in columns if not (supervised and c == target)]

    def _build_pipeline(self, config: dict[str, Any], features: list[str], pdf: Any, spec: Any, seed: int) -> Any:
        from sklearn.pipeline import Pipeline

        from app.ml.models import build_estimator

        estimator = build_estimator(config["model_type"], config.get("hyperparameters"), seed)
        preprocessor = self._build_preprocessor(config, features, pdf)
        steps = []
        if preprocessor is not None:
            steps.append(("preprocessor", preprocessor))
        steps.append(("model", estimator))
        return Pipeline(steps)

    def _build_preprocessor(self, config: dict[str, Any], features: list[str], pdf: Any) -> Any:
        import pandas as pd
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, RobustScaler, StandardScaler

        pre = config.get("preprocessing") or {}
        if pre:
            numeric = pre.get("numeric_columns", [])
            categorical = pre.get("categorical_columns", [])
        else:
            numeric = [c for c in features if pd.api.types.is_numeric_dtype(pdf[c])]
            categorical = [c for c in features if c not in numeric]

        scalers = {"standard_scaler": StandardScaler, "minmax_scaler": MinMaxScaler, "robust_scaler": RobustScaler}
        num_strategy = pre.get("numeric_strategy", "standard_scaler")
        transformers = []
        if numeric:
            steps: list[tuple[str, Any]] = [("impute", SimpleImputer(strategy=pre.get("impute_numeric", "median")))]
            if num_strategy in scalers:
                steps.append(("scale", scalers[num_strategy]()))
            transformers.append(("num", Pipeline(steps), numeric))
        if categorical:
            cat_steps: list[tuple[str, Any]] = [
                ("impute", SimpleImputer(strategy=pre.get("impute_categorical", "most_frequent"))),
                ("encode", OneHotEncoder(handle_unknown="ignore")),
            ]
            transformers.append(("cat", Pipeline(cat_steps), categorical))
        if not transformers:
            return None
        return ColumnTransformer(transformers, remainder="drop")

    # -- code export ---------------------------------------------------------

    def _preprocessor_code(self, config: dict[str, Any]) -> tuple[list[str], list[str]]:
        """Emit code that rebuilds the same ColumnTransformer as ``_build_preprocessor``.

        Returns ``(lines, steps)`` where ``lines`` define ``_preprocessor`` and
        ``steps`` is the leading Pipeline step list (``[]`` when no preprocessing
        is needed). When the config pins explicit numeric/categorical columns we
        emit literals; otherwise we detect them by dtype at runtime, exactly like
        the executor.
        """
        pre = config.get("preprocessing") or {}
        impute_numeric = pre.get("impute_numeric", "median")
        impute_categorical = pre.get("impute_categorical", "most_frequent")
        num_strategy = pre.get("numeric_strategy", "standard_scaler")

        lines: list[str] = []
        if pre.get("numeric_columns") is not None or pre.get("categorical_columns") is not None:
            lines.append(f"_numeric = {list(pre.get('numeric_columns') or [])!r}")
            lines.append(f"_categorical = {list(pre.get('categorical_columns') or [])!r}")
        else:
            lines.append("_numeric = [c for c in _features if pd.api.types.is_numeric_dtype(X[c])]")
            lines.append("_categorical = [c for c in _features if c not in _numeric]")

        num_steps = [f"('impute', SimpleImputer(strategy={impute_numeric!r}))"]
        if num_strategy in self._SCALER_CLASSES:
            num_steps.append(f"('scale', {self._SCALER_CLASSES[num_strategy]}())")
        num_pipe = "Pipeline([" + ", ".join(num_steps) + "])"
        cat_pipe = (
            "Pipeline(["
            f"('impute', SimpleImputer(strategy={impute_categorical!r})), "
            "('encode', OneHotEncoder(handle_unknown='ignore'))])"
        )
        lines += [
            "_transformers = []",
            f"if _numeric:\n    _transformers.append(('num', {num_pipe}, _numeric))",
            f"if _categorical:\n    _transformers.append(('cat', {cat_pipe}, _categorical))",
            "_preprocessor = ColumnTransformer(_transformers, remainder='drop')",
        ]
        return lines, ["('preprocessor', _preprocessor)"]

    def _estimator_repr(self, config: dict[str, Any]) -> str:
        # Build the estimator just to render a faithful repr in exported code.
        from app.ml.models import build_estimator

        est = build_estimator(config["model_type"], config.get("hyperparameters"), config.get("seed"))
        return repr(est)

    def _pipeline_imports(self, config: dict[str, Any]) -> list[str]:
        """Import lines the exported script needs for the estimator + preprocessing."""
        from app.ml.models import build_estimator

        est = build_estimator(config["model_type"], config.get("hyperparameters"), config.get("seed"))
        cls = type(est).__name__
        top = type(est).__module__.split(".")[0]
        if top in ("xgboost", "lightgbm"):
            est_import = f"from {top} import {cls}"
        else:
            # Use the public sklearn module (e.g. sklearn.ensemble), not the private
            # implementation module (sklearn.ensemble._forest) the class lives in.
            parts: list[str] = []
            for part in type(est).__module__.split("."):
                if part.startswith("_"):
                    break
                parts.append(part)
            est_import = f"from {'.'.join(parts)} import {cls}"
        imps = [
            "from sklearn.pipeline import Pipeline",
            est_import,
            # The exported preprocessing pipeline mirrors execute() (see _preprocessor_code).
            "from sklearn.compose import ColumnTransformer",
            "from sklearn.impute import SimpleImputer",
            "from sklearn.preprocessing import OneHotEncoder",
        ]
        num_strategy = (config.get("preprocessing") or {}).get("numeric_strategy", "standard_scaler")
        if num_strategy in self._SCALER_CLASSES:
            imps.append(f"from sklearn.preprocessing import {self._SCALER_CLASSES[num_strategy]}")
        return imps


class MetadataMLTransformation(MLTransformation, EmitsNodeMetadata):
    """An ML node that also surfaces non-frame metadata onto its NodeResult.

    Subclasses implement :meth:`execute_with_metadata`; :meth:`execute` delegates to
    it and drops the metadata, so preview (frames only) and the run executor (frames
    + metadata) share one implementation. Metadata is returned, never stored on
    ``self`` — the registry holds a single shared instance per node type.
    """

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        frames, _meta = self.execute_with_metadata(engine, inputs, config)
        return frames

    @abstractmethod
    def execute_with_metadata(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> tuple[dict[str, AnyFrame], NodeMetadata | None]: ...
