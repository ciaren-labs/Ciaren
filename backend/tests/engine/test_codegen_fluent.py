# SPDX-License-Identifier: AGPL-3.0-only
"""Fluent method-chain fusion (``fuse_method_chains``).

Variable reuse leaves linear chains as repeated ``df_1 = df_1.method(...)``
statements; the fusion pass merges each such run into a single chained
expression — one line when short, parenthesized fluent style when long. These
tests pin down:

1. **Unit** — which statement runs fuse, which act as boundaries, and the
   safety rules (a statement whose RHS references its own target more than
   once may start a chain but never continue one).
2. **Rendering** — single-line vs parenthesized output, per-call splitting,
   subscript continuation.
3. **Runtime** — fused output is valid Python and computes the same frames as
   the unfused statements, on pandas and polars.
4. **Driver** — both generators emit fused chains end-to-end and the scripts
   still run.
"""

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from app.engine.codegen import CodeGenerator
from app.engine.codegen_common import fuse_method_chains
from app.engine.polars_codegen import PolarsCodeGenerator

# --- unit: grouping rules -----------------------------------------------------


def test_short_run_merges_to_single_line() -> None:
    lines = ["df_1 = df_1.dropna()", "df_1 = df_1.head(5)"]
    assert fuse_method_chains(lines) == ["df_1 = df_1.dropna().head(5)"]


def test_single_statement_left_untouched() -> None:
    lines = ["df_1 = df_1.dropna()"]
    assert fuse_method_chains(lines) == lines


def test_empty_and_non_assign_lines_untouched() -> None:
    lines = [
        "import pandas as pd",
        "",
        "df_1 = pd.read_csv('in.csv')",
        "df_1.to_csv('out.csv', index=False)",
        "del df_1",
    ]
    assert fuse_method_chains(list(lines)) == lines


def test_long_run_renders_parenthesized_one_call_per_line() -> None:
    lines = [
        "df_1 = df_1.filter(pl.col('amount') > 0)",
        "df_1 = df_1.group_by(['region']).agg([pl.col('amount').sum().alias('amount')])",
        "df_1 = df_1.rename({'amount': 'total_sales'})",
        "df_1 = df_1.sort(['total_sales'], descending=True, nulls_last=True)",
    ]
    fused = fuse_method_chains(lines)
    assert fused == [
        "df_1 = (",
        "    df_1.filter(pl.col('amount') > 0)",
        "    .group_by(['region'])",
        "    .agg([pl.col('amount').sum().alias('amount')])",
        "    .rename({'amount': 'total_sales'})",
        "    .sort(['total_sales'], descending=True, nulls_last=True)",
        ")",
    ]
    compile("\n".join(fused), "<fused>", "exec")


def test_spine_split_never_splits_inside_arguments() -> None:
    # pl.col('a').sum() lives inside agg's argument list: its dots are not
    # spine dots and must stay on the .agg line.
    lines = [
        "df_1 = df_1.group_by(['a']).agg([pl.col('b').sum().alias('b'), pl.col('c').mean().alias('c')])",
        "df_1 = df_1.sort(['a'], descending=False, nulls_last=True)",
    ]
    fused = fuse_method_chains(lines)
    assert "    .agg([pl.col('b').sum().alias('b'), pl.col('c').mean().alias('c')])" in fused


def test_multi_ref_statement_may_start_but_not_continue() -> None:
    # df_1[df_1['a'] > 0] reads df_1 twice: as a chain continuation the mask
    # would see the pre-chain frame — it must break the run instead.
    lines = [
        "df_1 = df_1.dropna()",
        "df_1 = df_1[df_1['a'] > 0]",
        "df_1 = df_1.sort_values(by=['a'], ascending=True)",
    ]
    fused = fuse_method_chains(lines)
    assert fused[0] == "df_1 = df_1.dropna()"
    assert fused[1] == "df_1 = df_1[df_1['a'] > 0].sort_values(by=['a'], ascending=True)"


def test_loc_lambda_filter_continues_a_chain() -> None:
    # The pandas filter emitters use `.loc[lambda _d: …]` precisely so the
    # statement references its variable once and can sit mid-chain; the lambda
    # body's `_d` names must not count as extra references.
    lines = [
        "df_1 = df_1.dropna()",
        "df_1 = df_1.loc[lambda _d: _d['age'] > 21]",
        "df_1 = df_1.sort_values(by=['age'], ascending=True)",
    ]
    fused = fuse_method_chains(list(lines))
    assert fused == [
        "df_1 = (",
        "    df_1.dropna()",
        "    .loc[lambda _d: _d['age'] > 21]",
        "    .sort_values(by=['age'], ascending=True)",
        ")",
    ]
    df = pd.DataFrame({"age": [30.0, None, 25.0, 18.0], "name": ["a", "b", "c", "d"]})
    plain = _exec_lines(list(lines), {"df_1": df.copy()})
    fused_ns = _exec_lines(fused, {"df_1": df.copy()})
    pd.testing.assert_frame_equal(plain["df_1"], fused_ns["df_1"])


def test_assign_referencing_source_may_start_chain() -> None:
    # calculatedColumn's pandas form references src in its argument; as the
    # first step every reference still sees the same pre-chain frame.
    lines = [
        "df_1 = df_1.assign(**{'x2': df_1.eval('a * 2')})",
        "df_1 = df_1.rename(columns={'a': 'alpha'})",
    ]
    fused = fuse_method_chains(lines)
    assert fused == ["df_1 = df_1.assign(**{'x2': df_1.eval('a * 2')}).rename(columns={'a': 'alpha'})"]


def test_fanout_start_rooted_in_other_variable_fuses() -> None:
    lines = [
        "df_2 = df_1.groupby(['r']).agg({'v': 'sum'}).reset_index()",
        "df_2 = df_2.rename(columns={'v': 'total'})",
    ]
    fused = fuse_method_chains(lines)
    # Just over the single-line budget, so it renders parenthesized — rooted
    # in df_1, with df_2's intermediate assignment gone.
    assert fused == [
        "df_2 = (",
        "    df_1.groupby(['r'])",
        "    .agg({'v': 'sum'})",
        "    .reset_index()",
        "    .rename(columns={'v': 'total'})",
        ")",
    ]


def test_fanout_start_short_run_merges_to_single_line() -> None:
    lines = [
        "df_2 = df_1.dropna()",
        "df_2 = df_2.head(5)",
    ]
    assert fuse_method_chains(lines) == ["df_2 = df_1.dropna().head(5)"]


def test_different_targets_do_not_fuse() -> None:
    lines = [
        "df_2 = df_1.dropna()",
        "df_3 = df_2.head(5)",
    ]
    assert fuse_method_chains(list(lines)) == lines


def test_del_between_statements_breaks_the_run() -> None:
    lines = [
        "df_1 = df_1.dropna()",
        "del df_2",
        "df_1 = df_1.head(5)",
    ]
    assert fuse_method_chains(list(lines)) == lines


def test_comment_and_multiline_entries_break_the_run() -> None:
    lines = [
        "df_1 = df_1.dropna()",
        "# pivot has no lazy equivalent — materialize here",
        "df_1 = df_1.head(5)",
    ]
    assert fuse_method_chains(list(lines)) == lines
    multi = "df_1['a'] = df_1['a'].astype(float)\ndf_1['b'] = df_1['b'].astype(str)"
    lines2 = ["df_1 = df_1.dropna()", multi, "df_1 = df_1.head(5)"]
    assert fuse_method_chains(list(lines2)) == lines2


def test_non_df_roots_and_targets_are_boundaries() -> None:
    lines = [
        "df_1 = pd.read_csv('in.csv')",  # root pd: never fused into
        "df_1 = df_1.dropna()",
        "_eager_1 = df_1.collect()",  # target not df_N
        "df_2 = _eager_1.lazy()",  # root not df_N
    ]
    assert fuse_method_chains(list(lines)) == lines


def test_subscript_continuation_stays_on_previous_line() -> None:
    # selectColumns emits a bare subscript; `[` opening a line would read as
    # indexing thin air, so it must attach to the previous physical line.
    lines = [
        "df_1 = df_1.drop_duplicates(keep='first')",
        "df_1 = df_1[['name', 'age', 'city', 'country', 'email', 'phone', 'signup_date']]",
        "df_1 = df_1.sort_values(by=['signup_date'], ascending=False)",
    ]
    fused = fuse_method_chains(lines)
    assert fused == [
        "df_1 = (",
        "    df_1.drop_duplicates(keep='first')[['name', 'age', 'city', 'country', 'email', 'phone', 'signup_date']]",
        "    .sort_values(by=['signup_date'], ascending=False)",
        ")",
    ]
    compile("\n".join(fused), "<fused>", "exec")


def test_indented_lines_are_boundaries() -> None:
    lines = [
        "with open('in.txt') as _f:",
        '    df_1 = pl.DataFrame({"text": _f.read().splitlines()})',
        "df_1 = df_1.head(5)",
    ]
    assert fuse_method_chains(list(lines)) == lines


def test_augmented_and_tuple_assigns_are_boundaries() -> None:
    lines = [
        "df_1 = df_1.dropna()",
        "df_1, df_2 = df_1.a(), df_1.b()",
        "df_1 += df_1.c()",
        "df_1 = df_1.head(5)",
    ]
    assert fuse_method_chains(list(lines)) == lines


def test_unicode_column_names_split_at_real_spine_dots() -> None:
    # ast col offsets are UTF-8 byte offsets; str slicing is per character.
    # Accented names before a spine dot used to shift the split point — in the
    # worst case onto a '.' inside a later string literal, emitting code that
    # doesn't compile.
    lines = [
        "df_1 = df_1.groupby(['ééééééé']).agg({'.y': 'sum'}).reset_index()",
        "df_1 = df_1.rename(columns={'zzzzzzzzzzzzzzzzzzzzzz': 'w'})",
    ]
    fused = fuse_method_chains(list(lines))
    compile("\n".join(fused), "<fused>", "exec")
    assert fused == [
        "df_1 = (",
        "    df_1.groupby(['ééééééé'])",
        "    .agg({'.y': 'sum'})",
        "    .reset_index()",
        "    .rename(columns={'zzzzzzzzzzzzzzzzzzzzzz': 'w'})",
        ")",
    ]


def test_unicode_fused_statements_compute_same_frame() -> None:
    df = pd.DataFrame({"région": ["n", "s", "n"], "montant": [1.0, 2.0, 3.0]})
    lines = [
        "df_1 = df_1.groupby(['région']).agg({'montant': 'sum'}).reset_index()",
        "df_1 = df_1.rename(columns={'montant': 'total récolté'})",
        "df_1 = df_1.sort_values(by=['total récolté'], ascending=False)",
    ]
    plain = _exec_lines(list(lines), {"df_1": df.copy()})
    fused_lines = fuse_method_chains(list(lines))
    assert fused_lines[0] == "df_1 = ("  # long enough to take the paren path
    fused = _exec_lines(fused_lines, {"df_1": df.copy()})
    pd.testing.assert_frame_equal(plain["df_1"], fused["df_1"])


# --- runtime: fused output computes the same frames ---------------------------


def _exec_lines(lines: list[str], namespace: dict) -> dict:
    exec("\n".join(lines), namespace)  # noqa: S102 — test fixture
    return namespace


def test_fused_pandas_statements_compute_same_frame() -> None:
    df = pd.DataFrame({"a": [3.0, 1.0, None, 2.0], "b": ["x", "y", "z", "w"]})
    lines = [
        "df_1 = df_1.dropna()",
        "df_1 = df_1.rename(columns={'a': 'alpha'})",
        "df_1 = df_1.sort_values(by=['alpha'], ascending=True)",
        "df_1 = df_1.head(2)",
    ]
    plain = _exec_lines(lines, {"df_1": df.copy()})
    fused_lines = fuse_method_chains(list(lines))
    assert fused_lines != lines  # the pass actually rewrote something
    fused = _exec_lines(fused_lines, {"df_1": df.copy()})
    pd.testing.assert_frame_equal(plain["df_1"], fused["df_1"])


def test_fused_polars_statements_compute_same_frame() -> None:
    pl = pytest.importorskip("polars")
    # Distinct per-group sums (n=4, s=9): group_by has no defined row order, so
    # a tie would make the final sort nondeterministic between runs.
    df = pl.DataFrame({"region": ["n", "s", "n", "s"], "amount": [1.0, -2.0, 3.0, 9.0]})
    lines = [
        "df_1 = df_1.filter(pl.col('amount') > 0)",
        "df_1 = df_1.group_by(['region']).agg([pl.col('amount').sum().alias('amount')])",
        "df_1 = df_1.rename({'amount': 'total_sales'})",
        "df_1 = df_1.sort(['total_sales'], descending=True, nulls_last=True)",
    ]
    plain = _exec_lines(list(lines), {"df_1": df.clone(), "pl": pl})
    fused_lines = fuse_method_chains(list(lines))
    assert fused_lines[0] == "df_1 = ("  # long chain went parenthesized
    fused = _exec_lines(fused_lines, {"df_1": df.clone(), "pl": pl})
    assert plain["df_1"].equals(fused["df_1"])


def test_fused_multi_ref_start_computes_same_frame() -> None:
    df = pd.DataFrame({"a": [3.0, -1.0, 2.0], "b": [1, 2, 3]})
    lines = [
        "df_1 = df_1[df_1['a'] > 0]",
        "df_1 = df_1.sort_values(by=['a'], ascending=True)",
    ]
    plain = _exec_lines(list(lines), {"df_1": df.copy()})
    fused = _exec_lines(fuse_method_chains(list(lines)), {"df_1": df.copy()})
    pd.testing.assert_frame_equal(plain["df_1"], fused["df_1"])


# --- driver: end-to-end generated scripts -------------------------------------


def _sales_graph() -> dict:
    return {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "d"}}},
            {"id": "f", "type": "filterRows", "data": {"config": {"column": "amount", "operator": ">", "value": 0}}},
            {
                "id": "g",
                "type": "groupByAggregate",
                "data": {"config": {"group_by": ["region"], "aggregations": {"amount": "sum"}}},
            },
            {"id": "r", "type": "renameColumns", "data": {"config": {"mapping": {"amount": "total_sales"}}}},
            {"id": "s", "type": "sortRows", "data": {"config": {"columns": ["total_sales"], "ascending": False}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "f"},
            {"id": "e2", "source": "f", "target": "g"},
            {"id": "e3", "source": "g", "target": "r"},
            {"id": "e4", "source": "r", "target": "s"},
            {"id": "e5", "source": "s", "target": "out"},
        ],
    }


def _run(code: str, tmp_path: Path) -> pd.DataFrame:
    script = tmp_path / "script.py"
    script.write_text(code, encoding="utf-8")
    result = subprocess.run([sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, f"generated script failed:\n{result.stderr}\n---\n{code}"
    return pd.read_csv(tmp_path / "out.csv")


def _write_sales(tmp_path: Path) -> dict[str, str]:
    (tmp_path / "in.csv").write_text("region,amount\nnorth,10\nsouth,-5\nnorth,20\nsouth,7\neast,3\n")
    return {"d": "in.csv"}


def test_polars_generator_emits_fluent_chain(tmp_path: Path) -> None:
    paths = _write_sales(tmp_path)
    for lazy in (False, True):
        code = PolarsCodeGenerator().generate(_sales_graph(), paths, lazy=lazy)
        assert "df_1 = (" in code
        assert "\n    .group_by('region')\n" in code
        assert "\n    .agg(pl.col('amount').sum())\n" in code
        assert "\n    .rename({'amount': 'total_sales'})\n" in code
        out = _run(code, tmp_path)
        assert list(out["region"]) == ["north", "south", "east"]
        assert list(out["total_sales"]) == [30, 7, 3]


def test_pandas_generator_emits_fluent_chain(tmp_path: Path) -> None:
    paths = _write_sales(tmp_path)
    code = CodeGenerator().generate(_sales_graph(), paths)
    assert "df_1 = (" in code
    # The filter's callable form chains like any other step.
    assert "\n    df_1.loc[lambda _d: _d['amount'] > 0]\n" in code
    assert "\n    .groupby('region')\n" in code
    out = _run(code, tmp_path)
    assert list(out["region"]) == ["north", "south", "east"]
    assert list(out["total_sales"]) == [30, 7, 3]


def test_free_intermediates_still_correct_with_fusion(tmp_path: Path) -> None:
    """Fusion must not swallow or cross `del` statements on fan-out flows."""
    paths = _write_sales(tmp_path)
    graph = _sales_graph()
    # Fan-out: the filter output feeds both the aggregate and a join with it;
    # the sort node is dropped, the join defines the output.
    graph["nodes"] = [n for n in graph["nodes"] if n["id"] != "s"]
    graph["nodes"].insert(
        4,
        {
            "id": "j",
            "type": "join",
            "data": {"config": {"left_on": ["region"], "right_on": ["region"], "how": "inner"}},
        },
    )
    graph["edges"] = [
        {"id": "e1", "source": "in", "target": "f"},
        {"id": "e2", "source": "f", "target": "g"},
        {"id": "e3", "source": "g", "target": "r"},
        {"id": "e4", "source": "f", "target": "j", "targetHandle": "left"},
        {"id": "e5", "source": "r", "target": "j", "targetHandle": "right"},
        {"id": "e6", "source": "j", "target": "out"},
    ]
    for code in (
        CodeGenerator().generate(graph, paths, free_intermediates=True),
        PolarsCodeGenerator().generate(graph, paths, free_intermediates=True),
    ):
        out = _run(code, tmp_path)
        assert len(out) == 4  # north x2, south, east — negative amount filtered
