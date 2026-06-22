from pathlib import Path
from typing import Any

from app.engine.backends import AnyFrame, EngineBackend, get_engine
from app.engine.graph import topological_sort, validate_graph
from app.engine.registry import get_transformation

_INPUT_TYPES = {"csvInput": "csv", "excelInput": "excel", "parquetInput": "parquet"}
_OUTPUT_TYPES = {"csvOutput": "csv", "excelOutput": "excel", "parquetOutput": "parquet"}
_OUTPUT_SUFFIX = {"csv": ".csv", "excel": ".xlsx", "parquet": ".parquet"}


def _build_inputs(
    incoming: list[dict[str, Any]], frames: dict[str, AnyFrame]
) -> dict[str, AnyFrame]:
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
    def compute_frames(
        self,
        graph: dict[str, Any],
        dataset_paths: dict[str, Path],
        engine: EngineBackend,
        require_output: bool = True,
    ) -> dict[str, AnyFrame]:
        """Run the graph in memory and return each node's resulting frame.

        Output nodes pass their upstream frame through unchanged (no file is
        written here), which is what preview needs.
        """
        validate_graph(graph, require_output=require_output)
        order = topological_sort(graph)

        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        incoming: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes_by_id}
        for edge in graph.get("edges", []):
            incoming[edge["target"]].append(edge)

        frames: dict[str, AnyFrame] = {}
        for node_id in order:
            node = nodes_by_id[node_id]
            node_type = node["type"]
            config: dict[str, Any] = node.get("data", {}).get("config", {})

            if node_type in _INPUT_TYPES:
                path = dataset_paths[config["dataset_id"]]
                frames[node_id] = engine.read(str(path), _INPUT_TYPES[node_type])
            elif node_type in _OUTPUT_TYPES:
                frames[node_id] = frames[incoming[node_id][0]["source"]]
            else:
                transformation = get_transformation(node_type)
                inputs = _build_inputs(incoming[node_id], frames)
                result = transformation.execute(engine, inputs, config)
                frames[node_id] = result.get("out", next(iter(result.values())))

        return frames

    def execute(
        self,
        graph: dict[str, Any],
        dataset_paths: dict[str, Path],
        output_dir: Path,
        engine_name: str = "pandas",
    ) -> dict[str, Path]:
        engine = get_engine(engine_name)
        frames = self.compute_frames(graph, dataset_paths, engine)

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
