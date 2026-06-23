"""ML-specific run endpoints: read a run's ML metrics and promote its model to the
MLflow registry. Registration requires the ML extension (501 otherwise); reading
metrics is a pure read of stored run data and always works."""
from fastapi import APIRouter

from app.api.deps import MLServiceDep
from app.schemas.run import MLNodeMetrics, MLRegisterRequest

router = APIRouter()


@router.get("/runs/{run_id}/ml/metrics", response_model=list[MLNodeMetrics])
async def get_run_ml_metrics(run_id: str, service: MLServiceDep) -> list[MLNodeMetrics]:
    nodes = await service.get_metrics(run_id)
    return [MLNodeMetrics(**n) for n in nodes]


@router.post("/runs/{run_id}/ml/register")
async def register_run_model(
    run_id: str, body: MLRegisterRequest, service: MLServiceDep
) -> dict[str, object]:
    return await service.register_model(run_id, body.model_name, body.stage)


@router.get("/flows/{flow_id}/ml/experiments")
async def list_flow_ml_experiments(flow_id: str, service: MLServiceDep) -> list[dict[str, object]]:
    """MLflow experiments this flow's mlTrain nodes log to."""
    return await service.list_experiments(flow_id)
