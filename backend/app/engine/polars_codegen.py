"""Generate readable **polars** code for a flow graph.

Thin driver mirroring :class:`app.engine.codegen.CodeGenerator` (pandas): it
handles input-read / output-write nodes inline and delegates every
transformation node to its own ``to_polars_code`` method, so each node's polars
mapping lives next to its ``execute`` and ``to_python_code``.

Two opt-in modes:

- ``lazy=True`` builds a single ``LazyFrame`` query (``scan_csv`` → … →
  ``collect()``) so polars applies projection / predicate pushdown and join
  optimization. The transformation bodies are expression-based and run on a
  ``LazyFrame`` unchanged; the few eager-only nodes (``pivot``, ``sample``, see
  ``polars_lazy_safe``) are materialized in place with ``.collect()`` /
  ``.lazy()``.
- ``free_intermediates=True`` (eager mode only) emits ``del`` once each
  intermediate's last consumer has run, lowering peak memory. It is a no-op in
  lazy mode, where the named variables are query plans, not materialized data.
"""

from typing import Any

from app.engine.codegen_common import last_consumer_index
from app.engine.graph import topological_sort, validate_graph
from app.engine.node_kinds import SQL_INPUT_TYPE, SQL_OUTPUT_TYPE, output_handles
from app.engine.registry import get_transformation
from app.engine.sql_codegen import engine_url_expr, graph_has_sql

_INPUT_READ = {
    "csvInput": "pl.read_csv",
    "excelInput": "pl.read_excel",
    "parquetInput": "pl.read_parquet",
    "jsonInput": "pl.read_json",
}
# Lazy scan equivalents. Excel has no scanner, so it is read eagerly and
# converted with ``.lazy()`` (handled below).
_INPUT_SCAN = {
    "csvInput": "pl.scan_csv",
    "parquetInput": "pl.scan_parquet",
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
        *,
        lazy: bool = False,
        free_intermediates: bool = False,
    ) -> str:
        validate_graph(graph)
        order = topological_sort(graph)
        connections = connections or {}

        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        edges = graph.get("edges", [])
        incoming: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes_by_id}
        for edge in edges:
            incoming[edge["target"]].append(edge)

        # del only makes sense for materializing (eager) frames; a lazy variable
        # is a query plan, so freeing it reclaims nothing.
        emit_del = free_intermediates and not lazy
        last_use = last_consumer_index(order, edges) if emit_del else {}
        pending_del: dict[int, list[str]] = {}

        base_header = ["import polars as pl"]
        if graph_has_sql(graph):
            base_header = ["import os", "import polars as pl", "from sqlalchemy import create_engine"]
        # ML nodes emit pandas code; their imports (sklearn, joblib, numpy) plus a
        # pandas import are collected during the walk and merged into the header so
        # a polars flow containing an ML node still produces a runnable script.
        lines: list[str] = []
        extra_imports: list[str] = []
        seen_imports: set[str] = set(base_header)

        def add_imports(imports: list[str]) -> None:
            for imp in imports:
                if imp not in seen_imports:
                    seen_imports.add(imp)
                    extra_imports.append(imp)

        var_counter = 0
        eager_counter = 0
        # node id -> {output handle: variable}. Multi-output nodes (trainTestSplit,
        # mlTrain) expose several handles; downstream edges pick one via sourceHandle.
        node_outputs: dict[str, dict[str, str]] = {}
        engine_vars: dict[str, str] = {}

        def next_var() -> str:
            nonlocal var_counter
            var_counter += 1
            return f"df_{var_counter}"

        def next_eager() -> str:
            nonlocal eager_counter
            eager_counter += 1
            return f"_eager_{eager_counter}"

        def source_var(edge: dict[str, Any]) -> str:
            """The variable an edge carries, honoring sourceHandle for multi-output nodes."""
            outs = node_outputs[edge["source"]]
            handle = edge.get("sourceHandle")
            if handle and handle in outs:
                return outs[handle]
            if "out" in outs:
                return outs["out"]
            return next(iter(outs.values()))

        def schedule_del(node_id: str, var: str) -> None:
            li = last_use.get(node_id)
            if li is not None and li < len(order) - 1:
                pending_del.setdefault(li, []).append(var)

        def engine_for(connection_id: str) -> str:
            if connection_id not in engine_vars:
                var = f"_engine_{len(engine_vars) + 1}"
                info = connections.get(connection_id, {"provider": "sqlite", "database": ""})
                lines.append(f"{var} = create_engine({engine_url_expr(info)})")
                engine_vars[connection_id] = var
            return engine_vars[connection_id]

        def emit_pandas_bridge(
            node_id: str,
            transformation: Any,
            edges_in: list[dict[str, Any]],
            handles: tuple[str, ...],
            config: dict[str, Any],
        ) -> None:
            """Run a pandas-bodied node (ML) inside the polars script: convert each
            polars *frame* input to pandas, run the pandas code, then lift frame
            outputs back to polars.

            The ``model`` reference an ML flow passes between nodes (mlTrain ->
            mlPredict / featureImportance) is a fitted estimator object, **not** a
            frame — identified by ``sourceHandle == "model"`` on its edge and the
            ``"model"`` output handle. Those never go through pandas/polars
            conversion; they stay plain Python variables.
            """
            pdf_inputs: dict[str, str] = {}
            converted: dict[str, str] = {}
            for i, e in enumerate(edges_in):
                handle = e.get("targetHandle") or "in"
                if handle in pdf_inputs:
                    handle = f"{handle}_{i}"
                src_v = source_var(e)
                if e.get("sourceHandle") == "model":
                    pdf_inputs[handle] = src_v  # estimator object — pass through
                    continue
                if src_v not in converted:
                    pdf = next_eager()
                    # collect() first in lazy mode (the var is a query plan).
                    expr = f"{src_v}.collect().to_pandas()" if lazy else f"{src_v}.to_pandas()"
                    lines.append(f"{pdf} = {expr}")
                    converted[src_v] = pdf
                pdf_inputs[handle] = converted[src_v]
            pdf_outs = {h: next_eager() for h in handles}
            lines.append(transformation.to_polars_code(pdf_inputs, pdf_outs, config))
            outs: dict[str, str] = {}
            for h in handles:
                if h == "model":
                    outs[h] = pdf_outs[h]  # estimator object — keep as a plain variable
                    continue
                v = next_var()
                suffix = ".lazy()" if lazy else ""
                lines.append(f"{v} = pl.from_pandas({pdf_outs[h]}){suffix}")
                outs[h] = v
            node_outputs[node_id] = outs

        def emit_transformation(node_id: str, node_type: str, config: dict[str, Any]) -> None:
            transformation = get_transformation(node_type)
            handles = output_handles(node_type)
            if transformation.emits_pandas_code:
                # The node's to_polars_code is actually pandas (scikit-learn). Bridge
                # it: hand it pandas frames and lift the pandas results back to polars
                # so the surrounding (lazy or eager) polars plan is unaffected.
                add_imports(["import pandas as pd", *transformation.imports(config)])
                emit_pandas_bridge(node_id, transformation, incoming[node_id], handles, config)
                return
            input_vars: dict[str, str] = {}
            for i, e in enumerate(incoming[node_id]):
                handle = e.get("targetHandle") or "in"
                if handle in input_vars:
                    handle = f"{handle}_{i}"
                input_vars[handle] = source_var(e)
            if lazy and not transformation.polars_lazy_safe:
                # No lazy equivalent: collect the inputs, run the op eagerly, and
                # re-enter the lazy plan so downstream nodes stay optimized.
                lines.append(f"# {node_type} has no lazy equivalent — materialize here")
                collected: dict[str, str] = {}
                eager_inputs: dict[str, str] = {}
                for handle, lv in input_vars.items():
                    if lv not in collected:
                        etmp = next_eager()
                        lines.append(f"{etmp} = {lv}.collect()")
                        collected[lv] = etmp
                    eager_inputs[handle] = collected[lv]
                eager_outs = {h: next_eager() for h in handles}
                lines.append(transformation.to_polars_code(eager_inputs, eager_outs, config))
                outs: dict[str, str] = {}
                for h in handles:
                    v = next_var()
                    lines.append(f"{v} = {eager_outs[h]}.lazy()")
                    outs[h] = v
                node_outputs[node_id] = outs
            else:
                outs = {h: next_var() for h in handles}
                node_outputs[node_id] = outs
                lines.append(transformation.to_polars_code(input_vars, outs, config))

        for idx, node_id in enumerate(order):
            node = nodes_by_id[node_id]
            node_type = node["type"]
            config: dict[str, Any] = node.get("data", {}).get("config", {})

            if node_type == SQL_INPUT_TYPE:
                var = next_var()
                node_outputs[node_id] = {"out": var}
                eng = engine_for(config.get("connection_id", ""))
                query = (
                    config.get("query", "")
                    if config.get("mode") == "query"
                    else f"SELECT * FROM {config.get('table', '')}"
                )
                read = f"pl.read_database({query!r}, {eng}.connect())"
                lines.append(f"{var} = {read}.lazy()" if lazy else f"{var} = {read}")
            elif node_type == SQL_OUTPUT_TYPE:
                src_var = source_var(incoming[node_id][0])
                eng = engine_for(config.get("connection_id", ""))
                if_exists = config.get("if_exists", "replace")
                frame = f"{src_var}.collect()" if lazy else src_var
                lines.append(
                    f"{frame}.write_database({config.get('table', '')!r}, "
                    f"connection={eng}, if_table_exists={if_exists!r})"
                )
            elif node_type == "textInput":
                var = next_var()
                node_outputs[node_id] = {"out": var}
                path = dataset_paths.get(config.get("dataset_id", ""), "input.txt")
                suffix = ".lazy()" if lazy else ""
                lines.append(f"with open({path!r}) as _f:")
                lines.append(f'    {var} = pl.DataFrame({{"text": _f.read().splitlines()}}){suffix}')
            elif node_type in _INPUT_READ:
                var = next_var()
                node_outputs[node_id] = {"out": var}
                path = dataset_paths.get(config.get("dataset_id", ""), "input.csv")
                # repr() the path so Windows backslashes / spaces / quotes stay valid.
                if lazy and node_type in _INPUT_SCAN:
                    lines.append(f"{var} = {_INPUT_SCAN[node_type]}({path!r})")
                else:
                    extra = _INPUT_READ_KWARGS.get(node_type, "")
                    suffix = ".lazy()" if lazy else ""
                    lines.append(f"{var} = {_INPUT_READ[node_type]}({path!r}{extra}){suffix}")
            elif node_type in _OUTPUT_WRITE:
                src_var = source_var(incoming[node_id][0])
                out_path = config.get("path", "output.csv")
                frame = f"{src_var}.collect()" if lazy else src_var
                lines.append(f"{frame}.{_OUTPUT_WRITE[node_type]}({out_path!r})")
            else:
                emit_transformation(node_id, node_type, config)

            if emit_del:
                outs = node_outputs.get(node_id, {})
                # Multi-output liveness is ambiguous; only free single-output nodes.
                if len(outs) == 1:
                    schedule_del(node_id, next(iter(outs.values())))
                for dead in pending_del.pop(idx, []):
                    lines.append(f"del {dead}")

        # ``import x`` lines first (sorted), then ``from x import y`` (sorted),
        # appended after the fixed polars/sql base header.
        plain = sorted(i for i in extra_imports if i.startswith("import "))
        froms = sorted(i for i in extra_imports if not i.startswith("import "))
        header = [*base_header, *plain, *froms]
        return "\n".join([*header, "", *lines]) + "\n"
