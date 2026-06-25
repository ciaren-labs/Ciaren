"""Feature-engineering ML nodes: scaleFeatures, encodeCategories,
selectFeatures, reduceDimensions.

(Missing-value imputation lives in the Fill Nulls cleaning node, which covers
mean/median/mode/constant fills on both engines — see app/engine/transformations/nulls.py.)

These are pure dataframe -> dataframe transforms. They are **stateless in the
graph**: each refits on whatever frame arrives, which is correct for exploration
and preview. For training, the fitted state must travel with the model — mlTrain
bundles equivalent preprocessing into the sklearn Pipeline so the exact same
transform is reapplied at predict time (see docs/ml-architecture.md §3.2 / §3.4).
"""

from __future__ import annotations

import logging
from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.ml.base import MLSchema, MLTransformation

logger = logging.getLogger(__name__)


def _require_columns(config: dict[str, Any], node: str) -> list[str]:
    cols = config.get("columns")
    if not isinstance(cols, list) or not cols or not all(isinstance(c, str) for c in cols):
        raise ValueError(f"{node} requires a non-empty 'columns' list of column names.")
    return cols


def _check_present(columns: list[str], available: list[str], node: str) -> None:
    missing = [c for c in columns if c not in available]
    if missing:
        raise ValueError(f"{node}: columns not found in input: {missing}. Available: {available}.")


# -- scaleFeatures ----------------------------------------------------------

_SCALERS = {
    "standard": ("StandardScaler", "StandardScaler()"),
    "minmax": ("MinMaxScaler", "MinMaxScaler()"),
    "robust": ("RobustScaler", "RobustScaler()"),
}


class ScaleFeaturesTransformation(MLTransformation):
    type = "scaleFeatures"

    def validate_config(self, config: dict[str, Any]) -> None:
        _require_columns(config, "scaleFeatures")
        method = config.get("method", "standard")
        if method not in _SCALERS:
            raise ValueError(f"scaleFeatures 'method' must be one of {sorted(_SCALERS)}.")

    def validate_with_schema(self, config: dict[str, Any], schema: MLSchema) -> None:
        _check_present(config["columns"], schema.columns, "scaleFeatures")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler

        scalers = {"standard": StandardScaler, "minmax": MinMaxScaler, "robust": RobustScaler}
        columns = config["columns"]
        pdf = engine.to_pandas(inputs["in"]).copy()
        _check_present(columns, list(pdf.columns), "scaleFeatures")
        scaler = scalers[config.get("method", "standard")]()
        pdf[columns] = scaler.fit_transform(pdf[columns])
        return {"out": engine.from_pandas(pdf)}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        cols = config["columns"]
        _, ctor = _SCALERS[config.get("method", "standard")]
        return f"{dst} = {src}.copy()\n{dst}[{cols!r}] = {ctor}.fit_transform({dst}[{cols!r}])"

    def imports(self, config: dict[str, Any]) -> list[str]:
        return [f"from sklearn.preprocessing import {_SCALERS[config.get('method', 'standard')][0]}"]


# -- encodeCategories -------------------------------------------------------


class EncodeCategoriesTransformation(MLTransformation):
    type = "encodeCategories"

    def validate_config(self, config: dict[str, Any]) -> None:
        _require_columns(config, "encodeCategories")
        method = config.get("method", "onehot")
        if method not in {"onehot", "ordinal"}:
            raise ValueError("encodeCategories 'method' must be 'onehot' or 'ordinal'.")

    def validate_with_schema(self, config: dict[str, Any], schema: MLSchema) -> None:
        _check_present(config["columns"], schema.columns, "encodeCategories")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        import pandas as pd

        columns = config["columns"]
        method = config.get("method", "onehot")
        pdf = engine.to_pandas(inputs["in"])
        _check_present(columns, list(pdf.columns), "encodeCategories")
        if method == "onehot":
            result = pd.get_dummies(pdf, columns=columns, drop_first=bool(config.get("drop_first", False)))
        else:
            from sklearn.preprocessing import OrdinalEncoder

            result = pdf.copy()
            enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
            result[columns] = enc.fit_transform(result[columns].astype(str))
        return {"out": engine.from_pandas(result)}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        cols = config["columns"]
        if config.get("method", "onehot") == "onehot":
            drop_first = bool(config.get("drop_first", False))
            return f"{dst} = pd.get_dummies({src}, columns={cols!r}, drop_first={drop_first!r})"
        return (
            f"{dst} = {src}.copy()\n"
            f"{dst}[{cols!r}] = OrdinalEncoder(handle_unknown='use_encoded_value', "
            f"unknown_value=-1).fit_transform({dst}[{cols!r}].astype(str))"
        )

    def imports(self, config: dict[str, Any]) -> list[str]:
        # onehot uses pd.get_dummies (no import); ordinal needs the sklearn encoder.
        if config.get("method", "onehot") == "ordinal":
            return ["from sklearn.preprocessing import OrdinalEncoder"]
        return []


# -- selectFeatures ---------------------------------------------------------


class SelectFeaturesTransformation(MLTransformation):
    type = "selectFeatures"

    def validate_config(self, config: dict[str, Any]) -> None:
        method = config.get("method", "variance")
        if method not in {"variance", "correlation", "kbest"}:
            raise ValueError("selectFeatures 'method' must be 'variance', 'correlation', or 'kbest'.")
        if method == "kbest":
            if not config.get("target_column"):
                raise ValueError("selectFeatures 'kbest' requires a 'target_column'.")
            k = config.get("k")
            if not isinstance(k, int) or isinstance(k, bool) or k < 1:
                raise ValueError("selectFeatures 'kbest' requires a positive integer 'k'.")
        else:
            threshold = config.get("threshold", 0.0 if method == "variance" else 0.9)
            if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
                raise ValueError("selectFeatures 'threshold' must be a number.")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        method = config.get("method", "variance")
        pdf = engine.to_pandas(inputs["in"])
        if method == "variance":
            result = self._variance(pdf, float(config.get("threshold", 0.0)))
        elif method == "correlation":
            result = self._correlation(pdf, float(config.get("threshold", 0.9)))
        else:
            result = self._kbest(pdf, config["target_column"], int(config["k"]))
        return {"out": engine.from_pandas(result)}

    def _numeric(self, pdf: Any) -> list[str]:
        return list(pdf.select_dtypes(include="number").columns)

    def _variance(self, pdf: Any, threshold: float) -> Any:
        from sklearn.feature_selection import VarianceThreshold

        numeric = self._numeric(pdf)
        if not numeric:
            return pdf
        selector = VarianceThreshold(threshold=threshold)
        selector.fit(pdf[numeric])
        dropped = [c for c, keep in zip(numeric, selector.get_support()) if not keep]
        return pdf.drop(columns=dropped)

    def _correlation(self, pdf: Any, threshold: float) -> Any:
        import numpy as np

        numeric = self._numeric(pdf)
        if len(numeric) < 2:
            return pdf
        corr = pdf[numeric].corr().abs()
        upper = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1))
        to_drop = [c for c in upper.columns if (upper[c] > threshold).any()]
        return pdf.drop(columns=to_drop)

    def _kbest(self, pdf: Any, target: str, k: int) -> Any:
        from sklearn.feature_selection import SelectKBest, f_classif, f_regression

        if target not in pdf.columns:
            raise ValueError(f"selectFeatures: target column {target!r} not found.")
        features = [c for c in self._numeric(pdf) if c != target]
        if not features:
            raise ValueError("selectFeatures kbest: no numeric feature columns to select from.")
        x = pdf[features]
        y = pdf[target]
        scorer = f_regression if self._is_regression(y) else f_classif
        selector = SelectKBest(scorer, k=min(k, len(features)))
        selector.fit(x, y)
        kept = [c for c, keep in zip(features, selector.get_support()) if keep]
        # Preserve original column order; keep non-feature columns + the target.
        keep_set = set(kept) | {target} | (set(pdf.columns) - set(features))
        return pdf[[c for c in pdf.columns if c in keep_set]]

    # A numeric target with more distinct values than this is treated as a
    # regression target (f_regression); otherwise classification (f_classif).
    _REGRESSION_NUNIQUE_THRESHOLD = 20

    @classmethod
    def _is_regression(cls, y: Any) -> bool:
        import pandas as pd

        return bool(pd.api.types.is_numeric_dtype(y) and y.nunique() > cls._REGRESSION_NUNIQUE_THRESHOLD)

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        method = config.get("method", "variance")
        if method == "variance":
            threshold = float(config.get("threshold", 0.0))
            return (
                f"_num = {src}.select_dtypes(include='number')\n"
                f"_sel = VarianceThreshold(threshold={threshold!r}).fit(_num)\n"
                f"_drop = [c for c, k in zip(_num.columns, _sel.get_support()) if not k]\n"
                f"{dst} = {src}.drop(columns=_drop)"
            )
        if method == "correlation":
            threshold = float(config.get("threshold", 0.9))
            return (
                f"_num = {src}.select_dtypes(include='number')\n"
                f"_corr = _num.corr().abs()\n"
                f"_upper = _corr.where(np.triu(np.ones(_corr.shape, dtype=bool), k=1))\n"
                f"_drop = [c for c in _upper.columns if (_upper[c] > {threshold!r}).any()]\n"
                f"{dst} = {src}.drop(columns=_drop)"
            )
        target, k = config["target_column"], int(config["k"])
        thresh = self._REGRESSION_NUNIQUE_THRESHOLD
        # Mirror execute(): pick the scorer by target dtype, and keep every
        # non-feature column (ids, strings, the target) — only the unselected
        # numeric features are dropped.
        return (
            f"_features = [c for c in {src}.select_dtypes(include='number').columns if c != {target!r}]\n"
            f"_scorer = f_regression if (pd.api.types.is_numeric_dtype({src}[{target!r}]) "
            f"and {src}[{target!r}].nunique() > {thresh}) else f_classif\n"
            f"_sel = SelectKBest(_scorer, k=min({k!r}, len(_features))).fit({src}[_features], {src}[{target!r}])\n"
            f"_kept = [c for c, kp in zip(_features, _sel.get_support()) if kp]\n"
            f"{dst} = {src}.drop(columns=[c for c in _features if c not in _kept])"
        )

    def imports(self, config: dict[str, Any]) -> list[str]:
        method = config.get("method", "variance")
        if method == "variance":
            return ["from sklearn.feature_selection import VarianceThreshold"]
        if method == "correlation":
            return ["import numpy as np"]
        return ["from sklearn.feature_selection import SelectKBest, f_classif, f_regression"]


# -- reduceDimensions (PCA transform) ---------------------------------------


class ReduceDimensionsTransformation(MLTransformation):
    type = "reduceDimensions"

    def validate_config(self, config: dict[str, Any]) -> None:
        method = config.get("method", "pca")
        if method != "pca":
            raise ValueError("reduceDimensions only supports method 'pca' in v1.")
        n = config.get("n_components")
        valid_int = isinstance(n, int) and not isinstance(n, bool) and n >= 1
        valid_frac = isinstance(n, float) and 0.0 < n < 1.0
        if not (valid_int or valid_frac):
            raise ValueError(
                "reduceDimensions 'n_components' must be a positive integer (component count) "
                "or a float in (0, 1) (explained-variance fraction)."
            )

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        import pandas as pd
        from sklearn.decomposition import PCA

        pdf = engine.to_pandas(inputs["in"])
        columns = config.get("columns") or list(pdf.select_dtypes(include="number").columns)
        _check_present(columns, list(pdf.columns), "reduceDimensions")
        prefix = config.get("prefix", "pc")
        n = config["n_components"]
        if isinstance(n, int):
            capped = min(n, len(columns), len(pdf))
            if capped < n:
                logger.info("reduceDimensions: capping n_components from %s to %s.", n, capped)
            n = capped
        pca = PCA(n_components=n, random_state=config.get("seed"))
        components = pca.fit_transform(pdf[columns])
        names = [f"{prefix}_{i + 1}" for i in range(components.shape[1])]
        comp_df = pd.DataFrame(components, columns=names, index=pdf.index)
        others = pdf.drop(columns=columns)
        result = pd.concat([others, comp_df], axis=1)
        return {"out": engine.from_pandas(result)}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        prefix = config.get("prefix", "pc")
        n = config["n_components"]
        cols_expr = (
            repr(config["columns"]) if config.get("columns") else f"list({src}.select_dtypes(include='number').columns)"
        )
        # Mirror execute(): an integer component count is capped to the number of
        # features and rows so the exported script doesn't crash when n_components
        # exceeds them (a variance fraction in (0, 1) is passed through untouched).
        n_expr = f"min({n!r}, len(_cols), len({src}))" if isinstance(n, int) else f"{n!r}"
        return (
            f"_cols = {cols_expr}\n"
            f"_pca = PCA(n_components={n_expr}, random_state={config.get('seed')!r})\n"
            f"_comp = _pca.fit_transform({src}[_cols])\n"
            f"_names = [f'{prefix}_{{i + 1}}' for i in range(_comp.shape[1])]\n"
            f"{dst} = pd.concat([{src}.drop(columns=_cols), "
            f"pd.DataFrame(_comp, columns=_names, index={src}.index)], axis=1)"
        )

    def imports(self, config: dict[str, Any]) -> list[str]:
        return ["from sklearn.decomposition import PCA"]
