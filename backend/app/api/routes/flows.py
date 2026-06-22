from fastapi import APIRouter, status

from app.api.deps import CodegenServiceDep, FlowServiceDep, PreviewServiceDep
from app.schemas.flow import CodeExportResponse, FlowCreate, FlowRead, FlowUpdate
from app.schemas.preview import FlowPreviewRequest, PreviewResponse

router = APIRouter()


@router.get("", response_model=list[FlowRead])
async def list_flows(
    service: FlowServiceDep, project_id: str | None = None
) -> list[FlowRead]:
    return await service.list_all(project_id)


@router.post("", response_model=FlowRead, status_code=status.HTTP_201_CREATED)
async def create_flow(body: FlowCreate, service: FlowServiceDep) -> FlowRead:
    return await service.create(body)


@router.get("/{flow_id}", response_model=FlowRead)
async def get_flow(flow_id: str, service: FlowServiceDep) -> FlowRead:
    return await service.get(flow_id)


@router.put("/{flow_id}", response_model=FlowRead)
async def update_flow(flow_id: str, body: FlowUpdate, service: FlowServiceDep) -> FlowRead:
    return await service.update(flow_id, body)


@router.delete("/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow(flow_id: str, service: FlowServiceDep) -> None:
    await service.delete(flow_id)


@router.post("/{flow_id}/preview", response_model=PreviewResponse)
async def preview_flow(
    flow_id: str, body: FlowPreviewRequest, service: PreviewServiceDep
) -> PreviewResponse:
    return await service.preview_flow(flow_id, body)


@router.post("/{flow_id}/export/python", response_model=CodeExportResponse)
async def export_flow_python(
    flow_id: str, service: CodegenServiceDep
) -> CodeExportResponse:
    code = await service.export(flow_id)
    return CodeExportResponse(code=code["pandas"], polars=code["polars"])
