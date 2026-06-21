from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.deps import PreviewServiceDep

router = APIRouter()


@router.post("/preview")
async def preview_transformation(
    body: dict[str, Any], service: PreviewServiceDep
) -> dict[str, Any]:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
