from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.flow import FlowCreate, FlowRead, FlowUpdate


class FlowService:
    async def list(self, db: AsyncSession) -> list[FlowRead]:
        raise NotImplementedError

    async def create(self, db: AsyncSession, data: FlowCreate) -> FlowRead:
        raise NotImplementedError

    async def get(self, db: AsyncSession, flow_id: str) -> FlowRead:
        raise NotImplementedError

    async def update(self, db: AsyncSession, flow_id: str, data: FlowUpdate) -> FlowRead:
        raise NotImplementedError

    async def delete(self, db: AsyncSession, flow_id: str) -> None:
        raise NotImplementedError
