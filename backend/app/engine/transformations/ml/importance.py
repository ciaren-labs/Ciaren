"""featureImportance — extract per-feature importance from a trained model.

Reads the model reference frame (mlTrain's ``model`` output), loads the model, and
returns a ``feature_name | importance | rank`` frame. Works for tree-based models
(``feature_importances_``), linear models (``coef_``), and gradient boosting;
models without either (SVM-rbf, KNN) are rejected with a clear message.
"""

from __future__ import annotations

from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.preview_context import in_preview
from app.engine.transformations.base import NodeMetadata
from app.engine.transformations.ml.base import MetadataMLTransformation


class FeatureImportanceTransformation(MetadataMLTransformation):
    type = "featureImportance"
    # The single input is mlTrain's "model" reference frame. Using the default
    # "in" handle keeps edge wiring conventional (no special targetHandle needed).
    input_handles = ("in",)

    def validate_config(self, config: dict[str, Any]) -> None:
        top_n = config.get("top_n")
        if top_n is not None and (not isinstance(top_n, int) or isinstance(top_n, bool) or top_n < 1):
            raise ValueError("featureImportance 'top_n' must be a positive integer or null.")

    def execute_with_metadata(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> tuple[dict[str, AnyFrame], NodeMetadata | None]:
        import pandas as pd

        # During preview we don't load the model; pass the reference frame through.
        if in_preview():
            return {"out": inputs["in"]}, None

        from app.ml.loader import load_model

        ref = engine.to_pandas(inputs["in"])
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
                return name[len(prefix) :]
        return name

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        dst = output_vars["out"]
        model_var = input_vars.get("in", "model")
        top_n = config.get("top_n")
        # Mirror execute(): pull importances from the inner estimator, then recover
        # *real* feature names from the fitted preprocessor (post one-hot names,
        # with the ColumnTransformer prefix stripped) — otherwise the exported frame
        # would label features with bare integers instead of the column names the
        # run shows. Also emit the same 'rank' column and honour top_n.
        lines = [
            f"_est = {model_var}.named_steps.get('model', {model_var}) "
            f"if hasattr({model_var}, 'named_steps') else {model_var}",
            "_imp = getattr(_est, 'feature_importances_', None)",
            "if _imp is None:",
            "    _imp = abs(_est.coef_).mean(axis=0) if _est.coef_.ndim > 1 else abs(_est.coef_)",
            f"if hasattr({model_var}, 'named_steps') and 'preprocessor' in {model_var}.named_steps:",
            f"    _raw = [str(c) for c in {model_var}[:-1].get_feature_names_out()]",
            "    _names = [next((c[len(p):] for p in ('num__', 'cat__', 'remainder__') "
            "if c.startswith(p)), c) for c in _raw]",
            "else:",
            "    _fn = getattr(_est, 'feature_names_in_', None)",
            "    _names = [str(c) for c in _fn] if _fn is not None else [f'feature_{i}' for i in range(len(_imp))]",
            f"{dst} = pd.DataFrame({{'feature_name': _names, 'importance': _imp}})"
            ".sort_values('importance', ascending=False).reset_index(drop=True)",
            f"{dst}['rank'] = {dst}.index + 1",
        ]
        if top_n:
            lines.append(f"{dst} = {dst}.head({int(top_n)})")
        return "\n".join(lines)

    def imports(self, config: dict[str, Any]) -> list[str]:
        return []
