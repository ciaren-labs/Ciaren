"""featureImportance — extract per-feature importance from a trained model.

Reads the model reference frame (mlTrain's ``model`` output), loads the model, and
returns a ``feature_name | importance | rank`` frame. Works for tree-based models
(``feature_importances_``), linear models (``coef_``), and gradient boosting;
models without either (SVM-rbf, KNN) are rejected with a clear message.
"""
from __future__ import annotations

from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import NodeMetadata
from app.engine.transformations.ml.base import MetadataMLTransformation


class FeatureImportanceTransformation(MetadataMLTransformation):
    type = "featureImportance"
    input_handles = ("model",)

    def validate_config(self, config: dict[str, Any]) -> None:
        top_n = config.get("top_n")
        if top_n is not None and (not isinstance(top_n, int) or isinstance(top_n, bool) or top_n < 1):
            raise ValueError("featureImportance 'top_n' must be a positive integer or null.")

    def execute_with_metadata(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> tuple[dict[str, AnyFrame], NodeMetadata | None]:
        import pandas as pd

        from app.ml.loader import load_model

        ref = engine.to_pandas(inputs["model"])
        if ref.empty or "model_uri" not in ref.columns or pd.isna(ref.iloc[0]["model_uri"]):
            raise ValueError("featureImportance: the model input has no usable model_uri.")
        uri = str(ref.iloc[0]["model_uri"])
        task = ref.iloc[0]["task_type"] if "task_type" in ref.columns else None
        model = load_model(uri)

        importances = self._extract_importances(model)
        names = self._feature_names(model, len(importances))
        result = pd.DataFrame({"feature_name": names, "importance": importances})
        result = result.sort_values("importance", ascending=False).reset_index(drop=True)
        result["rank"] = result.index + 1
        top_n = config.get("top_n")
        if top_n:
            result = result.head(top_n)

        meta = NodeMetadata(model_uri=uri, task_type=task if isinstance(task, str) else None)
        return {"out": engine.from_pandas(result)}, meta

    def _estimator(self, model: Any) -> Any:
        if hasattr(model, "named_steps") and "model" in getattr(model, "named_steps", {}):
            return model.named_steps["model"]
        return model

    def _extract_importances(self, model: Any) -> Any:
        import numpy as np

        est = self._estimator(model)
        if hasattr(est, "feature_importances_"):
            return np.asarray(est.feature_importances_, dtype=float)
        if hasattr(est, "coef_"):
            coef = np.abs(np.asarray(est.coef_, dtype=float))
            return coef.mean(axis=0) if coef.ndim > 1 else coef
        raise ValueError(
            f"featureImportance does not support {type(est).__name__}: it exposes neither "
            f"feature_importances_ nor coef_ (e.g. SVM with a non-linear kernel, KNN)."
        )

    def _feature_names(self, model: Any, n: int) -> list[str]:
        # After preprocessing (e.g. one-hot), names come from the transformer.
        if hasattr(model, "named_steps") and "preprocessor" in getattr(model, "named_steps", {}):
            try:
                names = list(model[:-1].get_feature_names_out())
                if len(names) == n:
                    return [self._strip_transformer_prefix(str(x)) for x in names]
            except Exception:  # noqa: BLE001 - fall back to generic names
                pass
        for obj in (model, self._estimator(model)):
            names_in = getattr(obj, "feature_names_in_", None)
            if names_in is not None and len(names_in) == n:
                return [str(x) for x in names_in]
        return [f"feature_{i}" for i in range(n)]

    @staticmethod
    def _strip_transformer_prefix(name: str) -> str:
        """ColumnTransformer prefixes its outputs with the transformer name
        (``num__x1``, ``cat__color_r``). Strip those so importances read naturally."""
        for prefix in ("num__", "cat__", "remainder__"):
            if name.startswith(prefix):
                return name[len(prefix):]
        return name

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        dst = output_vars["out"]
        return (
            "_est = model.named_steps.get('model', model) if hasattr(model, 'named_steps') else model\n"
            "_imp = getattr(_est, 'feature_importances_', None)\n"
            "if _imp is None:\n"
            "    _imp = abs(_est.coef_).mean(axis=0) if _est.coef_.ndim > 1 else abs(_est.coef_)\n"
            f"{dst} = pd.DataFrame({{'feature_name': getattr(_est, 'feature_names_in_', range(len(_imp))), "
            f"'importance': _imp}}).sort_values('importance', ascending=False)"
        )

    def imports(self, config: dict[str, Any]) -> list[str]:
        return []
