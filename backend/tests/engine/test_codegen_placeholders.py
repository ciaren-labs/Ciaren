"""Placeholder paths and emitted dependency comments.

An input node whose dataset id is missing from the caller's ``dataset_paths``
map (graph validation guarantees an id is *bound*, but direct generate()
callers may not resolve it) falls back to a placeholder filename that matches
its format — pd.read_excel('input.xlsx'), never pd.read_excel('input.csv').

Separately: a "polars" script that secretly needs pandas at runtime
(filterExpression / assertExpression evaluate via pandas eval) must say so in
an emitted comment.
"""

import pytest

from app.engine.codegen import CodeGenerator
from app.engine.polars_codegen import PolarsCodeGenerator


def _input_graph(node_type: str, config: dict | None = None) -> dict:
    return {
        "nodes": [
            {"id": "in", "type": node_type, "data": {"config": {"dataset_id": "unresolved", **(config or {})}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [{"id": "e1", "source": "in", "target": "out"}],
    }


@pytest.mark.parametrize(
    "node_type,config,expected",
    [
        ("csvInput", None, "input.csv"),
        ("excelInput", None, "input.xlsx"),
        ("parquetInput", None, "input.parquet"),
        ("jsonInput", None, "input.json"),
        ("fileInput", {"format": "tsv"}, "input.tsv"),
        ("fileInput", {"format": "jsonl"}, "input.jsonl"),
        ("fileInput", {"format": "text"}, "input.txt"),
    ],
)
def test_unresolved_input_placeholder_matches_format(node_type: str, config: dict | None, expected: str) -> None:
    graph = _input_graph(node_type, config)
    for code in (
        CodeGenerator().generate(graph, {}),
        PolarsCodeGenerator().generate(graph, {}),
    ):
        assert repr(expected) in code, f"{node_type}: expected {expected!r} placeholder in:\n{code}"
        if expected != "input.csv":
            assert "'input.csv'" not in code


def test_polars_pandas_bridge_comment_on_filter_expression() -> None:
    """A 'polars' script that secretly needs pandas at runtime must say so."""
    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "d"}}},
            {"id": "f", "type": "filterExpression", "data": {"config": {"expression": "a > 1"}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "f"},
            {"id": "e2", "source": "f", "target": "out"},
        ],
    }
    code = PolarsCodeGenerator().generate(graph, {"d": "in.csv"})
    assert "needs pandas + pyarrow installed" in code


def test_polars_pandas_bridge_comment_on_assert_expression() -> None:
    from app.engine.registry import get_transformation

    t = get_transformation("assertExpression")
    code = t.to_polars_code({"in": "df_1"}, {"out": "df_1"}, {"expression": "a > 0"})
    assert "needs pandas + pyarrow installed" in code
    compile(code, "<polars-assert>", "exec")
