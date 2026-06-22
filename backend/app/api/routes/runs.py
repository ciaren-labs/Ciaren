from fastapi import APIRouter, status

from app.api.deps import ExecutionServiceDep
from app.schemas.run import FlowRunCreate, FlowRunRead

router = APIRouter()


@router.post(
    "/flows/{flow_id}/runs", response_model=FlowRunRead, status_code=status.HTTP_201_CREATED
)
async def create_run(
    flow_id: str, body: FlowRunCreate, service: ExecutionServiceDep
) -> FlowRunRead:
    return await service.run(flow_id, body)


@router.get("/runs/{run_id}", response_model=FlowRunRead)
async def get_run(run_id: str, service: ExecutionServiceDep) -> FlowRunRead:
    return await service.get(run_id)
