# SPDX-License-Identifier: AGPL-3.0-only
"""Generate readable **polars** code for a flow graph.

Thin driver mirroring :class:`app.engine.codegen.CodeGenerator` (pandas): it
handles input-read / output-write nodes inline and delegates every
transformation node to its own ``to_polars_code`` method, so each node's polars
mapping lives next to its ``execute`` and ``to_python_code``. On linear chains
a node writes its result back into its input's variable (``df_1 =
df_1.drop_nulls()``) instead of minting a new ``df_N`` — see
:func:`app.engine.codegen_common.reusable_output_var` — and a final pass fuses
each run of such statements into one fluent chained expression
(:func:`app.engine.codegen_common.fuse_method_chains`).

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

from app.engine.codegen_common import (
    DelScheduler,
    assert_params_do_not_shadow_imports,
    collect_input_vars,
    dialect_needs_decode,
    edge_source_var,
    fuse_method_chains,
    incoming_by_target,
    last_consumer_index,
    ordered_imports,
    placeholder_input_path,
    polars_dialect_kwargs,
    reusable_output_var,
    sql_engine_var,
    strip_self_assign,
)
from app.engine.graph import topological_sort, validate_graph
from app.engine.node_kinds import (
    FILE_INPUT_TYPE,
    FILE_OUTPUT_TYPE,
    SQL_INPUT_TYPE,
    SQL_OUTPUT_TYPE,
    edge_carries_model,
    input_source_type,
    model_output_handles,
    output_handles,
    output_source_type,
)
from app.engine.registry import get_transformation
from app.engine.sql_codegen import graph_has_sql

_INPUT_READ = {
    "fileInput": "pl.read_csv",
    "csvInput": "pl.read_csv",
    "excelInput": "pl.read_excel",
    "parquetInput": "pl.read_parquet",
    "jsonInput": "pl.read_json",
}
# Lazy scan equivalents. Excel has no scanner, so it is read eagerly and
# converted with ``.lazy()`` (handled below).
_INPUT_SCAN = {
    "fileInput": "pl.scan_csv",
    "csvInput": "pl.scan_csv",
    "parquetInput": "pl.scan_parquet",
}
_INPUT_READ_BY_FORMAT = {
    "csv": "pl.read_csv",
    "tsv": "pl.read_csv",
    "excel": "pl.read_excel",
    "parquet": "pl.read_parquet",
    "json": "pl.read_json",
    "jsonl": "pl.read_ndjson",
}
_INPUT_SCAN_BY_FORMAT = {
    "csv": "pl.scan_csv",
    "tsv": "pl.scan_csv",
    "parquet": "pl.scan_parquet",
    "jsonl": "pl.scan_ndjson",
}
# Extra keyword args appended to a read call, per input type. Excel reads via
# openpyxl to match the engine and Ciaren's shipped deps (no fastexcel needed).
_INPUT_READ_KWARGS = {"excelInput": ', engine="openpyxl"'}
_OUTPUT_WRITE = {
    "csvOutput": "write_csv",
    "excelOutput": "write_excel",
    "parquetOutput": "write_parquet",
}
# fileOutput writes by its configured format. (method, kwargs, extension)
_FILE_OUTPUT_WRITE_PL = {
    "csv": ("write_csv", "", ".csv"),
    "tsv": ("write_csv", "separator='\\t'", ".tsv"),
    "excel": ("write_excel", "", ".xlsx"),
    "parquet": ("write_parquet", "", ".parquet"),
    "json": ("write_json", "", ".json"),
    "jsonl": ("write_ndjson", "", ".jsonl"),
    "text": ("write_csv", "include_header=False, separator='\\t'", ".txt"),
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
        parameter_lines: list[str] | None = None,
        dataset_parse_options: dict[str, dict[str, Any]] | None = None,
    ) -> str:
        validate_graph(graph)
        order = topological_sort(graph)
        connections = connections or {}

        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        incoming = incoming_by_target(graph)

        # Liveness feeds variable reuse on linear chains (df_1 = df_1.head(...))
        # in every mode. del additionally only makes sense for materializing
        # (eager) frames; a lazy variable is a query plan, freeing it reclaims
        # nothing.
        last_use = last_consumer_index(order, graph.get("edges", []))
        dels = DelScheduler(order, last_use, enabled=free_intermediates and not lazy)

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
            return edge_source_var(node_outputs, edge)

        def engine_for(connection_id: str) -> str:
            return sql_engine_var(connection_id, connections, engine_vars, lines)

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
                src_type = nodes_by_id[e["source"]]["type"]
                if edge_carries_model(src_type, e.get("sourceHandle")):
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
            node_type = nodes_by_id[node_id]["type"]
            model_handles = model_output_handles(node_type)
            outs: dict[str, str] = {}
            for h in handles:
                if h in model_handles:
                    outs[h] = pdf_outs[h]  # estimator object — keep as a plain variable
                    continue
                v = next_var()
                suffix = ".lazy()" if lazy else ""
                lines.append(f"{v} = pl.from_pandas({pdf_outs[h]}){suffix}")
                outs[h] = v
            node_outputs[node_id] = outs

        def emit_transformation(idx: int, node_id: str, node_type: str, config: dict[str, Any]) -> None:
            transformation = get_transformation(node_type)
            handles = output_handles(node_type)
            if transformation.emits_pandas_code:
                # The node's to_polars_code is actually pandas (scikit-learn). Bridge
                # it: hand it pandas frames and lift the pandas results back to polars
                # so the surrounding (lazy or eager) polars plan is unaffected.
                add_imports(["import pandas as pd", *transformation.imports(config)])
                emit_pandas_bridge(node_id, transformation, incoming[node_id], handles, config)
                return
            input_vars = collect_input_vars(incoming[node_id], node_outputs)
            # On linear chains, write the result back into the input's (now dead)
            # variable instead of minting a new df_N. When reuse applies the node
            # has exactly one output handle, so out_var is called once.
            reuse = reusable_output_var(idx, incoming[node_id], node_outputs, len(handles), last_use)
            if reuse is not None:
                dels.cancel(idx, reuse)

            def out_var() -> str:
                return reuse if reuse is not None else next_var()

            # Polars-dialect nodes may need header imports too (e.g. warn-mode
            # asserts need `import warnings`); the bridge path above collects
            # its own. polars_imports, not imports: a node's pandas code may
            # need e.g. numpy where its polars code doesn't.
            add_imports(transformation.polars_imports(config))
            if lazy and not transformation.polars_lazy_safe_for(config):
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
                    v = out_var()
                    lines.append(f"{v} = {eager_outs[h]}.lazy()")
                    outs[h] = v
                node_outputs[node_id] = outs
            else:
                outs = {h: out_var() for h in handles}
                node_outputs[node_id] = outs
                lines.append(strip_self_assign(transformation.to_polars_code(input_vars, outs, config)))

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
            elif node_type == "textInput" or (
                node_type == FILE_INPUT_TYPE and input_source_type(node_type, config) == "text"
            ):
                var = next_var()
                node_outputs[node_id] = {"out": var}
                path = dataset_paths.get(config.get("dataset_id", ""), placeholder_input_path("text"))
                suffix = ".lazy()" if lazy else ""
                lines.append(f"with open({path!r}) as _f:")
                lines.append(f'    {var} = pl.DataFrame({{"text": _f.read().splitlines()}}){suffix}')
            elif node_type in _INPUT_READ:
                var = next_var()
                node_outputs[node_id] = {"out": var}
                source_type = input_source_type(node_type, config)
                path = dataset_paths.get(config.get("dataset_id", ""), placeholder_input_path(source_type))
                dialect = (dataset_parse_options or {}).get(config.get("dataset_id", ""))
                dialect_kwargs = polars_dialect_kwargs(source_type, dialect)
                # repr() the path so Windows backslashes / spaces / quotes stay valid.
                if dialect_needs_decode(source_type, dialect):
                    # polars only reads UTF-8; the user's original file isn't.
                    # Decode via Python, then parse the UTF-8 bytes — eager even
                    # in lazy mode (scan_csv cannot re-encode a file).
                    assert dialect is not None  # dialect_needs_decode implies it
                    suffix = ".lazy()" if lazy else ""
                    # Build the separator explicitly: TSV always needs the tab
                    # (polars_dialect_kwargs never emits it for tsv, and the
                    # decimal flag being present must not displace it).
                    sep_kwargs = ""
                    if source_type == "tsv":
                        sep_kwargs += ', separator="\\t"'
                    elif dialect.get("delimiter", ",") != ",":
                        sep_kwargs += f", separator={dialect['delimiter']!r}"
                    if dialect.get("decimal", ".") == ",":
                        sep_kwargs += ", decimal_comma=True"
                    lines.append(f"with open({path!r}, encoding={dialect['encoding']!r}) as _f:")
                    lines.append(f"    {var} = pl.read_csv(_f.read().encode(){sep_kwargs}){suffix}")
                elif node_type == FILE_INPUT_TYPE:
                    read = _INPUT_READ_BY_FORMAT.get(source_type, "pl.read_csv")
                    scan = _INPUT_SCAN_BY_FORMAT.get(source_type)
                    extra = (', separator="\\t"' if source_type == "tsv" else "") + dialect_kwargs
                    if lazy and scan is not None:
                        lines.append(f"{var} = {scan}({path!r}{extra})")
                    else:
                        suffix = ".lazy()" if lazy else ""
                        lines.append(f"{var} = {read}({path!r}{extra}){suffix}")
                elif lazy and node_type in _INPUT_SCAN:
                    lines.append(f"{var} = {_INPUT_SCAN[node_type]}({path!r}{dialect_kwargs})")
                else:
                    extra = _INPUT_READ_KWARGS.get(node_type, "") + dialect_kwargs
                    suffix = ".lazy()" if lazy else ""
                    lines.append(f"{var} = {_INPUT_READ[node_type]}({path!r}{extra}){suffix}")
            elif node_type == FILE_OUTPUT_TYPE:
                src_var = source_var(incoming[node_id][0])
                method, kwargs, suffix = _FILE_OUTPUT_WRITE_PL[output_source_type(node_type, config)]
                frame = f"{src_var}.collect()" if lazy else src_var
                out_path = config.get("path") or f"{config.get('dataset_name') or 'output'}{suffix}"
                args = f"{out_path!r}" + (f", {kwargs}" if kwargs else "")
                lines.append(f"{frame}.{method}({args})")
            elif node_type in _OUTPUT_WRITE:
                src_var = source_var(incoming[node_id][0])
                out_path = config.get("path", "output.csv")
                frame = f"{src_var}.collect()" if lazy else src_var
                lines.append(f"{frame}.{_OUTPUT_WRITE[node_type]}({out_path!r})")
            else:
                emit_transformation(idx, node_id, node_type, config)

            dels.schedule(node_id, node_outputs.get(node_id, {}))
            lines.extend(dels.flush(idx))

        header = [*base_header, *ordered_imports(extra_imports)]
        assert_params_do_not_shadow_imports(header, parameter_lines or [])
        prelude = [*parameter_lines, ""] if parameter_lines else []
        return "\n".join([*header, "", *prelude, *fuse_method_chains(lines)]) + "\n"
