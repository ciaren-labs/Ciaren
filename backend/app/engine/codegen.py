"""Generate readable **pandas** code for a flow graph.

The counterpart to :class:`app.engine.polars_codegen.PolarsCodeGenerator`: it walks
the graph in topological order, assigns each node output a ``df_N`` variable,
handles input-read / output-write / SQL nodes inline, and delegates every
transformation node to its own ``to_python_code`` method — so a node's pandas
mapping lives next to its ``execute`` and ``to_polars_code``.

Multi-output nodes (e.g. ``trainTestSplit``, ``mlTrain``) get one variable per
declared handle; downstream edges pick the right one via ``sourceHandle``. Nodes
may also declare extra ``imports()`` (e.g. scikit-learn) which are collected and
de-duplicated into the script header.

The optional ``free_intermediates`` mode emits a ``del`` once each dataframe's last
consumer has run, lowering peak memory on long pipelines (see
:func:`app.engine.codegen_common.last_consumer_index` for the liveness analysis
that guarantees a variable is never freed before its final use).
"""

from typing import Any

from app.engine.codegen_common import last_consumer_index
from app.engine.graph import topological_sort, validate_graph
from app.engine.node_kinds import INPUT_TYPES as _INPUT_TYPES
from app.engine.node_kinds import OUTPUT_TYPES as _OUTPUT_TYPES
from app.engine.node_kinds import SQL_INPUT_TYPE, SQL_OUTPUT_TYPE, output_handles
from app.engine.registry import get_transformation
from app.engine.sql_codegen import engine_url_expr, graph_has_sql

_READ_FUNCS = {
    "csvInput": "pd.read_csv",
    "excelInput": "pd.read_excel",
    "parquetInput": "pd.read_parquet",
    "jsonInput": "pd.read_json",
}
_WRITE_FUNCS = {
    "csvOutput": ("to_csv", "index=False"),
    "excelOutput": ("to_excel", "index=False"),
    "parquetOutput": ("to_parquet", "index=False"),
}


def _source_var(node_outputs: dict[str, dict[str, str]], edge: dict[str, Any]) -> str:
    """The variable an edge carries, honoring ``sourceHandle`` for multi-output nodes."""
    outs = node_outputs[edge["source"]]
    handle = edge.get("sourceHandle")
    if handle and handle in outs:
        return outs[handle]
    if "out" in outs:
        return outs["out"]
    return next(iter(outs.values()))


def _ordered_imports(imports: list[str]) -> list[str]:
    """``import x`` lines first, then ``from x import y`` lines, each sorted."""
    plain = sorted(i for i in imports if i.startswith("import "))
    froms = sorted(i for i in imports if not i.startswith("import "))
    return plain + froms


class CodeGenerator:
    """Turns a React Flow graph into a standalone, runnable pandas script."""

    def generate(
        self,
        graph: dict[str, Any],
        dataset_paths: dict[str, str],
        connections: dict[str, dict[str, Any]] | None = None,
        *,
        free_intermediates: bool = False,
    ) -> str:
        """Return the pandas script for ``graph`` as a single string.

        ``dataset_paths`` maps each input node's ``dataset_id`` to the path/filename
        to read; ``connections`` carries SQL connection metadata (never secrets).
        Set ``free_intermediates`` to emit ``del`` statements that free each
        intermediate dataframe after its last use.
        """
        validate_graph(graph)
        order = topological_sort(graph)
        connections = connections or {}

        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        edges = graph.get("edges", [])
        incoming: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes_by_id}
        for edge in edges:
            incoming[edge["target"]].append(edge)

        # When freeing intermediates, drop each var right after its last consumer
        # runs (never before — see last_consumer_index), but never the final node.
        last_use = last_consumer_index(order, edges) if free_intermediates else {}
        pending_del: dict[int, list[str]] = {}

        base_header = ["import pandas as pd"]
        if graph_has_sql(graph):
            base_header = ["import os", "import pandas as pd", "from sqlalchemy import create_engine"]
        body: list[str] = []

        var_counter = 0
        node_outputs: dict[str, dict[str, str]] = {}
        engine_vars: dict[str, str] = {}  # connection_id -> engine var
        extra_imports: list[str] = []
        seen_imports = set(base_header)

        def next_var() -> str:
            nonlocal var_counter
            var_counter += 1
            return f"df_{var_counter}"

        def add_imports(imports: list[str]) -> None:
            for imp in imports:
                if imp not in seen_imports:
                    seen_imports.add(imp)
                    extra_imports.append(imp)

        def schedule_del(node_id: str, var: str) -> None:
            li = last_use.get(node_id)
            if li is not None and li < len(order) - 1:
                pending_del.setdefault(li, []).append(var)

        def engine_for(connection_id: str) -> str:
            if connection_id not in engine_vars:
                var = f"_engine_{len(engine_vars) + 1}"
                info = connections.get(connection_id, {"provider": "sqlite", "database": ""})
                body.append(f"{var} = create_engine({engine_url_expr(info)})")
                engine_vars[connection_id] = var
            return engine_vars[connection_id]

        for idx, node_id in enumerate(order):
            node = nodes_by_id[node_id]
            node_type = node["type"]
            config: dict[str, Any] = node.get("data", {}).get("config", {})

            if node_type == SQL_INPUT_TYPE:
                var = next_var()
                node_outputs[node_id] = {"out": var}
                eng = engine_for(config.get("connection_id", ""))
                if config.get("mode") == "query":
                    body.append(f"{var} = pd.read_sql_query({config.get('query', '')!r}, {eng})")
                else:
                    body.append(f"{var} = pd.read_sql_table({config.get('table', '')!r}, {eng})")

            elif node_type == SQL_OUTPUT_TYPE:
                src_var = _source_var(node_outputs, incoming[node_id][0])
                eng = engine_for(config.get("connection_id", ""))
                if_exists = config.get("if_exists", "replace")
                body.append(
                    f"{src_var}.to_sql({config.get('table', '')!r}, {eng}, if_exists={if_exists!r}, index=False)"
                )

            elif node_type in _INPUT_TYPES:
                var = next_var()
                node_outputs[node_id] = {"out": var}
                path = dataset_paths.get(config.get("dataset_id", ""), "input.csv")
                func = _READ_FUNCS.get(node_type)
                if func is not None:
                    body.append(f'{var} = {func}("{path}")')
                elif node_type == "textInput":
                    body.append(
                        f'{var} = pd.read_csv("{path}", sep="\\n", header=None, '
                        f'names=["text"], engine="python", dtype=str)'
                    )
                else:
                    body.append(f'{var} = pd.read_csv("{path}")  # unsupported input type: {node_type}')

            elif node_type in _OUTPUT_TYPES:
                src_var = _source_var(node_outputs, incoming[node_id][0])
                method, extra = _WRITE_FUNCS[node_type]
                out_path = config.get("path", "output.csv")
                body.append(f'{src_var}.{method}("{out_path}", {extra})')

            else:
                transformation = get_transformation(node_type)
                input_vars: dict[str, str] = {}
                for i, e in enumerate(incoming[node_id]):
                    handle = e.get("targetHandle") or "in"
                    if handle in input_vars:
                        handle = f"{handle}_{i}"
                    input_vars[handle] = _source_var(node_outputs, e)
                output_vars = {h: next_var() for h in output_handles(node_type)}
                node_outputs[node_id] = output_vars
                add_imports(transformation.imports(config))
                body.append(transformation.to_python_code(input_vars, output_vars, config))

            if free_intermediates and node_id in node_outputs:
                outs = node_outputs[node_id]
                if len(outs) == 1:  # multi-output liveness is ambiguous; only free singles
                    schedule_del(node_id, next(iter(outs.values())))
                for dead in pending_del.pop(idx, []):
                    body.append(f"del {dead}")

        header = base_header + _ordered_imports(extra_imports)
        return "\n".join([*header, "", *body]) + "\n"
