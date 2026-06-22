from pathlib import Path
from typing import Any

from app.engine.backends import AnyFrame, get_engine
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
    def execute(
        self,
        graph: dict[str, Any],
        dataset_paths: dict[str, Path],
        output_dir: Path,
        engine_name: str = "pandas",
    ) -> dict[str, Path]:
        validate_graph(graph)
        order = topological_sort(graph)
        engine = get_engine(engine_name)

        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        edges = graph.get("edges", [])

        incoming: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes_by_id}
        for edge in edges:
            incoming[edge["target"]].append(edge)

        frames: dict[str, AnyFrame] = {}
        output_paths: dict[str, Path] = {}

        for node_id in order:
            node = nodes_by_id[node_id]
            node_type = node["type"]
            config: dict[str, Any] = node.get("data", {}).get("config", {})

            if node_type in _INPUT_TYPES:
                source_type = _INPUT_TYPES[node_type]
                path = dataset_paths[config["dataset_id"]]
                frames[node_id] = engine.read(str(path), source_type)

            elif node_type in _OUTPUT_TYPES:
                source_type = _OUTPUT_TYPES[node_type]
                df = frames[incoming[node_id][0]["source"]]
                out_path = output_dir / f"{node_id}{_OUTPUT_SUFFIX[source_type]}"
                engine.write(df, str(out_path), source_type)
                output_paths[node_id] = out_path

            else:
                transformation = get_transformation(node_type)
                inputs = _build_inputs(incoming[node_id], frames)
                result = transformation.execute(engine, inputs, config)
                frames[node_id] = result.get("out", next(iter(result.values())))

        return output_paths
