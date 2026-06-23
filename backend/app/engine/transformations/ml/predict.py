"""mlPredict — load a trained model and score a dataframe.

The model comes from the ``model`` input handle (the reference frame mlTrain emits)
or, for production flows, from a ``model_uri`` in the config (e.g.
``models:/churn/Production``). The URI is security-validated before any load, and
the input columns are checked against the model's expected features.
"""
from __future__ import annotations

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
        uri, task = self._resolve_model(engine, inputs, config)
        model = load_model(uri)

        x = self._align_features(model, pdf)
        output_column = config.get("output_column", "prediction")
        batch_size = config.get("batch_size")
        if batch_size is None and len(pdf) > _LARGE_FRAME_ROWS:
            logger.warning(
                "mlPredict: predicting %d rows at once; set batch_size to bound memory.", len(pdf)
            )
        pdf[output_column] = self._predict(model, x, batch_size)

        proba_columns = config.get("output_proba_columns")
        if proba_columns:
            self._add_probabilities(model, x, pdf, proba_columns, task)

        meta = NodeMetadata(model_uri=uri, task_type=task)
        return {"out": engine.from_pandas(pdf)}, meta

    # -- helpers -------------------------------------------------------------

    def _resolve_model(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> tuple[str, str | None]:
        # A blank string from the config form counts as "not set" — fall back to
        # the wired model. (The UI saves model_uri="" by default, so only treating
        # None as absent would ignore a perfectly good wired model.)
        uri = config.get("model_uri")
        if isinstance(uri, str):
            uri = uri.strip() or None
        task: str | None = None
        model_frame = inputs.get("model")
        if model_frame is not None:
            ref = engine.to_pandas(model_frame)
            if not ref.empty:
                if not uri and "model_uri" in ref.columns:
                    uri = ref.iloc[0]["model_uri"]
                if "task_type" in ref.columns:
                    task = ref.iloc[0]["task_type"]
        if not uri or (isinstance(uri, float)):  # float catches a NaN cell
            raise ValueError(
                "mlPredict: no model to load — connect the 'model' input or set 'model_uri'."
            )
        return str(uri), task

    def _align_features(self, model: Any, pdf: Any) -> Any:
        expected = getattr(model, "feature_names_in_", None)
        if expected is None:
            return pdf
        expected = list(expected)
        missing = [c for c in expected if c not in pdf.columns]
        if missing:
            raise ValueError(
                f"mlPredict: input is missing model features {missing}. "
                f"Model expects {expected}."
            )
        extra = [c for c in pdf.columns if c not in expected]
        if extra:
            logger.warning("mlPredict: dropping columns not seen in training: %s", extra)
        return pdf[expected]

    def _predict(self, model: Any, x: Any, batch_size: int | None) -> Any:
        import numpy as np

        if not batch_size or len(x) <= batch_size:
            return model.predict(x)
        chunks = [model.predict(x.iloc[i:i + batch_size]) for i in range(0, len(x), batch_size)]
        return np.concatenate(chunks)

    def _add_probabilities(
        self, model: Any, x: Any, pdf: Any, proba_columns: list[str], task: str | None
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
        for i, col in enumerate(proba_columns):
            pdf[col] = proba[:, i]

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        output_column = config.get("output_column", "prediction")
        # Prefer the upstream trained-model variable; fall back to loading a URI.
        model_var = input_vars.get("model")
        load = "" if model_var else (
            f"_model = mlflow.sklearn.load_model("
            f"{config.get('model_uri', 'models:/your-model/Production')!r})\n"
        )
        model_ref = model_var or "_model"
        return (
            f"{load}{dst} = {src}.copy()\n"
            f"{dst}[{output_column!r}] = {model_ref}.predict({src})"
        )

    def imports(self, config: dict[str, Any]) -> list[str]:
        # Only need the MLflow loader when there's no upstream model variable.
        return ["import mlflow.sklearn"]
