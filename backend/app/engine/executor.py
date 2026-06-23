import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.engine.backends import AnyFrame, EngineBackend, get_engine
from app.engine.graph import topological_sort, validate_graph
from app.engine.node_kinds import INPUT_SOURCE_TYPES as _INPUT_TYPES
from app.engine.node_kinds import OUTPUT_SOURCE_TYPES as _OUTPUT_TYPES
from app.engine.node_kinds import OUTPUT_SUFFIX as _OUTPUT_SUFFIX
from app.engine.node_kinds import SQL_INPUT_TYPE
from app.engine.registry import get_transformation


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


def _build_inputs(incoming: list[dict[str, Any]], frames: dict[str, AnyFrame]) -> dict[str, AnyFrame]:
    """Map incoming edges to a handle->frame dict.

    Missing target handles default to ``"in"``. If multiple edges share a
    handle (e.g. a variadic concat node), later ones get a unique suffix so
    none are silently dropped.
    """
    inputs: dict[str, AnyFrame] = {}
    for i, edge in enumerate(incoming):
        handle = edge.get("targetHandle") or "in"
        if handle in inputs:
            handle = f"{handle}_{i}"
        inputs[handle] = frames[edge["source"]]
    return inputs


class FlowExecutor:
    def _node_frame(
        self,
        engine: EngineBackend,
        node: dict[str, Any],
        incoming: dict[str, list[dict[str, Any]]],
        frames: dict[str, AnyFrame],
        dataset_paths: dict[str, Path],
        sql_input_paths: dict[str, Path],
    ) -> AnyFrame:
        """Compute a single node's output frame from its upstream frames."""
        node_id = node["id"]
        node_type = node["type"]
        config: dict[str, Any] = node.get("data", {}).get("config", {})

        if node_type == SQL_INPUT_TYPE:
            # The DB read happened in the parent (async) layer, which materialized
            # the result to a parquet snapshot; the executor just loads it.
            return engine.read(str(sql_input_paths[node_id]), "parquet")
        if node_type in _INPUT_TYPES:
            key = dataset_ref_key(config["dataset_id"], config.get("dataset_version"))
            return engine.read(str(dataset_paths[key]), _INPUT_TYPES[node_type])
        if node_type in _OUTPUT_TYPES:
            return frames[incoming[node_id][0]["source"]]
        transformation = get_transformation(node_type)
        inputs = _build_inputs(incoming[node_id], frames)
        result = transformation.execute(engine, inputs, config)
        return result.get("out", next(iter(result.values())))

    def compute_frames(
        self,
        graph: dict[str, Any],
        dataset_paths: dict[str, Path],
        engine: EngineBackend,
        require_output: bool = True,
        sql_input_paths: dict[str, Path] | None = None,
    ) -> dict[str, AnyFrame]:
        """Run the graph in memory and return each node's resulting frame.

        Output nodes pass their upstream frame through unchanged (no file is
        written here), which is what preview needs.
        """
        validate_graph(graph, require_output=require_output)
        order = topological_sort(graph)

        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        incoming = _incoming_by_target(graph, nodes_by_id)
        sql_paths = sql_input_paths or {}

        frames: dict[str, AnyFrame] = {}
        for node_id in order:
            node = nodes_by_id[node_id]
            frames[node_id] = self._node_frame(engine, node, incoming, frames, dataset_paths, sql_paths)

        return frames

    def execute(
        self,
        graph: dict[str, Any],
        dataset_paths: dict[str, Path],
        output_dir: Path,
        engine_name: str = "pandas",
        sql_input_paths: dict[str, Path] | None = None,
    ) -> dict[str, Path]:
        engine = get_engine(engine_name)
        frames = self.compute_frames(graph, dataset_paths, engine, sql_input_paths=sql_input_paths)

        output_paths: dict[str, Path] = {}
        for node in graph["nodes"]:
            node_type = node["type"]
            if node_type not in _OUTPUT_TYPES:
                continue
            source_type = _OUTPUT_TYPES[node_type]
            out_path = output_dir / f"{node['id']}{_OUTPUT_SUFFIX[source_type]}"
            engine.write(frames[node["id"]], str(out_path), source_type)
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
        sql_paths = sql_input_paths or {}

        frames: dict[str, AnyFrame] = {}
        node_results: list[NodeResult] = []
        error: str | None = None

        for node_id in order:
            node = nodes_by_id[node_id]
            label = node.get("data", {}).get("label") or node["type"]
            if error is not None:
                node_results.append(NodeResult(node_id, node["type"], label, "skipped"))
                continue
            started = time.perf_counter()
            try:
                frame = self._node_frame(engine, node, incoming, frames, dataset_paths, sql_paths)
                frames[node_id] = frame
                pdf = engine.to_pandas(frame)
                node_results.append(
                    NodeResult(
                        node_id=node_id,
                        type=node["type"],
                        label=label,
                        status="success",
                        rows=int(engine.row_count(frame)),
                        columns=[str(c) for c in pdf.columns],
                        sample=engine.to_records(frame, sample_rows),
                        duration_ms=_elapsed_ms(started),
                    )
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

        output_paths: dict[str, Path] = {}
        if error is None:
            for node in graph["nodes"]:
                node_type = node["type"]
                if node_type not in _OUTPUT_TYPES:
                    continue
                source_type = _OUTPUT_TYPES[node_type]
                out_path = output_dir / f"{node['id']}{_OUTPUT_SUFFIX[source_type]}"
                engine.write(frames[node["id"]], str(out_path), source_type)
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
