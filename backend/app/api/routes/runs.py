from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, status
from fastapi.responses import FileResponse

from app.api.deps import ExecutionServiceDep
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.schemas.run import FlowRunCreate, FlowRunRead, FlowRunSummary

_OUTPUT_SUFFIXES = [".csv", ".xlsx", ".parquet"]

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


@router.get("/runs/{run_id}/output")
async def download_run_output(
    run_id: str, node_id: str, service: ExecutionServiceDep
) -> FileResponse:
    """Stream a specific output node's result file as a download."""
    await service.get(run_id)  # raises 404 if not found
    settings = get_settings()
    output_dir = Path(settings.DATA_DIR) / "outputs" / run_id
    for suffix in _OUTPUT_SUFFIXES:
        file_path = output_dir / f"{node_id}{suffix}"
        if file_path.exists():
            return FileResponse(
                path=str(file_path),
                filename=f"{node_id}{suffix}",
                media_type="application/octet-stream",
            )
    raise NotFoundError("Output file", f"{run_id}/{node_id}")
