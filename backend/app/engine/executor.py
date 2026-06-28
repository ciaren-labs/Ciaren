import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.engine.backends import AnyFrame, EngineBackend, get_engine
from app.engine.graph import GraphValidationError, topological_sort, validate_graph
from app.engine.node_kinds import INPUT_SOURCE_TYPES as _INPUT_TYPES
from app.engine.node_kinds import OUTPUT_SUFFIX as _OUTPUT_SUFFIX
from app.engine.node_kinds import OUTPUT_TYPES as _OUTPUT_TYPES
from app.engine.node_kinds import PRE_MATERIALIZED_INPUT_TYPES, primary_output_handle
from app.engine.node_kinds import output_source_type as _output_source_type
from app.engine.registry import get_transformation
from app.engine.transformations.base import EmitsNodeMetadata, NodeMetadata
from app.plugin_api.events import EventBus, Hook

# A node's outputs, keyed by source handle. Single-output nodes use ``{"out": df}``.
NodeOutputs = dict[str, AnyFrame]


@dataclass
class NodeResult:
    """Per-node outcome captured during a run, for the read-only run DAG view."""

    node_id: str
    type: str
    label: str
    status: str  # success | failed | skipped
    rows: int | None = None
    columns: list[str] = field(default_factory=list)
    sample: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    # Wall-clock time spent computing this node (None for skipped nodes).
    duration_ms: float | None = None
    # ML-specific metadata — None for ETL nodes (see EmitsNodeMetadata / NodeMetadata).
    ml_metrics: dict[str, float] | None = None
    mlflow_run_id: str | None = None
    model_uri: str | None = None
    task_type: str | None = None
    cv_scores: list[float] | None = None
    # Assertion node metadata — None for non-assertion nodes.
    assertion_passed: bool | None = None
    assertion_violation_count: int | None = None
    assertion_violating_sample: list[dict[str, Any]] | None = None

    def apply_metadata(self, meta: NodeMetadata | None) -> None:
        if meta is None:
            return
        self.ml_metrics = meta.ml_metrics
        self.mlflow_run_id = meta.mlflow_run_id
        self.model_uri = meta.model_uri
        self.task_type = meta.task_type
        self.cv_scores = meta.cv_scores
        self.assertion_passed = meta.assertion_passed
        self.assertion_violation_count = meta.assertion_violation_count
        self.assertion_violating_sample = meta.assertion_violating_sample

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "type": self.type,
            "label": self.label,
            "status": self.status,
            "rows": self.rows,
            "columns": self.columns,
            "sample": self.sample,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "ml_metrics": self.ml_metrics,
            "mlflow_run_id": self.mlflow_run_id,
            "model_uri": self.model_uri,
            "task_type": self.task_type,
            "cv_scores": self.cv_scores,
            "assertion_passed": self.assertion_passed,
            "assertion_violation_count": self.assertion_violation_count,
            "assertion_violating_sample": self.assertion_violating_sample,
        }


@dataclass
class RunResult:
    """Outcome of :meth:`FlowExecutor.run_with_results`."""

    output_paths: dict[str, Path]
    node_results: list[NodeResult]
    error: str | None = None


def dataset_ref_key(dataset_id: str, version: int | None) -> str:
    """Stable key for a (dataset, version) pair used in the ``dataset_paths``
    map. ``None`` means "latest", matching graphs created before versioning."""
    return f"{dataset_id}:{version if version is not None else 'latest'}"


def _resolve_source(outputs: dict[str, NodeOutputs], edge: dict[str, Any]) -> AnyFrame:
    """Pick the upstream frame an edge carries, honoring ``sourceHandle``.

    Single-output sources (the common case) need no handle: their sole frame is
    used. Multi-output sources (e.g. ``trainTestSplit``) require the edge to name
    which output via ``sourceHandle``; an absent or unknown handle is a wiring
    error the frontend prevents but the API could still submit.
    """
    src = outputs[edge["source"]]
    handle = edge.get("sourceHandle")
    if handle is not None:
        if handle not in src:
            raise GraphValidationError(
                f"Edge from {edge['source']!r} names output {handle!r}, but that node emits {sorted(src)}."
            )
        return src[handle]
    if len(src) == 1:
        return next(iter(src.values()))
    if "out" in src:
        return src["out"]
    raise GraphValidationError(
        f"Edge from {edge['source']!r} has no sourceHandle, but that node emits "
        f"multiple outputs {sorted(src)} — specify which one."
    )


def _build_inputs(incoming: list[dict[str, Any]], outputs: dict[str, NodeOutputs]) -> dict[str, AnyFrame]:
    """Map a node's incoming edges to a target-handle -> frame dict.

    Missing target handles default to ``"in"``. If multiple edges share a handle
    (e.g. a variadic concat node), later ones get a unique suffix so none are
    silently dropped. Each edge's frame is resolved through its ``sourceHandle``.
    """
    inputs: dict[str, AnyFrame] = {}
    for i, edge in enumerate(incoming):
        handle = edge.get("targetHandle") or "in"
        if handle in inputs:
            handle = f"{handle}_{i}"
        inputs[handle] = _resolve_source(outputs, edge)
    return inputs


def _primary_frame(node_type: str, node_outputs: NodeOutputs) -> AnyFrame:
    """The single frame that represents a node in single-frame views (preview, the
    run DAG sample). For multi-output nodes this is the declared primary handle."""
    handle = primary_output_handle(node_type)
    if handle in node_outputs:
        return node_outputs[handle]
    return next(iter(node_outputs.values()))


class FlowExecutor:
    def __init__(self, events: EventBus | None = None) -> None:
        """``events`` is an optional plugin :class:`EventBus`. When provided (the
        in-process / thread execution path), node-level hooks fire around each
        node so plugins can observe execution. It is intentionally omitted in
        ``process`` mode — a worker process can't reach parent-registered
        subscribers — so node hooks are an in-process facility by design."""
        self._events = events

    def _node_outputs(
        self,
        engine: EngineBackend,
        node: dict[str, Any],
        incoming: dict[str, list[dict[str, Any]]],
        outputs: dict[str, NodeOutputs],
        dataset_paths: dict[str, Path],
        pre_paths: dict[str, Path],
    ) -> tuple[NodeOutputs, NodeMetadata | None]:
        """Compute one node's output frames (keyed by handle) and any metadata.

        Input/output/passthrough nodes are single-output (``{"out": ...}``).
        Transformations return their own handle map; metadata-emitting nodes also
        return a :class:`NodeMetadata` to attach to the run's NodeResult.
        """
        node_id = node["id"]
        node_type = node["type"]
        config: dict[str, Any] = node.get("data", {}).get("config", {})

        if node_type in PRE_MATERIALIZED_INPUT_TYPES:
            # Both sqlInput and storageInput are resolved in the parent async layer
            # to parquet snapshots; the executor just loads the snapshot.
            return {"out": engine.read(str(pre_paths[node_id]), "parquet")}, None
        if node_type in _INPUT_TYPES:
            key = dataset_ref_key(config["dataset_id"], config.get("dataset_version"))
            return {"out": engine.read(str(dataset_paths[key]), _INPUT_TYPES[node_type])}, None
        if node_type in _OUTPUT_TYPES:
            return {"out": _resolve_source(outputs, incoming[node_id][0])}, None
        transformation = get_transformation(node_type)
        inputs = _build_inputs(incoming[node_id], outputs)
        if isinstance(transformation, EmitsNodeMetadata):
            return transformation.execute_with_metadata(engine, inputs, config)
        return transformation.execute(engine, inputs, config), None

    def compute_frames(
        self,
        graph: dict[str, Any],
        dataset_paths: dict[str, Path],
        engine: EngineBackend,
        require_output: bool = True,
        sql_input_paths: dict[str, Path] | None = None,
        storage_input_paths: dict[str, Path] | None = None,
    ) -> dict[str, AnyFrame]:
        """Run the graph in memory and return each node's *primary* frame.

        Output nodes pass their upstream frame through unchanged (no file is
        written here), which is what preview needs. Multi-output nodes are
        collapsed to their primary handle; downstream wiring still sees every
        handle via :meth:`_compute_all_outputs`.
        """
        outputs = self._compute_all_outputs(
            graph,
            dataset_paths,
            engine,
            require_output=require_output,
            sql_input_paths=sql_input_paths,
            storage_input_paths=storage_input_paths,
        )
        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        return {nid: _primary_frame(nodes_by_id[nid]["type"], outs) for nid, outs in outputs.items()}

    def _compute_all_outputs(
        self,
        graph: dict[str, Any],
        dataset_paths: dict[str, Path],
        engine: EngineBackend,
        require_output: bool = True,
        sql_input_paths: dict[str, Path] | None = None,
        storage_input_paths: dict[str, Path] | None = None,
    ) -> dict[str, NodeOutputs]:
        validate_graph(graph, require_output=require_output)
        order = topological_sort(graph)

        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        incoming = _incoming_by_target(graph, nodes_by_id)
        pre_paths = {**(sql_input_paths or {}), **(storage_input_paths or {})}

        outputs: dict[str, NodeOutputs] = {}
        for node_id in order:
            node = nodes_by_id[node_id]
            node_outputs, _meta = self._node_outputs(engine, node, incoming, outputs, dataset_paths, pre_paths)
            outputs[node_id] = node_outputs
        return outputs

    def execute(
        self,
        graph: dict[str, Any],
        dataset_paths: dict[str, Path],
        output_dir: Path,
        engine_name: str = "pandas",
        sql_input_paths: dict[str, Path] | None = None,
        storage_input_paths: dict[str, Path] | None = None,
    ) -> dict[str, Path]:
        engine = get_engine(engine_name)
        outputs = self._compute_all_outputs(
            graph,
            dataset_paths,
            engine,
            sql_input_paths=sql_input_paths,
            storage_input_paths=storage_input_paths,
        )

        output_paths: dict[str, Path] = {}
        for node in graph["nodes"]:
            node_type = node["type"]
            if node_type not in _OUTPUT_TYPES:
                continue
            source_type = _output_source_type(node_type, node.get("data", {}).get("config", {}))
            out_path = output_dir / f"{node['id']}{_OUTPUT_SUFFIX[source_type]}"
            engine.write(outputs[node["id"]]["out"], str(out_path), source_type)
            output_paths[node["id"]] = out_path

        return output_paths

    def run_with_results(
        self,
        graph: dict[str, Any],
        dataset_paths: dict[str, Path],
        output_dir: Path,
        engine_name: str = "pandas",
        sample_rows: int = 20,
        sql_input_paths: dict[str, Path] | None = None,
        storage_input_paths: dict[str, Path] | None = None,
    ) -> RunResult:
        """Execute the graph, capturing each node's row/column counts and a small
        sample for the read-only run view.

        Unlike :meth:`execute`, a failure does not bubble up: the failing node is
        marked ``failed``, every later node ``skipped``, and the error is returned
        on the :class:`RunResult` so the caller records a failed (but inspectable)
        run. Output files are only written when every node succeeds.
        """
        engine = get_engine(engine_name)
        validate_graph(graph, require_output=True)
        order = topological_sort(graph)

        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        incoming = _incoming_by_target(graph, nodes_by_id)
        pre_paths = {**(sql_input_paths or {}), **(storage_input_paths or {})}

        outputs: dict[str, NodeOutputs] = {}
        node_results: list[NodeResult] = []
        error: str | None = None

        for node_id in order:
            node = nodes_by_id[node_id]
            label = node.get("data", {}).get("label") or node["type"]
            if error is not None:
                node_results.append(NodeResult(node_id, node["type"], label, "skipped"))
                continue
            started = time.perf_counter()
            if self._events is not None:
                self._events.emit(Hook.before_node_execute, node_id=node_id, node_type=node["type"], engine=engine_name)
            try:
                node_outputs, meta = self._node_outputs(engine, node, incoming, outputs, dataset_paths, pre_paths)
                outputs[node_id] = node_outputs
                frame = _primary_frame(node["type"], node_outputs)
                # Use column_names (cheap for both engines) rather than converting
                # the whole frame to pandas just to read its columns — that copy
                # doubled peak memory on every node of a polars run.
                result = NodeResult(
                    node_id=node_id,
                    type=node["type"],
                    label=label,
                    status="success",
                    rows=int(engine.row_count(frame)),
                    columns=[str(c) for c in engine.column_names(frame)],
                    sample=engine.to_records(frame, sample_rows),
                    duration_ms=_elapsed_ms(started),
                )
                result.apply_metadata(meta)
                node_results.append(result)
                if self._events is not None:
                    self._events.emit(
                        Hook.after_node_execute,
                        node_id=node_id,
                        node_type=node["type"],
                        status="success",
                        rows=result.rows,
                        duration_ms=result.duration_ms,
                    )
            except Exception as exc:  # noqa: BLE001 - surfaced on the run record
                node_results.append(
                    NodeResult(
                        node_id,
                        node["type"],
                        label,
                        "failed",
                        error=str(exc),
                        duration_ms=_elapsed_ms(started),
                    )
                )
                error = str(exc)
                if self._events is not None:
                    self._events.emit(
                        Hook.after_node_execute,
                        node_id=node_id,
                        node_type=node["type"],
                        status="failed",
                        error=str(exc),
                    )

        output_paths: dict[str, Path] = {}
        if error is None:
            for node in graph["nodes"]:
                node_type = node["type"]
                if node_type not in _OUTPUT_TYPES:
                    continue
                source_type = _output_source_type(node_type, node.get("data", {}).get("config", {}))
                out_path = output_dir / f"{node['id']}{_OUTPUT_SUFFIX[source_type]}"
                engine.write(outputs[node["id"]]["out"], str(out_path), source_type)
                output_paths[node["id"]] = out_path

        return RunResult(output_paths, node_results, error)


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def _incoming_by_target(
    graph: dict[str, Any], nodes_by_id: dict[str, dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    incoming: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes_by_id}
    for edge in graph.get("edges", []):
        incoming[edge["target"]].append(edge)
    return incoming
