"""Tests for data-quality assertion nodes.

Covers: pass, fail (error mode), fail (warn mode), and validate_config
errors — on both pandas and polars engines.
"""

import pandas as pd
import polars as pl
import pytest

from app.engine.backends import get_engine
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


# ---------------------------------------------------------------------------
# Codegen smoke tests — generated code must compile and run correctly
# ---------------------------------------------------------------------------


def _exec_codegen(code: str, df_in: pd.DataFrame) -> pd.DataFrame:
    """Execute generated pandas code in an isolated namespace."""
    ns: dict = {"df_1": df_in, "pd": pd}
    exec(code, ns)  # noqa: S102
    return ns["df_2"]


def _exec_polars_codegen(code: str, df_in: pl.DataFrame) -> pl.DataFrame:
    ns: dict = {"df_1": df_in, "pl": pl}
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
    import warnings

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
