from fastapi import APIRouter

from app.api.deps import PreviewServiceDep
from app.core.enums import TransformationCategory
from app.core.exceptions import MLNotEnabledError
from app.engine.registry import is_ml_node, list_transformation_types, ml_node_types
from app.ml.availability import ml_extension_ready
from app.schemas.preview import PreviewResponse, TransformationPreviewRequest

router = APIRouter()


@router.get("")
async def list_transformations(
    category: TransformationCategory | None = None,
) -> list[str]:
    """The transformation node types the engine supports.

    ML nodes are only listed when the ML extension is ready (``ML_ENABLED`` and the
    ``[ml]`` extra installed). ``category=ml`` returns just the ML nodes (empty when
    not ready); ``category=etl`` returns just the core ETL nodes.
    """
    all_types = list_transformation_types()
    ml_types = ml_node_types()
    ready = ml_extension_ready()

    if category == TransformationCategory.ML:
        return sorted(ml_types) if ready else []
    if category == TransformationCategory.ETL:
        return sorted(t for t in all_types if t not in ml_types)
    # Default: ETL always; ML only when the extension is ready.
    if ready:
        return all_types
    return sorted(t for t in all_types if t not in ml_types)


@router.post("/preview", response_model=PreviewResponse)
async def preview_transformation(body: TransformationPreviewRequest, service: PreviewServiceDep) -> PreviewResponse:
    # Block previewing ML nodes when the extension is off, so the UI gets a clear
    # 501 rather than a confusing import/runtime error.
    if is_ml_node(body.type) and not ml_extension_ready():
        raise MLNotEnabledError(
            f"'{body.type}' is a machine-learning node, but ML support is not enabled. "
            f"Set ML_ENABLED and install the [ml] extra."
        )
    return await service.preview_transformation(body)
