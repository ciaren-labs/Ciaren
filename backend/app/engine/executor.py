from pathlib import Path
from typing import Any

import pandas as pd

from app.engine.graph import topological_sort, validate_graph
from app.engine.registry import get_transformation

_INPUT_TYPES = {"csvInput", "excelInput", "parquetInput"}
_OUTPUT_TYPES = {"csvOutput", "excelOutput", "parquetOutput"}


class FlowExecutor:
    def execute(
        self,
        graph: dict[str, Any],
        dataset_paths: dict[str, Path],
        output_dir: Path,
    ) -> dict[str, Path]:
        validate_graph(graph)
        order = topological_sort(graph)

        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        edges = graph.get("edges", [])

        # Map: node_id -> list of (source_node_id, source_handle, target_handle)
        incoming: dict[str, list[dict]] = {nid: [] for nid in nodes_by_id}
        for edge in edges:
            incoming[edge["target"]].append(edge)

        frames: dict[str, pd.DataFrame] = {}
        output_paths: dict[str, Path] = {}

        for node_id in order:
            node = nodes_by_id[node_id]
            node_type = node["type"]
            config: dict = node.get("data", {}).get("config", {})

            if node_type in _INPUT_TYPES:
                dataset_id = config["dataset_id"]
                path = dataset_paths[dataset_id]
                frames[node_id] = _read_file(path)

            elif node_type in _OUTPUT_TYPES:
                src_edge = incoming[node_id][0]
                df = frames[src_edge["source"]]
                out_path = output_dir / f"{node_id}.csv"
                _write_file(df, out_path, node_type)
                output_paths[node_id] = out_path

            else:
                transformation = get_transformation(node_type)
                inputs = {
                    e.get("targetHandle", "default"): frames[e["source"]]
                    for e in incoming[node_id]
                }
                result = transformation.execute(inputs, config)
                frames[node_id] = result.get("default", next(iter(result.values())))

        return output_paths


def _read_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported file type: {suffix}")


def _write_file(df: pd.DataFrame, path: Path, node_type: str) -> None:
    if node_type == "csvOutput":
        df.to_csv(path, index=False)
    elif node_type == "excelOutput":
        path = path.with_suffix(".xlsx")
        df.to_excel(path, index=False)
    elif node_type == "parquetOutput":
        path = path.with_suffix(".parquet")
        df.to_parquet(path, index=False)
