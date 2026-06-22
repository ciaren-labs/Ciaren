from datetime import datetime

from fastapi import APIRouter, status

from app.api.deps import ExecutionServiceDep
from app.schemas.run import FlowRunCreate, FlowRunRead, FlowRunSummary

router = APIRouter()


@router.post(
    "/flows/{flow_id}/runs", response_model=FlowRunRead, status_code=status.HTTP_201_CREATED
)
async def create_run(
    flow_id: str, body: FlowRunCreate, service: ExecutionServiceDep
) -> FlowRunRead:
    return await service.run(flow_id, body)


@router.get("/runs", response_model=list[FlowRunSummary])
async def list_runs(
    service: ExecutionServiceDep,
    flow_id: str | None = None,
    project_id: str | None = None,
    dataset_id: str | None = None,
    status: str | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    limit: int = 100,
) -> list[FlowRunSummary]:
    return await service.list_runs(
        flow_id=flow_id,
        project_id=project_id,
        dataset_id=dataset_id,
        status=status,
        started_after=started_after,
        started_before=started_before,
        limit=limit,
    )


@router.get("/runs/{run_id}", response_model=FlowRunRead)
async def get_run(run_id: str, service: ExecutionServiceDep) -> FlowRunRead:
    return await service.get(run_id)
