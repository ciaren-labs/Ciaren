from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.run import FlowRunCreate, FlowRunRead


class ExecutionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run(self, flow_id: str, data: FlowRunCreate) -> FlowRunRead:
        raise NotImplementedError
