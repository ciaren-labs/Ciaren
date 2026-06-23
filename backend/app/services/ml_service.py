"""ML-specific run operations: reading per-node ML metrics off a finished run and
promoting a run's trained model into the MLflow registry."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import MLNotEnabledError, NotFoundError, ValidationError
from app.db.models.flow import Flow
from app.db.models.run import FlowRun
from app.ml.availability import ml_extension_ready

# mlTrain's default experiment name when a node sets no mlflow_experiment.
_DEFAULT_EXPERIMENT = "flowframe"

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

    async def list_experiments(self, flow_id: str) -> list[dict[str, Any]]:
        """The MLflow experiments this flow's mlTrain nodes log to.

        Experiment names are derived from the flow graph (each mlTrain node's
        ``mlflow_experiment`` config, or the default), then looked up in MLflow so
        the response reflects what actually exists.
        """
        if not ml_extension_ready():
            raise MLNotEnabledError("Listing experiments requires the ML extension (ML_ENABLED + [ml] extra).")
        flow = await self._get_flow(flow_id)
        names = self._experiment_names(flow.graph_json or {})
        if not names:
            return []

        from app.ml.tracking import configure_mlflow

        mlflow = configure_mlflow()
        client = mlflow.tracking.MlflowClient()
        experiments: list[dict[str, Any]] = []
        for name in sorted(names):
            exp = client.get_experiment_by_name(name)
            if exp is not None:
                experiments.append(
                    {
                        "name": exp.name,
                        "experiment_id": exp.experiment_id,
                        "lifecycle_stage": exp.lifecycle_stage,
                        "artifact_location": exp.artifact_location,
                    }
                )
        return experiments

    def _experiment_names(self, graph: dict[str, Any]) -> set[str]:
        names: set[str] = set()
        for node in graph.get("nodes", []):
            if node.get("type") == "mlTrain":
                config = node.get("data", {}).get("config", {})
                names.add(config.get("mlflow_experiment") or _DEFAULT_EXPERIMENT)
        return names

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

    async def _get_flow(self, flow_id: str) -> Flow:
        result = await self.db.execute(select(Flow).where(Flow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        return flow
