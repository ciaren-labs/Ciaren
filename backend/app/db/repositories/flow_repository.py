from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.flow import Flow


class FlowRepository:
    async def get_all(self, db: AsyncSession) -> list[Flow]:
        raise NotImplementedError

    async def get_by_id(self, db: AsyncSession, flow_id: str) -> Flow | None:
        raise NotImplementedError

    async def create(self, db: AsyncSession, flow: Flow) -> Flow:
        raise NotImplementedError

    async def update(self, db: AsyncSession, flow: Flow) -> Flow:
        raise NotImplementedError

    async def delete(self, db: AsyncSession, flow_id: str) -> None:
        raise NotImplementedError
