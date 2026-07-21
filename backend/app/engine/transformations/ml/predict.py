# SPDX-License-Identifier: AGPL-3.0-only
"""mlPredict — load a trained model and score a dataframe.

The model comes from the ``model`` input handle (the reference frame mlTrain emits)
or, for production flows, from a ``model_uri`` in the config (e.g.
``models:/churn/Production``). The URI is security-validated before any load, and
the input columns are checked against the model's expected features.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.preview_context import in_preview
from app.engine.transformations.base import NodeMetadata
from app.engine.transformations.ml.base import MetadataMLTransformation

logger = logging.getLogger(__name__)

# Warn before predicting on very large frames without batching (OOM risk).
_LARGE_FRAME_ROWS = 1_000_000


class MLPredictTransformation(MetadataMLTransformation):
    type = "mlPredict"
    input_handles = ("in",)
    optional_input_handles = ("model",)

    def validate_config(self, config: dict[str, Any]) -> None:
        batch = config.get("batch_size")
        if batch is not None and (not isinstance(batch, int) or isinstance(batch, bool) or batch < 1):
            raise ValueError("mlPredict 'batch_size' must be a positive integer or null.")
        proba = config.get("output_proba_columns")
        if proba is not None and (not isinstance(proba, list) or not all(isinstance(c, str) for c in proba)):
            raise ValueError("mlPredict 'output_proba_columns' must be a list of column names or null.")

    def execute_with_metadata(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> tuple[dict[str, AnyFrame], NodeMetadata | None]:
        # During preview we don't load a model or score; pass the data through.
        if in_preview():
            return {"out": inputs["in"]}, None

        from app.ml.loader import load_model

        pdf = engine.to_pandas(inputs["in"]).copy()
        # Snapshot the input columns *before* we write any output: prediction /
        # probability columns that collide with existing data would silently
        # clobber it, so we warn against this original set.
        original_columns = set(pdf.columns)
        uri, task, recorded_features = self._resolve_model(engine, inputs, config)
        model = load_model(uri)

        x = self._align_features(model, pdf, recorded_features)
        output_column = config.get("output_column", "prediction")
        if output_column in original_columns:
            logger.warning(
                "mlPredict: output_column %r already exists in the input — its values will be overwritten "
                "by the predictions. Set a different 'output_column' to preserve the original column.",
                output_column,
            )
        batch_size = config.get("batch_size")
        if batch_size is None and len(pdf) > _LARGE_FRAME_ROWS:
            logger.warning("mlPredict: predicting %d rows at once; set batch_size to bound memory.", len(pdf))
        pdf[output_column] = self._predict(model, x, batch_size)

        proba_columns = config.get("output_proba_columns")
        if proba_columns:
            self._add_probabilities(model, x, pdf, proba_columns, task, original_columns)

        meta = NodeMetadata(model_uri=uri, task_type=task)
        return {"out": engine.from_pandas(pdf)}, meta

    # -- helpers -------------------------------------------------------------

    def _resolve_model(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> tuple[str, str | None, list[str]]:
        # A blank string from the config form counts as "not set" — fall back to
        # the wired model. (The UI saves model_uri="" by default, so only treating
        # None as absent would ignore a perfectly good wired model.)
        uri = config.get("model_uri")
        if isinstance(uri, str):
            uri = uri.strip() or None
        task: str | None = None
        recorded_features: list[str] = []
        model_frame = inputs.get("model")
        if model_frame is not None:
            ref = engine.to_pandas(model_frame)
            if not ref.empty:
                if not uri and "model_uri" in ref.columns:
                    uri = ref.iloc[0]["model_uri"]
                if "task_type" in ref.columns:
                    task = ref.iloc[0]["task_type"]
                recorded_features = self._recorded_features(ref)
        if not uri or (isinstance(uri, float)):  # float catches a NaN cell
            raise ValueError("mlPredict: no model to load — connect the 'model' input or set 'model_uri'.")
        return str(uri), task, recorded_features

    @staticmethod
    def _recorded_features(ref: Any) -> list[str]:
        """The feature columns train.py recorded on the model reference frame
        (``feature_columns_json``). Used to align inputs for models that don't
        carry ``feature_names_in_``. Tolerant of a missing/NaN/malformed cell."""
        if "feature_columns_json" not in ref.columns:
            return []
        raw = ref.iloc[0]["feature_columns_json"]
        if not isinstance(raw, str) or not raw:
            return []
        try:
            parsed = json.loads(raw)
        except ValueError:
            return []
        return [str(c) for c in parsed] if isinstance(parsed, list) else []

    def _align_features(self, model: Any, pdf: Any, recorded_features: list[str] | None = None) -> Any:
        expected = getattr(model, "feature_names_in_", None)
        if expected is None:
            # Model carries no fitted feature names (e.g. fit on a numpy array, or
            # an external model). Fall back to the feature columns the train node
            # recorded on the model reference so we still subset to the training
            # features instead of feeding the whole frame (target + extras)
            # positionally. With neither source we pass the frame through (the rare
            # external-model case).
            if not recorded_features:
                return pdf
            expected = recorded_features
        expected = list(expected)
        missing = [c for c in expected if c not in pdf.columns]
        if missing:
            raise ValueError(f"mlPredict: input is missing model features {missing}. Model expects {expected}.")
        extra = [c for c in pdf.columns if c not in expected]
        if extra:
            logger.warning("mlPredict: dropping columns not seen in training: %s", extra)
        return pdf[expected]

    def _predict(self, model: Any, x: Any, batch_size: int | None) -> Any:
        import numpy as np

        if not batch_size or len(x) <= batch_size:
            return model.predict(x)
        chunks = [model.predict(x.iloc[i : i + batch_size]) for i in range(0, len(x), batch_size)]
        return np.concatenate(chunks)

    def _add_probabilities(
        self,
        model: Any,
        x: Any,
        pdf: Any,
        proba_columns: list[str],
        task: str | None,
        original_columns: set[str] | None = None,
    ) -> None:
        if not hasattr(model, "predict_proba"):
            logger.warning("mlPredict: model has no predict_proba (task=%s); skipping probabilities.", task)
            return
        proba = model.predict_proba(x)
        if proba.shape[1] != len(proba_columns):
            raise ValueError(
                f"mlPredict: output_proba_columns has {len(proba_columns)} names but the model "
                f"produces {proba.shape[1]} class probabilities."
            )
        clobbered = [c for c in proba_columns if c in (original_columns or set())]
        if clobbered:
            logger.warning(
                "mlPredict: probability column(s) %s already exist in the input and will be overwritten. "
                "Rename them via 'output_proba_columns' to preserve the original data.",
                clobbered,
            )
        for i, col in enumerate(proba_columns):
            pdf[col] = proba[:, i]

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        output_column = config.get("output_column", "prediction")
        # Prefer the upstream trained-model variable; fall back to loading a URI.
        # Use MLflow-3 alias syntax (models:/name@alias) — the legacy /Stage form
        # silently resolves to nothing.
        model_var = input_vars.get("model")
        uri = config.get("model_uri") or "models:/your-model@production"
        load = "" if model_var else f"_model = mlflow.sklearn.load_model({uri!r})\n"
        model_ref = model_var or "_model"
        # Score only the model's training features (drop the target / extra columns),
        # mirroring _align_features — otherwise sklearn raises on a feature mismatch.
        lines = [
            f"{load}{dst} = {src}.copy()",
            f"_model_features = list(getattr({model_ref}, 'feature_names_in_', {src}.columns))",
            f"{dst}[{output_column!r}] = {model_ref}.predict({src}[_model_features])",
        ]
        proba_columns = config.get("output_proba_columns")
        if proba_columns:
            lines.append(f"_proba = {model_ref}.predict_proba({src}[_model_features])")
            for i, col in enumerate(proba_columns):
                lines.append(f"{dst}[{col!r}] = _proba[:, {i}]")
        return "\n".join(lines)

    def imports(self, config: dict[str, Any]) -> list[str]:
        # Only need the MLflow loader when there's no upstream model variable.
        return ["import mlflow.sklearn"]
