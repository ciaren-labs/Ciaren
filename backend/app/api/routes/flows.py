from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.schemas.flow import FlowCreate, FlowRead, FlowUpdate

router = APIRouter()


@router.get("", response_model=list[FlowRead])
async def list_flows(db: DbSession) -> list[FlowRead]:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.post("", response_model=FlowRead, status_code=status.HTTP_201_CREATED)
async def create_flow(body: FlowCreate, db: DbSession) -> FlowRead:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/{flow_id}", response_model=FlowRead)
async def get_flow(flow_id: str, db: DbSession) -> FlowRead:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.put("/{flow_id}", response_model=FlowRead)
async def update_flow(flow_id: str, body: FlowUpdate, db: DbSession) -> FlowRead:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.delete("/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow(flow_id: str, db: DbSession) -> None:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
