from fastapi import APIRouter, status

from app.api.deps import FlowServiceDep
from app.schemas.flow import FlowCreate, FlowRead, FlowUpdate

router = APIRouter()


@router.get("", response_model=list[FlowRead])
async def list_flows(service: FlowServiceDep) -> list[FlowRead]:
    return await service.list()


@router.post("", response_model=FlowRead, status_code=status.HTTP_201_CREATED)
async def create_flow(body: FlowCreate, service: FlowServiceDep) -> FlowRead:
    return await service.create(body)


@router.get("/{flow_id}", response_model=FlowRead)
async def get_flow(flow_id: str, service: FlowServiceDep) -> FlowRead:
    return await service.get(flow_id)


@router.put("/{flow_id}", response_model=FlowRead)
async def update_flow(flow_id: str, body: FlowUpdate, service: FlowServiceDep) -> FlowRead:
    return await service.update(flow_id, body)


@router.delete("/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow(flow_id: str, service: FlowServiceDep) -> None:
    await service.delete(flow_id)
