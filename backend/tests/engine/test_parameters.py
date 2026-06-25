"""Unit tests for the pure flow-parameter engine (``app.engine.parameters``)."""

import pytest

from app.engine.parameters import (
    ParameterError,
    apply_parameters,
    read_parameter_specs,
    resolve_values,
    substitute,
)


def _graph(parameters, config):
    return {
        "parameters": parameters,
        "nodes": [
            {"id": "n1", "type": "csvInput", "data": {"config": {"dataset_id": "ds"}}},
            {"id": "n2", "type": "limitRows", "data": {"config": config}},
        ],
        "edges": [{"id": "e", "source": "n1", "target": "n2"}],
    }


# -- read_parameter_specs ----------------------------------------------------


def test_read_specs_absent_returns_empty():
    assert read_parameter_specs({"nodes": []}) == []
    assert read_parameter_specs(None) == []


def test_read_specs_non_list_raises():
    with pytest.raises(ParameterError):
        read_parameter_specs({"parameters": {"oops": 1}})


# -- resolve_values ----------------------------------------------------------


def test_default_used_when_no_override():
    specs = [{"name": "n", "type": "integer", "default": 5}]
    assert resolve_values(specs, {}) == {"n": 5}


def test_override_wins_over_default():
    specs = [{"name": "n", "type": "integer", "default": 5}]
    assert resolve_values(specs, {"n": 9}) == {"n": 9}


def test_missing_required_raises():
    specs = [{"name": "n", "type": "integer"}]  # no default, no override
    with pytest.raises(ParameterError, match="no value"):
        resolve_values(specs, {})


def test_unknown_override_raises():
    specs = [{"name": "n", "type": "integer", "default": 1}]
    with pytest.raises(ParameterError, match="Unknown parameter override"):
        resolve_values(specs, {"typo": 2})


def test_duplicate_spec_name_raises():
    specs = [{"name": "n", "default": 1}, {"name": "n", "default": 2}]
    with pytest.raises(ParameterError, match="Duplicate"):
        resolve_values(specs, {})


@pytest.mark.parametrize("bad_name", ["1bad", "with space", "", None])
def test_invalid_name_raises(bad_name):
    with pytest.raises(ParameterError, match="Invalid parameter name"):
        resolve_values([{"name": bad_name, "default": 1}], {})


def test_unknown_type_raises():
    with pytest.raises(ParameterError, match="unknown type"):
        resolve_values([{"name": "n", "type": "date", "default": "x"}], {})


# -- coercion ----------------------------------------------------------------


def test_integer_coercion_from_string():
    assert resolve_values([{"name": "n", "type": "integer"}], {"n": "7"}) == {"n": 7}


def test_integer_coercion_rejects_non_integral():
    with pytest.raises(ParameterError, match="integer"):
        resolve_values([{"name": "n", "type": "integer"}], {"n": "abc"})
    with pytest.raises(ParameterError, match="integer"):
        resolve_values([{"name": "n", "type": "integer"}], {"n": 1.5})


def test_number_coercion():
    assert resolve_values([{"name": "x", "type": "number"}], {"x": "2.5"}) == {"x": 2.5}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("true", True), ("False", False), ("1", True), ("0", False), ("yes", True), (False, False)],
)
def test_boolean_coercion(raw, expected):
    assert resolve_values([{"name": "b", "type": "boolean"}], {"b": raw}) == {"b": expected}


def test_boolean_coercion_rejects_garbage():
    with pytest.raises(ParameterError, match="boolean"):
        resolve_values([{"name": "b", "type": "boolean"}], {"b": "maybe"})


def test_string_is_default_type():
    assert resolve_values([{"name": "s"}], {"s": 123}) == {"s": "123"}


# -- substitute --------------------------------------------------------------


def test_full_match_preserves_type():
    # A value that is exactly a reference keeps the typed (non-string) value.
    assert substitute("{{ n }}", {"n": 5}) == 5
    assert substitute("{{ flag }}", {"flag": True}) is True


def test_embedded_reference_is_stringified():
    assert substitute("data/{{ date }}.csv", {"date": "2026-06"}) == "data/2026-06.csv"


def test_unknown_reference_left_untouched():
    assert substitute("{{ missing }}", {"n": 1}) == "{{ missing }}"
    assert substitute("a {{ missing }} b", {"n": 1}) == "a {{ missing }} b"


def test_substitute_recurses_into_dicts_and_lists():
    out = substitute({"k": ["{{ n }}", "x"], "d": {"v": "{{ n }}"}}, {"n": 3})
    assert out == {"k": [3, "x"], "d": {"v": 3}}


# -- apply_parameters --------------------------------------------------------


def test_apply_no_specs_returns_graph_unchanged():
    graph = {"nodes": [], "edges": []}
    out, values = apply_parameters(graph, {})
    assert out is graph
    assert values == {}


def test_apply_overrides_without_specs_raises():
    with pytest.raises(ParameterError, match="declares no parameters"):
        apply_parameters({"nodes": []}, {"x": 1})


def test_apply_substitutes_into_node_config_and_is_pure():
    graph = _graph([{"name": "keep", "type": "integer", "default": 2}], {"n": "{{ keep }}"})
    out, values = apply_parameters(graph, {"keep": 10})
    assert values == {"keep": 10}
    # The typed int reached the node config...
    assert out["nodes"][1]["data"]["config"]["n"] == 10
    # ...and the original graph was not mutated.
    assert graph["nodes"][1]["data"]["config"]["n"] == "{{ keep }}"
