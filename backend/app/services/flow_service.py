# SPDX-License-Identifier: AGPL-3.0-only
import copy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.flow import Flow
from app.db.models.run import FlowRun
from app.engine.node_kinds import INPUT_TYPES as _INPUT_TYPES
from app.engine.node_kinds import OUTPUT_TYPES as _OUTPUT_TYPES
from app.engine.parameters import ParameterError, validate_parameter_specs
from app.engine.registry import list_transformation_types
from app.schemas.flow import FlowCreate, FlowImport, FlowRead, FlowUpdate
from app.services.project_service import ProjectService

# Config keys that bind a node to *this* environment (a specific uploaded dataset,
# a saved connection). They are stripped on import so the flow is portable; the
# importer re-selects them. (model_uri is a logical MLflow reference, kept as-is.)
_ENV_BOUND_CONFIG_KEYS = ("dataset_id", "dataset_version", "connection_id")


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
        flows = list(result.scalars().all())
        return await self._with_last_run(flows)

    async def list_using_dataset(self, dataset_id: str) -> list[FlowRead]:
        """Flows whose graph has an input node bound to ``dataset_id`` (lineage)."""
        result = await self.db.execute(select(Flow).order_by(Flow.updated_at.desc()))
        matches = [f for f in result.scalars().all() if _references_dataset(f.graph_json, dataset_id)]
        return await self._with_last_run(matches)

    async def _with_last_run(self, flows: list[Flow]) -> list[FlowRead]:
        """Attach each flow's most-recent run time in a single grouped query."""
        if not flows:
            return []
        ids = [f.id for f in flows]
        rows = await self.db.execute(
            select(FlowRun.flow_id, func.max(FlowRun.created_at))
            .where(FlowRun.flow_id.in_(ids))
            .group_by(FlowRun.flow_id)
        )
        last_run: dict[str, datetime] = {fid: ts for fid, ts in rows.all()}
        reads: list[FlowRead] = []
        for f in flows:
            read = FlowRead.model_validate(f)
            read.last_run_at = last_run.get(f.id)
            reads.append(read)
        return reads

    async def create(self, data: FlowCreate) -> FlowRead:
        self._validate_parameters(data.graph_json)
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

    async def import_flow(self, data: FlowImport) -> FlowRead:
        """Create a flow from an exported document, stripping environment-specific
        bindings so it is portable across machines (CI/CD friendly)."""
        graph = self._sanitize_imported_graph(data.graph_json)
        project_id = await ProjectService(self.db).resolve_id(data.project_id)
        flow = Flow(
            name=(data.name or "Imported flow").strip()[:255] or "Imported flow",
            description=data.description,
            project_id=project_id,
            graph_json=graph,
        )
        self.db.add(flow)
        await self.db.commit()
        await self.db.refresh(flow)
        return FlowRead.model_validate(flow)

    def _sanitize_imported_graph(self, graph: Any) -> dict[str, Any]:
        """Validate structure + node types and drop environment-specific config.

        Deliberately lenient about config completeness (a stripped input has no
        dataset yet): the editor and save/run validation surface what still needs
        wiring. We only reject things that make the graph unusable — unknown node
        types or edges that point at missing nodes."""
        if not isinstance(graph, dict):
            raise ValidationError("graph_json must be an object with 'nodes' and 'edges'.")
        nodes = graph.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            raise ValidationError("The flow has no nodes to import.")

        known = set(list_transformation_types()) | _INPUT_TYPES | _OUTPUT_TYPES
        node_ids: set[str] = set()
        unknown: set[str] = set()
        clean_nodes: list[dict[str, Any]] = []
        for node in nodes:
            if not isinstance(node, dict) or not node.get("id") or not node.get("type"):
                raise ValidationError("Every node needs an 'id' and a 'type'.")
            node_type = node["type"]
            if node_type not in known:
                unknown.add(node_type)
                continue
            node_ids.add(node["id"])
            clean = copy.deepcopy(node)
            config = clean.setdefault("data", {}).setdefault("config", {})
            if isinstance(config, dict):
                for key in _ENV_BOUND_CONFIG_KEYS:
                    config.pop(key, None)
            clean_nodes.append(clean)

        if unknown:
            raise ValidationError(
                f"Unknown node types not available on this server: {sorted(unknown)}. "
                "Install the matching extra (e.g. [ml]) or edit the document."
            )

        clean_edges: list[dict[str, Any]] = []
        for edge in graph.get("edges", []) or []:
            if not isinstance(edge, dict):
                continue
            if edge.get("source") in node_ids and edge.get("target") in node_ids:
                clean_edges.append(copy.deepcopy(edge))

        return {"nodes": clean_nodes, "edges": clean_edges}

    async def get(self, flow_id: str) -> FlowRead:
        flow = await self._get_or_raise(flow_id)
        return FlowRead.model_validate(flow)

    async def update(self, flow_id: str, data: FlowUpdate) -> FlowRead:
        flow = await self._get_or_raise(flow_id)
        updates = data.model_dump(exclude_unset=True)
        if "graph_json" in updates:
            self._validate_parameters(updates["graph_json"])
        for field, value in updates.items():
            setattr(flow, field, value)
        # Explicit timestamp: SQLite's onupdate fires but doesn't reflect until refresh,
        # and SQLite's second-level resolution means tests may see the same value.
        flow.updated_at = datetime.now(UTC).replace(tzinfo=None)
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

    def _validate_parameters(self, graph: Any) -> None:
        """Reject a malformed ``parameters`` list at save time (clear 400) instead
        of letting it surface only when the flow is run."""
        if not isinstance(graph, dict):
            return
        try:
            validate_parameter_specs(graph)
        except ParameterError as exc:
            raise ValidationError(str(exc)) from exc

    async def _get_or_raise(self, flow_id: str) -> Flow:
        result = await self.db.execute(select(Flow).where(Flow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        return flow
