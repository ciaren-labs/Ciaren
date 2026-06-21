from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, status

router = APIRouter()


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_dataset(file: UploadFile) -> dict[str, Any]:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("")
async def list_datasets() -> list[dict[str, Any]]:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/{dataset_id}")
async def get_dataset(dataset_id: str) -> dict[str, Any]:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/{dataset_id}/schema")
async def get_dataset_schema(dataset_id: str) -> list[dict[str, Any]]:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/{dataset_id}/sample")
async def get_dataset_sample(dataset_id: str) -> list[dict[str, Any]]:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
