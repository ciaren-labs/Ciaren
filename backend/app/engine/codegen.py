# SPDX-License-Identifier: AGPL-3.0-only
"""Generate readable **pandas** code for a flow graph.

The counterpart to :class:`app.engine.polars_codegen.PolarsCodeGenerator`: it walks
the graph in topological order, assigns each node output a variable, handles
input-read / output-write / SQL / storage nodes inline, and delegates every
transformation node to its own ``to_python_code`` method — so a node's pandas
mapping lives next to its ``execute`` and ``to_polars_code``.

Input frames are named after their dataset file or SQL table
(``df_sales = pd.read_csv('sales.csv')`` — see
:func:`app.engine.codegen_common.frame_var_name`); everything else falls back
to the numbered ``df_N`` sequence.

Multi-output nodes (e.g. ``trainTestSplit``, ``mlTrain``) get one variable per
declared handle; downstream edges pick the right one via ``sourceHandle``. Nodes
may also declare extra ``imports()`` (e.g. scikit-learn) which are collected and
de-duplicated into the script header.

On linear chains a node writes its result back into its input's variable
(``df_1 = df_1.dropna()``) instead of minting a new ``df_N`` — see
:func:`app.engine.codegen_common.reusable_output_var` for when that is safe.
A final pass (:func:`app.engine.codegen_common.fuse_method_chains`) then merges
each such run of statements into one fluent chained expression, so a
straight-line flow exports the way a person would write it:
``df_1 = df_1.dropna().head(5)``, or parenthesized one-call-per-line when long —
and :func:`app.engine.codegen_common.insert_paragraph_breaks` separates those
chains with blank lines so the script reads in paragraphs.

The optional ``free_intermediates`` mode emits a ``del`` once each dataframe's last
consumer has run, lowering peak memory on long pipelines (see
:func:`app.engine.codegen_common.last_consumer_index` for the liveness analysis
that guarantees a variable is never freed before its final use).
"""

from typing import Any

from app.engine.codegen_common import (
    DelScheduler,
    assert_params_do_not_shadow_imports,
    collect_input_vars,
    edge_source_var,
    frame_var_name,
    fuse_method_chains,
    incoming_by_target,
    insert_paragraph_breaks,
    last_consumer_index,
    ordered_imports,
    pandas_dialect_kwargs,
    parameter_names,
    placeholder_input_path,
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
    STORAGE_INPUT_TYPE,
    input_source_type,
    output_handles,
    output_source_type,
)
from app.engine.node_kinds import INPUT_TYPES as _INPUT_TYPES
from app.engine.node_kinds import OUTPUT_TYPES as _OUTPUT_TYPES
from app.engine.registry import get_transformation
from app.engine.sql_codegen import graph_has_sql, sql_secret_imports

_READ_FUNCS = {
    "fileInput": "pd.read_csv",
    "csvInput": "pd.read_csv",
    "excelInput": "pd.read_excel",
    "parquetInput": "pd.read_parquet",
    "jsonInput": "pd.read_json",
}
_READ_FUNCS_BY_FORMAT = {
    "csv": "pd.read_csv",
    "tsv": "pd.read_csv",
    "excel": "pd.read_excel",
    "parquet": "pd.read_parquet",
    "json": "pd.read_json",
    "jsonl": "pd.read_json",
}
# Legacy single-format outputs. (method, kwargs, default filename) — the
# default must match the node's format, not blanket "output.csv".
_WRITE_FUNCS = {
    "csvOutput": ("to_csv", "index=False", "output.csv"),
    "excelOutput": ("to_excel", "index=False", "output.xlsx"),
    "parquetOutput": ("to_parquet", "index=False", "output.parquet"),
}
# fileOutput writes by its configured format. (method, kwargs, extension)
_FILE_OUTPUT_WRITE = {
    "csv": ("to_csv", "index=False", ".csv"),
    "tsv": ("to_csv", "index=False, sep='\\t'", ".tsv"),
    "excel": ("to_excel", "index=False", ".xlsx"),
    "parquet": ("to_parquet", "index=False", ".parquet"),
    "json": ("to_json", "orient='records', indent=2", ".json"),
    "jsonl": ("to_json", "orient='records', lines=True", ".jsonl"),
    "text": ("to_csv", "index=False, header=False, sep='\\t'", ".txt"),
}


class CodeGenerator:
    """Turns a React Flow graph into a standalone, runnable pandas script."""

    def generate(
        self,
        graph: dict[str, Any],
        dataset_paths: dict[str, str],
        connections: dict[str, dict[str, Any]] | None = None,
        *,
        free_intermediates: bool = False,
        parameter_lines: list[str] | None = None,
        dataset_parse_options: dict[str, dict[str, Any]] | None = None,
    ) -> str:
        """Return the pandas script for ``graph`` as a single string.

        ``dataset_paths`` maps each input node's ``dataset_id`` to the path/filename
        to read; ``connections`` carries SQL connection metadata (never secrets).
        Set ``free_intermediates`` to emit ``del`` statements that free each
        intermediate dataframe after its last use. ``parameter_lines`` is an
        optional ``name = default`` prelude (flow parameters) inserted after the
        imports. ``dataset_parse_options`` maps dataset ids to the original
        upload's dialect so the emitted read reproduces the user's own file
        (Ciaren's stored copy is normalized; the user's file is not).
        """
        validate_graph(graph)
        order = topological_sort(graph)
        connections = connections or {}

        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        incoming = incoming_by_target(graph)

        # Liveness (see last_consumer_index) drives two things: reusing a dead
        # variable as its consumer's output on linear chains, and — when freeing
        # intermediates — emitting a del right after a variable's last consumer
        # runs (never before, and never for the final node).
        last_use = last_consumer_index(order, graph.get("edges", []))
        dels = DelScheduler(order, last_use, free_intermediates)

        base_header = ["import pandas as pd"]
        if graph_has_sql(graph):
            base_header = ordered_imports(
                ["import os", "import pandas as pd", "from sqlalchemy import URL, create_engine"]
                + sql_secret_imports(connections)
            )
        body: list[str] = []

        var_counter = 0
        node_outputs: dict[str, dict[str, str]] = {}
        engine_vars: dict[str, str] = {}  # connection_id -> engine var
        extra_imports: list[str] = []
        seen_imports = set(base_header)
        # Names already claimed: flow parameters must not be clobbered by a
        # semantic input variable (a parameter named df_sales is legal).
        taken_names = parameter_names(parameter_lines)

        def next_var() -> str:
            nonlocal var_counter
            var_counter += 1
            return f"df_{var_counter}"

        def input_var(name_hint: str | None) -> str:
            """A semantic name for an input frame (sales.csv -> df_sales) when
            the hint yields one, else the next numbered df_N."""
            return frame_var_name(name_hint, taken_names) or next_var()

        def add_imports(imports: list[str]) -> None:
            for imp in imports:
                if imp not in seen_imports:
                    seen_imports.add(imp)
                    extra_imports.append(imp)

        def engine_for(connection_id: str) -> str:
            return sql_engine_var(connection_id, connections, engine_vars, body)

        for idx, node_id in enumerate(order):
            node = nodes_by_id[node_id]
            node_type = node["type"]
            config: dict[str, Any] = node.get("data", {}).get("config", {})

            if node_type == SQL_INPUT_TYPE:
                eng = engine_for(config.get("connection_id", ""))
                if config.get("mode") == "query":
                    var = next_var()
                    body.append(f"{var} = pd.read_sql_query({config.get('query', '')!r}, {eng})")
                else:
                    table = config.get("table")
                    # Name after the table, minus any schema prefix (public.orders
                    # -> df_orders); a parameterized table (CodeRef) falls back.
                    hint = table.rsplit(".", 1)[-1] if isinstance(table, str) else None
                    var = input_var(hint)
                    body.append(f"{var} = pd.read_sql_table({table or ''!r}, {eng})")
                node_outputs[node_id] = {"out": var}

            elif node_type == SQL_OUTPUT_TYPE:
                src_var = edge_source_var(node_outputs, incoming[node_id][0])
                eng = engine_for(config.get("connection_id", ""))
                if_exists = config.get("if_exists", "replace")
                body.append(
                    f"{src_var}.to_sql({config.get('table', '')!r}, {eng}, if_exists={if_exists!r}, index=False)"
                )

            elif node_type in _INPUT_TYPES:
                if node_type == STORAGE_INPUT_TYPE:
                    # Cloud storage isn't reproduced in the portable script: read
                    # the object by its file name, tell the user to fetch it first.
                    source_type = config.get("format") or "csv"
                    remote = config.get("path") or ""
                    if isinstance(remote, str):
                        name_hint = remote.split("/")[-1].split("\\")[-1] or None
                        path = name_hint or placeholder_input_path(source_type)
                    else:  # parameterized path (CodeRef): !r renders the variable
                        name_hint, path = None, remote
                    func = _READ_FUNCS_BY_FORMAT.get(source_type)
                    body.append(f"# {node_type}: download {remote or path!r} from your storage connection first")
                else:
                    source_type = input_source_type(node_type, config)
                    # Semantic names only for resolved datasets — a placeholder's
                    # "input.csv" stem says nothing about the data.
                    name_hint = dataset_paths.get(config.get("dataset_id", ""))
                    path = name_hint or placeholder_input_path(source_type)
                    func = (
                        _READ_FUNCS_BY_FORMAT.get(source_type)
                        if node_type == FILE_INPUT_TYPE
                        else _READ_FUNCS.get(node_type)
                    )
                var = input_var(name_hint)
                node_outputs[node_id] = {"out": var}
                # repr() the path so Windows backslashes, spaces, or quotes in a
                # dataset name / output path can't produce invalid Python.
                if func is not None:
                    kwargs = ""
                    if source_type == "tsv":
                        kwargs = ", sep='\\t'"
                    elif source_type == "jsonl":
                        kwargs = ", lines=True"
                    dialect = (dataset_parse_options or {}).get(config.get("dataset_id", ""))
                    kwargs += pandas_dialect_kwargs(source_type, dialect)
                    body.append(f"{var} = {func}({path!r}{kwargs})")
                elif source_type == "text":
                    body.append(
                        f'{var} = pd.read_csv({path!r}, sep="\\n", header=None, '
                        f'names=["text"], engine="python", dtype=str)'
                    )
                else:
                    body.append(f"{var} = pd.read_csv({path!r})  # unsupported input type: {node_type}")

            elif node_type == FILE_OUTPUT_TYPE:
                src_var = edge_source_var(node_outputs, incoming[node_id][0])
                method, extra, suffix = _FILE_OUTPUT_WRITE[output_source_type(node_type, config)]
                out_path = config.get("path") or f"{config.get('dataset_name') or 'output'}{suffix}"
                body.append(f"{src_var}.{method}({out_path!r}, {extra})")

            elif node_type in _WRITE_FUNCS:
                src_var = edge_source_var(node_outputs, incoming[node_id][0])
                method, extra, default_path = _WRITE_FUNCS[node_type]
                out_path = config.get("path") or default_path
                body.append(f"{src_var}.{method}({out_path!r}, {extra})")

            elif node_type in _OUTPUT_TYPES:
                # Storage output (cloud) isn't reproduced in the portable script.
                src_var = edge_source_var(node_outputs, incoming[node_id][0])
                body.append(f"# {node_type}: write {src_var} to your configured storage target")

            else:
                transformation = get_transformation(node_type)
                input_vars = collect_input_vars(incoming[node_id], node_outputs)
                handles = output_handles(node_type)
                reuse = reusable_output_var(idx, incoming[node_id], node_outputs, len(handles), last_use)
                if reuse is not None:
                    output_vars = {handles[0]: reuse}
                    # The variable now holds this node's output — cancel the del
                    # its previous owner scheduled for this position.
                    dels.cancel(idx, reuse)
                else:
                    output_vars = {h: next_var() for h in handles}
                node_outputs[node_id] = output_vars
                add_imports(transformation.imports(config))
                body.append(strip_self_assign(transformation.to_python_code(input_vars, output_vars, config)))

            dels.schedule(node_id, node_outputs.get(node_id, {}))
            body.extend(dels.flush(idx))

        header = base_header + ordered_imports(extra_imports)
        assert_params_do_not_shadow_imports(header, parameter_lines or [])
        prelude = [*parameter_lines, ""] if parameter_lines else []
        script_body = insert_paragraph_breaks(fuse_method_chains(body))
        return "\n".join([*header, "", *prelude, *script_body]) + "\n"
