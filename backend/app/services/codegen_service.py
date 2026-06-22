from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.dataset import Dataset
from app.db.models.flow import Flow
from app.engine.codegen import CodeGenerator
from app.engine.graph import GraphValidationError

_INPUT_TYPES = {"csvInput", "excelInput", "parquetInput"}


class CodegenService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def export_python(self, flow_id: str) -> str:
        flow = await self._get_flow(flow_id)
        graph = flow.graph_json
        # Use readable dataset filenames rather than absolute local paths so the
        # exported script is portable and we don't leak the server filesystem.
        dataset_names = await self._dataset_filenames(graph)
        try:
            return CodeGenerator().generate(graph, dataset_names)
        except GraphValidationError as exc:
            raise ValidationError(str(exc)) from exc
        except KeyError as exc:
            raise ValidationError(f"Unknown node type: {exc}") from exc

    async def _dataset_filenames(self, graph: dict[str, Any]) -> dict[str, str]:
        dataset_ids = {
            n["data"]["config"]["dataset_id"]
            for n in graph.get("nodes", [])
            if n["type"] in _INPUT_TYPES
        }
        if not dataset_ids:
            return {}
        result = await self.db.execute(
            select(Dataset).where(Dataset.id.in_(dataset_ids))
        )
        datasets = {d.id: d for d in result.scalars().all()}
        missing = dataset_ids - datasets.keys()
        if missing:
            raise NotFoundError("Dataset", ", ".join(sorted(missing)))
        return {ds_id: ds.name for ds_id, ds in datasets.items()}

    async def _get_flow(self, flow_id: str) -> Flow:
        result = await self.db.execute(select(Flow).where(Flow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        return flow
