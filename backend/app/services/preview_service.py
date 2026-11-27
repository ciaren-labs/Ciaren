# SPDX-License-Identifier: AGPL-3.0-only
import asyncio
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from itertools import islice
from pathlib import Path
from typing import Any, Literal, get_args

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.flow import Flow
from app.engine.backends import AnyFrame, EngineBackend, get_engine
from app.engine.backends.pandas_engine import PandasEngine
from app.engine.executor import FlowExecutor, NodeExecutionError
from app.engine.graph import GraphValidationError, ancestor_subgraph, topological_sort
from app.engine.node_kinds import INPUT_TYPES
from app.engine.parameters import ParameterError, apply_parameters
from app.engine.preview_context import preview_mode
from app.engine.profile import profile_frame
from app.engine.registry import get_transformation, ml_node_types
from app.engine.transformations.base import BaseTransformation
from app.schemas.preview import (
    FlowPreviewRequest,
    PreviewResponse,
    TransformationPreviewRequest,
)
from app.services.assistant_inputs import resolve_input
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
        # Mirrors ExecutionService.run(): a disabled flow (e.g. its dataset was
        # deleted/disabled and cascaded the disable) must not execute any part of
        # its graph, even a branch fed by a different, still-enabled input —
        # preview was the one execution path that didn't check this.
        if flow.is_disabled:
            raise ValidationError("This flow is disabled and cannot be previewed.")
        # Resolve flow parameters so the preview reflects the values a run would use.
        try:
            graph, _ = apply_parameters(flow.graph_json, req.parameters or {})
        except ParameterError as exc:
            raise ValidationError(str(exc)) from exc

        # Only the previewed node's upstream slice is computed: unrelated
        # branches cost time, and a failing node elsewhere (violated assertion,
        # typo'd column) must not break this node's preview.
        try:
            node_id, graph = _slice(graph, req.node_id)
        except GraphValidationError as exc:
            # A malformed graph (no nodes, dangling edge, cycle) is a bad
            # request, not a server error.
            raise ValidationError(str(exc)) from exc
        # Same ML feature gate as a run — previewing executes the slice. After
        # pruning on purpose: an ML node on an unrelated branch must not block
        # previewing a clean ETL node when ML is unavailable.
        from app.ml.availability import guard_graph_ml_enabled

        guard_graph_ml_enabled(graph)
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
                frames = _compute_frames(graph, dataset_paths, self.engine, sql_input_paths, storage_input_paths)
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
        try:
            _check_ml_schema(transformation, config, [str(c) for c in df.columns], int(self.engine.row_count(df)))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def _get_transformation(self, node_type: str) -> BaseTransformation:
        try:
            return get_transformation(node_type)
        except KeyError as exc:
            raise NotFoundError("Transformation", node_type) from exc

    def _to_response(self, df: AnyFrame, limit: int, profile: bool = False) -> PreviewResponse:
        return _response(self.engine, df, limit, profile)

    async def _get_flow(self, flow_id: str) -> Flow:
        result = await self.db.execute(select(Flow).where(Flow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        return flow


def _response(engine: EngineBackend, df: AnyFrame, limit: int, profile: bool) -> PreviewResponse:
    total = engine.row_count(df)
    return PreviewResponse(
        columns=list(df.columns),
        rows=engine.to_records(df, limit),
        row_count=total,
        truncated=total > limit,
        profile=profile_frame(engine, df) if profile else None,
    )


def _default_node(graph: dict[str, Any]) -> str:
    # The deepest node in topological order is the natural preview target.
    order = topological_sort(graph)
    if not order:
        raise ValidationError("The flow has no nodes to preview.")
    return order[-1]


def _slice(graph: dict[str, Any], node_id: str | None) -> tuple[str, dict[str, Any]]:
    """Return the preview target and the upstream slice that computes it."""
    target = node_id or _default_node(graph)
    if not any(n.get("id") == target for n in graph.get("nodes", [])):
        raise NotFoundError("Node", target)
    return target, ancestor_subgraph(graph, target)


def _compute_frames(
    graph: dict[str, Any],
    dataset_paths: dict[str, Path],
    engine: EngineBackend,
    sql_input_paths: dict[str, Path] | None = None,
    storage_input_paths: dict[str, Path] | None = None,
) -> dict[str, AnyFrame]:
    # preview_mode keeps ML nodes from fitting/logging in a preview.
    with preview_mode():
        return FlowExecutor().compute_frames(
            graph,
            dataset_paths,
            engine,
            require_output=False,
            sql_input_paths=sql_input_paths,
            storage_input_paths=storage_input_paths,
        )


def _check_ml_schema(
    transformation: BaseTransformation, config: dict[str, Any], columns: list[str], row_count: int | None
) -> None:
    """Run an ML node's data-aware validation; a no-op for every other node.

    Raises the node's ``ValueError`` unchanged so each caller chooses how to report it.
    """
    from app.engine.transformations.ml.base import MLSchema, MLTransformation

    if isinstance(transformation, MLTransformation):
        transformation.validate_with_schema(config, MLSchema(columns=columns, row_count=row_count))


# -- Unsaved-graph preview (assistant) ------------------------------------

IssueCode = Literal["missing_column", "bad_type", "bad_port", "cycle", "policy", "limit", "config"]
ISSUE_CODES: frozenset[str] = frozenset(get_args(IssueCode))


@dataclass(frozen=True)
class Issue:
    """A problem found while previewing. ``message`` is raw server-side text that
    may name columns and data values: pass it through :func:`redact_issue` before
    it leaves the server."""

    node: str | None
    code: IssueCode
    message: str


@dataclass
class GraphPreview:
    node: str
    # The target node's rows; None when the graph failed to compute.
    preview: PreviewResponse | None
    # (column, dtype) per computed node, in column order.
    schemas: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    # True when at least one input had more rows than the sample.
    sampled: bool = False


class _SampleEngine(PandasEngine):
    """Pandas engine whose reads stop after ``rows`` rows.

    It reads ``rows + 1`` rows so truncation is observable. JSON documents have no
    row stream and are parsed whole before slicing.
    """

    def __init__(self, rows: int) -> None:
        self.rows = rows
        self.truncated = False

    def read(self, path: str, source_type: str) -> pd.DataFrame:
        n = self.rows + 1
        if source_type in ("csv", "tsv"):
            df = pd.read_csv(path, nrows=n, sep="\t" if source_type == "tsv" else ",")
        elif source_type == "excel":
            df = pd.read_excel(path, nrows=n)
        elif source_type == "jsonl":
            df = pd.read_json(path, lines=True, nrows=n)
        elif source_type == "parquet":
            pf = pq.ParquetFile(path)  # type: ignore[no-untyped-call, unused-ignore]
            batches, seen = [], 0
            for batch in pf.iter_batches(batch_size=n):  # type: ignore[no-untyped-call, unused-ignore]
                batches.append(batch)
                seen += batch.num_rows
                if seen >= n:
                    break
            df = pa.Table.from_batches(batches, schema=pf.schema_arrow).to_pandas()
        elif source_type == "text":
            with open(path, encoding="utf-8") as fh:
                df = pd.DataFrame({"text": [line.rstrip("\r\n") for line in islice(fh, n)]})
        else:
            df = super().read(path, source_type)
        if len(df) > self.rows:
            self.truncated = True
            df = df.head(self.rows)
        return df


def classify_issue(exc: BaseException) -> IssueCode:
    """Map a preview failure onto the stable issue code the assistant sees."""
    text = str(exc).lower()
    if isinstance(exc, GraphValidationError):
        if "cycle" in text:
            return "cycle"
        if any(w in text for w in ("input", "output", "connection", "edge")):
            return "bad_port"
        return "config"
    if isinstance(exc, KeyError) or (
        "column" in text and any(w in text for w in ("not found", "not in", "missing", "unknown", "not exist"))
    ):
        return "missing_column"
    if isinstance(exc, TypeError) or any(w in text for w in ("dtype", "could not convert", "not numeric")):
        return "bad_type"
    if any(w in text for w in ("at least", "at most", "too many", "too few", "exceed")):
        return "limit"
    return "config"


_QUOTED = r"'([^']*)'|\"([^\"]*)\"|`([^`]*)`"


def redact_issue(message: str, code: str, refs: Mapping[str, str]) -> dict[str, str]:
    """Make an issue safe to show the model: real names become refs, every other
    quoted literal is dropped, and the text is capped at 200 characters."""
    if code not in ISSUE_CODES:
        raise ValueError(f"Unknown issue code {code!r}")
    bare = "|".join(re.escape(n) for n in sorted((n for n in refs if n), key=len, reverse=True))
    pattern = re.compile(_QUOTED + (rf"|(?<!\w)({bare})(?!\w)" if bare else ""))

    def swap(m: re.Match[str]) -> str:
        if m.lastindex == 4:
            return refs[m.group(4)]
        inner = next(g for g in m.groups()[:3] if g is not None)
        return f"'{refs[inner]}'" if inner in refs else "'…'"

    return {"code": code, "message": pattern.sub(swap, message)[:200]}


async def preview_graph(
    db: AsyncSession,
    project_id: str,
    graph: dict[str, Any],
    node_id: str | None,
    limit: int,
    profile: bool,
    sample_rows: int = 2000,
) -> GraphPreview:
    """Preview an unsaved graph on the first ``sample_rows`` rows of each input.

    With ``node_id`` only that node's upstream slice is computed; without it the
    whole graph is computed and the deepest node is the target. Every input must
    be an available file dataset of ``project_id``, otherwise ``ValidationError``.
    Graph and node failures come back as ``issues`` so the caller can repair them.
    ML nodes are validated against their upstream schema and never fit.
    """
    try:
        graph, _ = apply_parameters(graph, {})
        target, graph = _slice(graph, node_id) if node_id else (_default_node(graph), graph)
    except (GraphValidationError, ParameterError) as exc:
        return GraphPreview(node_id or "", None, issues=[Issue(None, classify_issue(exc), str(exc))])
    # build_dataset_paths is not project-scoped, so every input is checked first.
    for node in graph.get("nodes", []):
        if node.get("type") in INPUT_TYPES:
            await resolve_input(db, project_id, None, node)
    from app.ml.availability import guard_graph_ml_enabled

    guard_graph_ml_enabled(graph)
    dataset_paths, _ = await build_dataset_paths(db, graph)
    engine = _SampleEngine(sample_rows)

    def _compute() -> GraphPreview:
        try:
            frames = _compute_frames(graph, dataset_paths, engine)
        except GraphValidationError as exc:
            return GraphPreview(target, None, issues=[Issue(None, classify_issue(exc), str(exc))])
        except NodeExecutionError as exc:
            issue = Issue(exc.node_id, classify_issue(exc.original), str(exc.original))
            return GraphPreview(target, None, issues=[issue], sampled=engine.truncated)
        result = GraphPreview(
            target,
            _response(engine, frames[target], limit, profile),
            {nid: [(str(c), str(t)) for c, t in df.dtypes.items()] for nid, df in frames.items()},
            sampled=engine.truncated,
        )
        ml_types = ml_node_types()
        for node in graph["nodes"]:
            if node["type"] not in ml_types:
                continue
            source = next(
                (
                    e["source"]
                    for e in graph["edges"]
                    if e["target"] == node["id"] and e.get("targetHandle") in (None, "in")
                ),
                None,
            )
            if source is None:
                continue
            upstream = frames[source]
            try:
                _check_ml_schema(
                    get_transformation(node["type"]),
                    node["data"]["config"],
                    [str(c) for c in upstream.columns],
                    # A truncated sample would make row-count rules judge the sample.
                    None if engine.truncated else len(upstream),
                )
            except ValueError as exc:
                result.issues.append(Issue(node["id"], classify_issue(exc), str(exc)))
        return result

    return await asyncio.to_thread(_compute)
