from fastapi import APIRouter

from app.api.deps import PreviewServiceDep
from app.engine.registry import list_transformation_types
from app.schemas.preview import PreviewResponse, TransformationPreviewRequest

router = APIRouter()


@router.get("")
async def list_transformations() -> list[str]:
    """The transformation node types the engine supports."""
    return list_transformation_types()


@router.post("/preview", response_model=PreviewResponse)
async def preview_transformation(
    body: TransformationPreviewRequest, service: PreviewServiceDep
) -> PreviewResponse:
    return await service.preview_transformation(body)
