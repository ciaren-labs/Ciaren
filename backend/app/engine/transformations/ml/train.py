"""mlTrain — fit a model and log it to MLflow.

The central ML node. It bundles preprocessing INTO an sklearn ``Pipeline`` so the
exact transforms used at fit time are reapplied at predict time (no train/serve
skew, no leakage from upstream nodes fitting on the full dataset). It emits two
outputs — ``out`` (the training frame, passed through) and ``model`` (a one-row
reference frame with the MLflow run id / model URI / task) — plus run metadata
(metrics, cv scores) onto its NodeResult.
"""
from __future__ import annotations

import io
import json
import logging
from typing import Any

from app.core.config import get_settings
from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.preview_context import in_preview
from app.engine.transformations.base import NodeMetadata
from app.engine.transformations.ml.base import MetadataMLTransformation, MLSchema
from app.ml.models import CLASSIFICATION, build_estimator, get_model_spec

logger = logging.getLogger(__name__)

MIN_TRAIN_ROWS = 10
SMALL_TRAIN_ROWS = 50  # warn below this


class MLTrainTransformation(MetadataMLTransformation):
    type = "mlTrain"
    input_handles = ("in",)

    # -- validation ----------------------------------------------------------

    def validate_config(self, config: dict[str, Any]) -> None:
        seed = config.get("seed")
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError("mlTrain requires an integer 'seed' for reproducibility.")
        model_type = config.get("model_type")
        if not isinstance(model_type, str) or not model_type:
            raise ValueError("mlTrain requires a 'model_type'.")
        spec = get_model_spec(model_type)  # raises with the supported list if unknown

        if spec.supervised:
            target = config.get("target_column")
            if not isinstance(target, str) or not target:
                raise ValueError(f"mlTrain: model_type {model_type!r} is supervised and needs a 'target_column'.")
            features = config.get("feature_columns")
            if features is not None:
                if not isinstance(features, list) or not all(isinstance(c, str) for c in features):
                    raise ValueError("mlTrain 'feature_columns' must be a list of column names.")
                if target in features:
                    raise ValueError(
                        f"mlTrain: target_column {target!r} is also in feature_columns — data leakage."
                    )
        if config.get("cross_validate"):
            folds = config.get("cv_folds", 5)
            if not isinstance(folds, int) or isinstance(folds, bool) or folds < 2:
                raise ValueError("mlTrain 'cv_folds' must be an integer >= 2 when cross_validate is on.")

    def validate_with_schema(self, config: dict[str, Any], schema: MLSchema) -> None:
        settings = get_settings()
        spec = get_model_spec(config["model_type"])
        target = config.get("target_column")
        if spec.supervised and target and target not in schema.columns:
            raise ValueError(f"mlTrain: target_column {target!r} not in input columns {schema.columns}.")
        features = self._resolve_features(config, schema.columns, spec.supervised, target)
        missing = [c for c in features if c not in schema.columns]
        if missing:
            raise ValueError(f"mlTrain: feature columns not found: {missing}.")
        if len(features) > settings.ML_MAX_FEATURE_COLUMNS:
            raise ValueError(
                f"mlTrain: {len(features)} feature columns exceeds the limit of "
                f"{settings.ML_MAX_FEATURE_COLUMNS} (ML_MAX_FEATURE_COLUMNS)."
            )
        if schema.row_count is not None:
            if schema.row_count > settings.ML_MAX_TRAINING_ROWS:
                raise ValueError(
                    f"mlTrain: {schema.row_count} rows exceeds the training limit of "
                    f"{settings.ML_MAX_TRAINING_ROWS} (ML_MAX_TRAINING_ROWS)."
                )
            if schema.row_count < MIN_TRAIN_ROWS:
                raise ValueError(f"mlTrain: need at least {MIN_TRAIN_ROWS} rows to train (got {schema.row_count}).")

    # -- execution -----------------------------------------------------------

    def execute_with_metadata(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> tuple[dict[str, AnyFrame], NodeMetadata | None]:
        import pandas as pd

        spec = get_model_spec(config["model_type"])
        # During preview we must not fit a model or create an MLflow run: pass the
        # training frame through and hand downstream a placeholder model reference.
        if in_preview():
            placeholder = pd.DataFrame([{"mlflow_run_id": None, "model_uri": None, "task_type": spec.task}])
            return (
                {"out": inputs["in"], "model": engine.from_pandas(placeholder)},
                NodeMetadata(task_type=spec.task),
            )

        settings = get_settings()
        seed = config["seed"]
        pdf = engine.to_pandas(inputs["in"])

        n = len(pdf)
        if n < MIN_TRAIN_ROWS:
            raise ValueError(f"mlTrain: need at least {MIN_TRAIN_ROWS} rows to train (got {n}).")
        if n > settings.ML_MAX_TRAINING_ROWS:
            raise ValueError(
                f"mlTrain: {n} rows exceeds ML_MAX_TRAINING_ROWS ({settings.ML_MAX_TRAINING_ROWS})."
            )
        if n < SMALL_TRAIN_ROWS:
            logger.warning("mlTrain: training on only %d rows — results may be unreliable.", n)

        target = config.get("target_column")
        features = self._resolve_features(config, list(pdf.columns), spec.supervised, target)
        missing = [c for c in features if c not in pdf.columns]
        if missing:
            raise ValueError(f"mlTrain: feature columns not found: {missing}.")
        if len(features) > settings.ML_MAX_FEATURE_COLUMNS:
            raise ValueError(
                f"mlTrain: {len(features)} feature columns exceeds ML_MAX_FEATURE_COLUMNS "
                f"({settings.ML_MAX_FEATURE_COLUMNS})."
            )
        if spec.supervised:
            if not target or target not in pdf.columns:
                raise ValueError(f"mlTrain: target_column {target!r} not found.")
            if target in features:
                raise ValueError(f"mlTrain: target_column {target!r} is in feature_columns — data leakage.")
            self._warn_id_leakage(pdf, features)

        pipeline = self._build_pipeline(config, features, pdf, spec, seed)

        x = pdf[features]
        metrics: dict[str, float] = {}
        cv_scores: list[float] | None = None
        if spec.supervised:
            y = pdf[target]
            pipeline.fit(x, y)
            metrics = self._supervised_metrics(spec.task, pipeline, x, y)
            if config.get("cross_validate"):
                cv_scores = self._cross_validate(pipeline, x, y, spec.task, int(config.get("cv_folds", 5)), n)
                metrics["cv_mean"] = float(sum(cv_scores) / len(cv_scores))
        else:
            pipeline.fit(x)
            metrics = self._unsupervised_metrics(config["model_type"], pipeline, x)

        self._enforce_model_size(pipeline, settings.ML_MAX_MODEL_SIZE_MB)

        run_id, model_uri = self._log_to_mlflow(config, pipeline, features, metrics, n, seed)

        model_ref = pd.DataFrame(
            [{"mlflow_run_id": run_id, "model_uri": model_uri, "task_type": spec.task}]
        )
        meta = NodeMetadata(
            ml_metrics=metrics,
            mlflow_run_id=run_id,
            model_uri=model_uri,
            task_type=spec.task,
            cv_scores=cv_scores,
        )
        return {"out": engine.from_pandas(pdf), "model": engine.from_pandas(model_ref)}, meta

    # -- helpers -------------------------------------------------------------

    def _resolve_features(
        self, config: dict[str, Any], columns: list[str], supervised: bool, target: str | None
    ) -> list[str]:
        features = config.get("feature_columns")
        if features:
            return list(features)
        return [c for c in columns if not (supervised and c == target)]

    def _warn_id_leakage(self, pdf: Any, features: list[str]) -> None:
        for col in features:
            if pdf[col].nunique(dropna=False) == len(pdf) and len(pdf) > 1:
                logger.warning(
                    "mlTrain: column %r has a unique value per row — possible ID leakage.", col
                )

    def _build_pipeline(
        self, config: dict[str, Any], features: list[str], pdf: Any, spec: Any, seed: int
    ) -> Any:
        from sklearn.pipeline import Pipeline

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

    def _supervised_metrics(self, task: str, pipeline: Any, x: Any, y: Any) -> dict[str, float]:
        preds = pipeline.predict(x)
        if task == CLASSIFICATION:
            from sklearn.metrics import accuracy_score, f1_score

            return {
                "train_accuracy": float(accuracy_score(y, preds)),
                "train_f1_weighted": float(f1_score(y, preds, average="weighted", zero_division=0)),
            }
        from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

        return {
            "train_r2": float(r2_score(y, preds)),
            "train_rmse": float(root_mean_squared_error(y, preds)),
            "train_mae": float(mean_absolute_error(y, preds)),
        }

    def _cross_validate(self, pipeline: Any, x: Any, y: Any, task: str, folds: int, n: int) -> list[float]:
        from sklearn.model_selection import cross_val_score

        if folds > n:
            raise ValueError(f"mlTrain: cannot run {folds}-fold CV with only {n} training rows.")
        scoring = "f1_weighted" if task == CLASSIFICATION else "r2"
        scores = cross_val_score(pipeline, x, y, cv=folds, scoring=scoring)
        return [float(s) for s in scores]

    def _unsupervised_metrics(self, model_type: str, pipeline: Any, x: Any) -> dict[str, float]:
        model = pipeline.named_steps["model"]
        if get_model_spec(model_type).task == "clustering":
            from sklearn.metrics import silhouette_score

            labels = getattr(model, "labels_", None)
            metrics: dict[str, float] = {}
            if hasattr(model, "inertia_"):
                metrics["inertia"] = float(model.inertia_)
            xt = pipeline[:-1].transform(x) if len(pipeline) > 1 else x
            unique = set(labels) - {-1} if labels is not None else set()
            # silhouette needs 2..n-1 distinct clusters (excluding DBSCAN's -1 noise).
            if labels is not None and 1 < len(unique) < len(labels):
                metrics["silhouette"] = float(silhouette_score(xt, labels))
            elif labels is not None and set(labels) == {-1}:
                logger.warning("mlTrain: DBSCAN assigned all points to noise — adjust eps/min_samples.")
            return metrics
        # pca_fit
        ratio = getattr(model, "explained_variance_ratio_", None)
        return {"explained_variance": float(ratio.sum())} if ratio is not None else {}

    def _enforce_model_size(self, pipeline: Any, max_mb: int) -> None:
        import joblib

        buf = io.BytesIO()
        joblib.dump(pipeline, buf)
        size_mb = buf.tell() / 1_000_000
        if size_mb > max_mb:
            raise ValueError(
                f"mlTrain: trained model is {size_mb:.1f} MB, over the "
                f"{max_mb} MB limit (ML_MAX_MODEL_SIZE_MB)."
            )

    def _log_to_mlflow(
        self, config: dict[str, Any], pipeline: Any, features: list[str], metrics: dict[str, float], n: int, seed: int
    ) -> tuple[str | None, str | None]:
        try:
            import sklearn

            from app.ml.tracking import configure_mlflow

            mlflow = configure_mlflow()
            import mlflow.sklearn  # noqa: F811 - load the submodule onto the configured client

            mlflow.set_experiment(config.get("mlflow_experiment") or "flowframe")
            params = {
                "model_type": config["model_type"],
                "target_column": config.get("target_column"),
                "feature_columns": json.dumps(features),
                "seed": seed,
                "train_rows": n,
                "sklearn_version": sklearn.__version__,
                **{f"hp_{k}": v for k, v in (config.get("hyperparameters") or {}).items()},
            }
            with mlflow.start_run() as run:
                # Params/metrics/tags are secondary: a bad value (e.g. an over-long
                # hyperparameter) must never stop the model itself from being saved.
                try:
                    mlflow.log_params(params)
                    if metrics:
                        mlflow.log_metrics(metrics)
                    tags = self._reproducibility_tags()
                    if tags:
                        mlflow.set_tags(tags)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("mlTrain: could not log params/metrics/tags (%s).", exc)
                # cloudpickle is MLflow's standard sklearn format; the newer skops
                # default rejects common numpy types. User-supplied model paths are
                # still validated separately in mlPredict (see app/ml/security.py).
                info = mlflow.sklearn.log_model(
                    pipeline, name="model", serialization_format="cloudpickle"
                )
                return run.info.run_id, info.model_uri
        except Exception as exc:  # noqa: BLE001 - MLflow problems must not fail a good model
            logger.warning("mlTrain: MLflow logging failed (%s) — model trained but not tracked.", exc)
            return None, None

    def _reproducibility_tags(self) -> dict[str, str]:
        """Back-pointer tags linking the MLflow run to the FlowFrame run/flow and the
        input datasets — used by the dataset-deletion guard and for traceability."""
        from app.engine.run_context import current_run_context

        ctx = current_run_context()
        if not ctx:
            return {}
        tags: dict[str, str] = {}
        if ctx.get("flow_id"):
            tags["flowframe_flow_id"] = str(ctx["flow_id"])
        if ctx.get("run_id"):
            tags["flowframe_run_id"] = str(ctx["run_id"])
        if ctx.get("dataset_ids"):
            tags["flowframe_dataset_ids"] = json.dumps(ctx["dataset_ids"])
        return tags

    # -- code export ---------------------------------------------------------

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src = input_vars["in"]
        out = output_vars.get("out", "df_out")
        model_var = output_vars.get("model", "model")
        target = config.get("target_column")
        features = config.get("feature_columns")
        feat_expr = repr(features) if features else f"[c for c in {src}.columns if c != {target!r}]"
        spec = get_model_spec(config["model_type"])
        est_repr = self._estimator_repr(config)
        lines = [
            f"_features = {feat_expr}",
            f"X = {src}[_features]",
        ]
        if spec.supervised:
            lines += [
                f"y = {src}[{target!r}]",
                f"{model_var} = Pipeline([('model', {est_repr})])",
                f"{model_var}.fit(X, y)",
            ]
        else:
            lines += [
                f"{model_var} = Pipeline([('model', {est_repr})])",
                f"{model_var}.fit(X)",
            ]
        lines.append(f"{out} = {src}")
        return "\n".join(lines)

    def _estimator_repr(self, config: dict[str, Any]) -> str:
        # Build the estimator just to render a faithful repr in exported code.
        est = build_estimator(config["model_type"], config.get("hyperparameters"), config.get("seed"))
        return repr(est)

    def imports(self, config: dict[str, Any]) -> list[str]:
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
        return ["import joblib", "from sklearn.pipeline import Pipeline", est_import]
