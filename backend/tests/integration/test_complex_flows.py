"""End-to-end integration tests for COMPLEX, multi-input ETL flows.

These build real React-Flow-compatible ``graph_json`` from registered node types
and run them through :class:`app.engine.executor.FlowExecutor`, asserting exact
output values (computed by hand / with a direct pandas reference). The point is to
prove that nodes behave correctly when *composed* into branched, multi-input
pipelines -- not merely that the engine "runs without error".

Driven directly through the engine for speed and clarity; one API-level run test
(:func:`test_api_level_complex_run`) covers the full HTTP path.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from httpx import AsyncClient

from app.engine.executor import FlowExecutor, dataset_ref_key

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _paths(**by_id: Path) -> dict[str, Path]:
    """Key dataset paths the way the engine resolves them (id -> 'id:latest')."""
    return {dataset_ref_key(ds_id, None): path for ds_id, path in by_id.items()}


def _write_csv(path: Path, df: pd.DataFrame) -> Path:
    df.to_csv(path, index=False)
    return path


def _run_to_df(
    graph: dict[str, Any],
    paths: dict[str, Path],
    out_dir: Path,
    engine_name: str = "pandas",
) -> pd.DataFrame:
    """Execute a single-output graph and read the written CSV back as pandas."""
    out_dir.mkdir(exist_ok=True)
    outputs = FlowExecutor().execute(graph, paths, out_dir, engine_name=engine_name)
    assert len(outputs) == 1, f"expected one output, got {list(outputs)}"
    return pd.read_csv(next(iter(outputs.values())))


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Sort columns and rows so only data (not incidental order) is compared."""
    df = df.reindex(sorted(df.columns), axis=1)
    return df.sort_values(by=list(df.columns), na_position="last").reset_index(drop=True)


def _node(node_id: str, node_type: str, **config: Any) -> dict[str, Any]:
    return {"id": node_id, "type": node_type, "data": {"config": config}}


def _edge(source: str, target: str, target_handle: str | None = None) -> dict[str, Any]:
    edge: dict[str, Any] = {"id": f"{source}->{target}", "source": source, "target": target}
    if target_handle is not None:
        edge["targetHandle"] = target_handle
    return edge


# ---------------------------------------------------------------------------
# 1. LINEAR pipeline
#    input -> dropNulls -> fillNulls -> stringTransform -> parseDates
#          -> filterRows -> sortRows -> output
# ---------------------------------------------------------------------------


def test_linear_cleaning_pipeline(tmp_path: Path) -> None:
    raw = pd.DataFrame(
        {
            "name": ["alice", "BOB", "charlie", "dave", None],
            "score": [50.0, None, 90.0, 30.0, 70.0],
            "joined": ["2021-01-15", "2020-06-01", "2019-03-10", "2022-12-25", "2021-07-04"],
            "region": ["us", "eu", "us", "eu", "us"],
        }
    )
    src = _write_csv(tmp_path / "people.csv", raw)

    graph = {
        "nodes": [
            _node("in", "csvInput", dataset_id="ds1"),
            # Drop the row whose name is null (row 4). score null (row 1) stays.
            _node("drop", "dropNulls", subset=["name"]),
            # Fill the remaining null score (row 1, BOB) with the column mean.
            _node("fill", "fillNulls", strategy="mean", columns=["score"]),
            # Uppercase names so they are comparable.
            _node("upper", "stringTransform", column="name", operation="upper"),
            _node("dates", "parseDates", columns=["joined"]),
            # Keep only scores >= 60.
            _node("flt", "filterRows", column="score", operator=">=", value=60),
            _node("sort", "sortRows", columns=["score"], ascending=[False]),
            _node("out", "csvOutput"),
        ],
        "edges": [
            _edge("in", "drop"),
            _edge("drop", "fill"),
            _edge("fill", "upper"),
            _edge("upper", "dates"),
            _edge("dates", "flt"),
            _edge("flt", "sort"),
            _edge("sort", "out"),
        ],
    }

    result = _run_to_df(graph, _paths(ds1=src), tmp_path / "out")

    # Reference by hand:
    #   dropNulls(name) removes the last row.
    #   remaining scores: [50, None, 90, 30]; mean of present = (50+90+30)/3 = 56.667
    #   BOB's null becomes 56.667; filter score >= 60 keeps CHARLIE(90) only.
    assert list(result["name"]) == ["CHARLIE"]
    assert result.loc[0, "score"] == pytest.approx(90.0)
    assert str(result.loc[0, "joined"]).startswith("2019-03-10")
    assert list(result.columns) == ["name", "score", "joined", "region"]


def test_linear_pipeline_fill_mean_value_and_ordering(tmp_path: Path) -> None:
    """Same shape but a lower filter so the mean-fill + sort are both exercised."""
    raw = pd.DataFrame(
        {
            "name": ["a", "b", "c", "d"],
            "score": [10.0, None, 40.0, 70.0],
        }
    )
    src = _write_csv(tmp_path / "s.csv", raw)
    graph = {
        "nodes": [
            _node("in", "csvInput", dataset_id="ds1"),
            _node("fill", "fillNulls", strategy="mean", columns=["score"]),
            _node("flt", "filterRows", column="score", operator=">=", value=20),
            _node("sort", "sortRows", columns=["score"], ascending=[True]),
            _node("out", "csvOutput"),
        ],
        "edges": [
            _edge("in", "fill"),
            _edge("fill", "flt"),
            _edge("flt", "sort"),
            _edge("sort", "out"),
        ],
    }
    result = _run_to_df(graph, _paths(ds1=src), tmp_path / "out")
    # mean of [10,40,70] = 40 -> b becomes 40. >=20 keeps b(40), c(40), d(70).
    # ascending sort by score: [40, 40, 70]; the two 40s are b and c (stable order).
    assert list(result["score"]) == [40.0, 40.0, 70.0]
    assert set(result["name"]) == {"b", "c", "d"}


# ---------------------------------------------------------------------------
# 2. TWO-INPUT JOIN: each branch cleaned independently, then join + calc + groupby
# ---------------------------------------------------------------------------


def _two_input_graph(how: str) -> dict[str, Any]:
    return {
        "nodes": [
            _node("orders", "csvInput", dataset_id="orders"),
            _node("cust", "csvInput", dataset_id="customers"),
            # Branch A: orders -> drop cancelled rows.
            _node("active", "filterRows", column="status", operator="==", value="active"),
            # Branch B: customers -> uppercase the region.
            _node("region", "stringTransform", column="region", operation="upper"),
            _node("j", "join", on="customer_id", how=how),
            _node("rev", "calculatedColumn", column_name="revenue", expression="qty * price"),
            _node(
                "grp",
                "groupByAggregate",
                group_by=["region"],
                aggregations={"revenue": "sum"},
            ),
            _node("out", "csvOutput"),
        ],
        "edges": [
            _edge("orders", "active"),
            _edge("cust", "region"),
            _edge("active", "j", "left"),
            _edge("region", "j", "right"),
            _edge("j", "rev"),
            _edge("rev", "grp"),
            _edge("grp", "out"),
        ],
    }


@pytest.fixture
def join_inputs(tmp_path: Path) -> dict[str, Path]:
    orders = pd.DataFrame(
        {
            "customer_id": [1, 1, 2, 3, None],
            "status": ["active", "cancelled", "active", "active", "active"],
            "qty": [2, 5, 1, 4, 9],
            "price": [10.0, 10.0, 20.0, 5.0, 100.0],
        }
    )
    customers = pd.DataFrame(
        {
            "customer_id": [1, 2, 4],
            "region": ["us", "eu", "us"],
        }
    )
    return _paths(
        orders=_write_csv(tmp_path / "orders.csv", orders),
        customers=_write_csv(tmp_path / "customers.csv", customers),
    )


def test_two_input_inner_join_aggregate(join_inputs: dict[str, Path], tmp_path: Path) -> None:
    result = _run_to_df(_two_input_graph("inner"), join_inputs, tmp_path / "out")

    # Active orders (cancelled dropped, null customer_id row has no match):
    #   cid=1 qty=2 price=10 -> rev 20  (region us)
    #   cid=2 qty=1 price=20 -> rev 20  (region eu)
    #   cid=3 ... -> no customer match (inner join drops it)
    #   null cid -> no match
    # group by region: US=20, EU=20.
    out = {row["region"]: row["revenue"] for _, row in result.iterrows()}
    assert out == {"US": 20.0, "EU": 20.0}


def test_two_input_left_join_keeps_unmatched(join_inputs: dict[str, Path], tmp_path: Path) -> None:
    result = _run_to_df(_two_input_graph("left"), join_inputs, tmp_path / "out")

    # Left join keeps active order rows with no customer (cid=3 and null cid).
    # Those rows have region == NaN, so after upper() it is still missing.
    #   cid=1 rev 20 (US), cid=2 rev 20 (EU),
    #   cid=3 qty=4 price=5 -> rev 20 (region NaN -> dropped from groupby keys),
    #   null cid qty=9 price=100 -> rev 900 (region NaN -> dropped).
    # pandas groupby drops NaN group keys, so only US and EU survive.
    out = {row["region"]: row["revenue"] for _, row in result.iterrows()}
    assert out == {"US": 20.0, "EU": 20.0}


def test_two_input_join_cardinality_with_duplicate_keys(tmp_path: Path) -> None:
    """An inner join must produce the cartesian product within a key group."""
    left = _write_csv(tmp_path / "l.csv", pd.DataFrame({"k": [1, 1, 2], "lv": ["a", "b", "c"]}))
    right = _write_csv(tmp_path / "r.csv", pd.DataFrame({"k": [1, 1, 3], "rv": ["x", "y", "z"]}))
    graph = {
        "nodes": [
            _node("l", "csvInput", dataset_id="L"),
            _node("r", "csvInput", dataset_id="R"),
            _node("j", "join", on="k", how="inner"),
            _node("out", "csvOutput"),
        ],
        "edges": [
            _edge("l", "j", "left"),
            _edge("r", "j", "right"),
            _edge("j", "out"),
        ],
    }
    result = _run_to_df(graph, _paths(L=left, R=right), tmp_path / "out")
    # k=1 has 2 left x 2 right = 4 rows; k=2 unmatched; k=3 unmatched. Total = 4.
    assert len(result) == 4
    assert set(result["k"]) == {1}
    assert sorted(zip(result["lv"], result["rv"])) == [
        ("a", "x"),
        ("a", "y"),
        ("b", "x"),
        ("b", "y"),
    ]


# ---------------------------------------------------------------------------
# 3. THREE-INPUT pipeline
#    orders + order_items joined, then joined to products; conditionalColumn,
#    removeOutliers, groupByAggregate.
# ---------------------------------------------------------------------------


def test_three_input_pipeline(tmp_path: Path) -> None:
    orders = _write_csv(
        tmp_path / "orders.csv",
        pd.DataFrame({"order_id": [1, 2, 3], "channel": ["web", "store", "web"]}),
    )
    items = _write_csv(
        tmp_path / "items.csv",
        pd.DataFrame(
            {
                "order_id": [1, 1, 2, 3, 3],
                "product_id": [10, 11, 10, 11, 12],
                "qty": [1, 2, 1, 5, 1000],  # 1000 is an outlier
            }
        ),
    )
    products = _write_csv(
        tmp_path / "products.csv",
        pd.DataFrame(
            {
                "product_id": [10, 11, 12],
                "price": [100.0, 50.0, 5.0],
            }
        ),
    )

    graph = {
        "nodes": [
            _node("o", "csvInput", dataset_id="orders"),
            _node("i", "csvInput", dataset_id="items"),
            _node("p", "csvInput", dataset_id="products"),
            # Join orders to items on order_id.
            _node("oi", "join", on="order_id", how="inner"),
            # Join the result to products on product_id.
            _node("oip", "join", on="product_id", how="inner"),
            # Drop the qty=1000 outlier via IQR before computing revenue.
            _node("noout", "removeOutliers", columns=["qty"], method="iqr", action="drop"),
            _node("rev", "calculatedColumn", column_name="line_total", expression="qty * price"),
            # Tag each line big/small.
            _node(
                "tag",
                "conditionalColumn",
                new_column="size",
                default="small",
                rules=[{"column": "line_total", "operator": ">=", "value": 200, "result": "big"}],
            ),
            _node(
                "grp",
                "groupByAggregate",
                group_by=["channel"],
                aggregations={"line_total": "sum"},
            ),
            _node("out", "csvOutput"),
        ],
        "edges": [
            _edge("o", "oi", "left"),
            _edge("i", "oi", "right"),
            _edge("oi", "oip", "left"),
            _edge("p", "oip", "right"),
            _edge("oip", "noout"),
            _edge("noout", "rev"),
            _edge("rev", "tag"),
            _edge("tag", "grp"),
            _edge("grp", "out"),
        ],
    }

    result = _run_to_df(graph, _paths(orders=orders, items=items, products=products), tmp_path / "out")

    # Build a pandas reference independently.
    o = pd.read_csv(orders)
    i = pd.read_csv(items)
    p = pd.read_csv(products)
    merged = o.merge(i, on="order_id").merge(p, on="product_id")
    q = merged["qty"]
    q1, q3 = q.quantile(0.25), q.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    kept = merged[q.between(lo, hi) | q.isna()].copy()
    # The qty=1000 row must have been dropped as an outlier.
    assert 1000 not in set(kept["qty"]), "outlier row should be removed before revenue"
    kept["line_total"] = kept["qty"] * kept["price"]
    expected = kept.groupby("channel")["line_total"].sum().reset_index().sort_values("channel")

    got = result.sort_values("channel").reset_index(drop=True)
    pd.testing.assert_frame_equal(
        got[["channel", "line_total"]].reset_index(drop=True),
        expected.reset_index(drop=True),
        check_dtype=False,
    )


def test_three_input_with_concat_branch(tmp_path: Path) -> None:
    """Two same-shape stores are concatenated, then joined to a region lookup."""
    store_a = _write_csv(
        tmp_path / "a.csv",
        pd.DataFrame({"store": ["a", "a"], "sales": [100, 200]}),
    )
    store_b = _write_csv(
        tmp_path / "b.csv",
        pd.DataFrame({"store": ["b", "b"], "sales": [300, 400]}),
    )
    lookup = _write_csv(
        tmp_path / "lk.csv",
        pd.DataFrame({"store": ["a", "b"], "region": ["north", "south"]}),
    )
    graph = {
        "nodes": [
            _node("a", "csvInput", dataset_id="A"),
            _node("b", "csvInput", dataset_id="B"),
            _node("lk", "csvInput", dataset_id="LK"),
            _node("cat", "concatRows"),
            _node("j", "join", on="store", how="inner"),
            _node("grp", "groupByAggregate", group_by=["region"], aggregations={"sales": "sum"}),
            _node("out", "csvOutput"),
        ],
        "edges": [
            _edge("a", "cat"),
            _edge("b", "cat"),
            _edge("cat", "j", "left"),
            _edge("lk", "j", "right"),
            _edge("j", "grp"),
            _edge("grp", "out"),
        ],
    }
    result = _run_to_df(graph, _paths(A=store_a, B=store_b, LK=lookup), tmp_path / "out")
    out = {row["region"]: row["sales"] for _, row in result.iterrows()}
    # north = a's 100+200 = 300; south = b's 300+400 = 700.
    assert out == {"north": 300, "south": 700}


# ---------------------------------------------------------------------------
# 4. NODE-FOCUSED correctness (each node's effect asserted explicitly)
# ---------------------------------------------------------------------------


def test_groupby_multiple_agg_funcs(tmp_path: Path) -> None:
    src = _write_csv(
        tmp_path / "g.csv",
        pd.DataFrame(
            {
                "dept": ["eng", "eng", "sales", "sales"],
                "salary": [100, 300, 200, 200],
                "bonus": [10, 20, 5, 15],
            }
        ),
    )
    graph = {
        "nodes": [
            _node("in", "csvInput", dataset_id="ds1"),
            _node(
                "grp",
                "groupByAggregate",
                group_by=["dept"],
                # Distinct funcs per column (the dict maps one func per column).
                aggregations={"salary": "mean", "bonus": "sum"},
            ),
            _node("out", "csvOutput"),
        ],
        "edges": [_edge("in", "grp"), _edge("grp", "out")],
    }
    result = _run_to_df(graph, _paths(ds1=src), tmp_path / "out").set_index("dept")
    assert result.loc["eng", "salary"] == pytest.approx(200.0)  # mean(100,300)
    assert result.loc["sales", "salary"] == pytest.approx(200.0)
    assert result.loc["eng", "bonus"] == 30  # sum(10,20)
    assert result.loc["sales", "bonus"] == 20  # sum(5,15)


def test_pivot_unpivot_roundtrip(tmp_path: Path) -> None:
    """unpivot a wide frame to long, then pivot back; values must round-trip."""
    wide = pd.DataFrame(
        {
            "city": ["NYC", "LA"],
            "jan": [10, 20],
            "feb": [30, 40],
        }
    )
    src = _write_csv(tmp_path / "w.csv", wide)
    graph = {
        "nodes": [
            _node("in", "csvInput", dataset_id="ds1"),
            _node(
                "long",
                "unpivot",
                id_vars=["city"],
                value_vars=["jan", "feb"],
                var_name="month",
                value_name="sales",
            ),
            _node(
                "wide",
                "pivot",
                index="city",
                columns="month",
                values="sales",
                aggfunc="sum",
            ),
            _node("out", "csvOutput"),
        ],
        "edges": [_edge("in", "long"), _edge("long", "wide"), _edge("wide", "out")],
    }
    result = _run_to_df(graph, _paths(ds1=src), tmp_path / "out")
    pd.testing.assert_frame_equal(_normalize(result), _normalize(wide), check_dtype=False)


def test_window_row_number_running_total_and_lag(tmp_path: Path) -> None:
    src = _write_csv(
        tmp_path / "tx.csv",
        pd.DataFrame(
            {
                "acct": ["a", "a", "a", "b", "b"],
                "day": [1, 2, 3, 1, 2],
                "amount": [10, 20, 30, 100, 200],
            }
        ),
    )
    graph = {
        "nodes": [
            _node("in", "csvInput", dataset_id="ds1"),
            _node(
                "rn",
                "windowFunction",
                function="row_number",
                partition_by=["acct"],
                order_by=["day"],
                new_column="rn",
            ),
            _node(
                "run",
                "windowFunction",
                function="cumsum",
                partition_by=["acct"],
                order_by=["day"],
                target="amount",
                new_column="running",
            ),
            _node(
                "prev",
                "windowFunction",
                function="lag",
                partition_by=["acct"],
                order_by=["day"],
                target="amount",
                offset=1,
                new_column="prev_amount",
            ),
            _node("out", "csvOutput"),
        ],
        "edges": [
            _edge("in", "rn"),
            _edge("rn", "run"),
            _edge("run", "prev"),
            _edge("prev", "out"),
        ],
    }
    result = _run_to_df(graph, _paths(ds1=src), tmp_path / "out")
    # Original row order is preserved (window restores input order).
    assert list(result["rn"]) == [1, 2, 3, 1, 2]
    assert list(result["running"]) == [10, 30, 60, 100, 300]
    # lag(1) within partition: first row of each acct has no prior -> NaN.
    prev = result["prev_amount"].tolist()
    assert prev[0] != prev[0]  # NaN for a-day1
    assert prev[1] == 10
    assert prev[2] == 20
    assert prev[3] != prev[3]  # NaN for b-day1
    assert prev[4] == 100


def test_bin_column_equalwidth(tmp_path: Path) -> None:
    src = _write_csv(
        tmp_path / "b.csv",
        pd.DataFrame({"v": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}),
    )
    graph = {
        "nodes": [
            _node("in", "csvInput", dataset_id="ds1"),
            _node(
                "bin",
                "binColumn",
                column="v",
                new_column="bucket",
                method="equalwidth",
                bins=2,
                labels=["low", "high"],
            ),
            _node("out", "csvOutput"),
        ],
        "edges": [_edge("in", "bin"), _edge("bin", "out")],
    }
    result = _run_to_df(graph, _paths(ds1=src), tmp_path / "out")
    # equal-width split of [0,10] into 2 bins at 5: 0-5 -> low, 5-10 -> high.
    buckets = dict(zip(result["v"], result["bucket"]))
    assert buckets[0] == "low"
    assert buckets[5] == "low"  # 5 falls in the first (left-inclusive cut) bin edge
    assert buckets[6] == "high"
    assert buckets[10] == "high"


def test_map_values_with_default(tmp_path: Path) -> None:
    src = _write_csv(
        tmp_path / "m.csv",
        pd.DataFrame({"code": ["A", "B", "C", "Z"]}),
    )
    graph = {
        "nodes": [
            _node("in", "csvInput", dataset_id="ds1"),
            _node(
                "map",
                "mapValues",
                column="code",
                new_column="label",
                mapping={"A": "Alpha", "B": "Beta"},
                default="Other",
                use_default=True,
            ),
            _node("out", "csvOutput"),
        ],
        "edges": [_edge("in", "map"), _edge("map", "out")],
    }
    result = _run_to_df(graph, _paths(ds1=src), tmp_path / "out")
    labels = dict(zip(result["code"], result["label"]))
    assert labels == {"A": "Alpha", "B": "Beta", "C": "Other", "Z": "Other"}
    # Original column is preserved (new_column used).
    assert "code" in result.columns


def test_split_column_by_delimiter(tmp_path: Path) -> None:
    src = _write_csv(
        tmp_path / "n.csv",
        pd.DataFrame({"full": ["Ada Lovelace", "Alan Turing", "Grace Hopper"]}),
    )
    graph = {
        "nodes": [
            _node("in", "csvInput", dataset_id="ds1"),
            _node(
                "split",
                "splitColumn",
                column="full",
                into=["first", "last"],
                mode="delimiter",
                delimiter=" ",
                keep_original=False,
            ),
            _node("out", "csvOutput"),
        ],
        "edges": [_edge("in", "split"), _edge("split", "out")],
    }
    result = _run_to_df(graph, _paths(ds1=src), tmp_path / "out")
    assert list(result["first"]) == ["Ada", "Alan", "Grace"]
    assert list(result["last"]) == ["Lovelace", "Turing", "Hopper"]
    assert "full" not in result.columns  # keep_original=False dropped it


@pytest.mark.parametrize(
    "method,action,kwargs",
    [
        ("iqr", "drop", {}),
        ("zscore", "drop", {"threshold": 1.0}),
        ("percentile", "clip", {"lower": 10.0, "upper": 90.0}),
    ],
)
def test_remove_outliers_methods(tmp_path: Path, method: str, action: str, kwargs: dict[str, Any]) -> None:
    values = [10, 11, 12, 13, 14, 15, 16, 17, 18, 1000]
    src = _write_csv(tmp_path / f"o_{method}.csv", pd.DataFrame({"v": values}))
    graph = {
        "nodes": [
            _node("in", "csvInput", dataset_id="ds1"),
            _node("rm", "removeOutliers", columns=["v"], method=method, action=action, **kwargs),
            _node("out", "csvOutput"),
        ],
        "edges": [_edge("in", "rm"), _edge("rm", "out")],
    }
    result = _run_to_df(graph, _paths(ds1=src), tmp_path / "out")

    # Independent pandas reference for the same bounds.
    s = pd.Series(values, dtype="float64")
    if method == "iqr":
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    elif method == "zscore":
        lo = s.mean() - kwargs["threshold"] * s.std()
        hi = s.mean() + kwargs["threshold"] * s.std()
    else:  # percentile
        lo, hi = s.quantile(kwargs["lower"] / 100), s.quantile(kwargs["upper"] / 100)

    if action == "drop":
        expected = s[s.between(lo, hi)].tolist()
        assert sorted(result["v"].tolist()) == sorted(expected)
        assert 1000 not in result["v"].tolist()
    else:  # clip (compare with tolerance: CSV round-trip loses float precision)
        expected = sorted(s.clip(lo, hi).tolist())
        got = sorted(result["v"].tolist())
        assert got == pytest.approx(expected)
        assert result["v"].max() == pytest.approx(hi)


def test_conditional_column_first_rule_wins(tmp_path: Path) -> None:
    src = _write_csv(
        tmp_path / "c.csv",
        pd.DataFrame({"score": [95, 82, 70, 55, 40]}),
    )
    graph = {
        "nodes": [
            _node("in", "csvInput", dataset_id="ds1"),
            _node(
                "grade",
                "conditionalColumn",
                new_column="grade",
                default="F",
                rules=[
                    {"column": "score", "operator": ">=", "value": 90, "result": "A"},
                    {"column": "score", "operator": ">=", "value": 80, "result": "B"},
                    {"column": "score", "operator": ">=", "value": 60, "result": "C"},
                ],
            ),
            _node("out", "csvOutput"),
        ],
        "edges": [_edge("in", "grade"), _edge("grade", "out")],
    }
    result = _run_to_df(graph, _paths(ds1=src), tmp_path / "out")
    # First matching rule wins: 95->A, 82->B, 70->C, 55->F, 40->F.
    assert dict(zip(result["score"], result["grade"])) == {
        95: "A",
        82: "B",
        70: "C",
        55: "F",
        40: "F",
    }


# ---------------------------------------------------------------------------
# 5. ENGINE PARITY: a complex flow under pandas and polars must match.
# ---------------------------------------------------------------------------


def test_engine_parity_complex_join_pipeline(tmp_path: Path) -> None:
    orders = _write_csv(
        tmp_path / "orders.csv",
        pd.DataFrame(
            {
                "customer_id": [1, 1, 2, 3],
                "status": ["active", "active", "active", "active"],
                "qty": [2, 3, 1, 4],
                "price": [10.0, 10.0, 20.0, 5.0],
            }
        ),
    )
    customers = _write_csv(
        tmp_path / "customers.csv",
        pd.DataFrame({"customer_id": [1, 2, 3], "region": ["us", "eu", "us"]}),
    )
    graph = {
        "nodes": [
            _node("o", "csvInput", dataset_id="orders"),
            _node("c", "csvInput", dataset_id="customers"),
            _node("up", "stringTransform", column="region", operation="upper"),
            _node("j", "join", on="customer_id", how="inner"),
            _node("rev", "calculatedColumn", column_name="revenue", expression="qty * price"),
            _node("grp", "groupByAggregate", group_by=["region"], aggregations={"revenue": "sum"}),
            _node("sort", "sortRows", columns=["region"], ascending=[True]),
            _node("out", "csvOutput"),
        ],
        "edges": [
            _edge("o", "j", "left"),
            _edge("c", "up"),
            _edge("up", "j", "right"),
            _edge("j", "rev"),
            _edge("rev", "grp"),
            _edge("grp", "sort"),
            _edge("sort", "out"),
        ],
    }
    paths = _paths(orders=orders, customers=customers)
    pandas_out = _run_to_df(graph, paths, tmp_path / "pandas", "pandas")
    polars_out = _run_to_df(graph, paths, tmp_path / "polars", "polars")
    pd.testing.assert_frame_equal(_normalize(pandas_out), _normalize(polars_out), check_dtype=False, check_exact=False)


def test_engine_parity_window_and_conditional(tmp_path: Path) -> None:
    src = _write_csv(
        tmp_path / "w.csv",
        pd.DataFrame(
            {
                "acct": ["a", "a", "b", "b", "b"],
                "day": [1, 2, 1, 2, 3],
                "amount": [10, 40, 5, 5, 100],
            }
        ),
    )
    graph = {
        "nodes": [
            _node("in", "csvInput", dataset_id="ds1"),
            _node(
                "run",
                "windowFunction",
                function="cumsum",
                partition_by=["acct"],
                order_by=["day"],
                target="amount",
                new_column="running",
            ),
            _node(
                "tag",
                "conditionalColumn",
                new_column="band",
                default="low",
                rules=[
                    {"column": "running", "operator": ">=", "value": 50, "result": "high"},
                ],
            ),
            _node("out", "csvOutput"),
        ],
        "edges": [_edge("in", "run"), _edge("run", "tag"), _edge("tag", "out")],
    }
    paths = _paths(ds1=src)
    pandas_out = _run_to_df(graph, paths, tmp_path / "pandas", "pandas")
    polars_out = _run_to_df(graph, paths, tmp_path / "polars", "polars")
    pd.testing.assert_frame_equal(_normalize(pandas_out), _normalize(polars_out), check_dtype=False, check_exact=False)


# ---------------------------------------------------------------------------
# API-level end-to-end run (full HTTP path) for one complex branched flow.
# ---------------------------------------------------------------------------


async def _upload_csv(client: AsyncClient, name: str, df: pd.DataFrame) -> str:
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    r = await client.post(
        "/api/datasets/upload",
        files={"file": (name, buf.getvalue(), "text/csv")},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_api_level_complex_run(client: AsyncClient, tmp_path: Path) -> None:
    orders_id = await _upload_csv(
        client,
        "orders.csv",
        pd.DataFrame(
            {
                "customer_id": [1, 1, 2],
                "qty": [2, 3, 1],
                "price": [10.0, 10.0, 20.0],
            }
        ),
    )
    customers_id = await _upload_csv(
        client,
        "customers.csv",
        pd.DataFrame({"customer_id": [1, 2], "region": ["us", "eu"]}),
    )

    graph = {
        "nodes": [
            _node("o", "csvInput", dataset_id=orders_id),
            _node("c", "csvInput", dataset_id=customers_id),
            _node("j", "join", on="customer_id", how="inner"),
            _node("rev", "calculatedColumn", column_name="revenue", expression="qty * price"),
            _node("grp", "groupByAggregate", group_by=["region"], aggregations={"revenue": "sum"}),
            _node("out", "csvOutput"),
        ],
        "edges": [
            _edge("o", "j", "left"),
            _edge("c", "j", "right"),
            _edge("j", "rev"),
            _edge("rev", "grp"),
            _edge("grp", "out"),
        ],
    }
    flow = (await client.post("/api/flows", json={"name": "complex", "graph_json": graph})).json()

    r = await client.post(f"/api/flows/{flow['id']}/runs", json={"engine": "pandas"})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "success", run.get("error_message")

    out_file = tmp_path / "outputs" / run["output_location"]
    assert out_file.exists()
    result = pd.read_csv(out_file)
    # us: (2*10)+(3*10) = 50 ; eu: 1*20 = 20.
    out = {row["region"]: row["revenue"] for _, row in result.iterrows()}
    assert out == {"us": 50.0, "eu": 20.0}
