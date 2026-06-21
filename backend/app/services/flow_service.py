from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.flow import Flow
from app.schemas.flow import FlowCreate, FlowRead, FlowUpdate


class FlowService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(self) -> list[FlowRead]:
        result = await self.db.execute(select(Flow).order_by(Flow.updated_at.desc()))
        return [FlowRead.model_validate(f) for f in result.scalars().all()]

    async def create(self, data: FlowCreate) -> FlowRead:
        flow = Flow(
            name=data.name,
            description=data.description,
            graph_json=data.graph_json,
        )
        self.db.add(flow)
        await self.db.commit()
        await self.db.refresh(flow)
        return FlowRead.model_validate(flow)

    async def get(self, flow_id: str) -> FlowRead:
        flow = await self._get_or_raise(flow_id)
        return FlowRead.model_validate(flow)

    async def update(self, flow_id: str, data: FlowUpdate) -> FlowRead:
        flow = await self._get_or_raise(flow_id)
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(flow, field, value)
        # Explicit timestamp: SQLite's onupdate fires but doesn't reflect until refresh,
        # and SQLite's second-level resolution means tests may see the same value.
        flow.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(flow)
        return FlowRead.model_validate(flow)

    async def delete(self, flow_id: str) -> None:
        flow = await self._get_or_raise(flow_id)
        await self.db.delete(flow)
        await self.db.commit()

    async def _get_or_raise(self, flow_id: str) -> Flow:
        result = await self.db.execute(select(Flow).where(Flow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        return flow
