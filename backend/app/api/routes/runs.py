import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi import status as http_status
from fastapi.responses import FileResponse

from app.api.deps import ExecutionServiceDep
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.schemas.run import FlowRunCreate, FlowRunRead, FlowRunSummary

_OUTPUT_SUFFIXES = [".csv", ".xlsx", ".parquet"]
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

_VALID_SORT_FIELDS = {"created_at", "started_at", "status"}
_VALID_SORT_ORDERS = {"asc", "desc"}

router = APIRouter()


@router.post("/flows/{flow_id}/runs", response_model=FlowRunRead, status_code=http_status.HTTP_201_CREATED)
async def create_run(flow_id: str, body: FlowRunCreate, service: ExecutionServiceDep) -> FlowRunRead:
    return await service.run(flow_id, body)


@router.get("/runs", response_model=list[FlowRunSummary])
async def list_runs(
    service: ExecutionServiceDep,
    flow_id: str | None = None,
    project_id: str | None = None,
    dataset_id: str | None = None,
    schedule_id: str | None = None,
    run_status: str | None = Query(default=None, alias="status"),
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    sort_by: str = Query(default="created_at", pattern="^(created_at|started_at|status)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=100, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
) -> list[FlowRunSummary]:
    return await service.list_runs(
        flow_id=flow_id,
        project_id=project_id,
        dataset_id=dataset_id,
        schedule_id=schedule_id,
        status=run_status,
        started_after=started_after,
        started_before=started_before,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}", response_model=FlowRunRead)
async def get_run(run_id: str, service: ExecutionServiceDep) -> FlowRunRead:
    return await service.get(run_id)


@router.post("/runs/{run_id}/retry", response_model=FlowRunRead, status_code=http_status.HTTP_201_CREATED)
async def retry_run(run_id: str, service: ExecutionServiceDep) -> FlowRunRead:
    """Re-run this run's flow with the same config, creating a new run (new id)."""
    return await service.retry(run_id)


@router.get("/runs/{run_id}/output")
async def download_run_output(run_id: str, node_id: str, service: ExecutionServiceDep) -> FileResponse:
    """Stream a specific output node's result file as a download."""
    if not _SAFE_ID_RE.match(node_id):
        raise ValidationError(
            f"Invalid node_id {node_id!r}: only letters, digits, hyphens and underscores are allowed."
        )
    await service.get(run_id)  # raises 404 if not found
    settings = get_settings()
    output_dir = (Path(settings.DATA_DIR) / "outputs" / run_id).resolve()
    for suffix in _OUTPUT_SUFFIXES:
        file_path = (output_dir / f"{node_id}{suffix}").resolve()
        # Guard against path traversal — both paths are already resolved above.
        if not str(file_path).startswith(str(output_dir)):
            raise ValidationError("Invalid output path.")
        if file_path.exists():
            return FileResponse(
                path=str(file_path),
                filename=f"{node_id}{suffix}",
                media_type="application/octet-stream",
            )
    raise NotFoundError("Output file", f"{run_id}/{node_id}")
