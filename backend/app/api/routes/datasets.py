from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.api.deps import DbSession
from app.schemas.dataset import DatasetRead

router = APIRouter()


@router.post("/upload", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def upload_dataset(file: UploadFile, db: DbSession) -> DatasetRead:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("", response_model=list[DatasetRead])
async def list_datasets(db: DbSession) -> list[DatasetRead]:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/{dataset_id}", response_model=DatasetRead)
async def get_dataset(dataset_id: str, db: DbSession) -> DatasetRead:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/{dataset_id}/schema")
async def get_dataset_schema(dataset_id: str, db: DbSession) -> list[dict[str, Any]]:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/{dataset_id}/sample")
async def get_dataset_sample(dataset_id: str, db: DbSession) -> list[dict[str, Any]]:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
