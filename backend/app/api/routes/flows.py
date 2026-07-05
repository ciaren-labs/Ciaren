# SPDX-License-Identifier: AGPL-3.0-only
from fastapi import APIRouter, status

from app.api.deps import CodegenServiceDep, FlowServiceDep, PreviewServiceDep
from app.schemas.flow import (
    CodeExportResponse,
    FlowCreate,
    FlowImport,
    FlowMigrateDocumentRequest,
    FlowMigrateDocumentResponse,
    FlowRead,
    FlowUpdate,
)
from app.schemas.preview import FlowPreviewRequest, PreviewResponse
from app.services.flow_service import migrate_flow_document

router = APIRouter()


@router.get("", response_model=list[FlowRead])
async def list_flows(service: FlowServiceDep, project_id: str | None = None) -> list[FlowRead]:
    return await service.list_all(project_id)


@router.post("/import", response_model=FlowRead, status_code=status.HTTP_201_CREATED)
async def import_flow(body: FlowImport, service: FlowServiceDep) -> FlowRead:
    """Create a flow from an exported flow document. Environment-specific bindings
    (dataset / connection ids) in the graph are stripped — the imported flow keeps
    its node structure but its inputs/connections must be re-selected."""
    return await service.import_flow(body)


@router.post("/migrate-document", response_model=FlowMigrateDocumentResponse)
async def migrate_flow_document_route(body: FlowMigrateDocumentRequest) -> FlowMigrateDocumentResponse:
    """Migrate/validate a raw .flow document to the current schema version
    without importing it — a standalone file-to-file utility. Nothing is
    persisted."""
    return migrate_flow_document(body.document)


@router.post("", response_model=FlowRead, status_code=status.HTTP_201_CREATED)
async def create_flow(body: FlowCreate, service: FlowServiceDep) -> FlowRead:
    return await service.create(body)


@router.post("/{flow_id}/duplicate", response_model=FlowRead, status_code=status.HTTP_201_CREATED)
async def duplicate_flow(flow_id: str, service: FlowServiceDep, name: str | None = None) -> FlowRead:
    """Copy a flow (graph, parameters, engine). Schedules and run history stay
    with the original."""
    return await service.duplicate(flow_id, name)


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
async def preview_flow(flow_id: str, body: FlowPreviewRequest, service: PreviewServiceDep) -> PreviewResponse:
    return await service.preview_flow(flow_id, body)


@router.post("/{flow_id}/export/python", response_model=CodeExportResponse)
async def export_flow_python(
    flow_id: str, service: CodegenServiceDep, free_intermediates: bool = False
) -> CodeExportResponse:
    code = await service.export(flow_id, free_intermediates=free_intermediates)
    return CodeExportResponse(
        code=code["pandas"],
        polars=code["polars"],
        polars_lazy=code["polars_lazy"],
        flow_document=code["flow_document"],
    )
