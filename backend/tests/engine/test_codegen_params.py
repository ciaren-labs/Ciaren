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
