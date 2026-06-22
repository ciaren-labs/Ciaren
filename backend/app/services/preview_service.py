from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.dataset import Dataset
from app.db.models.flow import Flow
from app.engine.backends import AnyFrame, get_engine
from app.engine.executor import FlowExecutor
from app.engine.graph import topological_sort
from app.engine.registry import get_transformation
from app.engine.transformations.base import BaseTransformation
from app.schemas.preview import (
    FlowPreviewRequest,
    PreviewResponse,
    TransformationPreviewRequest,
)

_INPUT_TYPES = {"csvInput", "excelInput", "parquetInput"}


class PreviewService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.engine = get_engine("pandas")

    async def preview_transformation(
        self, req: TransformationPreviewRequest
    ) -> PreviewResponse:
        transformation = self._get_transformation(req.type)
        try:
            transformation.validate_config(req.config)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        dataset = await self._get_dataset(req.dataset_id)
        df = self.engine.read(dataset.location, dataset.source_type)
        result = transformation.execute(self.engine, {"in": df}, req.config)
        out = result.get("out", next(iter(result.values())))
        return self._to_response(out, req.limit)

    async def preview_flow(
        self, flow_id: str, req: FlowPreviewRequest
    ) -> PreviewResponse:
        flow = await self._get_flow(flow_id)
        graph = flow.graph_json
        dataset_paths = await self._dataset_paths(graph)

        frames = FlowExecutor().compute_frames(
            graph, dataset_paths, self.engine, require_output=False
        )
        node_id = req.node_id or self._default_node(graph)
        if node_id not in frames:
            raise NotFoundError("Node", node_id)
        return self._to_response(frames[node_id], req.limit)

    # -- Internals ------------------------------------------------------

    def _get_transformation(self, node_type: str) -> BaseTransformation:
        try:
            return get_transformation(node_type)
        except KeyError as exc:
            raise NotFoundError("Transformation", node_type) from exc

    def _to_response(self, df: AnyFrame, limit: int) -> PreviewResponse:
        total = self.engine.row_count(df)
        return PreviewResponse(
            columns=list(df.columns),
            rows=self.engine.to_records(df, limit),
            row_count=total,
            truncated=total > limit,
        )

    def _default_node(self, graph: dict[str, Any]) -> str:
        # The deepest node in topological order is the natural preview target.
        order = topological_sort(graph)
        return order[-1]

    async def _dataset_paths(self, graph: dict[str, Any]) -> dict[str, Path]:
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
        return {ds_id: Path(ds.location) for ds_id, ds in datasets.items()}

    async def _get_dataset(self, dataset_id: str) -> Dataset:
        result = await self.db.execute(
            select(Dataset).where(Dataset.id == dataset_id)
        )
        dataset = result.scalar_one_or_none()
        if dataset is None:
            raise NotFoundError("Dataset", dataset_id)
        return dataset

    async def _get_flow(self, flow_id: str) -> Flow:
        result = await self.db.execute(select(Flow).where(Flow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        return flow
