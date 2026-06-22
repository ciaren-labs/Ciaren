"""Cross-engine parity: a flow run through pandas and through polars must produce
the same output data.

This locks in the guarantee behind defaulting to polars — every transformation in
a representative pipeline yields identical results on both engines. Outputs are
normalised (column order, row order, dtype) before comparison because the engines
are free to differ on incidental ordering, not on values.
"""

import pandas as pd
import pytest

from app.engine.executor import FlowExecutor, dataset_ref_key


def _paths(**by_id: object) -> dict[str, object]:
    return {dataset_ref_key(ds_id, None): path for ds_id, path in by_id.items()}


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Sort columns and rows so only data (not incidental order) is compared."""
    df = df.reindex(sorted(df.columns), axis=1)
    return df.sort_values(by=list(df.columns), na_position="last").reset_index(drop=True)


def _run(engine_name: str, graph: dict, paths: dict, out_dir) -> pd.DataFrame:
    outputs = FlowExecutor().execute(graph, paths, out_dir, engine_name=engine_name)
    out_path = next(iter(outputs.values()))
    return pd.read_csv(out_path)


def _assert_parity(graph: dict, paths: dict, tmp_path) -> None:
    pandas_dir = tmp_path / "pandas"
    polars_dir = tmp_path / "polars"
    pandas_dir.mkdir()
    polars_dir.mkdir()
    pandas_out = _run("pandas", graph, paths, pandas_dir)
    polars_out = _run("polars", graph, paths, polars_dir)
    pd.testing.assert_frame_equal(
        _normalize(pandas_out),
        _normalize(polars_out),
        check_dtype=False,  # int64 vs float on a column of whole numbers is fine
        check_exact=False,
    )


@pytest.fixture
def messy_csv(tmp_path):
    path = tmp_path / "in.csv"
    pd.DataFrame(
        {
            "name": ["Alice", "bob", "CHARLIE", "alice", None, "Dan"],
            "dept": ["eng", "eng", "sales", "eng", "sales", "sales"],
            "salary": [100, 200, 150, 100, 300, None],
            "bonus": [10, 20, 15, 10, 30, 5],
        }
    ).to_csv(path, index=False)
    return path


def test_parity_cleaning_pipeline(tmp_path, messy_csv) -> None:
    """dropNulls -> rename -> filter -> calculatedColumn -> sort."""
    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            {
                "id": "ren",
                "type": "renameColumns",
                "data": {"config": {"mapping": {"salary": "pay"}}},
            },
            {
                "id": "flt",
                "type": "filterRows",
                "data": {"config": {"column": "pay", "operator": ">=", "value": 100}},
            },
            {
                "id": "calc",
                "type": "calculatedColumn",
                "data": {"config": {"column_name": "total", "expression": "pay + bonus"}},
            },
            {
                "id": "sort",
                "type": "sortRows",
                "data": {"config": {"columns": ["total"], "ascending": [True]}},
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "ren"},
            {"id": "e3", "source": "ren", "target": "flt"},
            {"id": "e4", "source": "flt", "target": "calc"},
            {"id": "e5", "source": "calc", "target": "sort"},
            {"id": "e6", "source": "sort", "target": "out"},
        ],
    }
    _assert_parity(graph, _paths(ds1=messy_csv), tmp_path)


def test_parity_groupby_aggregate(tmp_path, messy_csv) -> None:
    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            {
                "id": "grp",
                "type": "groupByAggregate",
                "data": {"config": {"group_by": ["dept"], "aggregations": {"bonus": "sum"}}},
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "grp"},
            {"id": "e3", "source": "grp", "target": "out"},
        ],
    }
    _assert_parity(graph, _paths(ds1=messy_csv), tmp_path)


def test_parity_join(tmp_path) -> None:
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    pd.DataFrame({"id": [1, 2, 3], "x": ["a", "b", "c"]}).to_csv(left, index=False)
    pd.DataFrame({"id": [1, 2, 4], "y": ["p", "q", "r"]}).to_csv(right, index=False)
    graph = {
        "nodes": [
            {"id": "l", "type": "csvInput", "data": {"config": {"dataset_id": "L"}}},
            {"id": "r", "type": "csvInput", "data": {"config": {"dataset_id": "R"}}},
            {"id": "j", "type": "join", "data": {"config": {"on": "id", "how": "inner"}}},
            {"id": "o", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "l", "target": "j", "targetHandle": "left"},
            {"id": "e2", "source": "r", "target": "j", "targetHandle": "right"},
            {"id": "e3", "source": "j", "target": "o"},
        ],
    }
    _assert_parity(graph, _paths(L=left, R=right), tmp_path)


def test_parity_excel_roundtrip(tmp_path) -> None:
    """Excel in -> transform -> Excel out, on both engines (validates the native
    polars Excel read/write path matches pandas)."""
    src = tmp_path / "in.xlsx"
    pd.DataFrame(
        {"city": ["NYC", "LA", "SF"], "pop": [8, 4, 1], "area": [300, 500, 230]}
    ).to_excel(src, index=False)

    graph = {
        "nodes": [
            {"id": "in", "type": "excelInput", "data": {"config": {"dataset_id": "ds1"}}},
            {
                "id": "calc",
                "type": "calculatedColumn",
                "data": {"config": {"column_name": "density", "expression": "pop * 1000 / area"}},
            },
            {"id": "out", "type": "excelOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "calc"},
            {"id": "e2", "source": "calc", "target": "out"},
        ],
    }

    pandas_dir = tmp_path / "pandas"
    polars_dir = tmp_path / "polars"
    pandas_dir.mkdir()
    polars_dir.mkdir()
    paths = _paths(ds1=src)
    pandas_out = pd.read_excel(
        next(iter(FlowExecutor().execute(graph, paths, pandas_dir, "pandas").values()))
    )
    polars_out = pd.read_excel(
        next(iter(FlowExecutor().execute(graph, paths, polars_dir, "polars").values()))
    )
    pd.testing.assert_frame_equal(
        _normalize(pandas_out), _normalize(polars_out), check_dtype=False, check_exact=False
    )
