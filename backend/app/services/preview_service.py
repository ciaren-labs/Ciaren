# SPDX-License-Identifier: AGPL-3.0-only
import asyncio
import os
import re
import tempfile
from collections.abc import Callable, Mapping
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
from app.engine.executor import FlowExecutor, NodeExecutionError, _build_inputs
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
PREVIEW_MAX_CELLS = 2_000_000
PREVIEW_DEADLINE_SECONDS = 15.0
PREVIEW_MAX_JSON_BYTES = 16 * 1024 * 1024
PREVIEW_MAX_NODES = 80
PREVIEW_MAX_EDGES = 160
PREVIEW_MAX_FAN_IN = 8

# Registry types a preview may execute. Every registered type is either here or in
# PREVIEW_EXCLUDED; a contract test fails for a new type until it is classified.
# File inputs and fileOutput are not transformations: inputs are checked against
# the project and fileOutput only passes its input through during a preview.
PREVIEW_SAFE_TYPES: frozenset[str] = frozenset(
    {
        # Core
        "assertNotNull", "assertRowCount", "assertUnique", "assertValueRange", "assertValuesInSet",
        "binColumn", "castDtypes", "coalesceColumns", "combineColumns", "concatRows", "conditionalColumn",
        "dateDifference", "dropColumns", "dropNulls", "explodeRows", "extractDateParts", "fillNulls",
        "filterRows", "groupByAggregate", "join", "limitRows", "mapValues", "parseDates", "pivot",
        "removeDuplicates", "removeOutliers", "renameColumns", "replaceValues", "rollingAggregate",
        "roundNumbers", "rowDifference", "sampleRows", "selectColumns", "sortRows", "splitColumn",
        "stringTransform", "unpivot", "windowFunction",
        # Charts pass their input through during a preview.
        "chartArea", "chartBar", "chartBoxPlot", "chartHeatmap", "chartHistogram", "chartLine",
        "chartPie", "chartScatter",
        # ML: preview mode never fits, logs or loads a model.
        "encodeCategories", "featureImportance", "mlClassifierModel", "mlCrossValidate", "mlEvaluate",
        "mlPredict", "mlRegressorModel", "mlTrainClassifier", "mlTrainClustering", "mlTrainDimReduction",
        "mlTrainRegressor", "reduceDimensions", "scaleFeatures", "selectFeatures",
        "trainTestSplit",
    }
)  # fmt: skip
_EXPRESSION_REASON = "evaluates a user expression with pandas eval; runs only after expression_guard accepts it"
PREVIEW_EXCLUDED: dict[str, str] = {
    "pythonTransform": "runs arbitrary Python with exec; never previewed",
    "mlTrainForecaster": "no runnable estimator yet, so its output size cannot be verified",
    "calculatedColumn": _EXPRESSION_REASON,
    "filterExpression": _EXPRESSION_REASON,
    "assertExpression": _EXPRESSION_REASON,
}
# Excluded types that a caller-supplied guard can admit, and the config fields it checks.
PREVIEW_EXPRESSION_TYPES: frozenset[str] = frozenset({"calculatedColumn", "filterExpression", "assertExpression"})
_EXPRESSION_FIELDS = ("expression",)
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
    Output sizes are estimated per node by ``_PreviewExecutor`` from ``EXPANSION``.
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


Estimate = tuple[int, int]
Estimator = Callable[[dict[str, pd.DataFrame], dict[str, Any]], Estimate]


def _as_list(value: Any) -> list[str] | None:
    if not value:
        return None
    return [value] if isinstance(value, str) else list(value)


def _frames(inputs: dict[str, pd.DataFrame]) -> list[pd.DataFrame]:
    return [f for f in inputs.values() if isinstance(f, pd.DataFrame)]


def _largest(inputs: dict[str, pd.DataFrame]) -> Estimate:
    frames = _frames(inputs)
    return max((len(f) for f in frames), default=1), max((len(f.columns) for f in frames), default=0)


def _join(inputs: dict[str, pd.DataFrame], config: dict[str, Any]) -> Estimate:
    left, right = inputs["left"], inputs["right"]
    how = config.get("how", "inner")
    left_keys, right_keys = _as_list(config.get("left_on")), _as_list(config.get("right_on"))
    if not (left_keys and right_keys):
        left_keys = right_keys = _as_list(config.get("on"))
    width = len(left.columns) + len(right.columns)
    if how == "cross":
        return len(left) * len(right), width
    if how in ("semi", "anti") or not left_keys or not right_keys:
        return len(left), width  # semi/anti keep a subset of the left rows
    counts = left.groupby(left_keys, dropna=False).size()
    other = right.groupby(right_keys, dropna=False).size()
    other.index = other.index.set_names(list(counts.index.names))
    # Matched pairs plus every row unmatched on either side bounds all join kinds.
    return int((counts * other).sum()) + len(left) + len(right), width


def _concat(inputs: dict[str, pd.DataFrame], config: dict[str, Any]) -> Estimate:
    frames = _frames(inputs)
    return sum(len(f) for f in frames), len({c for f in frames for c in f.columns})


def _unpivot(inputs: dict[str, pd.DataFrame], config: dict[str, Any]) -> Estimate:
    df = inputs["in"]
    id_vars = config.get("id_vars") or []
    melted = len(config.get("value_vars") or []) or len(df.columns) - len(id_vars)
    return len(df) * max(melted, 0), len(id_vars) + 2


def _explode(inputs: dict[str, pd.DataFrame], config: dict[str, Any]) -> Estimate:
    df = inputs["in"]
    values = df[config["column"]]
    delimiter = config.get("delimiter") or None
    # The same split the engine runs (a multi-character delimiter is a regex there).
    lists = values.astype("string").str.split(delimiter) if delimiter else values
    pieces = lists.map(lambda v: max(len(v), 1) if isinstance(v, list | tuple) else 1)
    return int(pieces.sum()), len(df.columns)


def _pivot(inputs: dict[str, pd.DataFrame], config: dict[str, Any]) -> Estimate:
    df = inputs["in"]
    index = _as_list(config.get("index")) or []
    rows = int(df.groupby(index, dropna=False).ngroups) if index else 1
    return rows, len(index) + int(df[config["columns"]].nunique(dropna=False))


def _split_column(inputs: dict[str, pd.DataFrame], config: dict[str, Any]) -> Estimate:
    df = inputs["in"]
    into = len(config.get("into") or [])
    if config.get("mode", "delimiter") == "regex":
        pieces = re.compile(config.get("pattern") or "").groups
    else:
        # The engine splits literally and expands every piece before keeping ``into``.
        counts = df[config["column"]].astype("string").str.count(re.escape(config.get("delimiter") or ","))
        pieces = int(counts.max()) + 1 if counts.notna().any() else 1
    return len(df), len(df.columns) + max(into, pieces)


def _encode_categories(inputs: dict[str, pd.DataFrame], config: dict[str, Any]) -> Estimate:
    df = inputs["in"]
    if config.get("method", "onehot") != "onehot":
        return len(df), len(df.columns)
    added = sum(int(df[c].nunique(dropna=False)) for c in config.get("columns") or [])
    return len(df), len(df.columns) + added


def _reduce_dimensions(inputs: dict[str, pd.DataFrame], config: dict[str, Any]) -> Estimate:
    df = inputs["in"]
    components = config.get("n_components")
    return len(df), len(df.columns) + (components if isinstance(components, int) and components > 0 else 0)


# How each safe type sizes its output. "bounded" means at most the largest input's
# rows and its columns plus BOUNDED_EXTRA_COLUMNS and one column per config list
# entry (a test checks each label on a
# fixture). An estimator returns (rows, columns), computed with the engine's own
# semantics on the sampled inputs before the node runs.
BOUNDED_EXTRA_COLUMNS = 16
_EXPANDING: dict[str, Estimator] = {
    "join": _join,
    "concatRows": _concat,
    "unpivot": _unpivot,
    "explodeRows": _explode,
    "pivot": _pivot,
    "splitColumn": _split_column,
    "encodeCategories": _encode_categories,
    "reduceDimensions": _reduce_dimensions,
}
EXPANSION: dict[str, Estimator | Literal["bounded"]] = {
    kind: _EXPANDING.get(kind, "bounded") for kind in PREVIEW_SAFE_TYPES
}


def _config_entries(config: Any) -> int:
    """Entries in every list of a config: an upper bound on the columns it can name.

    A "bounded" node can still repeat names (``selectColumns`` with a duplicated
    list), so its width estimate counts each listed entry once more.
    """
    if isinstance(config, dict):
        return sum(_config_entries(v) for v in config.values())
    if isinstance(config, list | tuple):
        return len(config) + sum(_config_entries(v) for v in config if isinstance(v, dict | list | tuple))
    return 0


def _check_size(rows: int, cols: int) -> None:
    if rows > PREVIEW_MAX_NODE_ROWS or rows * max(cols, 1) > PREVIEW_MAX_CELLS:
        raise PreviewLimit("node output would exceed the preview row or cell cap")


class _PreviewExecutor(FlowExecutor):
    """Sizes each node from its inputs before it runs and checks the result after.

    The deadline is checked before and after every node. It is cooperative: a
    thread cannot be interrupted inside one node, so a single slow operation (for
    example a pathological regex) can overrun it. The size caps keep each node small.
    """

    def __init__(self, deadline: float) -> None:
        super().__init__()
        self.deadline = deadline

    def _node_outputs(
        self, engine: Any, node: dict[str, Any], incoming: dict[str, Any], outputs: dict[str, Any], *rest: Any
    ) -> Any:
        if monotonic() >= self.deadline:
            raise PreviewLimit("preview deadline reached")
        rule = EXPANSION.get(node["type"])
        if rule is not None:
            inputs = _build_inputs(incoming.get(node["id"], []), outputs)
            if rule == "bounded":
                rows, cols = _largest(inputs)
                extra = BOUNDED_EXTRA_COLUMNS + _config_entries(node["data"]["config"])
                _check_size(rows, cols + extra)
            else:
                _check_size(*rule(inputs, node["data"]["config"]))
        result = super()._node_outputs(engine, node, incoming, outputs, *rest)
        for frame in result[0].values():
            _check_size(len(frame), len(frame.columns))
        if monotonic() >= self.deadline:
            raise PreviewLimit("preview deadline reached")
        return result


def _shape_issues(graph: dict[str, Any]) -> list[Issue]:
    nodes, edges = graph.get("nodes", []), graph.get("edges", [])
    if len(nodes) > PREVIEW_MAX_NODES or len(edges) > PREVIEW_MAX_EDGES:
        return [Issue(None, "limit", "graph exceeds the preview node or edge limit")]
    fan_in: dict[str, int] = {}
    for edge in edges:
        fan_in[edge.get("target")] = fan_in.get(edge.get("target"), 0) + 1
    return [
        Issue(target, "limit", "node exceeds the preview fan-in limit")
        for target, count in fan_in.items()
        if count > PREVIEW_MAX_FAN_IN
    ]


def _policy_issues(graph: dict[str, Any], expression_guard: Callable[[str], None] | None) -> list[Issue]:
    """Fail closed: only file inputs, fileOutput and PREVIEW_SAFE_TYPES may run.
    Expression nodes also run once ``expression_guard`` accepts every expression."""
    issues = []
    for node in graph.get("nodes", []):
        kind = node.get("type")
        config = (node.get("data") or {}).get("config") or {}
        if kind in ASSISTANT_INPUTS or kind == FILE_OUTPUT_TYPE:
            continue
        allowed = kind in PREVIEW_SAFE_TYPES or (
            kind in PREVIEW_EXPRESSION_TYPES and _guard_accepts(config, expression_guard)
        )
        if (
            not allowed
            # Same name, different code: a registered type must still be the built-in.
            or not _is_builtin(kind)
            # A model URI loads a pickled model from disk.
            or (kind == "mlPredict" and config.get("model_uri"))
        ):
            issues.append(Issue(node.get("id"), "policy", f"{kind} is not allowed in an assistant preview"))
    return issues


def _is_builtin(kind: str) -> bool:
    try:
        return type(get_transformation(kind)).__module__.startswith(_BUILTIN_MODULE_PREFIX)
    except KeyError:
        return False


def _guard_accepts(config: dict[str, Any], expression_guard: Callable[[str], None] | None) -> bool:
    if expression_guard is None:
        return False
    for name in _EXPRESSION_FIELDS:
        value = config.get(name)
        if not isinstance(value, str):
            return False
        try:
            expression_guard(value)
        # The guard signals rejection by raising; any exception refuses the node.
        except Exception:  # noqa: BLE001
            return False
    return True


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
    *,
    expression_guard: Callable[[str], None] | None = None,
) -> GraphPreview:
    """Preview an unsaved graph on the first ``sample_rows`` rows of each input.

    Nodes outside the preview allowlist return ``policy`` issues before anything
    runs. Expression nodes are allowed only when ``expression_guard`` returns for
    each of their expressions; it rejects one by raising. Graph shape limits, size
    estimates, the row cap and the deadline return ``limit`` issues.

    With ``node_id`` only that node's upstream slice is computed; without it the
    whole graph is computed and the deepest node is the target. Every input must
    be an available file dataset of ``project_id``, otherwise ``ValidationError``.
    Graph and node failures come back as ``issues`` so the caller can repair them.
    ML nodes are validated against their upstream schema and never fit.
    """
    if shape := _shape_issues(graph):
        return GraphPreview(node_id or "", None, issues=shape)
    try:
        graph, _ = apply_parameters(graph, {})
        target, graph = _slice(graph, node_id) if node_id else (_default_node(graph), graph)
    except (GraphValidationError, ParameterError) as exc:
        return GraphPreview(node_id or "", None, issues=[Issue(None, classify_issue(exc), str(exc))])
    # Checked before anything reads or executes.
    if policy := _policy_issues(graph, expression_guard):
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
