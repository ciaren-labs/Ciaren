"""Generate readable **polars** code for a flow graph.

Thin driver mirroring :class:`app.engine.codegen.CodeGenerator` (pandas): it
handles input-read / output-write nodes inline and delegates every
transformation node to its own ``to_polars_code`` method, so each node's polars
mapping lives next to its ``execute`` and ``to_python_code``.
"""

from typing import Any

from app.engine.graph import topological_sort, validate_graph
from app.engine.node_kinds import SQL_INPUT_TYPE, SQL_OUTPUT_TYPE
from app.engine.registry import get_transformation
from app.engine.sql_codegen import engine_url_expr, graph_has_sql

_INPUT_READ = {
    "csvInput": "pl.read_csv",
    "excelInput": "pl.read_excel",
    "parquetInput": "pl.read_parquet",
}
# Extra keyword args appended to a read call, per input type. Excel reads via
# openpyxl to match the engine and FlowFrame's shipped deps (no fastexcel needed).
_INPUT_READ_KWARGS = {"excelInput": ', engine="openpyxl"'}
_OUTPUT_WRITE = {
    "csvOutput": "write_csv",
    "excelOutput": "write_excel",
    "parquetOutput": "write_parquet",
}


class PolarsCodeGenerator:
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
        incoming: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes_by_id}
        for edge in graph.get("edges", []):
            incoming[edge["target"]].append(edge)

        header = ["import polars as pl"]
        if graph_has_sql(graph):
            header = ["import os", "import polars as pl", "from sqlalchemy import create_engine"]
        lines: list[str] = [*header, ""]

        var_counter = 0
        node_var: dict[str, str] = {}
        engine_vars: dict[str, str] = {}

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
                query = (
                    config.get("query", "")
                    if config.get("mode") == "query"
                    else f"SELECT * FROM {config.get('table', '')}"
                )
                lines.append(f"{var} = pl.read_database({query!r}, {eng}.connect())")
            elif node_type == SQL_OUTPUT_TYPE:
                src_var = node_var[incoming[node_id][0]["source"]]
                eng = engine_for(config.get("connection_id", ""))
                if_exists = config.get("if_exists", "replace")
                lines.append(
                    f"{src_var}.write_database({config.get('table', '')!r}, "
                    f"connection={eng}, if_table_exists={if_exists!r})"
                )
            elif node_type in _INPUT_READ:
                var = next_var()
                node_var[node_id] = var
                path = dataset_paths.get(config.get("dataset_id", ""), "input.csv")
                extra = _INPUT_READ_KWARGS.get(node_type, "")
                lines.append(f'{var} = {_INPUT_READ[node_type]}("{path}"{extra})')
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
