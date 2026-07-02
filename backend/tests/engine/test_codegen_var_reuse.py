"""Variable reuse on linear chains (``df_1 = df_1.dropna()`` instead of ``df_2 = …``).

Both generators write a node's result back into its input's variable when that
variable is dead afterwards (see ``reusable_output_var``). These tests pin down:

1. **Unit** — the reuse predicate's edge cases (fan-out, multi-input,
   multi-output source, last-consumer position).
2. **Static** — linear chains export with a single ``df_1``; fan-outs still get
   distinct variables per live branch.
3. **Runtime** — reused-variable scripts execute end-to-end and produce the
   same data as before, including with ``free_intermediates`` (a reused variable
   must never be ``del``'d at the point of reuse).
"""

import subprocess
import sys
from pathlib import Path

import pandas as pd

from app.engine.codegen import CodeGenerator
from app.engine.codegen_common import reusable_output_var
from app.engine.polars_codegen import PolarsCodeGenerator

# --- unit: the reuse predicate --------------------------------------------


def test_reuse_simple_linear_chain() -> None:
    edges = [{"source": "a", "target": "b"}]
    outs = {"a": {"out": "df_1"}}
    assert reusable_output_var(1, edges, outs, 1, {"a": 1}) == "df_1"


def test_no_reuse_when_node_is_not_last_consumer() -> None:
    # a fans out; the consumer at idx 1 must not steal the var needed at idx 2.
    edges = [{"source": "a", "target": "b"}]
    outs = {"a": {"out": "df_1"}}
    assert reusable_output_var(1, edges, outs, 1, {"a": 2}) is None


def test_no_reuse_for_multi_input_node() -> None:
    edges = [
        {"source": "a", "target": "j", "targetHandle": "left"},
        {"source": "b", "target": "j", "targetHandle": "right"},
    ]
    outs = {"a": {"out": "df_1"}, "b": {"out": "df_2"}}
    assert reusable_output_var(2, edges, outs, 1, {"a": 2, "b": 2}) is None


def test_no_reuse_for_multi_output_node() -> None:
    edges = [{"source": "a", "target": "b"}]
    assert reusable_output_var(1, edges, {"a": {"out": "df_1"}}, 2, {"a": 1}) is None


def test_no_reuse_from_multi_output_source() -> None:
    # Liveness is per node, not per handle: train may be dead but test still live.
    edges = [{"source": "split", "target": "b", "sourceHandle": "train"}]
    outs = {"split": {"train": "df_1", "test": "df_2"}}
    assert reusable_output_var(1, edges, outs, 1, {"split": 1}) is None


# --- static: generated script shape ----------------------------------------


def _linear_graph() -> dict:
    return {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            {"id": "flt", "type": "filterRows", "data": {"config": {"column": "age", "operator": ">", "value": 21}}},
            {"id": "srt", "type": "sortRows", "data": {"config": {"columns": ["age"]}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "flt"},
            {"id": "e3", "source": "flt", "target": "srt"},
            {"id": "e4", "source": "srt", "target": "out"},
        ],
    }


def test_pandas_linear_chain_uses_single_variable() -> None:
    code = CodeGenerator().generate(_linear_graph(), {"ds1": "in.csv"})
    assert "df_1 = pd.read_csv('in.csv')" in code
    assert "df_1 = df_1.dropna()" in code
    assert "df_1 = df_1[df_1['age'] > 21]" in code
    assert "df_1 = df_1.sort_values(by=['age'], ascending=True)" in code
    assert "df_1.to_csv('out.csv', index=False)" in code
    assert "df_2" not in code


def test_polars_linear_chain_uses_single_variable() -> None:
    for lazy in (False, True):
        code = PolarsCodeGenerator().generate(_linear_graph(), {"ds1": "in.csv"}, lazy=lazy)
        assert "df_2" not in code
        assert "df_1 = df_1.drop_nulls()" in code
        assert "df_1 = df_1.filter(pl.col('age') > 21)" in code


def _fanout_graph() -> dict:
    """in feeds two filters that re-converge in a concat; only the input's *last*
    consumer may take over df_1."""
    return {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "fa", "type": "filterRows", "data": {"config": {"column": "age", "operator": ">", "value": 25}}},
            {"id": "fb", "type": "filterRows", "data": {"config": {"column": "age", "operator": "<=", "value": 25}}},
            {"id": "cat", "type": "concatRows", "data": {"config": {}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "fa"},
            {"id": "e2", "source": "in", "target": "fb"},
            {"id": "e3", "source": "fa", "target": "cat"},
            {"id": "e4", "source": "fb", "target": "cat"},
            {"id": "e5", "source": "cat", "target": "out"},
        ],
    }


def test_pandas_fanout_keeps_live_branches_distinct() -> None:
    code = CodeGenerator().generate(_fanout_graph(), {"ds1": "in.csv"})
    # First branch must not overwrite df_1 (the second branch still reads it);
    # the second branch may. Concat is multi-input, so it gets a fresh var.
    assert "df_2 = df_1[df_1['age'] > 25]" in code
    assert "df_1 = df_1[df_1['age'] <= 25]" in code
    assert "df_3 = pd.concat([df_2, df_1], ignore_index=True)" in code


# --- runtime: scripts still compute the right thing --------------------------


def _run(code: str, tmp_path: Path) -> pd.DataFrame:
    script = tmp_path / "script.py"
    script.write_text(code, encoding="utf-8")
    result = subprocess.run([sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, f"generated script failed:\n{result.stderr}"
    return pd.read_csv(tmp_path / "out.csv")


def _write_people(tmp_path: Path) -> dict[str, str]:
    (tmp_path / "in.csv").write_text("name,age\nAlice,30\nBob,\nCarol,25\nDave,40\n")
    return {"ds1": "in.csv"}


def test_pandas_linear_chain_runs(tmp_path: Path) -> None:
    paths = _write_people(tmp_path)
    code = CodeGenerator().generate(_linear_graph(), paths)
    out = _run(code, tmp_path)
    assert list(out["name"]) == ["Carol", "Alice", "Dave"]  # null dropped, >21, sorted


def test_polars_linear_chain_runs(tmp_path: Path) -> None:
    paths = _write_people(tmp_path)
    for lazy in (False, True):
        code = PolarsCodeGenerator().generate(_linear_graph(), paths, lazy=lazy)
        out = _run(code, tmp_path)
        assert list(out["name"]) == ["Carol", "Alice", "Dave"]


# Bob's age is null, so he fails both filter branches: 3 rows re-converge.


def test_pandas_fanout_runs(tmp_path: Path) -> None:
    paths = _write_people(tmp_path)
    code = CodeGenerator().generate(_fanout_graph(), paths)
    out = _run(code, tmp_path)
    assert sorted(out["name"].astype(str)) == ["Alice", "Carol", "Dave"]


def test_polars_fanout_runs(tmp_path: Path) -> None:
    paths = _write_people(tmp_path)
    code = PolarsCodeGenerator().generate(_fanout_graph(), paths)
    out = _run(code, tmp_path)
    assert sorted(out["name"].astype(str)) == ["Alice", "Carol", "Dave"]


def test_reused_variable_is_never_deleted_at_reuse_point(tmp_path: Path) -> None:
    """free_intermediates must not del a variable that was just reused: the del the
    input's owner scheduled for this position is cancelled by the takeover."""
    paths = _write_people(tmp_path)
    for code in (
        CodeGenerator().generate(_linear_graph(), paths, free_intermediates=True),
        PolarsCodeGenerator().generate(_linear_graph(), paths, free_intermediates=True),
    ):
        # A fully reused linear chain leaves nothing to free.
        assert "del " not in code
        out = _run(code, tmp_path)
        assert list(out["name"]) == ["Carol", "Alice", "Dave"]


def test_fanout_free_intermediates_still_correct(tmp_path: Path) -> None:
    paths = _write_people(tmp_path)
    code = CodeGenerator().generate(_fanout_graph(), paths, free_intermediates=True)
    # df_2 (first branch) and df_1 (reused by second branch) die at the concat.
    assert "del df_2" in code
    out = _run(code, tmp_path)
    assert len(out) == 3


def _cast_chain_graph() -> dict:
    """csvInput -> castDtypes -> csvOutput: castDtypes seeds its snippet with
    ``dst = src``, which under reuse degenerates to ``df_1 = df_1``."""
    return {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "d"}}},
            {"id": "c", "type": "castDtypes", "data": {"config": {"casts": {"a": "float", "t": "datetime"}}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "c"},
            {"id": "e2", "source": "c", "target": "out"},
        ],
    }


def test_reuse_emits_no_self_assign_noop() -> None:
    """Seed-line emitters (castDtypes, asserts, outliers) must not leave a
    ``df_1 = df_1`` line behind when their output variable is the reused input."""
    for code in (
        CodeGenerator().generate(_cast_chain_graph(), {"d": "in.csv"}),
        PolarsCodeGenerator().generate(_cast_chain_graph(), {"d": "in.csv"}),
    ):
        for line in code.splitlines():
            name, sep, rhs = line.partition(" = ")
            if sep:
                assert rhs.strip() != name.strip(), f"self-assign no-op survived:\n{code}"
