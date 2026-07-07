# SPDX-License-Identifier: AGPL-3.0-only
"""Readability features of the exported scripts, and the I/O-node gaps found
alongside them.

1. **Naming** — input frames are named after their dataset file / SQL table
   (``df_sales = pd.read_csv('sales.csv')``) with sanitization, duplicate
   suffixes, and flow-parameter reservation; unusable stems fall back to the
   numbered ``df_N`` sequence.
2. **Paragraphs** — blank lines around parenthesized fluent chains, so a script
   reads as reads / transform blocks / writes.
3. **Storage nodes** — ``storageInput`` / ``storageOutput`` export a guided
   placeholder in both dialects instead of crashing the whole export.
4. **Sinks** — legacy typed outputs default to a filename matching their format,
   and a lazy fan-out to several sinks collects the plan once, not per sink.
"""

import subprocess
import sys
from pathlib import Path

import pandas as pd

from app.engine.codegen import CodeGenerator
from app.engine.codegen_common import frame_var_name, insert_paragraph_breaks
from app.engine.polars_codegen import PolarsCodeGenerator

# --- unit: frame_var_name ------------------------------------------------------


def test_stem_is_lowercased_and_sanitized() -> None:
    assert frame_var_name("Sales 2024 (final).csv", set()) == "df_sales_2024_final"


def test_directories_and_extension_are_stripped() -> None:
    assert frame_var_name("exports/monthly/orders.parquet", set()) == "df_orders"
    assert frame_var_name("exports\\monthly\\orders.parquet", set()) == "df_orders"


def test_table_name_without_extension_works() -> None:
    assert frame_var_name("customers", set()) == "df_customers"


def test_all_digit_stem_falls_back() -> None:
    # df_2024 would collide with the numbered df_N namespace.
    assert frame_var_name("2024.csv", set()) is None


def test_empty_and_overlong_stems_fall_back() -> None:
    assert frame_var_name("", set()) is None
    assert frame_var_name("???.csv", set()) is None
    assert frame_var_name("a" * 31 + ".csv", set()) is None


def test_duplicates_get_numeric_suffix() -> None:
    taken: set[str] = set()
    assert frame_var_name("sales.csv", taken) == "df_sales"
    assert frame_var_name("sales.csv", taken) == "df_sales_2"
    assert frame_var_name("sales.csv", taken) == "df_sales_3"


def test_taken_names_are_respected() -> None:
    # A flow parameter named df_sales must not be clobbered by the input read.
    assert frame_var_name("sales.csv", {"df_sales"}) == "df_sales_2"


def test_non_string_hint_falls_back() -> None:
    # A parameterized config holds a CodeRef, not a string (audit finding: this
    # used to raise and silently drop the parameter prelude from the export).
    from app.engine.codegen_params import CodeRef

    assert frame_var_name(CodeRef("tbl"), set()) is None
    assert frame_var_name(42, set()) is None


def test_df_prefixed_stem_is_not_double_prefixed() -> None:
    assert frame_var_name("df_sales.csv", set()) == "df_sales"


# --- unit: insert_paragraph_breaks ----------------------------------------------


def test_blank_lines_wrap_parenthesized_chains() -> None:
    lines = [
        "df_a = pd.read_csv('a.csv')",
        "df_1 = (",
        "    df_a.dropna()",
        "    .head(5)",
        ")",
        "df_1.to_csv('out.csv', index=False)",
    ]
    assert insert_paragraph_breaks(lines) == [
        "df_a = pd.read_csv('a.csv')",
        "",
        "df_1 = (",
        "    df_a.dropna()",
        "    .head(5)",
        ")",
        "",
        "df_1.to_csv('out.csv', index=False)",
    ]


def test_adjacent_chains_get_single_separator_and_no_trailing_blank() -> None:
    lines = ["df_1 = (", "    x.a()", "    .b()", ")", "df_2 = (", "    y.c()", "    .d()", ")"]
    out = insert_paragraph_breaks(lines)
    assert out.count("") == 1  # one blank between the chains, none at the edges
    assert out[0] == "df_1 = (" and out[-1] == ")"


def test_short_scripts_are_untouched() -> None:
    lines = ["df_a = pd.read_csv('a.csv')", "df_a = df_a.dropna()", "df_a.to_csv('out.csv', index=False)"]
    assert insert_paragraph_breaks(list(lines)) == lines


# --- driver: semantic input names -----------------------------------------------


def _linear_graph(dataset_id: str = "d") -> dict:
    return {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "out"},
        ],
    }


def test_input_variable_named_after_dataset() -> None:
    for code, read in (
        (CodeGenerator().generate(_linear_graph(), {"d": "sales.csv"}), "pd.read_csv"),
        (PolarsCodeGenerator().generate(_linear_graph(), {"d": "sales.csv"}), "pl.read_csv"),
    ):
        assert f"df_sales = {read}('sales.csv')" in code
        assert "df_1" not in code


def test_unresolved_dataset_keeps_numbered_variable() -> None:
    # A placeholder's "input.csv" stem says nothing about the data.
    code = CodeGenerator().generate(_linear_graph(), {})
    assert "df_1 = pd.read_csv('input.csv')" in code


def test_parameter_prelude_reserves_the_name() -> None:
    code = CodeGenerator().generate(
        _linear_graph(),
        {"d": "sales.csv"},
        parameter_lines=["df_sales = 10"],
    )
    assert "df_sales_2 = pd.read_csv('sales.csv')" in code


def test_two_datasets_with_same_stem_stay_distinct() -> None:
    graph = {
        "nodes": [
            {"id": "a", "type": "csvInput", "data": {"config": {"dataset_id": "d1"}}},
            {"id": "b", "type": "csvInput", "data": {"config": {"dataset_id": "d2"}}},
            {"id": "cat", "type": "concatRows", "data": {"config": {}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "a", "target": "cat"},
            {"id": "e2", "source": "b", "target": "cat"},
            {"id": "e3", "source": "cat", "target": "out"},
        ],
    }
    code = CodeGenerator().generate(graph, {"d1": "sales.csv", "d2": "archive/sales.csv"})
    assert "df_sales = " in code and "df_sales_2 = " in code


def _sql_graph(table: str) -> dict:
    return {
        "nodes": [
            {"id": "in", "type": "sqlInput", "data": {"config": {"connection_id": "c", "table": table}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [{"id": "e1", "source": "in", "target": "out"}],
    }


_CONNS = {"c": {"provider": "sqlite", "database": "db.sqlite"}}


def test_sql_table_read_uses_table_name() -> None:
    pandas_code = CodeGenerator().generate(_sql_graph("orders"), {}, _CONNS)
    assert "df_orders = pd.read_sql_table('orders', _engine_1)" in pandas_code
    polars_code = PolarsCodeGenerator().generate(_sql_graph("orders"), {}, _CONNS)
    assert "df_orders = pl.read_database('SELECT * FROM orders', _engine_1.connect())" in polars_code


def test_schema_qualified_table_names_after_the_table() -> None:
    # public.orders must not become df_public (and collide across the schema).
    code = CodeGenerator().generate(_sql_graph("public.orders"), {}, _CONNS)
    assert "df_orders = pd.read_sql_table('public.orders', _engine_1)" in code


def test_parameterized_sql_table_keeps_parameter_prelude() -> None:
    """Audit regression: a CodeRef table crashed frame_var_name, and the export
    service silently fell back to inlined defaults with no parameter block."""
    from app.engine.codegen_params import parameter_block_lines, substitute_for_codegen

    graph = _sql_graph("{{ tbl }}")
    graph["parameters"] = [{"name": "tbl", "type": "string", "default": "orders"}]
    params = parameter_block_lines(graph)
    code_graph = substitute_for_codegen(graph)
    pandas_code = CodeGenerator().generate(code_graph, {}, _CONNS, parameter_lines=params)
    assert "tbl = 'orders'" in pandas_code
    assert "df_1 = pd.read_sql_table(tbl, _engine_1)" in pandas_code
    compile(pandas_code, "<param-sql>", "exec")
    polars_code = PolarsCodeGenerator().generate(code_graph, {}, _CONNS, parameter_lines=params)
    assert "pl.read_database('SELECT * FROM ' + tbl, _engine_1.connect())" in polars_code
    compile(polars_code, "<param-sql-polars>", "exec")


def test_parameterized_storage_path_keeps_parameter_prelude() -> None:
    from app.engine.codegen_params import parameter_block_lines, substitute_for_codegen

    graph = {
        "nodes": [
            {
                "id": "a",
                "type": "storageInput",
                "data": {"config": {"connection_id": "c", "path": "{{ obj }}", "format": "parquet"}},
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [{"id": "e1", "source": "a", "target": "out"}],
        "parameters": [{"name": "obj", "type": "string", "default": "exports/sales.parquet"}],
    }
    params = parameter_block_lines(graph)
    code_graph = substitute_for_codegen(graph)
    for code in (
        CodeGenerator().generate(code_graph, {}, parameter_lines=params),
        PolarsCodeGenerator().generate(code_graph, {}, parameter_lines=params),
    ):
        assert "obj = 'exports/sales.parquet'" in code
        assert "(obj)" in code  # the read takes the parameter variable
        compile(code, "<param-storage>", "exec")


def test_semantic_named_chain_still_fuses_and_runs(tmp_path: Path) -> None:
    graph = _linear_graph()
    graph["nodes"].insert(2, {"id": "lim", "type": "limitRows", "data": {"config": {"n": 2}}})
    graph["edges"] = [
        {"id": "e1", "source": "in", "target": "drop"},
        {"id": "e2", "source": "drop", "target": "lim"},
        {"id": "e3", "source": "lim", "target": "out"},
    ]
    (tmp_path / "people.csv").write_text("name,age\nAlice,30\nBob,\nCarol,25\n")
    for code in (
        CodeGenerator().generate(graph, {"d": "people.csv"}),
        PolarsCodeGenerator().generate(graph, {"d": "people.csv"}, lazy=True),
    ):
        assert "df_people = df_people." in code  # reuse + fusion on the semantic name
        out = _run(code, tmp_path)
        assert list(out["name"]) == ["Alice", "Carol"]


# --- driver: storage nodes -------------------------------------------------------


def _storage_graph() -> dict:
    return {
        "nodes": [
            {
                "id": "a",
                "type": "storageInput",
                "data": {"config": {"connection_id": "c", "path": "exports/sales.parquet", "format": "parquet"}},
            },
            {"id": "b", "type": "limitRows", "data": {"config": {"n": 5}}},
            {
                "id": "c",
                "type": "storageOutput",
                "data": {"config": {"connection_id": "c", "path": "out.parquet"}},
            },
        ],
        "edges": [
            {"id": "e1", "source": "a", "target": "b"},
            {"id": "e2", "source": "b", "target": "c"},
        ],
    }


def test_storage_nodes_export_guided_placeholders() -> None:
    """Regression: storageInput used to raise KeyError in both generators,
    failing the whole export of any flow touching object storage."""
    pandas_code = CodeGenerator().generate(_storage_graph(), {})
    assert "# storageInput: download 'exports/sales.parquet' from your storage connection first" in pandas_code
    assert "df_sales = pd.read_parquet('sales.parquet')" in pandas_code
    assert "# storageOutput: write df_sales to your configured storage target" in pandas_code
    compile(pandas_code, "<storage-pandas>", "exec")

    eager = PolarsCodeGenerator().generate(_storage_graph(), {})
    assert "df_sales = pl.read_parquet('sales.parquet')" in eager
    lazy = PolarsCodeGenerator().generate(_storage_graph(), {}, lazy=True)
    assert "df_sales = pl.scan_parquet('sales.parquet')" in lazy
    for code in (eager, lazy):
        assert "# storageOutput: write df_sales to your configured storage target" in code
        compile(code, "<storage-polars>", "exec")


# --- driver: sink defaults and lazy collect-once ----------------------------------


def test_legacy_typed_outputs_default_to_matching_extension() -> None:
    for out_type, expected in (("excelOutput", "output.xlsx"), ("parquetOutput", "output.parquet")):
        graph = _linear_graph()
        graph["nodes"][2] = {"id": "out", "type": out_type, "data": {"config": {}}}
        for code in (
            CodeGenerator().generate(graph, {}),
            PolarsCodeGenerator().generate(graph, {}),
        ):
            assert repr(expected) in code, f"{out_type}: expected {expected!r} in:\n{code}"
            assert "'output.csv'" not in code


def _multi_sink_graph() -> dict:
    return {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "d"}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            {"id": "o1", "type": "csvOutput", "data": {"config": {"path": "a.csv"}}},
            {"id": "o2", "type": "csvOutput", "data": {"config": {"path": "b.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "o1"},
            {"id": "e3", "source": "drop", "target": "o2"},
        ],
    }


def test_lazy_fanout_to_sinks_collects_once(tmp_path: Path) -> None:
    code = PolarsCodeGenerator().generate(_multi_sink_graph(), {"d": "people.csv"}, lazy=True)
    # One collect for two writes — never one per sink.
    assert code.count(".collect()") == 1
    assert "df_people.write_csv('a.csv')" in code
    assert "df_people.write_csv('b.csv')" in code
    (tmp_path / "people.csv").write_text("name,age\nAlice,30\nBob,\n")
    _run(code, tmp_path, out_name="a.csv")
    assert len(pd.read_csv(tmp_path / "b.csv")) == 1


def test_lazy_single_sink_collects_inline(tmp_path: Path) -> None:
    code = PolarsCodeGenerator().generate(_linear_graph(), {"d": "people.csv"}, lazy=True)
    assert code.count(".collect()") == 1
    (tmp_path / "people.csv").write_text("name,age\nAlice,30\nBob,\n")
    out = _run(code, tmp_path)
    assert list(out["name"]) == ["Alice"]


# --- helpers ----------------------------------------------------------------------


def _run(code: str, tmp_path: Path, out_name: str = "out.csv") -> pd.DataFrame:
    script = tmp_path / "script.py"
    script.write_text(code, encoding="utf-8")
    result = subprocess.run([sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, f"generated script failed:\n{result.stderr}\n---\n{code}"
    return pd.read_csv(tmp_path / out_name)
