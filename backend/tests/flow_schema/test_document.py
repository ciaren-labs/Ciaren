import pytest

from app.flow_schema import (
    CURRENT_SCHEMA_VERSION,
    LEGACY_FORMAT,
    FlowSchemaError,
    from_legacy_document,
    graph_structure_issues,
    missing_node_types,
    to_legacy_document,
    validate,
    validate_document,
)
from app.flow_schema.document import FlowGraph, FlowSchemaDocument


def _doc(**overrides):
    base = {
        "project": {"name": "My Flow"},
        "graph": {
            "nodes": [
                {"id": "a", "type": "csvInput"},
                {"id": "b", "type": "filterRows"},
            ],
            "edges": [{"id": "e1", "source": "a", "target": "b"}],
        },
    }
    base.update(overrides)
    return base


def test_validate_minimal_document_defaults_version():
    doc = validate(_doc())
    assert doc.schema_version == CURRENT_SCHEMA_VERSION
    assert doc.project.name == "My Flow"
    assert doc.requirements.plugins == []


def test_validate_accepts_camelcase_aliases():
    doc = validate_document({**_doc(), "schemaVersion": "1.0.0", "flowframeVersion": "0.1.0"})
    assert doc.schema_version == "1.0.0"
    assert doc.flowframe_version == "0.1.0"


def test_to_json_dict_uses_aliases():
    payload = validate(_doc()).to_json_dict()
    assert "schemaVersion" in payload
    assert "schema_version" not in payload


def test_missing_project_name_is_invalid():
    with pytest.raises(FlowSchemaError):
        validate({"project": {}, "graph": {"nodes": [], "edges": []}})


def test_graph_structure_detects_problems():
    graph = FlowGraph(
        nodes=[
            {"id": "a", "type": "csvInput"},
            {"id": "a", "type": "filterRows"},  # duplicate id
            {"type": "noId"},  # missing id
            {"id": "c"},  # missing type
        ],
        edges=[
            {"id": "e1", "source": "a", "target": "missing"},  # unknown target
            {"id": "e2", "target": "a"},  # missing source
        ],
    )
    issues = graph_structure_issues(graph)
    joined = " | ".join(issues)
    assert "duplicate node id 'a'" in joined
    assert "missing an 'id'" in joined
    assert "missing a 'type'" in joined
    assert "references an unknown node" in joined
    assert "missing 'source'" in joined


def test_validate_rejects_structurally_broken_graph():
    with pytest.raises(FlowSchemaError, match="graph structure"):
        validate(
            _doc(graph={"nodes": [{"id": "a", "type": "x"}], "edges": [{"id": "e", "source": "a", "target": "z"}]})
        )


def test_missing_node_types():
    doc = validate(_doc())
    available = {"csvInput"}
    assert missing_node_types(doc, available) == ["filterRows"]
    assert missing_node_types(doc, {"csvInput", "filterRows"}) == []


def test_legacy_round_trip_preserves_graph_extras():
    legacy = {
        "format": LEGACY_FORMAT,
        "name": "Pipeline",
        "description": "desc",
        "graph_json": {
            "nodes": [{"id": "a", "type": "csvInput"}],
            "edges": [],
            "engine": "polars",
            "parameters": [{"name": "cutoff", "type": "number", "default": 5}],
        },
    }
    doc = from_legacy_document(legacy)
    assert doc.project.name == "Pipeline"
    assert doc.project.description == "desc"
    # Flow-level extras survive on the graph (extra="allow").
    assert doc.graph.model_dump()["engine"] == "polars"

    back = to_legacy_document(doc)
    assert back["format"] == LEGACY_FORMAT
    assert back["name"] == "Pipeline"
    assert back["graph_json"]["engine"] == "polars"
    assert back["graph_json"]["parameters"][0]["name"] == "cutoff"


def test_legacy_format_matches_backend_constant():
    # Guard against the schema package and the API export drifting apart.
    from app.schemas.flow import FLOW_DOCUMENT_FORMAT

    assert LEGACY_FORMAT == FLOW_DOCUMENT_FORMAT


def test_document_construct_with_field_names():
    doc = FlowSchemaDocument(project={"name": "x"}, graph={"nodes": [], "edges": []})  # type: ignore[arg-type]
    assert doc.schema_version == CURRENT_SCHEMA_VERSION
