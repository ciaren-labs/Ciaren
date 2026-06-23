"""mlEvaluate — compute evaluation metrics from a scored dataframe.

Returns a long-format frame (one row per metric) so it feeds a csvOutput or shows
in the node inspector, and surfaces the same scalars onto the NodeResult metadata
for the run's ML view.
"""
from __future__ import annotations

import logging
from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.preview_context import in_preview
from app.engine.transformations.base import NodeMetadata
from app.engine.transformations.ml.base import MetadataMLTransformation

logger = logging.getLogger(__name__)

_TASKS = {"classification", "regression", "clustering"}
_DEFAULT_METRICS = {
    "classification": ["accuracy", "precision", "recall", "f1"],
    "regression": ["rmse", "mae", "r2", "mape"],
    "clustering": ["silhouette", "davies_bouldin"],
}


class MLEvaluateTransformation(MetadataMLTransformation):
    type = "mlEvaluate"
    input_handles = ("in",)

    def validate_config(self, config: dict[str, Any]) -> None:
        task = config.get("task_type")
        if task not in _TASKS:
            raise ValueError(f"mlEvaluate 'task_type' must be one of {sorted(_TASKS)}.")
        if task in ("classification", "regression"):
            if not config.get("target_column"):
                raise ValueError("mlEvaluate requires a 'target_column'.")
            if not config.get("prediction_column"):
                raise ValueError("mlEvaluate requires a 'prediction_column'.")
        else:  # clustering
            if not config.get("prediction_column"):
                raise ValueError("mlEvaluate (clustering) requires a 'prediction_column' (the labels).")

    def execute_with_metadata(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> tuple[dict[str, AnyFrame], NodeMetadata | None]:
        import pandas as pd

        # During preview we skip metric computation; pass the input through.
        if in_preview():
            return {"out": inputs["in"]}, None

        pdf = engine.to_pandas(inputs["in"])
        task = config["task_type"]
        wanted = config.get("metrics") or _DEFAULT_METRICS[task]

        if task == "classification":
            metrics = self._classification(pdf, config, wanted)
        elif task == "regression":
            metrics = self._regression(pdf, config, wanted)
        else:
            metrics = self._clustering(pdf, config, wanted)

        long_df = pd.DataFrame(
            [{"metric": k, "value": v} for k, v in metrics.items()]
        )
        meta = NodeMetadata(ml_metrics=metrics, task_type=task)
        return {"out": engine.from_pandas(long_df)}, meta

    # -- per-task metric computation -----------------------------------------

    def _require_columns(self, pdf: Any, *columns: str) -> None:
        missing = [c for c in columns if c and c not in pdf.columns]
        if missing:
            raise ValueError(f"mlEvaluate: columns not found: {missing}. Available: {list(pdf.columns)}.")

    def _classification(self, pdf: Any, config: dict[str, Any], wanted: list[str]) -> dict[str, float]:
        from sklearn.metrics import (
            accuracy_score,
            confusion_matrix,
            f1_score,
            precision_score,
            recall_score,
            roc_auc_score,
        )

        target, pred = config["target_column"], config["prediction_column"]
        self._require_columns(pdf, target, pred)
        y_true, y_pred = pdf[target], pdf[pred]
        kw = {"average": "weighted", "zero_division": 0}
        computed = {
            "accuracy": lambda: float(accuracy_score(y_true, y_pred)),
            "precision": lambda: float(precision_score(y_true, y_pred, **kw)),
            "recall": lambda: float(recall_score(y_true, y_pred, **kw)),
            "f1": lambda: float(f1_score(y_true, y_pred, **kw)),
        }
        metrics: dict[str, float] = {m: computed[m]() for m in wanted if m in computed}

        if "roc_auc" in wanted:
            metrics.update(self._roc_auc(pdf, config, y_true, roc_auc_score))
        if "confusion_matrix" in wanted:
            cm = confusion_matrix(y_true, y_pred)
            for i, row in enumerate(cm):
                for j, count in enumerate(row):
                    metrics[f"cm_true{i}_pred{j}"] = float(count)
        return metrics

    def _roc_auc(self, pdf: Any, config: dict[str, Any], y_true: Any, roc_auc_score: Any) -> dict[str, float]:
        proba_cols = config.get("proba_columns")
        if not proba_cols:
            logger.warning("mlEvaluate: roc_auc requested but no proba_columns provided; skipping.")
            return {}
        self._require_columns(pdf, *proba_cols)
        try:
            if len(proba_cols) == 2:
                return {"roc_auc": float(roc_auc_score(y_true, pdf[proba_cols[1]]))}
            return {"roc_auc": float(roc_auc_score(y_true, pdf[proba_cols], multi_class="ovr"))}
        except ValueError as exc:
            logger.warning("mlEvaluate: roc_auc could not be computed (%s).", exc)
            return {}

    def _regression(self, pdf: Any, config: dict[str, Any], wanted: list[str]) -> dict[str, float]:
        import numpy as np
        from sklearn.metrics import (
            mean_absolute_error,
            mean_absolute_percentage_error,
            r2_score,
            root_mean_squared_error,
        )

        target, pred = config["target_column"], config["prediction_column"]
        self._require_columns(pdf, target, pred)
        y_true, y_pred = pdf[target], pdf[pred]
        computed = {
            "rmse": lambda: float(root_mean_squared_error(y_true, y_pred)),
            "mae": lambda: float(mean_absolute_error(y_true, y_pred)),
            "r2": lambda: float(r2_score(y_true, y_pred)),
            "mape": lambda: float(mean_absolute_percentage_error(y_true, y_pred)),
            "residual_std": lambda: float(np.std(y_true - y_pred)),
        }
        return {m: computed[m]() for m in wanted if m in computed}

    def _clustering(self, pdf: Any, config: dict[str, Any], wanted: list[str]) -> dict[str, float]:
        from sklearn.metrics import davies_bouldin_score, silhouette_score

        pred = config["prediction_column"]
        self._require_columns(pdf, pred)
        labels = pdf[pred]
        features = config.get("feature_columns") or [
            c for c in pdf.select_dtypes(include="number").columns if c != pred
        ]
        self._require_columns(pdf, *features)
        x = pdf[features]
        n_labels = labels.nunique()
        # silhouette/Davies-Bouldin require 2..n_samples-1 distinct clusters.
        if n_labels < 2 or n_labels >= len(labels):
            logger.warning(
                "mlEvaluate: clustering metrics need 2..n-1 clusters (got %d for %d rows).",
                n_labels, len(labels),
            )
            return {}
        computed = {
            "silhouette": lambda: float(silhouette_score(x, labels)),
            "davies_bouldin": lambda: float(davies_bouldin_score(x, labels)),
        }
        return {m: computed[m]() for m in wanted if m in computed}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        target = config.get("target_column")
        pred = config.get("prediction_column")
        if config.get("task_type") == "regression":
            return (
                f"_rmse = root_mean_squared_error({src}[{target!r}], {src}[{pred!r}])\n"
                f"{dst} = pd.DataFrame([{{'metric': 'rmse', 'value': _rmse}}])"
            )
        return (
            f"_acc = accuracy_score({src}[{target!r}], {src}[{pred!r}])\n"
            f"{dst} = pd.DataFrame([{{'metric': 'accuracy', 'value': _acc}}])"
        )

    def imports(self, config: dict[str, Any]) -> list[str]:
        if config.get("task_type") == "regression":
            return ["from sklearn.metrics import root_mean_squared_error"]
        return ["from sklearn.metrics import accuracy_score"]
