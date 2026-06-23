"""ML-specific run operations: reading per-node ML metrics off a finished run and
promoting a run's trained model into the MLflow registry."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import MLNotEnabledError, NotFoundError, ValidationError
from app.db.models.run import FlowRun
from app.ml.availability import ml_extension_ready

# NodeResult keys that make a node "ML" for the metrics view.
_ML_KEYS = ("ml_metrics", "model_uri", "task_type", "cv_scores", "mlflow_run_id")


class MLService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_metrics(self, run_id: str) -> list[dict[str, Any]]:
        """Per-node ML results for a run (only nodes that produced ML metadata).

        Pure read of the stored node results — works regardless of ML_ENABLED so
        historical runs remain inspectable even if ML is later turned off.
        """
        run = await self._get_run(run_id)
        results = run.node_results_json or []
        ml_nodes: list[dict[str, Any]] = []
        for r in results:
            if any(r.get(k) is not None for k in _ML_KEYS):
                ml_nodes.append(
                    {
                        "node_id": r.get("node_id"),
                        "type": r.get("type"),
                        "label": r.get("label"),
                        "ml_metrics": r.get("ml_metrics"),
                        "model_uri": r.get("model_uri"),
                        "task_type": r.get("task_type"),
                        "cv_scores": r.get("cv_scores"),
                        "mlflow_run_id": r.get("mlflow_run_id"),
                    }
                )
        return ml_nodes

    async def register_model(self, run_id: str, model_name: str, stage: str | None = None) -> dict[str, Any]:
        """Register the run's trained model in the MLflow registry, optionally
        tagging the new version with an alias (MLflow 3 replaced stages with
        aliases; the ``stage`` value is applied as a lowercase alias)."""
        if not ml_extension_ready():
            raise MLNotEnabledError("Model registration requires the ML extension (ML_ENABLED + [ml] extra).")
        if not model_name or not model_name.strip():
            raise ValidationError("A non-empty 'model_name' is required to register a model.")

        run = await self._get_run(run_id)
        model_uri = self._model_uri(run)
        if model_uri is None:
            raise ValidationError("This run has no trained model to register (no mlTrain node produced a model_uri).")

        from app.ml.tracking import configure_mlflow

        mlflow = configure_mlflow()
        version = mlflow.register_model(model_uri, model_name.strip())

        alias = None
        if stage:
            alias = stage.strip().lower()
            client = mlflow.tracking.MlflowClient()
            client.set_registered_model_alias(model_name.strip(), alias, version.version)

        return {
            "model_name": version.name,
            "version": version.version,
            "model_uri": model_uri,
            "alias": alias,
        }

    # -- internals -----------------------------------------------------------

    def _model_uri(self, run: FlowRun) -> str | None:
        for r in run.node_results_json or []:
            uri = r.get("model_uri")
            if uri:
                return str(uri)
        return None

    async def _get_run(self, run_id: str) -> FlowRun:
        result = await self.db.execute(select(FlowRun).where(FlowRun.id == run_id))
        run = result.scalar_one_or_none()
        if run is None:
            raise NotFoundError("FlowRun", run_id)
        return run
