from typing import Any

from fastapi import APIRouter, UploadFile, status

from app.api.deps import DatasetServiceDep
from app.schemas.dataset import DatasetRead

router = APIRouter()


@router.post("/upload", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def upload_dataset(file: UploadFile, service: DatasetServiceDep) -> DatasetRead:
    return await service.upload(file)


@router.get("", response_model=list[DatasetRead])
async def list_datasets(service: DatasetServiceDep) -> list[DatasetRead]:
    return await service.list_all()


@router.get("/{dataset_id}", response_model=DatasetRead)
async def get_dataset(dataset_id: str, service: DatasetServiceDep) -> DatasetRead:
    return await service.get(dataset_id)


@router.get("/{dataset_id}/schema")
async def get_dataset_schema(
    dataset_id: str, service: DatasetServiceDep
) -> list[dict[str, Any]]:
    return await service.get_schema(dataset_id)


@router.get("/{dataset_id}/sample")
async def get_dataset_sample(
    dataset_id: str, service: DatasetServiceDep
) -> list[dict[str, Any]]:
    return await service.get_sample(dataset_id)
