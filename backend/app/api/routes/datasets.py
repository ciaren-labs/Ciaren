# SPDX-License-Identifier: AGPL-3.0-only
from typing import Any

from fastapi import APIRouter, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import DatasetServiceDep, FlowServiceDep
from app.core.exceptions import NotFoundError
from app.schemas.dataset import DatasetRead, DatasetUpdate, DatasetVersionRead
from app.schemas.flow import FlowRead

router = APIRouter()


@router.post("/upload", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile,
    service: DatasetServiceDep,
    project_id: str | None = None,
    delimiter: str | None = None,
    encoding: str | None = None,
    decimal: str | None = None,
    sheet: str | None = None,
) -> DatasetRead:
    """Store an upload. Dialect options are optional: CSV/TSV delimiter,
    encoding and decimal mark are auto-detected when omitted; Excel reads the
    first sheet unless ``sheet`` (name or 0-based index) says otherwise."""
    parse_options = {
        k: v
        for k, v in {"delimiter": delimiter, "encoding": encoding, "decimal": decimal, "sheet": sheet}.items()
        if v is not None
    }
    return await service.upload(file, project_id, parse_options=parse_options)


@router.get("", response_model=list[DatasetRead])
async def list_datasets(
    service: DatasetServiceDep, project_id: str | None = None, include_deleted: bool = False
) -> list[DatasetRead]:
    return await service.list_all(project_id, include_deleted=include_deleted)


@router.post("/purge-expired")
async def purge_expired_datasets(service: DatasetServiceDep) -> dict[str, int]:
    """Hard-delete soft-deleted datasets past the retention window (removes files)."""
    return {"purged": await service.purge_expired()}


@router.patch("/{dataset_id}", response_model=DatasetRead)
async def patch_dataset(
    dataset_id: str,
    body: DatasetUpdate,
    service: DatasetServiceDep,
    flow_service: FlowServiceDep,
) -> DatasetRead:
    """Partial-update a dataset. Disabling cascades to flows that use it as input."""
    result = await service.update(dataset_id, body)
    if body.is_disabled is True:
        await flow_service.disable_flows_for_dataset(dataset_id)
    return result


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: str,
    service: DatasetServiceDep,
    flow_service: FlowServiceDep,
    purge: bool = False,
    force: bool = False,
) -> None:
    """Soft-delete a dataset (retained for restore); ``?purge=true`` deletes it and
    its files immediately. Refuses with 409 if a Production model was trained on it,
    unless ``?force=true``.

    Deleting a dataset disables the flows that use it as input — same cascade as
    disabling it via PATCH — so "out of use" means the same thing on both paths and
    a dependent flow can't silently keep running against a removed dataset."""
    await service.delete(dataset_id, purge=purge, force=force)
    await flow_service.disable_flows_for_dataset(dataset_id)


@router.post("/{dataset_id}/restore", response_model=DatasetRead)
async def restore_dataset(dataset_id: str, service: DatasetServiceDep) -> DatasetRead:
    return await service.restore(dataset_id)


@router.get("/{dataset_id}/flows", response_model=list[FlowRead])
async def list_dataset_flows(
    dataset_id: str, dataset_service: DatasetServiceDep, flow_service: FlowServiceDep
) -> list[FlowRead]:
    # 404 if the dataset doesn't exist, then return flows that reference it.
    await dataset_service.get(dataset_id)
    return await flow_service.list_using_dataset(dataset_id)


@router.get("/{dataset_id}", response_model=DatasetRead)
async def get_dataset(dataset_id: str, service: DatasetServiceDep) -> DatasetRead:
    return await service.get(dataset_id)


@router.get("/{dataset_id}/versions", response_model=list[DatasetVersionRead])
async def list_dataset_versions(
    dataset_id: str,
    service: DatasetServiceDep,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[DatasetVersionRead]:
    return await service.list_versions(dataset_id, limit=limit, offset=offset)


@router.get("/{dataset_id}/versions/{version_number}/download")
async def download_dataset_version(dataset_id: str, version_number: int, service: DatasetServiceDep) -> FileResponse:
    """Stream a specific dataset version's file as a download."""
    file_path = await service.get_version_location(dataset_id, version_number)
    if not file_path.exists():
        raise NotFoundError("Dataset version file", f"{dataset_id}/v{version_number}")
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@router.get("/{dataset_id}/schema")
async def get_dataset_schema(
    dataset_id: str, service: DatasetServiceDep, version: int | None = None
) -> list[dict[str, Any]]:
    return await service.get_schema(dataset_id, version)


@router.get("/{dataset_id}/sample")
async def get_dataset_sample(
    dataset_id: str, service: DatasetServiceDep, version: int | None = None
) -> list[dict[str, Any]]:
    return await service.get_sample(dataset_id, version)


@router.get("/{dataset_id}/profile")
async def get_dataset_profile(
    dataset_id: str, service: DatasetServiceDep, version: int | None = None
) -> list[dict[str, Any]]:
    return await service.get_profile(dataset_id, version)
