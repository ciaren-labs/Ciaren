from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.schemas.run import FlowRunCreate, FlowRunRead

router = APIRouter()


@router.post(
    "/flows/{flow_id}/runs", response_model=FlowRunRead, status_code=status.HTTP_201_CREATED
)
async def create_run(flow_id: str, body: FlowRunCreate, db: DbSession) -> FlowRunRead:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/runs/{run_id}", response_model=FlowRunRead)
async def get_run(run_id: str, db: DbSession) -> FlowRunRead:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
