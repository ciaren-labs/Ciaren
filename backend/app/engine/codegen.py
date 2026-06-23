from typing import Any

from app.engine.graph import topological_sort, validate_graph
from app.engine.node_kinds import INPUT_TYPES as _INPUT_TYPES
from app.engine.node_kinds import OUTPUT_TYPES as _OUTPUT_TYPES
from app.engine.node_kinds import SQL_INPUT_TYPE, SQL_OUTPUT_TYPE
from app.engine.registry import get_transformation
from app.engine.sql_codegen import engine_url_expr, graph_has_sql

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
    def generate(
        self,
        graph: dict[str, Any],
        dataset_paths: dict[str, str],
        connections: dict[str, dict[str, Any]] | None = None,
    ) -> str:
        validate_graph(graph)
        order = topological_sort(graph)
        connections = connections or {}

        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        edges = graph.get("edges", [])
        incoming: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes_by_id}
        for edge in edges:
            incoming[edge["target"]].append(edge)

        header = ["import pandas as pd"]
        if graph_has_sql(graph):
            header = ["import os", "import pandas as pd", "from sqlalchemy import create_engine"]
        lines: list[str] = [*header, ""]

        var_counter = 0
        node_var: dict[str, str] = {}
        engine_vars: dict[str, str] = {}  # connection_id -> engine var

        def next_var() -> str:
            nonlocal var_counter
            var_counter += 1
            return f"df_{var_counter}"

        def engine_for(connection_id: str) -> str:
            if connection_id not in engine_vars:
                var = f"_engine_{len(engine_vars) + 1}"
                info = connections.get(connection_id, {"provider": "sqlite", "database": ""})
                lines.append(f"{var} = create_engine({engine_url_expr(info)})")
                engine_vars[connection_id] = var
            return engine_vars[connection_id]

        for node_id in order:
            node = nodes_by_id[node_id]
            node_type = node["type"]
            config: dict[str, Any] = node.get("data", {}).get("config", {})

            if node_type == SQL_INPUT_TYPE:
                var = next_var()
                node_var[node_id] = var
                eng = engine_for(config.get("connection_id", ""))
                if config.get("mode") == "query":
                    lines.append(f"{var} = pd.read_sql_query({config.get('query', '')!r}, {eng})")
                else:
                    lines.append(f"{var} = pd.read_sql_table({config.get('table', '')!r}, {eng})")

            elif node_type == SQL_OUTPUT_TYPE:
                src_var = node_var[incoming[node_id][0]["source"]]
                eng = engine_for(config.get("connection_id", ""))
                if_exists = config.get("if_exists", "replace")
                lines.append(
                    f"{src_var}.to_sql({config.get('table', '')!r}, {eng}, "
                    f"if_exists={if_exists!r}, index=False)"
                )

            elif node_type in _INPUT_TYPES:
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
