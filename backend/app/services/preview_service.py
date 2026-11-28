# SPDX-License-Identifier: AGPL-3.0-only
import asyncio
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from itertools import islice
from pathlib import Path
from time import monotonic
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
from app.engine.node_kinds import FILE_OUTPUT_TYPE
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
from app.services.assistant_graph import INPUTS as ASSISTANT_INPUTS
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
    executor: FlowExecutor | None = None,
) -> dict[str, AnyFrame]:
    # preview_mode keeps ML nodes from fitting/logging in a preview.
    with preview_mode():
        return (executor or FlowExecutor()).compute_frames(
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
# The only text a model ever sees for an issue, besides refs. Raw exception text
# can carry data values in any shape, so it never leaves the server.
ISSUE_TEMPLATES: dict[str, str] = {
    "missing_column": "A referenced column is not available at this node.",
    "bad_type": "A column has a type this node cannot use.",
    "bad_port": "A connection uses a missing or invalid port.",
    "cycle": "The connections form a cycle.",
    "policy": "This node type cannot run in an assistant preview.",
    "limit": "The preview exceeded a size or time limit.",
    "config": "The node configuration is invalid.",
}
_REF = re.compile(r"[a-z][a-z0-9_]{0,23}")

# Resource bounds for one assistant preview. Module globals so tests can lower them.
PREVIEW_MAX_NODE_ROWS = 50_000
PREVIEW_DEADLINE_SECONDS = 15.0
PREVIEW_MAX_JSON_BYTES = 16 * 1024 * 1024
# Built-ins that evaluate user-written code or expressions. They wait for the
# assistant expression guard; preview never runs them.
_CODE_NODE_TYPES = frozenset({"pythonTransform", "filterExpression", "createCalculatedColumn", "assertExpression"})
_BUILTIN_MODULE_PREFIX = "app.engine.transformations."


class PreviewLimit(Exception):
    """A preview resource bound was reached."""


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
    row stream, so they are parsed whole only below ``PREVIEW_MAX_JSON_BYTES``.
    Joins are sized from key counts before they run.
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
        elif source_type == "json" and os.path.getsize(path) > PREVIEW_MAX_JSON_BYTES:
            raise PreviewLimit("JSON input is too large to sample")
        elif source_type == "text":
            with open(path, encoding="utf-8") as fh:
                df = pd.DataFrame({"text": [line.rstrip("\r\n") for line in islice(fh, n)]})
        else:
            df = super().read(path, source_type)
        if len(df) > self.rows:
            self.truncated = True
            df = df.head(self.rows)
        return df

    def join(
        self,
        left: pd.DataFrame,
        right: pd.DataFrame,
        on: list[str] | None,
        how: str,
        left_on: list[str] | None = None,
        right_on: list[str] | None = None,
        suffixes: tuple[str, str] = ("_x", "_y"),
    ) -> pd.DataFrame:
        left_keys, right_keys = (left_on, right_on) if left_on and right_on else (on, on)
        if how == "cross":
            estimate = len(left) * len(right)
        elif how in ("semi", "anti") or not left_keys or not right_keys:
            estimate = 0  # semi/anti keep a subset of the left rows; keyless joins fail validation
        else:
            counts = left.groupby(left_keys, dropna=False).size()
            other = right.groupby(right_keys, dropna=False).size()
            other.index = other.index.set_names(list(counts.index.names))
            # Matched pairs plus every row unmatched on either side bounds all join kinds.
            estimate = int((counts * other).sum()) + len(left) + len(right)
        if estimate > PREVIEW_MAX_NODE_ROWS:
            raise PreviewLimit("join output would exceed the preview row cap")
        return super().join(left, right, on, how, left_on, right_on, suffixes)


class _PreviewExecutor(FlowExecutor):
    """Stops between nodes at the row cap or the deadline.

    The deadline is cooperative: a thread cannot be interrupted mid-node, and the
    per-node and join caps keep each node small.
    """

    def __init__(self, deadline: float) -> None:
        super().__init__()
        self.deadline = deadline

    def _node_outputs(self, engine: Any, *args: Any) -> Any:
        result = super()._node_outputs(engine, *args)
        if any(engine.row_count(frame) > PREVIEW_MAX_NODE_ROWS for frame in result[0].values()):
            raise PreviewLimit("node output exceeds the preview row cap")
        if monotonic() >= self.deadline:
            raise PreviewLimit("preview deadline reached")
        return result


def _policy_issues(graph: dict[str, Any]) -> list[Issue]:
    """Fail closed: only file inputs, the pass-through file output and built-in
    core/ML transformations that run no user code may execute in a preview."""
    issues = []
    for node in graph.get("nodes", []):
        kind = node.get("type")
        config = (node.get("data") or {}).get("config") or {}
        if kind in ASSISTANT_INPUTS or kind == FILE_OUTPUT_TYPE:
            continue
        try:
            module = type(get_transformation(kind)).__module__
        except (KeyError, TypeError):
            module = ""
        if (
            kind in _CODE_NODE_TYPES
            or not module.startswith(_BUILTIN_MODULE_PREFIX)
            # A model URI loads a pickled model from disk.
            or (kind == "mlPredict" and config.get("model_uri"))
        ):
            issues.append(Issue(node.get("id"), "policy", f"{kind} is not allowed in an assistant preview"))
    return issues


def classify_issue(exc: BaseException) -> IssueCode:
    """Map a preview failure onto the stable issue code the assistant sees."""
    text = str(exc).lower()
    if isinstance(exc, PreviewLimit):
        return "limit"
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


def redact_issue(message: str, code: str, refs: Mapping[str, str]) -> dict[str, str]:
    """Model-facing form of an issue: the fixed template for ``code`` plus the refs
    of known names (columns, nodes) that appear in ``message``.

    Nothing else from ``message`` is copied, and only values shaped like refs are
    emitted, so unknown names and data values cannot leak.
    """
    if code not in ISSUE_CODES:
        raise ValueError(f"Unknown issue code {code!r}")
    found = sorted(
        {
            ref
            for name, ref in refs.items()
            if name and _REF.fullmatch(ref) and re.search(rf"(?<!\w){re.escape(name)}(?!\w)", message)
        }
    )
    suffix = f" Refs: {', '.join(found)}." if found else ""
    return {"code": code, "message": (ISSUE_TEMPLATES[code] + suffix)[:200]}


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

    Nodes outside the preview allowlist return ``policy`` issues before anything
    runs; the row cap, join estimate and deadline return ``limit`` issues.

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
    # Checked before anything reads or executes.
    if policy := _policy_issues(graph):
        return GraphPreview(target, None, issues=policy)
    # build_dataset_paths is not project-scoped, so every input is checked first.
    for node in graph.get("nodes", []):
        if node.get("type") in ASSISTANT_INPUTS:
            await resolve_input(db, project_id, None, node)
    from app.ml.availability import guard_graph_ml_enabled

    guard_graph_ml_enabled(graph)
    dataset_paths, _ = await build_dataset_paths(db, graph)
    engine = _SampleEngine(sample_rows)
    executor = _PreviewExecutor(monotonic() + PREVIEW_DEADLINE_SECONDS)

    def _compute() -> GraphPreview:
        try:
            frames = _compute_frames(graph, dataset_paths, engine, executor=executor)
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
