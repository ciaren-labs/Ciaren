from pathlib import Path
from typing import Any

from fastapi import APIRouter, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import DatasetServiceDep, FlowServiceDep
from app.core.exceptions import NotFoundError
from app.schemas.dataset import DatasetRead, DatasetVersionRead
from app.schemas.flow import FlowRead

router = APIRouter()


@router.post("/upload", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile, service: DatasetServiceDep, project_id: str | None = None
) -> DatasetRead:
    return await service.upload(file, project_id)


@router.get("", response_model=list[DatasetRead])
async def list_datasets(
    service: DatasetServiceDep, project_id: str | None = None
) -> list[DatasetRead]:
    return await service.list_all(project_id)


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
    dataset_id: str, service: DatasetServiceDep
) -> list[DatasetVersionRead]:
    return await service.list_versions(dataset_id)


@router.get("/{dataset_id}/versions/{version_number}/download")
async def download_dataset_version(
    dataset_id: str, version_number: int, service: DatasetServiceDep
) -> FileResponse:
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
