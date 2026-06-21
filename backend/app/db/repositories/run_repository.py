from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.run import FlowRun


class RunRepository:
    async def get_by_id(self, db: AsyncSession, run_id: str) -> FlowRun | None:
        raise NotImplementedError

    async def create(self, db: AsyncSession, run: FlowRun) -> FlowRun:
        raise NotImplementedError

    async def update(self, db: AsyncSession, run: FlowRun) -> FlowRun:
        raise NotImplementedError
