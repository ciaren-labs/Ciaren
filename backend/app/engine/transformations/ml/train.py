# SPDX-License-Identifier: AGPL-3.0-only
"""Train nodes — fit a model and log it to MLflow.

One node per learning task (classification, regression, clustering, timeseries,
dimensionality reduction) so each picker only offers relevant models and the
palette is self-explanatory. All share :class:`BaseTrainTransformation`: it bundles
preprocessing INTO an sklearn ``Pipeline`` so the exact transforms used at fit time
are reapplied at predict time (no train/serve skew, no leakage from upstream nodes
fitting on the full dataset). Each emits a single ``model`` output — a one-row
    reference frame with the MLflow run id / model URI / task and the estimator
    definition — plus run metadata (metrics) onto its NodeResult. The ``model`` wire is type-checked: it
can only feed a model input (mlPredict / featureImportance), never a data input.
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
from app.engine.transformations.ml.base import MetadataMLTransformation, MLSchema, SklearnPipelineMixin
from app.ml.models import CLASSIFICATION, build_estimator, get_model_spec
from app.plugin_api.model_ref import ModelRef

logger = logging.getLogger(__name__)

MIN_TRAIN_ROWS = 10
SMALL_TRAIN_ROWS = 50  # warn below this


class BaseTrainTransformation(SklearnPipelineMixin, MetadataMLTransformation):
    """Shared training logic. Subclasses set :attr:`type` and :attr:`allowed_tasks`
    (the tasks whose ``model_type`` values the node accepts)."""

    input_handles = ("in",)
    #: Tasks this node trains; a chosen model_type must belong to one of them.
    allowed_tasks: tuple[str, ...] = ()

    # -- validation ----------------------------------------------------------

    def validate_config(self, config: dict[str, Any]) -> None:
        nm = self.type
        seed = config.get("seed")
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError(f"{nm} requires an integer 'seed' for reproducibility.")
        model_type = config.get("model_type")
        if not isinstance(model_type, str) or not model_type:
            raise ValueError(f"{nm} requires a 'model_type'.")
        spec = get_model_spec(model_type)  # raises with the supported list if unknown
        self._check_task(model_type, spec)

        if spec.supervised:
            target = config.get("target_column")
            if not isinstance(target, str) or not target:
                raise ValueError(f"{nm}: model_type {model_type!r} is supervised and needs a 'target_column'.")
            features = config.get("feature_columns")
            if features is not None:
                if not isinstance(features, list) or not all(isinstance(c, str) for c in features):
                    raise ValueError(f"{nm} 'feature_columns' must be a list of column names.")
                if target in features:
                    raise ValueError(f"{nm}: target_column {target!r} is also in feature_columns — data leakage.")

    def _check_task(self, model_type: str, spec: Any) -> None:
        if self.allowed_tasks and spec.task not in self.allowed_tasks:
            allowed = ", ".join(self.allowed_tasks)
            raise ValueError(
                f"{self.type}: model_type {model_type!r} is a {spec.task} model, but this node trains {allowed} models."
            )

    def validate_with_schema(self, config: dict[str, Any], schema: MLSchema) -> None:
        nm = self.type
        settings = get_settings()
        spec = get_model_spec(config["model_type"])
        target = config.get("target_column")
        if spec.supervised and target and target not in schema.columns:
            raise ValueError(f"{nm}: target_column {target!r} not in input columns {schema.columns}.")
        features = self._resolve_features(config, schema.columns, spec.supervised, target)
        missing = [c for c in features if c not in schema.columns]
        if missing:
            raise ValueError(f"{nm}: feature columns not found: {missing}.")
        if len(features) > settings.ML_MAX_FEATURE_COLUMNS:
            raise ValueError(
                f"{nm}: {len(features)} feature columns exceeds the limit of "
                f"{settings.ML_MAX_FEATURE_COLUMNS} (ML_MAX_FEATURE_COLUMNS)."
            )
        if schema.row_count is not None:
            if schema.row_count > settings.ML_MAX_TRAINING_ROWS:
                raise ValueError(
                    f"{nm}: {schema.row_count} rows exceeds the training limit of "
                    f"{settings.ML_MAX_TRAINING_ROWS} (ML_MAX_TRAINING_ROWS)."
                )
            if schema.row_count < MIN_TRAIN_ROWS:
                raise ValueError(f"{nm}: need at least {MIN_TRAIN_ROWS} rows to train (got {schema.row_count}).")

    # -- execution -----------------------------------------------------------

    def execute_with_metadata(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> tuple[dict[str, AnyFrame], NodeMetadata | None]:
        import pandas as pd

        nm = self.type
        spec = get_model_spec(config["model_type"])
        self._check_task(config["model_type"], spec)
        # During preview we must not fit a model or create an MLflow run: hand
        # downstream a placeholder model reference so the graph still resolves.
        if in_preview():
            placeholder = pd.DataFrame([self._model_ref(None, None, spec.task, config, [])])
            return (
                {"model": engine.from_pandas(placeholder)},
                NodeMetadata(task_type=spec.task),
            )

        settings = get_settings()
        seed = config["seed"]
        pdf = engine.to_pandas(inputs["in"])

        n = len(pdf)
        if n < MIN_TRAIN_ROWS:
            raise ValueError(f"{nm}: need at least {MIN_TRAIN_ROWS} rows to train (got {n}).")
        if n > settings.ML_MAX_TRAINING_ROWS:
            raise ValueError(f"{nm}: {n} rows exceeds ML_MAX_TRAINING_ROWS ({settings.ML_MAX_TRAINING_ROWS}).")
        if n < SMALL_TRAIN_ROWS:
            logger.warning("%s: training on only %d rows — results may be unreliable.", nm, n)

        target = config.get("target_column")
        features = self._resolve_features(config, list(pdf.columns), spec.supervised, target)
        missing = [c for c in features if c not in pdf.columns]
        if missing:
            raise ValueError(f"{nm}: feature columns not found: {missing}.")
        if len(features) > settings.ML_MAX_FEATURE_COLUMNS:
            raise ValueError(
                f"{nm}: {len(features)} feature columns exceeds ML_MAX_FEATURE_COLUMNS "
                f"({settings.ML_MAX_FEATURE_COLUMNS})."
            )
        if spec.supervised:
            if not target or target not in pdf.columns:
                raise ValueError(f"{nm}: target_column {target!r} not found.")
            if target in features:
                raise ValueError(f"{nm}: target_column {target!r} is in feature_columns — data leakage.")
            self._warn_id_leakage(pdf, features)

        pipeline = self._build_pipeline(config, features, pdf, spec, seed)

        x = pdf[features]
        metrics: dict[str, float] = {}
        if spec.supervised:
            y = pdf[target]
            pipeline.fit(x, y)
            metrics = self._supervised_metrics(spec.task, pipeline, x, y)
        else:
            pipeline.fit(x)
            metrics = self._unsupervised_metrics(config["model_type"], pipeline, x)

        self._enforce_model_size(pipeline, settings.ML_MAX_MODEL_SIZE_MB)

        run_id, model_uri = self._log_to_mlflow(config, pipeline, features, metrics, n, seed, x)

        model_ref = pd.DataFrame([self._model_ref(run_id, model_uri, spec.task, config, features)])
        meta = NodeMetadata(
            ml_metrics=metrics,
            mlflow_run_id=run_id,
            model_uri=model_uri,
            task_type=spec.task,
        )
        return {"model": engine.from_pandas(model_ref)}, meta

    # -- helpers -------------------------------------------------------------

    def _warn_id_leakage(self, pdf: Any, features: list[str]) -> None:
        for col in features:
            if pdf[col].nunique(dropna=False) == len(pdf) and len(pdf) > 1:
                logger.warning("%s: column %r has a unique value per row — possible ID leakage.", self.type, col)

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
                logger.warning("%s: DBSCAN assigned all points to noise — adjust eps/min_samples.", self.type)
            return metrics
        # pca_fit
        ratio = getattr(model, "explained_variance_ratio_", None)
        return {"explained_variance": float(ratio.sum())} if ratio is not None else {}

    def _model_ref(
        self,
        run_id: str | None,
        model_uri: str | None,
        task: str,
        config: dict[str, Any],
        features: list[str],
    ) -> dict[str, Any]:
        # The row layout is a public contract shared with plugins — see
        # app.plugin_api.model_ref.ModelRef (plugin train nodes emit the same
        # frame, and either side's consumers can read the other's).
        model_config = {
            "model_type": config["model_type"],
            "target_column": config.get("target_column"),
            "feature_columns": features or config.get("feature_columns") or [],
            "hyperparameters": config.get("hyperparameters") or {},
            "preprocessing": config.get("preprocessing") or {},
            "seed": config.get("seed"),
        }
        return ModelRef(
            task_type=task,
            model_type=config["model_type"],
            mlflow_run_id=run_id,
            model_uri=model_uri,
            target_column=config.get("target_column"),
            feature_columns=tuple(model_config["feature_columns"]),
            training_config=model_config,
        ).to_row()

    def _enforce_model_size(self, pipeline: Any, max_mb: int) -> None:
        import joblib

        buf = io.BytesIO()
        joblib.dump(pipeline, buf)
        size_mb = buf.tell() / 1_000_000
        if size_mb > max_mb:
            raise ValueError(
                f"{self.type}: trained model is {size_mb:.1f} MB, over the {max_mb} MB limit (ML_MAX_MODEL_SIZE_MB)."
            )

    def _log_to_mlflow(
        self,
        config: dict[str, Any],
        pipeline: Any,
        features: list[str],
        metrics: dict[str, float],
        n: int,
        seed: int,
        x: Any,
    ) -> tuple[str | None, str | None]:
        try:
            import sklearn

            from app.ml.tracking import configure_mlflow, mlflow_tracking_lock

            # Held for the whole configure-through-log-model block: configure_mlflow
            # and every mlflow.* call below read/write the SDK's process-global
            # state, so two trainings racing on this window (THREAD execution mode
            # runs multiple flows concurrently in one process) could otherwise log
            # one run's params/model against the other's tracking store.
            with mlflow_tracking_lock():
                mlflow = configure_mlflow()
                import mlflow.sklearn  # type: ignore[no-redef, unused-ignore]  # noqa: F811 - load the submodule onto the configured client

                mlflow.set_experiment(config.get("mlflow_experiment") or "ciaren")
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
                        logger.warning("%s: could not log params/metrics/tags (%s).", self.type, exc)
                    # cloudpickle is MLflow's standard sklearn format; the newer skops
                    # default rejects common numpy types. User-supplied model paths are
                    # still validated separately in mlPredict (see app/ml/security.py).
                    #
                    # Pin pip requirements to the *imported* versions and attach a
                    # signature: MLflow's automatic requirement inference can record a
                    # different version than the one actually loaded, producing a
                    # misleading "dependencies mismatch" warning at load time. Pinning
                    # to importlib.metadata versions (the same source the load-time check
                    # reads) keeps log-time and load-time in agreement.
                    signature = self._infer_signature(pipeline, x)
                    info = mlflow.sklearn.log_model(
                        pipeline,
                        name="model",
                        serialization_format="cloudpickle",
                        signature=signature,
                        input_example=x.head(5) if hasattr(x, "head") else None,
                        pip_requirements=self._pinned_requirements(config),
                    )
                    return run.info.run_id, info.model_uri
        except Exception as exc:  # noqa: BLE001 - MLflow problems must not fail a good model
            logger.warning("%s: MLflow logging failed (%s) — model trained but not tracked.", self.type, exc)
            return None, None

    def _infer_signature(self, pipeline: Any, x: Any) -> Any:
        """Best-effort MLflow signature from the training features and predictions.

        Unsupervised estimators without ``predict`` (e.g. PCA) or any inference
        hiccup simply yield no signature — never block logging a good model.
        """
        try:
            from mlflow.models import infer_signature

            sample = x.head(50) if hasattr(x, "head") else x
            return infer_signature(sample, pipeline.predict(sample))
        except Exception as exc:  # noqa: BLE001
            logger.debug("%s: could not infer model signature (%s).", self.type, exc)
            return None

    def _pinned_requirements(self, config: dict[str, Any]) -> list[str]:
        """Pin the model's core dependencies to the versions actually imported.

        Avoids MLflow's flaky requirement inference recording a version that
        differs from the runtime, which surfaces as a spurious dependency-mismatch
        warning when the model is loaded back in the same environment.
        """
        import importlib.metadata as md

        packages = ["scikit-learn", "numpy", "pandas", "cloudpickle"]
        est = build_estimator(config["model_type"], config.get("hyperparameters"), config.get("seed"))
        top = type(est).__module__.split(".")[0]
        if top in ("xgboost", "lightgbm"):
            packages.append(top)
        pinned: list[str] = []
        for name in packages:
            try:
                pinned.append(f"{name}=={md.version(name)}")
            except md.PackageNotFoundError:
                continue
        return pinned

    def _reproducibility_tags(self) -> dict[str, str]:
        """Back-pointer tags linking the MLflow run to the Ciaren run/flow and the
        input datasets — used by the dataset-deletion guard and for traceability."""
        from app.engine.run_context import current_run_context

        ctx = current_run_context()
        if not ctx:
            return {}
        tags: dict[str, str] = {}
        if ctx.get("flow_id"):
            tags["ciaren_flow_id"] = str(ctx["flow_id"])
        if ctx.get("run_id"):
            tags["ciaren_run_id"] = str(ctx["run_id"])
        if ctx.get("dataset_ids"):
            tags["ciaren_dataset_ids"] = json.dumps(ctx["dataset_ids"])
        return tags

    # -- code export ---------------------------------------------------------

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src = input_vars["in"]
        model_var = output_vars.get("model", "model")
        target = config.get("target_column")
        features = config.get("feature_columns")
        feat_expr = repr(features) if features else f"[c for c in {src}.columns if c != {target!r}]"
        spec = get_model_spec(config["model_type"])
        est_repr = self._estimator_repr(config)
        lines = [
            f"_features = {feat_expr}",
            f"_X = {src}[_features]",
        ]
        # Mirror execute(): bundle the same preprocessing into the Pipeline so the
        # exported script reproduces the run (imputation/scaling/encoding) and runs
        # on categorical or null-containing data — not just on clean numerics.
        pre_lines, steps = self._preprocessor_code(config)
        lines += pre_lines
        steps.append(f"('model', {est_repr})")
        pipeline_expr = "Pipeline([" + ", ".join(steps) + "])"
        if spec.supervised:
            lines += [
                f"_y = {src}[{target!r}]",
                f"{model_var} = {pipeline_expr}",
                f"{model_var}.fit(_X, _y)",
            ]
        else:
            lines += [
                f"{model_var} = {pipeline_expr}",
                f"{model_var}.fit(_X)",
            ]
        return "\n".join(lines)

    def imports(self, config: dict[str, Any]) -> list[str]:
        # joblib lets the exported training script persist the fitted pipeline.
        return ["import joblib", *self._pipeline_imports(config)]


class BaseModelDefinitionTransformation(BaseTrainTransformation):
    """Emit an unfitted model definition for nodes that evaluate by fitting clones.

    Unlike the Train nodes, this does not fit data or create an MLflow run. It
    carries the same estimator configuration on the model wire so Cross-Validate
    can build the pipeline inside each fold without a redundant full-data fit.
    """

    def validate_with_schema(self, config: dict[str, Any], schema: MLSchema) -> None:
        nm = self.type
        settings = get_settings()
        spec = get_model_spec(config["model_type"])
        self._check_task(config["model_type"], spec)
        target = config.get("target_column")
        if spec.supervised and target and target not in schema.columns:
            raise ValueError(f"{nm}: target_column {target!r} not in input columns {schema.columns}.")
        features = self._resolve_features(config, schema.columns, spec.supervised, target)
        missing = [c for c in features if c not in schema.columns]
        if missing:
            raise ValueError(f"{nm}: feature columns not found: {missing}.")
        if len(features) > settings.ML_MAX_FEATURE_COLUMNS:
            raise ValueError(
                f"{nm}: {len(features)} feature columns exceeds the limit of "
                f"{settings.ML_MAX_FEATURE_COLUMNS} (ML_MAX_FEATURE_COLUMNS)."
            )

    def execute_with_metadata(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> tuple[dict[str, AnyFrame], NodeMetadata | None]:
        import pandas as pd

        spec = get_model_spec(config["model_type"])
        self._check_task(config["model_type"], spec)
        pdf = engine.to_pandas(inputs["in"])
        target = config.get("target_column")
        features = self._resolve_features(config, list(pdf.columns), spec.supervised, target)
        if spec.supervised and (not target or target not in pdf.columns):
            raise ValueError(f"{self.type}: target_column {target!r} not found.")
        if target in features:
            raise ValueError(f"{self.type}: target_column {target!r} is in feature_columns — data leakage.")
        missing = [c for c in features if c not in pdf.columns]
        if missing:
            raise ValueError(f"{self.type}: feature columns not found: {missing}.")
        model_ref = pd.DataFrame([self._model_ref(None, None, spec.task, config, features)])
        return {"model": engine.from_pandas(model_ref)}, NodeMetadata(task_type=spec.task)


class ClassifierModelTransformation(BaseModelDefinitionTransformation):
    type = "mlClassifierModel"
    allowed_tasks = ("classification",)


class RegressorModelTransformation(BaseModelDefinitionTransformation):
    type = "mlRegressorModel"
    allowed_tasks = ("regression",)


# -- task-scoped train nodes -------------------------------------------------
# One node per learning task. They share BaseTrainTransformation; only the type
# and the accepted task(s) differ, so each model picker shows just its family.


class TrainClassifierTransformation(BaseTrainTransformation):
    type = "mlTrainClassifier"
    allowed_tasks = ("classification",)


class TrainRegressorTransformation(BaseTrainTransformation):
    type = "mlTrainRegressor"
    allowed_tasks = ("regression",)


class TrainClusteringTransformation(BaseTrainTransformation):
    type = "mlTrainClustering"
    allowed_tasks = ("clustering",)


class TrainForecasterTransformation(BaseTrainTransformation):
    """Timeseries forecasting. Defined as a scaffold — no estimators are registered
    for the ``timeseries`` task yet, so this node appears in the palette but isn't
    runnable until forecasting models are added."""

    type = "mlTrainForecaster"
    allowed_tasks = ("timeseries",)


class TrainDimReductionTransformation(BaseTrainTransformation):
    type = "mlTrainDimReduction"
    allowed_tasks = ("dimensionality_reduction",)


# Backwards-compatible alias for code that imported the old class name.
MLTrainTransformation = TrainClassifierTransformation
