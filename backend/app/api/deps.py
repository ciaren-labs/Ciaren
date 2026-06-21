from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.codegen_service import CodegenService
from app.services.execution_service import ExecutionService
from app.services.flow_service import FlowService
from app.services.preview_service import PreviewService

# Raw DB session — only used internally by service factories, never in routes directly.
_DbSession = Annotated[AsyncSession, Depends(get_db)]


def _flow_service(db: _DbSession) -> FlowService:
    return FlowService(db)


def _execution_service(db: _DbSession) -> ExecutionService:
    return ExecutionService(db)


def _preview_service(db: _DbSession) -> PreviewService:
    return PreviewService(db)


def _codegen_service(db: _DbSession) -> CodegenService:
    return CodegenService(db)


FlowServiceDep = Annotated[FlowService, Depends(_flow_service)]
ExecutionServiceDep = Annotated[ExecutionService, Depends(_execution_service)]
PreviewServiceDep = Annotated[PreviewService, Depends(_preview_service)]
CodegenServiceDep = Annotated[CodegenService, Depends(_codegen_service)]
