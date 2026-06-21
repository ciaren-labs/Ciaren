from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.flow import FlowCreate, FlowRead, FlowUpdate


class FlowService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(self) -> list[FlowRead]:
        raise NotImplementedError

    async def create(self, data: FlowCreate) -> FlowRead:
        raise NotImplementedError

    async def get(self, flow_id: str) -> FlowRead:
        raise NotImplementedError

    async def update(self, flow_id: str, data: FlowUpdate) -> FlowRead:
        raise NotImplementedError

    async def delete(self, flow_id: str) -> None:
        raise NotImplementedError
