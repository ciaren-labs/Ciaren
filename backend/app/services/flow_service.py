# SPDX-License-Identifier: AGPL-3.0-only
import copy
import logging
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.flow import DISABLED_BY_DATASET, DISABLED_MANUAL, Flow
from app.db.models.run import FlowRun
from app.engine.node_kinds import INPUT_TYPES as _INPUT_TYPES
from app.engine.node_kinds import OUTPUT_TYPES as _OUTPUT_TYPES
from app.engine.parameters import ParameterError, validate_parameter_specs
from app.engine.registry import list_transformation_types
from app.flow_schema import (
    CURRENT_SCHEMA_VERSION,
    FlowGraph,
    FlowSchemaError,
    MigrationError,
    document_version,
    migrate,
    validate,
    validate_document,
)
from app.schemas.flow import (
    FlowCreate,
    FlowImport,
    FlowMigrateDocumentResponse,
    FlowRead,
    FlowUpdate,
)
from app.services.project_service import ProjectService

# Config keys that bind a node to *this* environment (a specific uploaded dataset,
# a saved connection). They are stripped on import so the flow is portable; the
# importer re-selects them. (model_uri is a logical MLflow reference, kept as-is.)
_ENV_BOUND_CONFIG_KEYS = ("dataset_id", "dataset_version", "connection_id")

# A trailing " (N)" marker on a flow name, so duplicating a copy continues the
# sequence ("Sales (1)" -> "Sales (2)") instead of nesting ("Sales (1) (1)").
_COPY_SUFFIX_RE = re.compile(r"^(.*) \((\d+)\)$")

logger = logging.getLogger(__name__)


def _normalize_import_payload(data: FlowImport) -> dict[str, Any]:
    """Build the raw dict ``app.flow_schema.migrate``/``validate_document``
    expect from either import envelope: the legacy ``graph_json`` shape
    (today's real export format) or the versioned ``graph``/``schemaVersion``
    shape."""
    if data.graph is not None:
        raw: dict[str, Any] = {
            "graph": data.graph,
            "project": {"name": data.name or "Imported flow", "description": data.description},
        }
        if data.schema_version is not None:
            raw["schemaVersion"] = data.schema_version
        return raw
    return {
        "name": data.name or "Imported flow",
        "description": data.description,
        "graph_json": data.graph_json or {},
    }


def migrate_flow_document(data: dict[str, Any], target: str = CURRENT_SCHEMA_VERSION) -> FlowMigrateDocumentResponse:
    """Migrate/validate a raw ``.flow`` document to ``target`` without
    persisting anything — the standalone file-to-file utility backing
    ``POST /api/flows/migrate-document``. Unlike :meth:`FlowService.import_flow`,
    this uses the full ``validate()`` (shape + graph structure) since it's a
    generic file tool, decoupled from Ciaren's node-type registry, so
    structural issues (dangling edges, duplicate ids) should be reported as
    real errors."""
    from_version = document_version(data)
    try:
        document = validate(migrate(data, target=target))
    except (MigrationError, FlowSchemaError) as exc:
        raise ValidationError(str(exc)) from exc
    return FlowMigrateDocumentResponse(
        document=document.to_json_dict(),
        migrated=from_version != document.schema_version,
        from_version=from_version,
        to_version=document.schema_version,
    )


def _references_dataset(graph: dict[str, Any], dataset_id: str) -> bool:
    for node in FlowGraph.model_validate(graph).typed_nodes():
        if node.type not in _INPUT_TYPES:
            continue
        if node.config.get("dataset_id") == dataset_id:
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

    async def duplicate(self, flow_id: str, name: str | None = None) -> FlowRead:
        """Create an independent copy of a flow: same graph, parameters, engine
        choice, and disabled state; nothing operational comes along (no
        schedules, no run history — those belong to the original)."""
        original = await self._get_or_raise(flow_id)
        # An explicit name follows the same rules FlowCreate enforces: trimmed,
        # ≤255 (rejected, not silently truncated), and a blank one falls back to
        # the auto-numbered default. The default picks the next free " (N)"
        # within the same project (file-manager style), so repeated duplicates
        # never collide and per-project names stay distinct.
        trimmed = (name or "").strip()
        if len(trimmed) > 255:
            raise ValidationError("name must be at most 255 characters.")
        copy_name = trimmed or await self._next_copy_name(original.name, original.project_id)
        # Same parameter gate as create/update/import — but duplicate must not
        # fail on a legacy row that predates the gate, so copy verbatim and
        # log instead of raising; the copy fails loudly if it is ever run.
        try:
            self._validate_parameters(original.graph_json)
        except ValidationError as exc:
            logger.warning("Flow %s has invalid parameter specs (%s); duplicated verbatim.", flow_id, exc)
        flow = Flow(
            name=copy_name,
            description=original.description,
            project_id=original.project_id,
            graph_json=copy.deepcopy(original.graph_json),
            # An auto-disabled flow (e.g. its input dataset was deleted) must
            # not yield an enabled, schedulable copy with the same broken graph.
            # Carry the reason too so the copy behaves consistently under a later
            # project re-enable (a project-disabled copy is restored with it; a
            # dataset/manually-disabled copy stays off until fixed).
            is_disabled=original.is_disabled,
            disabled_reason=original.disabled_reason,
            disabled_by_project_id=original.disabled_by_project_id,
        )
        self.db.add(flow)
        await self.db.commit()
        await self.db.refresh(flow)
        return FlowRead.model_validate(flow)

    async def _next_copy_name(self, source_name: str, project_id: str | None) -> str:
        """Pick the next free ``base (N)`` name within ``project_id``.

        A trailing " (N)" on the source is stripped first so duplicating a copy
        continues the sequence ("Sales (1)" → "Sales (2)") rather than nesting.
        ``base`` is truncated so the suffix always fits in 255 chars, keeping the
        copy's name distinct from a max-length original."""
        match = _COPY_SUFFIX_RE.match(source_name)
        base = match.group(1) if match else source_name
        result = await self.db.execute(select(Flow.name).where(Flow.project_id == project_id))
        taken = {row[0] for row in result.all()}
        n = 1
        while True:
            suffix = f" ({n})"
            candidate = f"{base[: 255 - len(suffix)]}{suffix}"
            if candidate not in taken:
                return candidate
            n += 1

    async def import_flow(self, data: FlowImport) -> FlowRead:
        """Create a flow from an exported document, stripping environment-specific
        bindings so it is portable across machines (CI/CD friendly).

        Routes through ``app.flow_schema`` (migrate to the current schema
        version, then shape-validate) so a future ``schemaVersion`` bump has a
        real upgrade path instead of silently mis-parsing older exports. Uses
        ``validate_document`` (shape only), not the full ``validate`` — the
        latter treats dangling edges as a hard error, and import is
        deliberately lenient about those (they're dropped below instead)."""
        raw = _normalize_import_payload(data)
        try:
            document = validate_document(migrate(raw))
        except (MigrationError, FlowSchemaError) as exc:
            raise ValidationError(str(exc)) from exc
        graph = self._sanitize_imported_graph(document.graph.model_dump(mode="json"))
        # Same parameter-spec gate as create/update: an imported document with
        # invalid parameter names should fail here with a clear 400, not only
        # when the flow is first run.
        self._validate_parameters(graph)
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

        sanitized: dict[str, Any] = {"nodes": clean_nodes, "edges": clean_edges}
        # Flow-level keys the engine understands travel with the document
        # (parameters power {{ name }} references; engine picks pandas/polars).
        # Rebuilding only nodes+edges silently dropped both on import.
        for key in ("parameters", "engine"):
            if key in graph:
                sanitized[key] = copy.deepcopy(graph[key])
        return sanitized

    async def get(self, flow_id: str) -> FlowRead:
        flow = await self._get_or_raise(flow_id)
        return FlowRead.model_validate(flow)

    async def update(self, flow_id: str, data: FlowUpdate) -> FlowRead:
        flow = await self._get_or_raise(flow_id)
        updates = data.model_dump(exclude_unset=True)
        if "graph_json" in updates:
            self._validate_parameters(updates["graph_json"])
        # A move to another project must point at a real one — with SQLite FK
        # enforcement off, a bogus id would otherwise silently orphan the flow.
        if updates.get("project_id") is not None:
            updates["project_id"] = await ProjectService(self.db).resolve_id(updates["project_id"])
        # Capture before the setattr loop: a direct is_disabled *change* is the
        # user's own decision, so tag it MANUAL (or clear the reason on enable) so a
        # later project re-enable doesn't revive a flow the user turned off. Guard on
        # an actual change — a client that echoes is_disabled unchanged on an
        # unrelated save (e.g. a rename) must not flip a project-cascaded flow's
        # reason to MANUAL and thereby strand it disabled.
        disabled_changed = "is_disabled" in updates and updates["is_disabled"] != flow.is_disabled
        for field, value in updates.items():
            setattr(flow, field, value)
        if disabled_changed:
            flow.disabled_reason = DISABLED_MANUAL if updates["is_disabled"] else None
            flow.disabled_by_project_id = None
        # Explicit timestamp: SQLite's onupdate fires but doesn't reflect until refresh,
        # and SQLite's second-level resolution means tests may see the same value.
        flow.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.db.commit()
        await self.db.refresh(flow)
        return FlowRead.model_validate(flow)

    async def delete(self, flow_id: str) -> None:
        """Delete a flow along with its run history and schedules.

        The cascade is ORM-side (``Flow.runs`` / ``Flow.schedules``), so the
        relationships must be loaded before ``session.delete`` — an unloaded
        lazy relationship can't be fetched during the async flush.
        """
        result = await self.db.execute(
            select(Flow).options(selectinload(Flow.runs), selectinload(Flow.schedules)).where(Flow.id == flow_id)
        )
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        await self.db.delete(flow)
        await self.db.commit()

    async def disable_flows_for_dataset(self, dataset_id: str) -> None:
        """Disable all flows whose graph references the given dataset as an input.

        Tags them ``DISABLED_BY_DATASET`` (overriding a prior ``DISABLED_BY_PROJECT``
        tag) so re-enabling the *project* does not revive a flow whose dataset is
        still out of use."""
        result = await self.db.execute(select(Flow))
        changed = False
        for flow in result.scalars().all():
            if _references_dataset(flow.graph_json or {}, dataset_id):
                flow.is_disabled = True
                flow.disabled_reason = DISABLED_BY_DATASET
                flow.disabled_by_project_id = None
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
