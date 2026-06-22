"""Generate readable **polars** code for a flow graph.

Thin driver mirroring :class:`app.engine.codegen.CodeGenerator` (pandas): it
handles input-read / output-write nodes inline and delegates every
transformation node to its own ``to_polars_code`` method, so each node's polars
mapping lives next to its ``execute`` and ``to_python_code``.
"""

from typing import Any

from app.engine.graph import topological_sort, validate_graph
from app.engine.registry import get_transformation

_INPUT_READ = {
    "csvInput": "pl.read_csv",
    "excelInput": "pl.read_excel",
    "parquetInput": "pl.read_parquet",
}
_OUTPUT_WRITE = {
    "csvOutput": "write_csv",
    "excelOutput": "write_excel",
    "parquetOutput": "write_parquet",
}


class PolarsCodeGenerator:
    def generate(self, graph: dict[str, Any], dataset_paths: dict[str, str]) -> str:
        validate_graph(graph)
        order = topological_sort(graph)

        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        incoming: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes_by_id}
        for edge in graph.get("edges", []):
            incoming[edge["target"]].append(edge)

        lines: list[str] = ["import polars as pl", ""]
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

            if node_type in _INPUT_READ:
                var = next_var()
                node_var[node_id] = var
                path = dataset_paths.get(config.get("dataset_id", ""), "input.csv")
                lines.append(f'{var} = {_INPUT_READ[node_type]}("{path}")')
            elif node_type in _OUTPUT_WRITE:
                src_var = node_var[incoming[node_id][0]["source"]]
                out_path = config.get("path", "output.csv")
                lines.append(f'{src_var}.{_OUTPUT_WRITE[node_type]}("{out_path}")')
            else:
                transformation = get_transformation(node_type)
                input_vars: dict[str, str] = {}
                for i, e in enumerate(incoming[node_id]):
                    handle = e.get("targetHandle") or "in"
                    if handle in input_vars:
                        handle = f"{handle}_{i}"
                    input_vars[handle] = node_var[e["source"]]
                out_var = next_var()
                node_var[node_id] = out_var
                lines.append(
                    transformation.to_polars_code(input_vars, {"out": out_var}, config)
                )

        return "\n".join(lines) + "\n"
