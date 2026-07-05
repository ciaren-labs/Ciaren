"""Unit tests for rendering flow parameters as code (``app.engine.codegen_params``)."""

from app.engine.codegen_params import (
    CodeRef,
    parameter_block_lines,
    substitute_for_codegen,
)


def _graph(config):
    return {
        "parameters": [
            {"name": "keep", "type": "integer", "default": 2, "description": "rows to keep"},
            {"name": "date", "type": "string", "default": "2026-06"},
        ],
        "nodes": [{"id": "n", "type": "limitRows", "data": {"config": config}}],
        "edges": [],
    }


# -- CodeRef -----------------------------------------------------------------


def test_coderef_repr_is_raw_expression():
    assert repr(CodeRef("keep")) == "keep"


def test_coderef_addition_composes_expression():
    assert repr(0 + CodeRef("keep")) == "0 + keep"
    assert repr(CodeRef("offset") + 1) == "offset + 1"
    assert repr(CodeRef("a") + CodeRef("b")) == "a + b"


# -- substitute_for_codegen --------------------------------------------------


def test_full_match_becomes_bare_variable():
    out = substitute_for_codegen(_graph({"n": "{{ keep }}"}))
    assert repr(out["nodes"][0]["data"]["config"]["n"]) == "keep"


def test_embedded_reference_becomes_format_call():
    out = substitute_for_codegen(_graph({"path": "data/{{ date }}.csv"}))
    assert repr(out["nodes"][0]["data"]["config"]["path"]) == "'data/{}.csv'.format(date)"


def test_plain_string_untouched():
    out = substitute_for_codegen(_graph({"label": "hello"}))
    assert out["nodes"][0]["data"]["config"]["label"] == "hello"


def test_unknown_reference_left_as_literal():
    out = substitute_for_codegen(_graph({"x": "{{ missing }}"}))
    assert out["nodes"][0]["data"]["config"]["x"] == "{{ missing }}"


def test_substitution_is_pure():
    graph = _graph({"n": "{{ keep }}"})
    substitute_for_codegen(graph)
    assert graph["nodes"][0]["data"]["config"]["n"] == "{{ keep }}"


def test_no_parameters_returns_graph_unchanged():
    graph = {"nodes": [{"id": "n", "type": "dropNulls", "data": {"config": {}}}], "edges": []}
    assert substitute_for_codegen(graph) is graph


# -- parameter_block_lines ---------------------------------------------------


def test_parameter_block_lines_define_defaults_with_descriptions():
    lines = parameter_block_lines(_graph({"n": "{{ keep }}"}))
    assert lines[0].startswith("# Flow parameters")
    assert "keep = 2  # rows to keep" in lines
    assert "date = '2026-06'" in lines


def test_parameter_block_lines_empty_without_parameters():
    assert parameter_block_lines({"nodes": [], "edges": []}) == []


# -- import shadowing ---------------------------------------------------------


def test_parameter_shadowing_an_import_fails_export_with_clear_message():
    import pytest

    from app.engine.codegen import CodeGenerator
    from app.engine.graph import GraphValidationError
    from app.engine.polars_codegen import PolarsCodeGenerator

    # A sqlInput flow imports create_engine; a parameter with that name would
    # rebind the import right below it. The generator must refuse, by name.
    graph = {
        "parameters": [{"name": "create_engine", "type": "integer", "default": 1}],
        "nodes": [
            {
                "id": "in",
                "type": "sqlInput",
                "data": {"config": {"connection_id": "c1", "mode": "table", "table": "t"}},
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [{"id": "e1", "source": "in", "target": "out"}],
    }
    lines = ["# Flow parameters — override these to re-run with different values.", "create_engine = 1"]
    for gen in (CodeGenerator(), PolarsCodeGenerator()):
        with pytest.raises(GraphValidationError, match="create_engine"):
            gen.generate(graph, {}, {"c1": {"provider": "sqlite", "database": "db"}}, parameter_lines=lines)


def test_non_colliding_parameter_names_export_fine():
    from app.engine.codegen import CodeGenerator

    graph = {
        "parameters": [{"name": "keep", "type": "integer", "default": 2}],
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "d"}}},
            {"id": "lim", "type": "limitRows", "data": {"config": {"n": 2}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "lim"},
            {"id": "e2", "source": "lim", "target": "out"},
        ],
    }
    code = CodeGenerator().generate(graph, {"d": "in.csv"}, parameter_lines=["keep = 2"])
    assert "keep = 2" in code
