from typing import Any

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.post("/preview")
async def preview_transformation(body: dict[str, Any]) -> dict[str, Any]:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
