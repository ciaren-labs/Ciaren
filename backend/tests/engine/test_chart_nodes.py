"""Tests for chart nodes.

Chart nodes are pass-throughs that compute a render-ready, size-capped chart
artifact over the full frame and attach it as NodeMetadata.chart. Covers:
artifact shapes per node type, pass-through identity, caps + correct "Other"
folding for non-additive aggregates, count semantics, NaN/blank handling,
missing-column errors, validate_config, flow-terminal graph validation,
pass-through codegen, and the run-schema round-trip that keeps chart (and
assertion) fields in API responses.
"""

import json

import pandas as pd
import polars as pl
import pytest

from app.engine.backends import get_engine
from app.engine.graph import validate_graph, validate_node_configs
from app.engine.node_kinds import CHART_NODE_TYPES, is_flow_terminal
from app.engine.registry import get_transformation
from app.engine.transformations.charts import (
    DEFAULT_BAR_CATEGORIES,
    MAX_LINE_POINTS,
    MAX_SCATTER_POINTS,
    MAX_STACK_SERIES,
)
from app.schemas.run import NodeResultRead


@pytest.fixture(params=["pandas", "polars"])
def engine(request):
    return get_engine(request.param)


def _native(engine, pdf: pd.DataFrame):
    return pl.from_pandas(pdf) if engine.name == "polars" else pdf


def run_chart(engine, node_type, pdf, config):
    """Execute a chart node; returns (output_pdf, chart_artifact)."""
    t = get_transformation(node_type)
    t.validate_config(config)
    ins = {"in": _native(engine, pdf)}
    frames, meta = t.execute_with_metadata(engine, ins, config)
    assert meta is not None and meta.chart is not None
    json.dumps(meta.chart)  # every artifact must be JSON-serializable
    return engine.to_pandas(frames["out"]), meta.chart


@pytest.fixture
def orders() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "region": ["N", "S", "N", "E", "S", "N", None, "W", "W", "W"],
            "product": ["a", "b", "a", "c", "b", "b", "a", "c", "a", "b"],
            "amount": [10.0, 20.0, 30.0, 5.0, 15.0, 25.0, 8.0, float("nan"), 12.0, 40.0],
            "qty": [1, 2, 3, 1, 2, 5, 2, 4, 1, 3],
            "date": pd.date_range("2024-01-01", periods=10, freq="D"),
        }
    )


# ---------------------------------------------------------------------------
# chartBar
# ---------------------------------------------------------------------------


class TestChartBar:
    def test_sum_by_category_passthrough(self, engine, orders):
        out, art = run_chart(engine, "chartBar", orders, {"x": "region", "y": "amount", "aggregate": "sum"})
        assert len(out) == len(orders)  # pass-through
        assert art["kind"] == "bar"
        by_label = {d["label"]: d["value"] for d in art["data"]}
        assert by_label["N"] == 65.0
        assert by_label["S"] == 35.0
        assert "(blank)" in by_label  # None region gets the blank bucket
        assert art["total_categories"] == 5

    def test_count_counts_rows_not_numeric_cells(self, engine, orders):
        _, art = run_chart(engine, "chartBar", orders, {"x": "region", "aggregate": "count"})
        by_label = {d["label"]: d["value"] for d in art["data"]}
        assert by_label["W"] == 3  # includes the NaN-amount row

    def test_category_cap_with_correct_other_mean(self, engine):
        # 30 categories, one row each except the top ones; "Other" must be the
        # MEAN over the folded raw rows, not a sum of folded means.
        pdf = pd.DataFrame(
            {
                "cat": [f"c{i}" for i in range(30) for _ in range(2)],
                "val": [float(i) for i in range(30) for _ in range(2)],
            }
        )
        _, art = run_chart(engine, "chartBar", pdf, {"x": "cat", "y": "val", "aggregate": "mean", "limit": 5})
        labels = [d["label"] for d in art["data"]]
        assert len(labels) == 6  # 5 + Other
        assert labels[-1] == "Other"
        other = art["data"][-1]["value"]
        # Folded categories are c0..c24 -> mean of 0..24 = 12
        assert other == pytest.approx(12.0)
        assert art["total_categories"] == 30

    def test_default_limit(self, engine):
        pdf = pd.DataFrame({"cat": [f"c{i}" for i in range(40)], "val": [1.0] * 40})
        _, art = run_chart(engine, "chartBar", pdf, {"x": "cat", "y": "val", "aggregate": "sum"})
        assert len(art["data"]) == DEFAULT_BAR_CATEGORIES + 1  # top N + Other

    def test_stacked_series_capped_with_other(self, engine):
        pdf = pd.DataFrame(
            {
                "cat": ["x", "y"] * 30,
                "grp": [f"g{i % 12}" for i in range(60)],
                "val": [1.0] * 60,
            }
        )
        _, art = run_chart(engine, "chartBar", pdf, {"x": "cat", "y": "val", "aggregate": "sum", "group_by": "grp"})
        assert len(art["series"]) == MAX_STACK_SERIES
        assert art["series"][-1] == "Other"
        assert art["total_series"] == 12
        # Every value is present: totals across series match the raw sum.
        total = sum(v for row in art["rows"] for k, v in row.items() if k != "label" and v is not None)
        assert total == pytest.approx(60.0)

    def test_missing_column(self, engine, orders):
        with pytest.raises(ValueError, match="not found"):
            run_chart(engine, "chartBar", orders, {"x": "nope", "y": "amount", "aggregate": "sum"})

    def test_validate_config(self):
        t = get_transformation("chartBar")
        with pytest.raises(ValueError, match="'x'"):
            t.validate_config({"y": "amount"})
        with pytest.raises(ValueError, match="'y'"):
            t.validate_config({"x": "region", "aggregate": "sum"})
        with pytest.raises(ValueError, match="aggregate"):
            t.validate_config({"x": "region", "y": "amount", "aggregate": "mode"})
        with pytest.raises(ValueError, match="orientation"):
            t.validate_config({"x": "region", "aggregate": "count", "orientation": "diagonal"})
        with pytest.raises(ValueError, match="limit"):
            t.validate_config({"x": "region", "aggregate": "count", "limit": 0})
        t.validate_config({"x": "region", "aggregate": "count"})  # count needs no y


# ---------------------------------------------------------------------------
# chartLine / chartArea
# ---------------------------------------------------------------------------


class TestChartLine:
    def test_aggregates_per_x_sorted(self, engine):
        pdf = pd.DataFrame({"x": [3, 1, 2, 1], "y": [30.0, 10.0, 20.0, 20.0]})
        _, art = run_chart(engine, "chartLine", pdf, {"x": "x", "y_columns": ["y"], "aggregate": "mean"})
        assert art["kind"] == "line"
        assert [p["x"] for p in art["rows"]] == ["1", "2", "3"]
        assert art["rows"][0]["y"] == 15.0  # mean of the two x=1 rows

    def test_datetime_x_serialized_and_ordered(self, engine, orders):
        _, art = run_chart(engine, "chartLine", orders, {"x": "date", "y_columns": ["amount"], "aggregate": "sum"})
        xs = [p["x"] for p in art["rows"]]
        assert xs == sorted(xs)
        assert xs[0].startswith("2024-01-01")

    def test_point_cap_keeps_first_and_last(self, engine):
        n = MAX_LINE_POINTS * 3
        pdf = pd.DataFrame({"x": range(n), "y": [float(i) for i in range(n)]})
        _, art = run_chart(engine, "chartLine", pdf, {"x": "x", "y_columns": ["y"], "aggregate": "sum"})
        assert len(art["rows"]) == MAX_LINE_POINTS
        assert art["total_points"] == n
        assert art["rows"][0]["x"] == "0"
        assert art["rows"][-1]["x"] == str(n - 1)

    def test_area_kind(self, engine, orders):
        _, art = run_chart(engine, "chartArea", orders, {"x": "date", "y_columns": ["amount"]})
        assert art["kind"] == "area"

    def test_validate_config(self):
        t = get_transformation("chartLine")
        with pytest.raises(ValueError, match="y_columns"):
            t.validate_config({"x": "date", "y_columns": []})
        with pytest.raises(ValueError, match="at most"):
            t.validate_config({"x": "d", "y_columns": [f"c{i}" for i in range(9)]})


# ---------------------------------------------------------------------------
# chartScatter
# ---------------------------------------------------------------------------


class TestChartScatter:
    def test_drops_non_numeric_pairs(self, engine, orders):
        _, art = run_chart(engine, "chartScatter", orders, {"x": "qty", "y": "amount"})
        assert art["total_points"] == 9  # NaN amount row dropped
        assert all(len(p) == 2 for p in art["points"])

    def test_point_cap(self, engine):
        n = MAX_SCATTER_POINTS + 500
        pdf = pd.DataFrame({"a": range(n), "b": range(n)})
        _, art = run_chart(engine, "chartScatter", pdf, {"x": "a", "y": "b"})
        assert len(art["points"]) == MAX_SCATTER_POINTS
        assert art["total_points"] == n

    def test_validate_config(self):
        t = get_transformation("chartScatter")
        with pytest.raises(ValueError, match="requires"):
            t.validate_config({"x": "a"})
        with pytest.raises(ValueError, match="different"):
            t.validate_config({"x": "a", "y": "a"})


# ---------------------------------------------------------------------------
# chartPie
# ---------------------------------------------------------------------------


class TestChartPie:
    def test_count_default(self, engine, orders):
        _, art = run_chart(engine, "chartPie", orders, {"category": "product"})
        by_label = {d["label"]: d["value"] for d in art["data"]}
        assert by_label == {"a": 4, "b": 4, "c": 2}

    def test_slice_cap_folds_other(self, engine, orders):
        _, art = run_chart(
            engine, "chartPie", orders, {"category": "region", "value": "amount", "aggregate": "sum", "limit": 3}
        )
        labels = [d["label"] for d in art["data"]]
        assert labels[-1] == "Other"
        assert len(labels) == 4

    def test_validate_config(self):
        t = get_transformation("chartPie")
        with pytest.raises(ValueError, match="category"):
            t.validate_config({})
        with pytest.raises(ValueError, match="'value'"):
            t.validate_config({"category": "c", "aggregate": "sum"})
        with pytest.raises(ValueError, match="limit"):
            t.validate_config({"category": "c", "limit": 1})


# ---------------------------------------------------------------------------
# chartHistogram
# ---------------------------------------------------------------------------


class TestChartHistogram:
    def test_bins_and_counts(self, engine, orders):
        _, art = run_chart(engine, "chartHistogram", orders, {"column": "amount", "bins": 5})
        assert len(art["data"]) == 5
        assert sum(d["value"] for d in art["data"]) == 9  # NaN dropped

    def test_constant_column_single_bin(self, engine):
        pdf = pd.DataFrame({"v": [7.0] * 5})
        _, art = run_chart(engine, "chartHistogram", pdf, {"column": "v"})
        assert len(art["data"]) == 1
        assert art["data"][0]["value"] == 5

    def test_all_null_column_empty(self, engine):
        pdf = pd.DataFrame({"v": [None, None]})
        _, art = run_chart(engine, "chartHistogram", pdf, {"column": "v"})
        assert art["data"] == []

    def test_validate_config(self):
        t = get_transformation("chartHistogram")
        with pytest.raises(ValueError, match="column"):
            t.validate_config({})
        with pytest.raises(ValueError, match="bins"):
            t.validate_config({"column": "v", "bins": 999})


# ---------------------------------------------------------------------------
# chartBoxPlot
# ---------------------------------------------------------------------------


class TestChartBoxPlot:
    def test_five_number_summary(self, engine):
        pdf = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0, 100.0]})
        _, art = run_chart(engine, "chartBoxPlot", pdf, {"column": "v"})
        g = art["groups"][0]
        assert g["outliers"] == 1  # 100 is beyond the Tukey fence
        assert g["min"] <= g["q1"] <= g["median"] <= g["q3"] <= g["max"]
        assert g["count"] == 6

    def test_grouped_sorted_by_size(self, engine, orders):
        _, art = run_chart(engine, "chartBoxPlot", orders, {"column": "amount", "group_by": "product"})
        counts = [g["count"] for g in art["groups"]]
        assert counts == sorted(counts, reverse=True)
        assert art["total_groups"] == 3

    def test_group_cap(self, engine):
        pdf = pd.DataFrame({"v": [float(i) for i in range(40)], "g": [f"g{i % 20}" for i in range(40)]})
        _, art = run_chart(engine, "chartBoxPlot", pdf, {"column": "v", "group_by": "g"})
        assert len(art["groups"]) == 12
        assert art["total_groups"] == 20

    def test_validate_config(self):
        with pytest.raises(ValueError, match="column"):
            get_transformation("chartBoxPlot").validate_config({})


# ---------------------------------------------------------------------------
# chartHeatmap
# ---------------------------------------------------------------------------


class TestChartHeatmap:
    def test_auto_selects_numeric_not_datetime(self, engine, orders):
        _, art = run_chart(engine, "chartHeatmap", orders, {})
        assert art["columns"] == ["amount", "qty"]  # date excluded
        assert art["matrix"][0][0] == 1.0
        assert art["matrix"][0][1] == art["matrix"][1][0]

    def test_explicit_columns(self, engine, orders):
        _, art = run_chart(engine, "chartHeatmap", orders, {"columns": ["amount", "qty"]})
        assert art["columns"] == ["amount", "qty"]

    def test_needs_two_numeric(self, engine):
        pdf = pd.DataFrame({"a": ["x", "y"], "b": [1.0, 2.0]})
        with pytest.raises(ValueError, match="at least two"):
            run_chart(engine, "chartHeatmap", pdf, {})

    def test_validate_config(self):
        t = get_transformation("chartHeatmap")
        with pytest.raises(ValueError, match="list"):
            t.validate_config({"columns": "amount"})
        with pytest.raises(ValueError, match="at most"):
            t.validate_config({"columns": [f"c{i}" for i in range(13)]})


# ---------------------------------------------------------------------------
# Registry / graph / codegen / schema plumbing
# ---------------------------------------------------------------------------


class TestChartNodePlumbing:
    def test_all_chart_types_registered_and_terminal(self):
        for node_type in CHART_NODE_TYPES:
            assert get_transformation(node_type).type == node_type
            assert is_flow_terminal(node_type)

    def test_node_spec_keeps_chart_category(self):
        # Regression: NodeSpec normalizes unknown categories to "plugins" — the
        # "chart" category must be a recognized built-in or the palette misfiles
        # every chart node under Plugins.
        from app.plugins.builtin import build_node_spec

        spec = build_node_spec("chartBar")
        assert spec.category == "chart"
        assert spec.is_flow_terminal is True
        assert [p.id for p in spec.inputs] == ["in"]
        assert [p.id for p in spec.outputs] == ["out"]

    def test_graph_with_chart_terminal_is_complete(self):
        graph = {
            "nodes": [
                {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "d1"}}},
                {
                    "id": "c1",
                    "type": "chartBar",
                    "data": {"config": {"x": "region", "aggregate": "count"}},
                },
            ],
            "edges": [{"source": "in1", "target": "c1"}],
        }
        validate_graph(graph)  # no output node needed
        validate_node_configs(graph)

    def test_invalid_chart_config_fails_pre_run(self):
        graph = {
            "nodes": [
                {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "d1"}}},
                {"id": "c1", "type": "chartBar", "data": {"config": {}}},
            ],
            "edges": [{"source": "in1", "target": "c1"}],
        }
        validate_graph(graph)
        with pytest.raises(Exception, match="chartBar"):
            validate_node_configs(graph)

    def test_codegen_is_passthrough(self):
        for node_type in sorted(CHART_NODE_TYPES):
            t = get_transformation(node_type)
            code = t.to_python_code({"in": "df1"}, {"out": "df2"}, {})
            assert "df2 = df1" in code
            assert code == t.to_polars_code({"in": "df1"}, {"out": "df2"}, {})

    def test_node_result_schema_keeps_chart_and_assertion_fields(self):
        # Regression: pydantic drops undeclared keys when re-serializing
        # node_results_json; chart and assertion outcomes must survive the API.
        stored = {
            "node_id": "n1",
            "type": "chartBar",
            "label": "Bar Chart",
            "status": "success",
            "chart": {"kind": "bar", "data": [{"label": "N", "value": 1.0}]},
            "assertion_passed": False,
            "assertion_violation_count": 2,
            "assertion_violating_sample": [{"a": 1}],
        }
        read = NodeResultRead.model_validate(stored)
        dumped = read.model_dump()
        assert dumped["chart"]["kind"] == "bar"
        assert dumped["assertion_passed"] is False
        assert dumped["assertion_violation_count"] == 2
