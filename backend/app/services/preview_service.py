# SPDX-License-Identifier: AGPL-3.0-only
import asyncio
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.flow import Flow
from app.engine.backends import AnyFrame, get_engine
from app.engine.executor import FlowExecutor, NodeExecutionError
from app.engine.graph import GraphValidationError, ancestor_subgraph, topological_sort
from app.engine.parameters import ParameterError, apply_parameters
from app.engine.preview_context import preview_mode
from app.engine.profile import profile_frame
from app.engine.registry import get_transformation
from app.engine.transformations.base import BaseTransformation
from app.schemas.preview import (
    FlowPreviewRequest,
    PreviewResponse,
    TransformationPreviewRequest,
)
from app.services.dataset_resolver import build_dataset_paths, resolve_version
from app.services.sql_resolver import has_sql_inputs, materialize_sql_inputs
from app.services.storage_resolver import has_storage_inputs, materialize_storage_inputs

# Preview reads a bounded sample from external sources so it stays fast.
_PREVIEW_SQL_ROWS = 1000
_PREVIEW_STORAGE_ROWS = 1000


class PreviewService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.engine = get_engine("pandas")

    async def preview_transformation(self, req: TransformationPreviewRequest) -> PreviewResponse:
        transformation = self._get_transformation(req.type)
        try:
            transformation.validate_config(req.config)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        # Transformation preview always reads the dataset's latest version.
        version = await resolve_version(self.db, req.dataset_id, None)

        # The read + compute are CPU/IO-bound pandas work: run them in a worker
        # thread so a big dataset can't stall the event loop (and with it every
        # other request and the scheduler).
        def _compute() -> PreviewResponse:
            df = self.engine.read(version.location, version.dataset.source_type)
            # ML nodes expose a data-aware validation hook (column presence,
            # row/feature limits) that needs the upstream schema. Preview has
            # the real dataset in hand, so run it here to surface those errors
            # in the node config UI.
            self._validate_with_schema(transformation, req.config, df)
            # preview_mode keeps ML nodes from fitting/logging during a preview.
            with preview_mode():
                result = transformation.execute(self.engine, {"in": df}, req.config)
            out = result.get("out", next(iter(result.values())))
            return self._to_response(out, req.limit, req.profile)

        return await asyncio.to_thread(_compute)

    async def preview_flow(self, flow_id: str, req: FlowPreviewRequest) -> PreviewResponse:
        flow = await self._get_flow(flow_id)
        # Same ML feature gate as a run — previewing executes the graph too.
        from app.ml.availability import guard_graph_ml_enabled

        guard_graph_ml_enabled(flow.graph_json)
        # Resolve flow parameters so the preview reflects the values a run would use.
        try:
            graph, _ = apply_parameters(flow.graph_json, req.parameters or {})
        except ParameterError as exc:
            raise ValidationError(str(exc)) from exc

        # Only the previewed node's upstream slice is computed: unrelated
        # branches cost time, and a failing node elsewhere (violated assertion,
        # typo'd column) must not break this node's preview.
        try:
            node_id = req.node_id or self._default_node(graph)
            if not any(n.get("id") == node_id for n in graph.get("nodes", [])):
                raise NotFoundError("Node", node_id)
            graph = ancestor_subgraph(graph, node_id)
        except GraphValidationError as exc:
            # A malformed graph (no nodes, dangling edge, cycle) is a bad
            # request, not a server error.
            raise ValidationError(str(exc)) from exc
        dataset_paths, _ = await build_dataset_paths(self.db, graph)

        # SQL and storage inputs are materialized into parquet snapshots in a temp
        # dir that lives only for the duration of the in-memory compute.
        with tempfile.TemporaryDirectory() as tmp:
            sql_input_paths = (
                await materialize_sql_inputs(self.db, graph, Path(tmp), limit=_PREVIEW_SQL_ROWS)
                if has_sql_inputs(graph)
                else {}
            )
            storage_input_paths = (
                await materialize_storage_inputs(self.db, graph, Path(tmp), limit=_PREVIEW_STORAGE_ROWS)
                if has_storage_inputs(graph)
                else {}
            )

            # The graph compute is CPU-bound pandas work: run it in a worker
            # thread so a heavy preview can't stall the event loop (and with it
            # every other request and the scheduler).
            def _compute() -> PreviewResponse:
                # preview_mode keeps ML nodes from fitting/logging in a preview.
                with preview_mode():
                    frames = FlowExecutor().compute_frames(
                        graph,
                        dataset_paths,
                        self.engine,
                        require_output=False,
                        sql_input_paths=sql_input_paths,
                        storage_input_paths=storage_input_paths,
                    )
                return self._to_response(frames[node_id], req.limit, req.profile)

            try:
                return await asyncio.to_thread(_compute)
            except GraphValidationError as exc:
                # An invalid graph (no nodes, dangling edge, cycle) is a bad
                # request, not a server error.
                raise ValidationError(str(exc)) from exc
            except NodeExecutionError as exc:
                # A node failing on the user's data/config (violated assertion,
                # missing column) is their flow's problem — report it with the
                # node named, not as a bare 500.
                raise ValidationError(str(exc)) from exc

    # -- Internals ------------------------------------------------------

    def _validate_with_schema(self, transformation: BaseTransformation, config: dict[str, Any], df: AnyFrame) -> None:
        """Run an ML node's schema-aware validation against the previewed dataset.

        Non-ML transformations don't have this hook, so this is a no-op for them.
        """
        from app.engine.transformations.ml.base import MLSchema, MLTransformation

        if not isinstance(transformation, MLTransformation):
            return
        schema = MLSchema(
            columns=[str(c) for c in df.columns],
            row_count=int(self.engine.row_count(df)),
        )
        try:
            transformation.validate_with_schema(config, schema)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def _get_transformation(self, node_type: str) -> BaseTransformation:
        try:
            return get_transformation(node_type)
        except KeyError as exc:
            raise NotFoundError("Transformation", node_type) from exc

    def _to_response(self, df: AnyFrame, limit: int, profile: bool = False) -> PreviewResponse:
        total = self.engine.row_count(df)
        return PreviewResponse(
            columns=list(df.columns),
            rows=self.engine.to_records(df, limit),
            row_count=total,
            truncated=total > limit,
            profile=profile_frame(self.engine, df) if profile else None,
        )

    def _default_node(self, graph: dict[str, Any]) -> str:
        # The deepest node in topological order is the natural preview target.
        order = topological_sort(graph)
        if not order:
            raise ValidationError("The flow has no nodes to preview.")
        return order[-1]

    async def _get_flow(self, flow_id: str) -> Flow:
        result = await self.db.execute(select(Flow).where(Flow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        return flow
