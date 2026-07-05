"""Tests for data-quality assertion nodes.

Covers: pass, fail (error mode), fail (warn mode), validate_config errors —
on both pandas and polars engines, plus edge cases, executor integration,
and polars codegen.
"""

import warnings
from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from app.engine.backends import get_engine
from app.engine.executor import FlowExecutor, dataset_ref_key
from app.engine.registry import get_transformation
from app.engine.transformations.quality import AssertionViolationError


@pytest.fixture(params=["pandas", "polars"])
def engine(request):
    return get_engine(request.param)


def _native(engine, pdf: pd.DataFrame):
    return pl.from_pandas(pdf) if engine.name == "polars" else pdf


def run_assertion(engine, node_type, pdf, config):
    """Execute an assertion node; returns (output_pdf, node_metadata)."""
    t = get_transformation(node_type)
    t.validate_config(config)
    ins = {"in": _native(engine, pdf)}
    frames, meta = t.execute_with_metadata(engine, ins, config)
    return engine.to_pandas(frames["out"]), meta


# ---------------------------------------------------------------------------
# assertNotNull
# ---------------------------------------------------------------------------


class TestAssertNotNull:
    def test_pass_no_nulls(self, engine):
        pdf = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        out, meta = run_assertion(engine, "assertNotNull", pdf, {"columns": ["a", "b"]})
        assert len(out) == 3
        assert meta.assertion_passed is True
        assert meta.assertion_violation_count == 0

    def test_fail_error_mode(self, engine):
        pdf = pd.DataFrame({"a": [1, None, 3]})
        with pytest.raises(AssertionViolationError, match="assertNotNull"):
            run_assertion(engine, "assertNotNull", pdf, {"columns": ["a"], "mode": "error"})

    def test_fail_warn_mode(self, engine):
        pdf = pd.DataFrame({"a": [1, None, 3]})
        out, meta = run_assertion(engine, "assertNotNull", pdf, {"columns": ["a"], "mode": "warn"})
        # Output frame is unchanged
        assert len(out) == 3
        assert meta.assertion_passed is False
        assert meta.assertion_violation_count == 1
        assert len(meta.assertion_violating_sample) == 1

    def test_all_columns_default(self, engine):
        pdf = pd.DataFrame({"a": [1, None], "b": [None, 2]})
        out, meta = run_assertion(engine, "assertNotNull", pdf, {"mode": "warn"})
        assert meta.assertion_passed is False
        assert meta.assertion_violation_count == 2

    def test_validate_bad_mode(self):
        t = get_transformation("assertNotNull")
        with pytest.raises(ValueError, match="mode"):
            t.validate_config({"mode": "ignore"})

    def test_pass_has_empty_sample(self, engine):
        pdf = pd.DataFrame({"a": [1, 2, 3]})
        _, meta = run_assertion(engine, "assertNotNull", pdf, {"columns": ["a"]})
        assert meta.assertion_passed is True
        assert meta.assertion_violating_sample == []

    def test_empty_dataframe_passes(self, engine):
        pdf = pd.DataFrame({"a": pd.Series([], dtype=float)})
        _, meta = run_assertion(engine, "assertNotNull", pdf, {"columns": ["a"]})
        assert meta.assertion_passed is True
        assert meta.assertion_violation_count == 0

    def test_all_null_column(self, engine):
        pdf = pd.DataFrame({"a": [None, None, None]})
        _, meta = run_assertion(engine, "assertNotNull", pdf, {"columns": ["a"], "mode": "warn"})
        assert meta.assertion_passed is False
        assert meta.assertion_violation_count == 3

    def test_single_row_null_fails(self, engine):
        pdf = pd.DataFrame({"a": [None]})
        with pytest.raises(AssertionViolationError):
            run_assertion(engine, "assertNotNull", pdf, {"columns": ["a"]})

    def test_single_row_not_null_passes(self, engine):
        pdf = pd.DataFrame({"a": [42]})
        _, meta = run_assertion(engine, "assertNotNull", pdf, {"columns": ["a"]})
        assert meta.assertion_passed is True

    def test_unknown_column_raises(self, engine):
        pdf = pd.DataFrame({"a": [1, 2]})
        with pytest.raises(ValueError, match="not found"):
            run_assertion(engine, "assertNotNull", pdf, {"columns": ["ghost"], "mode": "warn"})

    def test_violating_sample_capped_at_five(self, engine):
        pdf = pd.DataFrame({"a": [None] * 10})
        _, meta = run_assertion(engine, "assertNotNull", pdf, {"columns": ["a"], "mode": "warn"})
        assert meta.assertion_violation_count == 10
        assert len(meta.assertion_violating_sample) == 5

    def test_partial_null_column(self, engine):
        # Only 'b' has a null; 'a' is fine. When checking only 'a', should pass.
        pdf = pd.DataFrame({"a": [1, 2, 3], "b": [None, 2, 3]})
        _, meta = run_assertion(engine, "assertNotNull", pdf, {"columns": ["a"]})
        assert meta.assertion_passed is True


# ---------------------------------------------------------------------------
# assertUnique
# ---------------------------------------------------------------------------


class TestAssertUnique:
    def test_pass_no_duplicates(self, engine):
        pdf = pd.DataFrame({"id": [1, 2, 3]})
        out, meta = run_assertion(engine, "assertUnique", pdf, {"columns": ["id"]})
        assert meta.assertion_passed is True

    def test_fail_error_mode(self, engine):
        pdf = pd.DataFrame({"id": [1, 1, 2]})
        with pytest.raises(AssertionViolationError, match="assertUnique"):
            run_assertion(engine, "assertUnique", pdf, {"columns": ["id"], "mode": "error"})

    def test_fail_warn_mode(self, engine):
        pdf = pd.DataFrame({"id": [1, 1, 2]})
        out, meta = run_assertion(engine, "assertUnique", pdf, {"columns": ["id"], "mode": "warn"})
        assert len(out) == 3
        assert meta.assertion_passed is False
        assert meta.assertion_violation_count == 2  # both duplicate rows counted

    def test_all_columns_default(self, engine):
        pdf = pd.DataFrame({"a": [1, 1], "b": [2, 2]})
        _, meta = run_assertion(engine, "assertUnique", pdf, {"mode": "warn"})
        assert meta.assertion_passed is False

    def test_empty_dataframe_passes(self, engine):
        pdf = pd.DataFrame({"id": pd.Series([], dtype=int)})
        _, meta = run_assertion(engine, "assertUnique", pdf, {"columns": ["id"]})
        assert meta.assertion_passed is True

    def test_single_row_always_unique(self, engine):
        pdf = pd.DataFrame({"id": [99]})
        _, meta = run_assertion(engine, "assertUnique", pdf, {"columns": ["id"]})
        assert meta.assertion_passed is True

    def test_multi_column_composite_key(self, engine):
        # (a, b) is unique even though individual columns have duplicates.
        pdf = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "y", "x"]})
        _, meta = run_assertion(engine, "assertUnique", pdf, {"columns": ["a", "b"]})
        assert meta.assertion_passed is True

    def test_multi_column_composite_key_fails(self, engine):
        pdf = pd.DataFrame({"a": [1, 1], "b": ["x", "x"]})
        _, meta = run_assertion(engine, "assertUnique", pdf, {"columns": ["a", "b"], "mode": "warn"})
        assert meta.assertion_passed is False
        assert meta.assertion_violation_count == 2

    def test_violating_sample_capped_at_five(self, engine):
        pdf = pd.DataFrame({"id": [1] * 10})
        _, meta = run_assertion(engine, "assertUnique", pdf, {"columns": ["id"], "mode": "warn"})
        assert meta.assertion_violation_count == 10
        assert len(meta.assertion_violating_sample) == 5

    def test_pass_has_empty_sample(self, engine):
        pdf = pd.DataFrame({"id": [1, 2, 3]})
        _, meta = run_assertion(engine, "assertUnique", pdf, {"columns": ["id"]})
        assert meta.assertion_violating_sample == []


# ---------------------------------------------------------------------------
# assertValueRange
# ---------------------------------------------------------------------------


class TestAssertValueRange:
    def test_pass_within_range(self, engine):
        pdf = pd.DataFrame({"score": [0.1, 0.5, 0.9]})
        _, meta = run_assertion(engine, "assertValueRange", pdf, {"column": "score", "min": 0.0, "max": 1.0})
        assert meta.assertion_passed is True

    def test_fail_below_min(self, engine):
        pdf = pd.DataFrame({"score": [0.5, -0.1]})
        with pytest.raises(AssertionViolationError):
            run_assertion(engine, "assertValueRange", pdf, {"column": "score", "min": 0.0, "mode": "error"})

    def test_fail_above_max(self, engine):
        pdf = pd.DataFrame({"score": [0.5, 1.5]})
        with pytest.raises(AssertionViolationError):
            run_assertion(engine, "assertValueRange", pdf, {"column": "score", "max": 1.0, "mode": "error"})

    def test_exclusive_bounds(self, engine):
        pdf = pd.DataFrame({"x": [0, 5, 10]})
        _, meta = run_assertion(
            engine, "assertValueRange", pdf, {"column": "x", "min": 0, "max": 10, "inclusive": False, "mode": "warn"}
        )
        assert meta.assertion_passed is False
        assert meta.assertion_violation_count == 2  # 0 and 10 excluded

    def test_warn_mode_returns_frame(self, engine):
        pdf = pd.DataFrame({"x": [1, 99]})
        out, meta = run_assertion(engine, "assertValueRange", pdf, {"column": "x", "max": 50, "mode": "warn"})
        assert len(out) == 2
        assert meta.assertion_passed is False

    def test_validate_missing_column(self):
        t = get_transformation("assertValueRange")
        with pytest.raises(ValueError, match="column"):
            t.validate_config({"min": 0})

    def test_validate_no_bounds(self):
        t = get_transformation("assertValueRange")
        with pytest.raises(ValueError, match="min.*max"):
            t.validate_config({"column": "x"})

    def test_exact_boundary_inclusive_passes(self, engine):
        pdf = pd.DataFrame({"x": [0, 10]})
        _, meta = run_assertion(
            engine, "assertValueRange", pdf, {"column": "x", "min": 0, "max": 10, "inclusive": True}
        )
        assert meta.assertion_passed is True

    def test_exact_boundary_exclusive_fails(self, engine):
        pdf = pd.DataFrame({"x": [0]})
        _, meta = run_assertion(
            engine, "assertValueRange", pdf, {"column": "x", "min": 0, "inclusive": False, "mode": "warn"}
        )
        assert meta.assertion_passed is False
        assert meta.assertion_violation_count == 1

    def test_empty_dataframe_passes(self, engine):
        pdf = pd.DataFrame({"x": pd.Series([], dtype=float)})
        _, meta = run_assertion(engine, "assertValueRange", pdf, {"column": "x", "min": 0, "max": 100})
        assert meta.assertion_passed is True

    def test_nan_treated_as_violation(self, engine):
        # NaN fails numeric coercion → out-of-range violation.
        pdf = pd.DataFrame({"x": [1.0, float("nan"), 3.0]})
        _, meta = run_assertion(engine, "assertValueRange", pdf, {"column": "x", "min": 0, "max": 10, "mode": "warn"})
        assert meta.assertion_passed is False
        assert meta.assertion_violation_count == 1

    def test_non_numeric_string_treated_as_violation(self, engine):
        pdf = pd.DataFrame({"x": ["1", "two", "3"]})
        _, meta = run_assertion(engine, "assertValueRange", pdf, {"column": "x", "min": 0, "mode": "warn"})
        assert meta.assertion_passed is False
        assert meta.assertion_violation_count == 1  # "two" can't be coerced

    def test_only_min_bound(self, engine):
        pdf = pd.DataFrame({"x": [5, 10, 15]})
        _, meta = run_assertion(engine, "assertValueRange", pdf, {"column": "x", "min": 0})
        assert meta.assertion_passed is True

    def test_only_max_bound(self, engine):
        pdf = pd.DataFrame({"x": [5, 10, 50]})
        _, meta = run_assertion(engine, "assertValueRange", pdf, {"column": "x", "max": 20, "mode": "warn"})
        assert meta.assertion_passed is False
        assert meta.assertion_violation_count == 1

    def test_unknown_column_raises(self, engine):
        pdf = pd.DataFrame({"a": [1, 2]})
        with pytest.raises(ValueError, match="not found"):
            run_assertion(engine, "assertValueRange", pdf, {"column": "ghost", "min": 0, "mode": "warn"})

    def test_violating_sample_capped_at_five(self, engine):
        pdf = pd.DataFrame({"x": list(range(-10, 0))})  # all below 0
        _, meta = run_assertion(engine, "assertValueRange", pdf, {"column": "x", "min": 0, "mode": "warn"})
        assert meta.assertion_violation_count == 10
        assert len(meta.assertion_violating_sample) == 5


# ---------------------------------------------------------------------------
# assertExpression
# ---------------------------------------------------------------------------


class TestAssertExpression:
    def test_pass(self, engine):
        pdf = pd.DataFrame({"price": [10, 20], "cost": [5, 15]})
        _, meta = run_assertion(engine, "assertExpression", pdf, {"expression": "price > cost"})
        assert meta.assertion_passed is True

    def test_fail_error_mode(self, engine):
        pdf = pd.DataFrame({"amount": [100, -5, 50]})
        with pytest.raises(AssertionViolationError, match="assertExpression"):
            run_assertion(engine, "assertExpression", pdf, {"expression": "amount > 0", "mode": "error"})

    def test_fail_warn_mode(self, engine):
        pdf = pd.DataFrame({"amount": [100, -5, 50]})
        out, meta = run_assertion(engine, "assertExpression", pdf, {"expression": "amount > 0", "mode": "warn"})
        assert len(out) == 3
        assert meta.assertion_passed is False
        assert meta.assertion_violation_count == 1
        assert meta.assertion_violating_sample[0]["amount"] == -5

    def test_validate_empty_expression(self):
        t = get_transformation("assertExpression")
        with pytest.raises(ValueError, match="expression"):
            t.validate_config({"expression": "  "})

    def test_always_true_expression(self, engine):
        pdf = pd.DataFrame({"a": [1, 2, 3]})
        _, meta = run_assertion(engine, "assertExpression", pdf, {"expression": "a > 0"})
        assert meta.assertion_passed is True
        assert meta.assertion_violation_count == 0

    def test_always_false_expression(self, engine):
        pdf = pd.DataFrame({"a": [1, 2, 3]})
        _, meta = run_assertion(engine, "assertExpression", pdf, {"expression": "a < 0", "mode": "warn"})
        assert meta.assertion_passed is False
        assert meta.assertion_violation_count == 3

    def test_empty_dataframe_passes(self, engine):
        pdf = pd.DataFrame({"a": pd.Series([], dtype=float)})
        _, meta = run_assertion(engine, "assertExpression", pdf, {"expression": "a > 0"})
        assert meta.assertion_passed is True

    def test_compound_expression_bitwise_and(self, engine):
        pdf = pd.DataFrame({"age": [17, 25, 70]})
        _, meta = run_assertion(
            engine, "assertExpression", pdf, {"expression": "age >= 18 & age <= 65", "mode": "warn"}
        )
        assert meta.assertion_passed is False

    def test_invalid_expression_raises_value_error(self, engine):
        pdf = pd.DataFrame({"a": [1, 2]})
        with pytest.raises(ValueError, match="assertExpression"):
            run_assertion(engine, "assertExpression", pdf, {"expression": "nonexistent_col > 0"})

    def test_violating_sample_capped_at_five(self, engine):
        pdf = pd.DataFrame({"a": list(range(-10, 0))})  # all negative
        _, meta = run_assertion(engine, "assertExpression", pdf, {"expression": "a > 0", "mode": "warn"})
        assert meta.assertion_violation_count == 10
        assert len(meta.assertion_violating_sample) == 5

    def test_sample_contains_correct_row(self, engine):
        pdf = pd.DataFrame({"x": [100, -99, 200]})
        _, meta = run_assertion(engine, "assertExpression", pdf, {"expression": "x >= 0", "mode": "warn"})
        assert meta.assertion_violation_count == 1
        assert meta.assertion_violating_sample[0]["x"] == -99


# ---------------------------------------------------------------------------
# assertRowCount
# ---------------------------------------------------------------------------


class TestAssertRowCount:
    def test_pass_within_bounds(self, engine):
        pdf = pd.DataFrame({"a": range(50)})
        _, meta = run_assertion(engine, "assertRowCount", pdf, {"min_rows": 10, "max_rows": 100})
        assert meta.assertion_passed is True

    def test_fail_too_few(self, engine):
        pdf = pd.DataFrame({"a": [1, 2]})
        with pytest.raises(AssertionViolationError, match="assertRowCount"):
            run_assertion(engine, "assertRowCount", pdf, {"min_rows": 10, "mode": "error"})

    def test_fail_too_many(self, engine):
        pdf = pd.DataFrame({"a": range(200)})
        with pytest.raises(AssertionViolationError):
            run_assertion(engine, "assertRowCount", pdf, {"max_rows": 100, "mode": "error"})

    def test_warn_mode_continues(self, engine):
        pdf = pd.DataFrame({"a": [1]})
        out, meta = run_assertion(engine, "assertRowCount", pdf, {"min_rows": 5, "mode": "warn"})
        assert len(out) == 1
        assert meta.assertion_passed is False

    def test_validate_no_bounds(self):
        t = get_transformation("assertRowCount")
        with pytest.raises(ValueError, match="min_rows.*max_rows"):
            t.validate_config({})

    def test_validate_inverted_bounds(self):
        t = get_transformation("assertRowCount")
        with pytest.raises(ValueError, match="<="):
            t.validate_config({"min_rows": 100, "max_rows": 10})

    def test_exact_min_boundary(self, engine):
        pdf = pd.DataFrame({"a": [1, 2, 3]})
        _, meta = run_assertion(engine, "assertRowCount", pdf, {"min_rows": 3})
        assert meta.assertion_passed is True

    def test_one_below_min_boundary(self, engine):
        pdf = pd.DataFrame({"a": [1, 2]})
        _, meta = run_assertion(engine, "assertRowCount", pdf, {"min_rows": 3, "mode": "warn"})
        assert meta.assertion_passed is False

    def test_exact_max_boundary(self, engine):
        pdf = pd.DataFrame({"a": [1, 2, 3]})
        _, meta = run_assertion(engine, "assertRowCount", pdf, {"max_rows": 3})
        assert meta.assertion_passed is True

    def test_one_above_max_boundary(self, engine):
        pdf = pd.DataFrame({"a": [1, 2, 3, 4]})
        _, meta = run_assertion(engine, "assertRowCount", pdf, {"max_rows": 3, "mode": "warn"})
        assert meta.assertion_passed is False

    def test_empty_dataframe_below_min(self, engine):
        pdf = pd.DataFrame({"a": pd.Series([], dtype=int)})
        _, meta = run_assertion(engine, "assertRowCount", pdf, {"min_rows": 1, "mode": "warn"})
        assert meta.assertion_passed is False
        assert meta.assertion_violation_count == 0  # row count used as violation_count

    def test_empty_dataframe_passes_with_max_only(self, engine):
        pdf = pd.DataFrame({"a": pd.Series([], dtype=int)})
        _, meta = run_assertion(engine, "assertRowCount", pdf, {"max_rows": 100})
        assert meta.assertion_passed is True

    def test_only_min_bound(self, engine):
        pdf = pd.DataFrame({"a": range(10)})
        _, meta = run_assertion(engine, "assertRowCount", pdf, {"min_rows": 5})
        assert meta.assertion_passed is True

    def test_violation_count_is_actual_row_count(self, engine):
        pdf = pd.DataFrame({"a": range(5)})
        _, meta = run_assertion(engine, "assertRowCount", pdf, {"min_rows": 10, "mode": "warn"})
        assert meta.assertion_violation_count == 5  # actual rows


# ---------------------------------------------------------------------------
# Executor integration — run_with_results with assertion nodes
# ---------------------------------------------------------------------------


def _paths(**by_id: Path):
    return {dataset_ref_key(ds_id, None): path for ds_id, path in by_id.items()}


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    path = tmp_path / "data.csv"
    pd.DataFrame({"id": [1, 2, 3], "score": [0.5, 0.8, 0.2]}).to_csv(path, index=False)
    return path


def _assert_graph(dataset_id: str, assert_node: dict) -> dict:
    """csvInput → assertion_node → csvOutput."""
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {"id": "assert", **assert_node},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "assert"},
            {"id": "e2", "source": "assert", "target": "out1"},
        ],
    }


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_executor_assertion_pass_records_metadata(tmp_path: Path, sample_csv: Path, engine_name: str):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = _assert_graph(
        "ds1",
        {"type": "assertNotNull", "data": {"config": {"columns": ["id", "score"]}}, "id": "assert"},
    )
    result = FlowExecutor().run_with_results(graph, _paths(ds1=sample_csv), out_dir, engine_name=engine_name)
    assert result.error is None
    node_map = {r.node_id: r for r in result.node_results}
    assert node_map["assert"].status == "success"
    assert node_map["assert"].assertion_passed is True
    assert node_map["assert"].assertion_violation_count == 0


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_executor_assertion_error_mode_fails_run(tmp_path: Path, sample_csv: Path, engine_name: str):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = _assert_graph(
        "ds1",
        {
            "type": "assertValueRange",
            "data": {"config": {"column": "score", "max": 0.5, "mode": "error"}},
            "id": "assert",
        },
    )
    result = FlowExecutor().run_with_results(graph, _paths(ds1=sample_csv), out_dir, engine_name=engine_name)
    assert result.error is not None
    node_map = {r.node_id: r for r in result.node_results}
    assert node_map["assert"].status == "failed"
    assert node_map["out1"].status == "skipped"  # downstream skipped


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_executor_assertion_warn_mode_continues(tmp_path: Path, sample_csv: Path, engine_name: str):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = _assert_graph(
        "ds1",
        {
            "type": "assertValueRange",
            "data": {"config": {"column": "score", "max": 0.5, "mode": "warn"}},
            "id": "assert",
        },
    )
    result = FlowExecutor().run_with_results(graph, _paths(ds1=sample_csv), out_dir, engine_name=engine_name)
    # warn mode: assertion fails internally but does NOT abort the run
    assert result.error is None
    node_map = {r.node_id: r for r in result.node_results}
    assert node_map["assert"].status == "success"
    assert node_map["assert"].assertion_passed is False
    assert node_map["out1"].status == "success"  # downstream still runs


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_executor_chain_of_assertions(tmp_path: Path, sample_csv: Path, engine_name: str):
    """Two sequential assertion nodes, both in warn mode — both should record results."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "a1", "type": "assertNotNull", "data": {"config": {"mode": "warn"}}},
            {"id": "a2", "type": "assertRowCount", "data": {"config": {"min_rows": 1, "mode": "warn"}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "a1"},
            {"id": "e2", "source": "a1", "target": "a2"},
            {"id": "e3", "source": "a2", "target": "out1"},
        ],
    }
    result = FlowExecutor().run_with_results(graph, _paths(ds1=sample_csv), out_dir, engine_name=engine_name)
    assert result.error is None
    node_map = {r.node_id: r for r in result.node_results}
    assert node_map["a1"].assertion_passed is True
    assert node_map["a2"].assertion_passed is True


def test_executor_assertion_node_result_serialises(tmp_path: Path, sample_csv: Path):
    """as_dict() includes all assertion fields — important for the API layer."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = _assert_graph(
        "ds1",
        {"type": "assertNotNull", "data": {"config": {"mode": "warn"}}, "id": "assert"},
    )
    result = FlowExecutor().run_with_results(graph, _paths(ds1=sample_csv), out_dir)
    node_map = {r.node_id: r for r in result.node_results}
    d = node_map["assert"].as_dict()
    assert "assertion_passed" in d
    assert "assertion_violation_count" in d
    assert "assertion_violating_sample" in d


def test_executor_non_assertion_node_has_none_fields(tmp_path: Path, sample_csv: Path):
    """Plain ETL nodes must not leak assertion fields with non-None values."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
    }
    result = FlowExecutor().run_with_results(graph, _paths(ds1=sample_csv), out_dir)
    node_map = {r.node_id: r for r in result.node_results}
    d = node_map["in1"].as_dict()
    assert d["assertion_passed"] is None
    assert d["assertion_violation_count"] is None
    assert d["assertion_violating_sample"] is None


# ---------------------------------------------------------------------------
# Codegen smoke tests — pandas generated code must compile and run correctly
# ---------------------------------------------------------------------------


def _exec_codegen(code: str, df_in: pd.DataFrame) -> pd.DataFrame:
    """Execute generated pandas code in an isolated namespace.

    warn-mode snippets rely on `import warnings` living in the script header
    (collected via the node's imports()); provide it like the drivers do."""
    ns: dict = {"df_1": df_in, "pd": pd, "warnings": warnings}
    exec(code, ns)  # noqa: S102
    return ns["df_2"]


def _exec_polars_codegen(code: str, df_in: pl.DataFrame) -> pl.DataFrame:
    ns: dict = {"df_1": df_in, "pl": pl, "warnings": warnings}
    exec(code, ns)  # noqa: S102
    return ns["df_2"]


@pytest.mark.parametrize(
    "node_type,pdf,config",
    [
        ("assertNotNull", pd.DataFrame({"a": [1, 2]}), {"columns": ["a"]}),
        ("assertUnique", pd.DataFrame({"id": [1, 2]}), {"columns": ["id"]}),
        ("assertValueRange", pd.DataFrame({"x": [5, 10]}), {"column": "x", "min": 0, "max": 100}),
        ("assertExpression", pd.DataFrame({"a": [1, 2]}), {"expression": "a > 0"}),
        ("assertRowCount", pd.DataFrame({"a": range(5)}), {"min_rows": 1, "max_rows": 10}),
    ],
)
def test_pandas_codegen_pass(node_type, pdf, config):
    t = get_transformation(node_type)
    code = t.to_python_code({"in": "df_1"}, {"out": "df_2"}, config)
    out = _exec_codegen(code, pdf)
    pd.testing.assert_frame_equal(out, pdf)


@pytest.mark.parametrize(
    "node_type,pdf,config",
    [
        ("assertNotNull", pd.DataFrame({"a": [1, None]}), {"columns": ["a"], "mode": "warn"}),
        ("assertUnique", pd.DataFrame({"id": [1, 1]}), {"columns": ["id"], "mode": "warn"}),
        ("assertValueRange", pd.DataFrame({"x": [-1, 5]}), {"column": "x", "min": 0, "mode": "warn"}),
        ("assertExpression", pd.DataFrame({"a": [-1, 2]}), {"expression": "a > 0", "mode": "warn"}),
        ("assertRowCount", pd.DataFrame({"a": [1]}), {"min_rows": 5, "mode": "warn"}),
    ],
)
def test_pandas_codegen_warn_does_not_raise(node_type, pdf, config):
    t = get_transformation(node_type)
    code = t.to_python_code({"in": "df_1"}, {"out": "df_2"}, config)
    with warnings.catch_warnings(record=True):
        out = _exec_codegen(code, pdf)
    pd.testing.assert_frame_equal(out, pdf)


@pytest.mark.parametrize(
    "node_type,pdf,config",
    [
        ("assertNotNull", pd.DataFrame({"a": [1, None]}), {"columns": ["a"]}),
        ("assertUnique", pd.DataFrame({"id": [1, 1]}), {"columns": ["id"]}),
        ("assertValueRange", pd.DataFrame({"x": [-1, 5]}), {"column": "x", "min": 0}),
        ("assertExpression", pd.DataFrame({"a": [-1, 2]}), {"expression": "a > 0"}),
        ("assertRowCount", pd.DataFrame({"a": [1]}), {"min_rows": 5}),
    ],
)
def test_pandas_codegen_error_raises(node_type, pdf, config):
    t = get_transformation(node_type)
    code = t.to_python_code({"in": "df_1"}, {"out": "df_2"}, config)
    with pytest.raises(ValueError):
        _exec_codegen(code, pdf)


# ---------------------------------------------------------------------------
# Phase 2: Polars codegen tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "node_type,pdf,config",
    [
        ("assertNotNull", pd.DataFrame({"a": [1, 2, 3]}), {"columns": ["a"]}),
        ("assertUnique", pd.DataFrame({"id": [1, 2, 3]}), {"columns": ["id"]}),
        ("assertValueRange", pd.DataFrame({"x": [5, 10, 15]}), {"column": "x", "min": 0, "max": 100}),
        ("assertExpression", pd.DataFrame({"a": [1, 2, 3]}), {"expression": "a > 0"}),
        ("assertRowCount", pd.DataFrame({"a": range(5)}), {"min_rows": 1, "max_rows": 10}),
    ],
)
def test_polars_codegen_pass(node_type, pdf, config):
    t = get_transformation(node_type)
    code = t.to_polars_code({"in": "df_1"}, {"out": "df_2"}, config)
    df_in = pl.from_pandas(pdf)
    out = _exec_polars_codegen(code, df_in)
    assert out.shape == df_in.shape
    pd.testing.assert_frame_equal(out.to_pandas(), pdf)


@pytest.mark.parametrize(
    "node_type,pdf,config",
    [
        ("assertNotNull", pd.DataFrame({"a": [1, None]}), {"columns": ["a"], "mode": "warn"}),
        ("assertUnique", pd.DataFrame({"id": [1, 1]}), {"columns": ["id"], "mode": "warn"}),
        ("assertValueRange", pd.DataFrame({"x": [-1, 5]}), {"column": "x", "min": 0, "mode": "warn"}),
        ("assertExpression", pd.DataFrame({"a": [-1, 2]}), {"expression": "a > 0", "mode": "warn"}),
        ("assertRowCount", pd.DataFrame({"a": [1]}), {"min_rows": 5, "mode": "warn"}),
    ],
)
def test_polars_codegen_warn_does_not_raise(node_type, pdf, config):
    t = get_transformation(node_type)
    code = t.to_polars_code({"in": "df_1"}, {"out": "df_2"}, config)
    df_in = pl.from_pandas(pdf)
    with warnings.catch_warnings(record=True):
        out = _exec_polars_codegen(code, df_in)
    assert out.shape == df_in.shape


@pytest.mark.parametrize(
    "node_type,pdf,config",
    [
        ("assertNotNull", pd.DataFrame({"a": [1, None]}), {"columns": ["a"]}),
        ("assertUnique", pd.DataFrame({"id": [1, 1]}), {"columns": ["id"]}),
        ("assertValueRange", pd.DataFrame({"x": [-1, 5]}), {"column": "x", "min": 0}),
        ("assertExpression", pd.DataFrame({"a": [-1, 2]}), {"expression": "a > 0"}),
        ("assertRowCount", pd.DataFrame({"a": [1]}), {"min_rows": 5}),
    ],
)
def test_polars_codegen_error_raises(node_type, pdf, config):
    t = get_transformation(node_type)
    code = t.to_polars_code({"in": "df_1"}, {"out": "df_2"}, config)
    df_in = pl.from_pandas(pdf)
    with pytest.raises((ValueError, Exception)):
        _exec_polars_codegen(code, df_in)


def test_polars_codegen_not_null_all_columns(tmp_path):
    """to_polars_code with no columns config uses df.columns."""
    t = get_transformation("assertNotNull")
    pdf = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    code = t.to_polars_code({"in": "df_1"}, {"out": "df_2"}, {})
    df_in = pl.from_pandas(pdf)
    out = _exec_polars_codegen(code, df_in)
    assert out.shape == df_in.shape


def test_polars_codegen_not_null_detects_nulls_in_non_first_column():
    """Regression: exported polars assertNotNull must detect nulls in ANY listed
    column, not just the first. The run (pandas) raises here, so the exported
    polars code must too — otherwise a data-quality gate silently passes."""
    t = get_transformation("assertNotNull")
    # Nulls live ONLY in the second column.
    pdf = pd.DataFrame({"a": [1, 2, 3], "b": [None, 2, 3]})
    code = t.to_polars_code({"in": "df_1"}, {"out": "df_2"}, {"columns": ["a", "b"]})
    df_in = pl.from_pandas(pdf)
    with pytest.raises(ValueError, match="assertNotNull"):
        _exec_polars_codegen(code, df_in)


def test_polars_codegen_not_null_count_matches_runtime():
    """Exported polars _null_count equals the run's rows-with-null count."""
    pdf = pd.DataFrame({"a": [1, None, 3], "b": [None, 2, 3]})
    cols = ["a", "b"]
    runtime = get_transformation("assertNotNull")._check(pdf.copy(), {"columns": cols})
    t = get_transformation("assertNotNull")
    code = t.to_polars_code({"in": "df_1"}, {"out": "df_2"}, {"columns": cols, "mode": "warn"})
    ns: dict = {"df_1": pl.from_pandas(pdf), "pl": pl, "warnings": warnings}
    with warnings.catch_warnings(record=True):
        exec(code, ns)  # noqa: S102
    assert ns["_null_count"] == runtime.violation_count == 2


def test_polars_codegen_value_range_counts_nulls_as_violations():
    """Regression: exported polars assertValueRange must count null / non-numeric
    values as violations, matching the run (pandas coerces them to NaN -> fail)."""
    t = get_transformation("assertValueRange")
    pdf = pd.DataFrame({"x": [1, 2, None, 5, 100]})
    runtime = t._check(pdf.copy(), {"column": "x", "min": 0, "max": 10})
    code = t.to_polars_code({"in": "df_1"}, {"out": "df_2"}, {"column": "x", "min": 0, "max": 10, "mode": "warn"})
    ns: dict = {"df_1": pl.from_pandas(pdf), "pl": pl, "warnings": warnings}
    with warnings.catch_warnings(record=True):
        exec(code, ns)  # noqa: S102
    assert ns["_range_violations"] == runtime.violation_count == 2


def test_polars_codegen_value_range_none_bounds():
    """assertValueRange with only min generates valid polars code."""
    t = get_transformation("assertValueRange")
    code = t.to_polars_code({"in": "df_1"}, {"out": "df_2"}, {"column": "x", "min": 0, "mode": "warn"})
    df_in = pl.DataFrame({"x": [1, 2, 3]})
    out = _exec_polars_codegen(code, df_in)
    assert out.shape == df_in.shape


def test_polars_codegen_row_count_only_min():
    """assertRowCount with only min_rows generates valid polars code."""
    t = get_transformation("assertRowCount")
    code = t.to_polars_code({"in": "df_1"}, {"out": "df_2"}, {"min_rows": 1})
    df_in = pl.DataFrame({"a": [1, 2, 3]})
    out = _exec_polars_codegen(code, df_in)
    assert out.shape == df_in.shape


def test_polars_codegen_row_count_only_max():
    """assertRowCount with only max_rows generates valid polars code."""
    t = get_transformation("assertRowCount")
    code = t.to_polars_code({"in": "df_1"}, {"out": "df_2"}, {"max_rows": 100})
    df_in = pl.DataFrame({"a": [1, 2, 3]})
    out = _exec_polars_codegen(code, df_in)
    assert out.shape == df_in.shape
