# SPDX-License-Identifier: AGPL-3.0-only
"""mlCrossValidate — estimate how well a connected model generalizes with cross-validation.

This dedicated node consumes a model reference from a train node and supports
several resampling strategies — k-fold,
stratified k-fold, shuffle-split, time-series split, group k-fold, repeated
k-fold, and leave-one-out — so the right scheme can be picked per problem
(stratify imbalanced classes, respect time order, keep groups intact, …).

It does **not** persist another model: it reconstructs the connected train node's
estimator definition, fits/scores it on each fold
and returns a tidy ``fold | <metric> …`` frame (one row per fold) so the scores
feed an output node or show in the inspector. The per-fold scores for the primary
metric plus the mean/std land on the NodeResult metadata (``cv_scores`` and the
``cv_*`` entries in ``ml_metrics``) for the run's ML view.

Preprocessing (imputation / scaling / one-hot) is bundled into the pipeline via
:class:`SklearnPipelineMixin`, so it is refit *inside* every fold — no leakage
from fitting on the held-out data.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import get_settings
from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.preview_context import in_preview
from app.engine.transformations.base import NodeMetadata
from app.engine.transformations.ml.base import (
    MetadataMLTransformation,
    MLSchema,
    SklearnPipelineMixin,
)
from app.ml.models import CLASSIFICATION, REGRESSION, get_model_spec

logger = logging.getLogger(__name__)

MIN_ROWS = 10

#: CV strategy -> human label (mirrors the frontend picker).
CV_STRATEGIES: dict[str, str] = {
    "kfold": "K-Fold",
    "stratified_kfold": "Stratified K-Fold",
    "shuffle_split": "Shuffle Split",
    "stratified_shuffle_split": "Stratified Shuffle Split",
    "group_kfold": "Group K-Fold",
    "time_series_split": "Time Series Split",
    "repeated_kfold": "Repeated K-Fold",
    "leave_one_out": "Leave-One-Out",
}

#: Strategies that need a discrete (classification) target to stratify on.
_STRATIFIED = {"stratified_kfold", "stratified_shuffle_split"}
#: Strategies whose split size is driven by ``test_size`` rather than ``n_splits`` folds.
_SHUFFLE = {"shuffle_split", "stratified_shuffle_split"}

#: Allowed scoring metrics per task. Restricted to a known set so an arbitrary
#: string can never reach sklearn's scorer lookup. ``neg_*`` scores are negated
#: and renamed (dropping ``neg_``) for the report so e.g. RMSE reads positive.
_SCORING: dict[str, tuple[str, ...]] = {
    CLASSIFICATION: (
        "accuracy",
        "balanced_accuracy",
        "f1_weighted",
        "f1_macro",
        "precision_weighted",
        "recall_weighted",
        "roc_auc",
    ),
    REGRESSION: (
        "r2",
        "neg_root_mean_squared_error",
        "neg_mean_absolute_error",
        "neg_mean_squared_error",
        "neg_mean_absolute_percentage_error",
    ),
}
_DEFAULT_SCORING: dict[str, tuple[str, ...]] = {
    CLASSIFICATION: ("accuracy", "f1_weighted"),
    REGRESSION: ("r2", "neg_root_mean_squared_error"),
}

#: sklearn splitter class for each strategy (for codegen imports).
_SPLITTER_CLASSES: dict[str, str] = {
    "kfold": "KFold",
    "stratified_kfold": "StratifiedKFold",
    "shuffle_split": "ShuffleSplit",
    "stratified_shuffle_split": "StratifiedShuffleSplit",
    "group_kfold": "GroupKFold",
    "time_series_split": "TimeSeriesSplit",
    "repeated_kfold": "RepeatedKFold",
    "leave_one_out": "LeaveOneOut",
}


def _friendly_metric(scoring: str) -> str:
    """Report-friendly column name: drop sklearn's ``neg_`` prefix."""
    return scoring[4:] if scoring.startswith("neg_") else scoring


class CrossValidateTransformation(SklearnPipelineMixin, MetadataMLTransformation):
    type = "mlCrossValidate"
    input_handles = ("in", "model")

    # -- validation ----------------------------------------------------------

    def validate_config(self, config: dict[str, Any]) -> None:
        nm = self.type
        seed = config.get("seed")
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError(f"{nm} requires an integer 'seed' for reproducibility.")

        strategy = config.get("cv_strategy", "kfold")
        if strategy not in CV_STRATEGIES:
            raise ValueError(f"{nm} 'cv_strategy' must be one of {sorted(CV_STRATEGIES)}.")
        if strategy != "leave_one_out":
            folds = config.get("n_splits", 5)
            if not isinstance(folds, int) or isinstance(folds, bool) or folds < 2:
                raise ValueError(f"{nm} 'n_splits' must be an integer >= 2.")
        if strategy == "repeated_kfold":
            repeats = config.get("n_repeats", 1)
            if not isinstance(repeats, int) or isinstance(repeats, bool) or repeats < 1:
                raise ValueError(f"{nm} 'n_repeats' must be an integer >= 1.")
        if strategy in _SHUFFLE:
            test_size = config.get("test_size", 0.2)
            if not isinstance(test_size, (int, float)) or isinstance(test_size, bool) or not (0.0 < test_size < 1.0):
                raise ValueError(f"{nm} 'test_size' must be a number strictly between 0 and 1.")
        if strategy == "group_kfold":
            group = config.get("group_column")
            if not isinstance(group, str) or not group:
                raise ValueError(f"{nm}: Group K-Fold needs a 'group_column' to keep each group within one fold.")

        scoring = config.get("scoring")
        if scoring is not None:
            if not isinstance(scoring, list) or not all(isinstance(s, str) for s in scoring):
                raise ValueError(f"{nm} 'scoring' must be a list of metric names.")
            allowed = set(_SCORING[CLASSIFICATION]) | set(_SCORING[REGRESSION])
            bad = [s for s in scoring if s not in allowed]
            if bad:
                raise ValueError(f"{nm}: unsupported scoring {bad}. Allowed: {sorted(allowed)}.")

    def validate_with_schema(self, config: dict[str, Any], schema: MLSchema) -> None:
        nm = self.type
        settings = get_settings()
        group = config.get("group_column")
        if config.get("cv_strategy") == "group_kfold" and group and group not in schema.columns:
            raise ValueError(f"{nm}: group_column {group!r} not in input columns {schema.columns}.")
        if schema.row_count is not None:
            if schema.row_count > settings.ML_MAX_TRAINING_ROWS:
                raise ValueError(
                    f"{nm}: {schema.row_count} rows exceeds the training limit of "
                    f"{settings.ML_MAX_TRAINING_ROWS} (ML_MAX_TRAINING_ROWS)."
                )
            if schema.row_count < MIN_ROWS:
                raise ValueError(f"{nm}: need at least {MIN_ROWS} rows to cross-validate (got {schema.row_count}).")
            self._check_folds_fit_rows(config, schema.row_count)

    def _check_folds_fit_rows(self, config: dict[str, Any], n: int) -> None:
        strategy = config.get("cv_strategy", "kfold")
        if strategy in _SHUFFLE or strategy == "leave_one_out":
            return
        folds = int(config.get("n_splits", 5))
        if folds > n:
            raise ValueError(f"{self.type}: cannot run {folds}-fold CV with only {n} rows.")

    # -- execution -----------------------------------------------------------

    def execute_with_metadata(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> tuple[dict[str, AnyFrame], NodeMetadata | None]:
        import pandas as pd

        model_config = self._model_config_from_input(engine, inputs)
        spec = get_model_spec(model_config["model_type"])
        if not spec.supervised or spec.task not in (CLASSIFICATION, REGRESSION):
            raise ValueError(
                f"{self.type}: connected model {model_config['model_type']!r} is a {spec.task} model; "
                "cross-validation supports classification and regression models only."
            )
        strategy_name = config.get("cv_strategy", "kfold")
        if strategy_name in _STRATIFIED and spec.task != CLASSIFICATION:
            raise ValueError(
                f"{self.type}: {CV_STRATEGIES[strategy_name]} stratifies on class labels and "
                "needs a classification model."
            )
        # During preview we don't fit anything — hand back an empty scores frame so
        # the graph still resolves and downstream column inference has a shape.
        if in_preview():
            scoring = self._resolve_scoring(config, spec.task)
            cols = ["fold", *[_friendly_metric(s) for s in scoring]]
            return {"out": engine.from_pandas(pd.DataFrame(columns=cols))}, NodeMetadata(task_type=spec.task)

        settings = get_settings()
        pdf = engine.to_pandas(inputs["in"])
        n = len(pdf)
        if n < MIN_ROWS:
            raise ValueError(f"{self.type}: need at least {MIN_ROWS} rows to cross-validate (got {n}).")
        if n > settings.ML_MAX_TRAINING_ROWS:
            raise ValueError(f"{self.type}: {n} rows exceeds ML_MAX_TRAINING_ROWS ({settings.ML_MAX_TRAINING_ROWS}).")
        self._check_folds_fit_rows(config, n)

        target = model_config.get("target_column")
        if not isinstance(target, str) or not target:
            raise ValueError(f"{self.type}: connected model is missing a target_column.")
        if target not in pdf.columns:
            raise ValueError(f"{self.type}: target_column {target!r} not found.")
        features = self._resolve_features(model_config, list(pdf.columns), spec.supervised, target)
        missing = [c for c in features if c not in pdf.columns]
        if missing:
            raise ValueError(f"{self.type}: feature columns not found: {missing}.")
        if target in features:
            raise ValueError(f"{self.type}: target_column {target!r} is in feature_columns — data leakage.")
        if len(features) > settings.ML_MAX_FEATURE_COLUMNS:
            raise ValueError(
                f"{self.type}: {len(features)} feature columns exceeds ML_MAX_FEATURE_COLUMNS "
                f"({settings.ML_MAX_FEATURE_COLUMNS})."
            )

        x = pdf[features]
        y = pdf[target]
        scoring = self._resolve_scoring(config, spec.task)
        splitter, groups = self._build_splitter(config, pdf, n)
        pipeline = self._build_pipeline(model_config, features, pdf, spec, int(model_config.get("seed") or 0))

        frame, metadata = self._run_cv(pipeline, x, y, splitter, groups, scoring, spec.task)
        return {"out": engine.from_pandas(frame)}, metadata

    def _model_config_from_input(self, engine: EngineBackend, inputs: dict[str, AnyFrame]) -> dict[str, Any]:
        import pandas as pd

        if "model" not in inputs:
            raise ValueError(f"{self.type}: connect a Train Model node to the 'model' input.")
        ref = engine.to_pandas(inputs["model"])
        if ref.empty:
            raise ValueError(f"{self.type}: model input is empty.")
        row = ref.iloc[0]
        raw = row.get("model_config_json") if isinstance(row, pd.Series) else None
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(
                f"{self.type}: connected model reference has no model_config_json. "
                "Re-run the upstream Train node with the current Ciaren version."
            )
        try:
            cfg = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{self.type}: connected model_config_json is invalid JSON.") from exc
        if not isinstance(cfg, dict) or not isinstance(cfg.get("model_type"), str):
            raise ValueError(f"{self.type}: connected model reference is missing model_type.")
        return cfg

    def _resolve_scoring(self, config: dict[str, Any], task: str) -> list[str]:
        chosen = config.get("scoring")
        if chosen:
            bad = [s for s in chosen if s not in _SCORING[task]]
            if bad:
                raise ValueError(f"{self.type}: scoring {bad} is not valid for a {task} model.")
            return list(chosen)
        return list(_DEFAULT_SCORING[task])

    def _build_splitter(self, config: dict[str, Any], pdf: Any, n: int) -> tuple[Any, Any]:
        """Construct the sklearn CV splitter (and the groups array, if any)."""
        from sklearn import model_selection as ms

        strategy = config.get("cv_strategy", "kfold")
        n_splits = int(config.get("n_splits", 5))
        seed = config["seed"]
        shuffle = bool(config.get("shuffle", True))
        test_size = config.get("test_size", 0.2)

        if strategy == "kfold":
            return ms.KFold(n_splits=n_splits, shuffle=shuffle, random_state=seed if shuffle else None), None
        if strategy == "stratified_kfold":
            return ms.StratifiedKFold(n_splits=n_splits, shuffle=shuffle, random_state=seed if shuffle else None), None
        if strategy == "shuffle_split":
            return ms.ShuffleSplit(n_splits=n_splits, test_size=test_size, random_state=seed), None
        if strategy == "stratified_shuffle_split":
            return ms.StratifiedShuffleSplit(n_splits=n_splits, test_size=test_size, random_state=seed), None
        if strategy == "group_kfold":
            group_col = config["group_column"]
            if group_col not in pdf.columns:
                raise ValueError(f"{self.type}: group_column {group_col!r} not found.")
            return ms.GroupKFold(n_splits=n_splits), pdf[group_col]
        if strategy == "time_series_split":
            return ms.TimeSeriesSplit(n_splits=n_splits), None
        if strategy == "repeated_kfold":
            repeats = int(config.get("n_repeats", 1))
            return ms.RepeatedKFold(n_splits=n_splits, n_repeats=repeats, random_state=seed), None
        # leave_one_out
        if n > 200:
            logger.warning("%s: Leave-One-Out fits %d models — this can be slow on larger data.", self.type, n)
        return ms.LeaveOneOut(), None

    def _run_cv(
        self, pipeline: Any, x: Any, y: Any, splitter: Any, groups: Any, scoring: list[str], task: str
    ) -> tuple[Any, NodeMetadata]:
        import numpy as np
        import pandas as pd
        from sklearn.model_selection import cross_validate

        results = cross_validate(pipeline, x, y, cv=splitter, scoring=scoring, groups=groups, return_train_score=False)

        # One row per fold; negate sklearn's neg_* scores and drop the prefix so the
        # report reads naturally (e.g. RMSE as a positive number).
        n_folds = len(results["fit_time"])
        rows: list[dict[str, float]] = []
        for i in range(n_folds):
            row: dict[str, float] = {"fold": float(i + 1)}
            for metric in scoring:
                value = float(results[f"test_{metric}"][i])
                row[_friendly_metric(metric)] = -value if metric.startswith("neg_") else value
            row["fit_time_s"] = float(results["fit_time"][i])
            rows.append(row)
        frame = pd.DataFrame(rows)

        # Surface aggregate scores onto the run's ML metadata. The first scoring
        # metric is the "primary" one shown as cv_mean / cv_scores.
        ml_metrics: dict[str, float] = {}
        primary = _friendly_metric(scoring[0])
        for metric in scoring:
            friendly = _friendly_metric(metric)
            values = frame[friendly].to_numpy(dtype=float)
            ml_metrics[f"cv_{friendly}_mean"] = float(np.mean(values))
            ml_metrics[f"cv_{friendly}_std"] = float(np.std(values))
        ml_metrics["cv_mean"] = ml_metrics[f"cv_{primary}_mean"]
        ml_metrics["cv_std"] = ml_metrics[f"cv_{primary}_std"]
        cv_scores = [float(v) for v in frame[primary].to_numpy(dtype=float)]

        meta = NodeMetadata(ml_metrics=ml_metrics, task_type=task, cv_scores=cv_scores)
        return frame, meta

    # -- code export ---------------------------------------------------------

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src = input_vars["in"]
        model_ref = input_vars["model"]
        dst = output_vars["out"]
        chosen_scoring = config.get("scoring") or []

        lines = [
            f"_model_ref = {model_ref}.iloc[0]",
            "_model_config = json.loads(_model_ref['model_config_json'])",
            "_task = _model_ref.get('task_type')",
            "_target = _model_config['target_column']",
            f"_features = _model_config.get('feature_columns') or [c for c in {src}.columns if c != _target]",
            f"_X = {src}[_features]",
            f"_y = {src}[_target]",
            "_pre = _model_config.get('preprocessing') or {}",
            "if 'numeric_columns' in _pre:",
            "    _numeric = _pre.get('numeric_columns')",
            "else:",
            "    _numeric = [c for c in _features if pd.api.types.is_numeric_dtype(_X[c])]",
            "if 'categorical_columns' in _pre:",
            "    _categorical = _pre.get('categorical_columns')",
            "else:",
            "    _categorical = [c for c in _features if c not in _numeric]",
            "_num_strategy = _pre.get('numeric_strategy', 'standard_scaler')",
            "_scalers = {",
            "    'standard_scaler': StandardScaler,",
            "    'minmax_scaler': MinMaxScaler,",
            "    'robust_scaler': RobustScaler,",
            "}",
            "_transformers = []",
            "if _numeric:",
            "    _num_steps = [('impute', SimpleImputer(strategy=_pre.get('impute_numeric', 'median')))]",
            "    if _num_strategy in _scalers:",
            "        _num_steps.append(('scale', _scalers[_num_strategy]()))",
            "    _transformers.append(('num', Pipeline(_num_steps), _numeric))",
            "if _categorical:",
            "    _cat_steps = [",
            "        ('impute', SimpleImputer(strategy=_pre.get('impute_categorical', 'most_frequent'))),",
            "        ('encode', OneHotEncoder(handle_unknown='ignore')),",
            "    ]",
            "    _transformers.append(('cat', Pipeline(_cat_steps), _categorical))",
            "_steps = []",
            "if _transformers:",
            "    _steps.append(('preprocessor', ColumnTransformer(_transformers, remainder='drop')))",
            "_estimator = build_estimator(",
            "    _model_config['model_type'],",
            "    _model_config.get('hyperparameters'),",
            "    _model_config.get('seed'),",
            ")",
            "_steps.append(('model', _estimator))",
            "_pipeline = Pipeline(_steps)",
        ]

        splitter_expr, group_col = self._splitter_code(config)
        lines.append(f"_cv = {splitter_expr}")
        lines.append(f"_scoring = {chosen_scoring!r}")
        lines.append("if not _scoring:")
        lines.append("    if _task == 'classification':")
        lines.append("        _scoring = ['accuracy', 'f1_weighted']")
        lines.append("    else:")
        lines.append("        _scoring = ['r2', 'neg_root_mean_squared_error']")
        groups_arg = f", groups={src}[{group_col!r}]" if group_col else ""
        lines.append(
            f"_scores = cross_validate(_pipeline, _X, _y, cv=_cv, "
            f"scoring=_scoring{groups_arg}, return_train_score=False)"
        )
        # Build a tidy fold-by-metric frame, mirroring execute(): negate neg_* and
        # drop the prefix so e.g. RMSE reads positive.
        lines += [
            "_rows = []",
            "_n_folds = len(_scores['fit_time'])",
            "for _i in range(_n_folds):",
            "    _row = {'fold': _i + 1}",
            "    for _m in _scoring:",
            "        _v = _scores['test_' + _m][_i]",
            "        _row[_m[4:] if _m.startswith('neg_') else _m] = -_v if _m.startswith('neg_') else _v",
            "    _rows.append(_row)",
            f"{dst} = pd.DataFrame(_rows)",
        ]
        return "\n".join(lines)

    def _splitter_code(self, config: dict[str, Any]) -> tuple[str, str | None]:
        strategy = config.get("cv_strategy", "kfold")
        n_splits = int(config.get("n_splits", 5))
        seed = config["seed"]
        shuffle = bool(config.get("shuffle", True))
        test_size = config.get("test_size", 0.2)
        rs = seed if shuffle else None
        if strategy == "kfold":
            return f"KFold(n_splits={n_splits}, shuffle={shuffle!r}, random_state={rs!r})", None
        if strategy == "stratified_kfold":
            return f"StratifiedKFold(n_splits={n_splits}, shuffle={shuffle!r}, random_state={rs!r})", None
        if strategy == "shuffle_split":
            return f"ShuffleSplit(n_splits={n_splits}, test_size={test_size!r}, random_state={seed!r})", None
        if strategy == "stratified_shuffle_split":
            return f"StratifiedShuffleSplit(n_splits={n_splits}, test_size={test_size!r}, random_state={seed!r})", None
        if strategy == "group_kfold":
            return f"GroupKFold(n_splits={n_splits})", config["group_column"]
        if strategy == "time_series_split":
            return f"TimeSeriesSplit(n_splits={n_splits})", None
        if strategy == "repeated_kfold":
            return (
                f"RepeatedKFold(n_splits={n_splits}, n_repeats={int(config.get('n_repeats', 1))}, "
                f"random_state={seed!r})",
                None,
            )
        return "LeaveOneOut()", None

    def imports(self, config: dict[str, Any]) -> list[str]:
        strategy = config.get("cv_strategy", "kfold")
        splitter = _SPLITTER_CLASSES.get(strategy, "KFold")
        return [
            "import json",
            "from app.ml.models import build_estimator",
            "from sklearn.compose import ColumnTransformer",
            "from sklearn.impute import SimpleImputer",
            "from sklearn.pipeline import Pipeline",
            "from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, RobustScaler, StandardScaler",
            f"from sklearn.model_selection import cross_validate, {splitter}",
        ]
