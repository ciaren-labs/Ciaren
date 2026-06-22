from typing import Any

from app.engine.graph import topological_sort, validate_graph
from app.engine.registry import get_transformation

_INPUT_TYPES = {"csvInput", "excelInput", "parquetInput"}
_OUTPUT_TYPES = {"csvOutput", "excelOutput", "parquetOutput"}

_READ_FUNCS = {
    "csvInput": "pd.read_csv",
    "excelInput": "pd.read_excel",
    "parquetInput": "pd.read_parquet",
}
_WRITE_FUNCS = {
    "csvOutput": ("to_csv", "index=False"),
    "excelOutput": ("to_excel", "index=False"),
    "parquetOutput": ("to_parquet", "index=False"),
}


class CodeGenerator:
    def generate(self, graph: dict[str, Any], dataset_paths: dict[str, str]) -> str:
        validate_graph(graph)
        order = topological_sort(graph)

        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        edges = graph.get("edges", [])
        incoming: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes_by_id}
        for edge in edges:
            incoming[edge["target"]].append(edge)

        lines: list[str] = ["import pandas as pd", ""]
        var_counter = 0
        node_var: dict[str, str] = {}

        def next_var() -> str:
            nonlocal var_counter
            var_counter += 1
            return f"df_{var_counter}"

        for node_id in order:
            node = nodes_by_id[node_id]
            node_type = node["type"]
            config: dict[str, Any] = node.get("data", {}).get("config", {})

            if node_type in _INPUT_TYPES:
                var = next_var()
                node_var[node_id] = var
                path = dataset_paths.get(config.get("dataset_id", ""), "input.csv")
                func = _READ_FUNCS[node_type]
                lines.append(f'{var} = {func}("{path}")')

            elif node_type in _OUTPUT_TYPES:
                src_id = incoming[node_id][0]["source"]
                src_var = node_var[src_id]
                method, extra = _WRITE_FUNCS[node_type]
                out_path = config.get("path", "output.csv")
                lines.append(f'{src_var}.{method}("{out_path}", {extra})')

            else:
                transformation = get_transformation(node_type)
                input_vars: dict[str, str] = {}
                for i, e in enumerate(incoming[node_id]):
                    handle = e.get("targetHandle") or "in"
                    if handle in input_vars:
                        handle = f"{handle}_{i}"
                    input_vars[handle] = node_var[e["source"]]
                out_var = next_var()
                output_vars = {"out": out_var}
                code = transformation.to_python_code(input_vars, output_vars, config)
                node_var[node_id] = out_var
                lines.append(code)

        return "\n".join(lines) + "\n"
