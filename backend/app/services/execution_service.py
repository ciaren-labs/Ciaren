from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.run import FlowRunCreate, FlowRunRead


class ExecutionService:
    async def run(self, db: AsyncSession, flow_id: str, data: FlowRunCreate) -> FlowRunRead:
        raise NotImplementedError
