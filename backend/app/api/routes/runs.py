import asyncio
import json
import re
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from fastapi import status as http_status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select

from app.api.deps import ExecutionServiceDep
from app.core.config import get_settings
from app.core.enums import RunSortField, RunStatus, SortOrder
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.run import FlowRun
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
    run_status: RunStatus | None = Query(default=None, alias="status"),
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    sort_by: RunSortField = RunSortField.CREATED_AT,
    sort_order: SortOrder = SortOrder.DESC,
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


async def _sse_log_stream(
    service: ExecutionServiceDep,
    run_id: str,
    poll_interval: float = 0.5,
    max_wait_seconds: float = 3600.0,
) -> AsyncGenerator[str, None]:
    """Async generator for SSE log events.

    Polls the DB until the run reaches a terminal state, then yields each
    stored log entry as an SSE ``data`` event, and closes with an
    ``event: done`` frame. Uses scalar column selects to bypass the
    SQLAlchemy session identity map so each poll is a genuine DB round-trip.
    """
    TERMINAL = {RunStatus.SUCCESS, RunStatus.FAILED}
    deadline = asyncio.get_event_loop().time() + max_wait_seconds

    while True:
        result = await service.db.execute(select(FlowRun.status, FlowRun.logs_json).where(FlowRun.id == run_id))
        row = result.one_or_none()
        if row is None:
            return
        status: str = row.status
        logs_json: list[dict[str, Any]] | None = row.logs_json

        if status in TERMINAL:
            for entry in logs_json or []:
                yield f"data: {json.dumps(entry)}\n\n"
            yield f"event: done\ndata: {json.dumps({'status': status, 'run_id': run_id})}\n\n"
            return

        if asyncio.get_event_loop().time() >= deadline:
            yield f"event: error\ndata: {json.dumps({'detail': 'Timed out waiting for run completion'})}\n\n"
            return

        await asyncio.sleep(poll_interval)


@router.get("/runs/{run_id}/logs/stream")
async def stream_run_logs(run_id: str, service: ExecutionServiceDep) -> StreamingResponse:
    """Stream run log entries as server-sent events (SSE).

    Polls the database until the run reaches a terminal state, then emits
    each stored log entry as an SSE ``data`` event and closes with an
    ``event: done`` frame containing ``{"status": "...", "run_id": "..."}``.

    Raises 404 immediately if the run does not exist (before any SSE data
    is sent), so callers get a proper HTTP error rather than a silent stream.
    """
    await service.get(run_id)  # raises NotFoundError → 404 if absent
    return StreamingResponse(
        _sse_log_stream(service, run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
