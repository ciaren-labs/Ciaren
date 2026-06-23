from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.flow import Flow
from app.engine.node_kinds import INPUT_TYPES as _INPUT_TYPES
from app.schemas.flow import FlowCreate, FlowRead, FlowUpdate
from app.services.project_service import ProjectService


def _references_dataset(graph: dict[str, Any], dataset_id: str) -> bool:
    for node in graph.get("nodes", []):
        if node.get("type") not in _INPUT_TYPES:
            continue
        if node.get("data", {}).get("config", {}).get("dataset_id") == dataset_id:
            return True
    return False


class FlowService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_all(self, project_id: str | None = None) -> list[FlowRead]:
        stmt = select(Flow).order_by(Flow.updated_at.desc())
        if project_id is not None:
            stmt = stmt.where(Flow.project_id == project_id)
        result = await self.db.execute(stmt)
        return [FlowRead.model_validate(f) for f in result.scalars().all()]

    async def list_using_dataset(self, dataset_id: str) -> list[FlowRead]:
        """Flows whose graph has an input node bound to ``dataset_id`` (lineage)."""
        result = await self.db.execute(select(Flow).order_by(Flow.updated_at.desc()))
        matches = [
            f for f in result.scalars().all() if _references_dataset(f.graph_json, dataset_id)
        ]
        return [FlowRead.model_validate(f) for f in matches]

    async def create(self, data: FlowCreate) -> FlowRead:
        project_id = await ProjectService(self.db).resolve_id(data.project_id)
        flow = Flow(
            name=data.name,
            description=data.description,
            project_id=project_id,
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

    async def disable_flows_for_dataset(self, dataset_id: str) -> None:
        """Disable all flows whose graph references the given dataset as an input."""
        result = await self.db.execute(select(Flow))
        changed = False
        for flow in result.scalars().all():
            if _references_dataset(flow.graph_json or {}, dataset_id):
                flow.is_disabled = True
                changed = True
        if changed:
            await self.db.commit()

    async def _get_or_raise(self, flow_id: str) -> Flow:
        result = await self.db.execute(select(Flow).where(Flow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        return flow
