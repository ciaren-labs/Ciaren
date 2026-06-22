"""Polars code generation: the script must be valid Python and use polars APIs."""

from app.engine.polars_codegen import PolarsCodeGenerator


def _wide_graph(dataset_id: str = "ds1") -> dict:
    """An input feeding a chain that exercises many node types."""
    return {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            {"id": "ren", "type": "renameColumns", "data": {"config": {"mapping": {"a": "alpha"}}}},
            {
                "id": "flt",
                "type": "filterRows",
                "data": {"config": {"column": "alpha", "operator": ">", "value": 1}},
            },
            {
                "id": "calc",
                "type": "calculatedColumn",
                "data": {"config": {"column_name": "x2", "expression": "alpha * 2"}},
            },
            {
                "id": "grp",
                "type": "groupByAggregate",
                "data": {"config": {"group_by": ["alpha"], "aggregations": {"x2": "sum"}}},
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "ren"},
            {"id": "e3", "source": "ren", "target": "flt"},
            {"id": "e4", "source": "flt", "target": "calc"},
            {"id": "e5", "source": "calc", "target": "grp"},
            {"id": "e6", "source": "grp", "target": "out"},
        ],
    }


def test_polars_codegen_is_valid_and_uses_polars() -> None:
    code = PolarsCodeGenerator().generate(_wide_graph(), {"ds1": "/data/in.csv"})
    assert code.startswith("import polars as pl")
    assert 'pl.read_csv("/data/in.csv")' in code
    assert ".drop_nulls()" in code
    assert ".rename({'a': 'alpha'})" in code
    assert ".filter(pl.col('alpha') > 1)" in code
    assert "pl.sql_expr('alpha * 2').alias('x2')" in code
    assert ".group_by(['alpha']).agg(" in code
    assert ".write_csv(" in code
    compile(code, "<generated-polars>", "exec")


def test_polars_join_and_concat() -> None:
    graph = {
        "nodes": [
            {"id": "l", "type": "csvInput", "data": {"config": {"dataset_id": "L"}}},
            {"id": "r", "type": "csvInput", "data": {"config": {"dataset_id": "R"}}},
            {"id": "j", "type": "join", "data": {"config": {"on": "id", "how": "outer"}}},
            {"id": "o", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "l", "target": "j", "targetHandle": "left"},
            {"id": "e2", "source": "r", "target": "j", "targetHandle": "right"},
            {"id": "e3", "source": "j", "target": "o"},
        ],
    }
    code = PolarsCodeGenerator().generate(graph, {"L": "l.csv", "R": "r.csv"})
    assert ".join(" in code
    assert "how='full'" in code  # pandas 'outer' maps to polars 'full'
    compile(code, "<generated-polars-join>", "exec")
