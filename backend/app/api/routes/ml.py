"""ML-specific run endpoints: read a run's ML metrics and promote its model to the
MLflow registry. Registration requires the ML extension (501 otherwise); reading
metrics is a pure read of stored run data and always works."""

from fastapi import APIRouter

from app.api.deps import MLServiceDep
from app.ml.models import model_catalog_status
from app.schemas.run import MLAliasRequest, MLNodeMetrics, MLRegisterRequest

router = APIRouter()


@router.get("/runs/{run_id}/ml/metrics", response_model=list[MLNodeMetrics])
async def get_run_ml_metrics(run_id: str, service: MLServiceDep) -> list[MLNodeMetrics]:
    nodes = await service.get_metrics(run_id)
    return [MLNodeMetrics(**n) for n in nodes]


@router.post("/runs/{run_id}/ml/register")
async def register_run_model(run_id: str, body: MLRegisterRequest, service: MLServiceDep) -> dict[str, object]:
    return await service.register_model(run_id, body.model_name, body.stage)


@router.get("/flows/{flow_id}/ml/experiments")
async def list_flow_ml_experiments(flow_id: str, service: MLServiceDep) -> list[dict[str, object]]:
    """MLflow experiments this flow's mlTrain nodes log to."""
    return await service.list_experiments(flow_id)


@router.get("/ml/models")
async def list_registered_models(service: MLServiceDep) -> list[dict[str, object]]:
    """All registered models with versions, aliases, metrics, and FlowFrame lineage."""
    return await service.list_registered_models()


@router.get("/ml/model-catalog")
async def list_model_catalog() -> list[dict[str, object]]:
    """Trainable model types annotated with optional dependency availability."""
    return model_catalog_status()


@router.post("/ml/models/{model_name}/alias")
async def set_model_alias(model_name: str, body: MLAliasRequest, service: MLServiceDep) -> dict[str, object]:
    """Point an alias (e.g. production) at a registered model version."""
    return await service.set_model_alias(model_name, body.version, body.alias)


@router.delete("/ml/models/{model_name}/alias/{alias}")
async def clear_model_alias(model_name: str, alias: str, service: MLServiceDep) -> dict[str, object]:
    """Remove an alias from a registered model."""
    return await service.clear_model_alias(model_name, alias)


@router.get("/ml/experiments")
async def list_ml_experiments(service: MLServiceDep) -> list[dict[str, object]]:
    """All MLflow experiments with a run count / last-run time."""
    return await service.list_all_experiments()


@router.get("/ml/experiments/{experiment_id}/runs")
async def list_ml_experiment_runs(
    experiment_id: str, service: MLServiceDep, limit: int = 100
) -> list[dict[str, object]]:
    """Runs in an experiment (metrics, params, lineage) for the leaderboard."""
    return await service.list_experiment_runs(experiment_id, limit=limit)
