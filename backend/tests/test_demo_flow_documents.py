"""Tests for the demo flow JSON documents and their loader.

The demo flow content lives as validated JSON artifacts under
``app/demo/resources``. These tests validate those documents *as artifacts*
(without running the seeder or a DB): the schema is enforced, every referenced
dataset exists, every hydrated graph is correctly wired, and the loader's
edge-case guards fire. End-to-end execution of the hydrated graphs is covered by
``tests/test_demo_seed.py``.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.demo.datasets import build_demo_frames
from app.demo.loader import (
    DemoFlowDocument,
    DemoResourceError,
    build_demo_flows,
    hydrate_document,
    load_demo_flow_documents,
)
from app.engine.graph import validate_graph
from app.engine.node_metadata import NODE_META_BY_TYPE

# Identity map (dataset_id == file name) so hydrated graphs are inspectable.
_ALL_DATASETS = {name: name for name in build_demo_frames(include_ml=True)}
_ETL_ONLY = set(build_demo_frames(include_ml=False))


def _valid_doc_dict() -> dict:
    """A minimal, valid document used as a base for negative cases."""
    return {
        "name": "Sample",
        "description": "desc",
        "nodes": [
            {"id": "in", "type": "fileInput", "position": {"x": 0, "y": 0}, "dataset": "customers.csv"},
            {
                "id": "out",
                "type": "fileOutput",
                "position": {"x": 250, "y": 0},
                "config": {"format": "csv", "dataset_name": "sample_out"},
            },
        ],
        "edges": [{"source": "in", "target": "out"}],
    }


# ---------------------------------------------------------------------------
# Happy path: the shipped documents
# ---------------------------------------------------------------------------


# The exact presentation order users see — pinned so renaming/renumbering a
# resource file (the whole point of the numeric prefixes) can't silently reorder
# the demo without a failing test.
_EXPECTED_ETL_ORDER = [
    "Clean Customers",
    "Order Revenue by Month",
    "Customer Orders Join",
    "Full Sales Mart",
    "Lead Intake Cleanup",
    "Web Event Engagement",
    "Survey Quality Contracts",
    "Regional Target Variance",
    "Product Catalog Scoring",
]
_EXPECTED_ML_ORDER = [
    "Iris — Quick Classifier",
    "Iris — Train, Validate & Evaluate",
    "House Prices — Regression",
    "Iris — PCA Explore",
    "Iris — Logistic CV Report",
    "Iris — KNN with Encoded Species",
    "House Prices — Feature Selection",
    "House Prices — Customer Segments",
    "House Prices — PCA Model",
]


def test_etl_documents_load_in_exact_order() -> None:
    docs = load_demo_flow_documents(include_ml=False)
    assert [d.name for d in docs] == _EXPECTED_ETL_ORDER


def test_ml_documents_appended_after_etl_in_order() -> None:
    full = load_demo_flow_documents(include_ml=True)
    assert [d.name for d in full] == _EXPECTED_ETL_ORDER + _EXPECTED_ML_ORDER


def test_etl_flows_carry_no_engine_hint() -> None:
    # ETL flows run under either engine; only the ML flows pin pandas.
    for doc in load_demo_flow_documents(include_ml=False):
        assert doc.engine is None, f"{doc.name} unexpectedly pins engine {doc.engine!r}"


def test_hydrated_config_is_isolated_from_the_cache() -> None:
    # Mutating one hydrated graph must not leak into the cached documents or a
    # later build (the documents are lru_cached and shared).
    first = build_demo_flows(_ALL_DATASETS, include_ml=False)[0][2]
    node = next(n for n in first["nodes"] if n["type"] != "fileInput")
    node["data"]["config"]["__poison__"] = True

    second = build_demo_flows(_ALL_DATASETS, include_ml=False)[0][2]
    second_node = next(n for n in second["nodes"] if n["id"] == node["id"])
    assert "__poison__" not in second_node["data"]["config"]


def test_every_document_has_unique_name() -> None:
    names = [d.name for d in load_demo_flow_documents(include_ml=True)]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("include_ml", [False, True])
def test_referenced_datasets_all_exist(include_ml: bool) -> None:
    available = set(_ALL_DATASETS) if include_ml else _ETL_ONLY
    for doc in load_demo_flow_documents(include_ml=include_ml):
        missing = doc.referenced_datasets() - available
        assert not missing, f"{doc.name} references unknown datasets {missing}"


@pytest.mark.parametrize("include_ml", [False, True])
def test_hydrated_graphs_are_valid(include_ml: bool) -> None:
    for name, description, graph in build_demo_flows(_ALL_DATASETS, include_ml=include_ml):
        assert name and description
        validate_graph(graph, require_output=True)


def test_hydration_injects_catalog_labels_and_resolves_datasets() -> None:
    _, _, graph = build_demo_flows(_ALL_DATASETS, include_ml=False)[0]
    for node in graph["nodes"]:
        label = node["data"]["label"]
        assert label and label != node["type"]
        meta = NODE_META_BY_TYPE.get(node["type"])
        if meta is not None:
            assert label == meta.label
        if node["type"] == "fileInput":
            cfg = node["data"]["config"]
            assert cfg == {"dataset_id": _ALL_DATASETS[cfg["dataset_id"]], "dataset_version": 1, "format": "csv"}


def test_engine_hint_preserved_when_present() -> None:
    ml = build_demo_flows(_ALL_DATASETS, include_ml=True)
    ml_graphs = [g for name, _, g in ml if "Iris" in name or "House Prices" in name]
    assert ml_graphs
    assert all(g.get("engine") == "pandas" for g in ml_graphs)


def test_load_is_cached() -> None:
    assert load_demo_flow_documents(include_ml=True) is load_demo_flow_documents(include_ml=True)


# ---------------------------------------------------------------------------
# Edge cases: loader / schema guards
# ---------------------------------------------------------------------------


def test_hydrate_raises_on_unknown_dataset() -> None:
    doc = DemoFlowDocument.model_validate(_valid_doc_dict())
    with pytest.raises(DemoResourceError, match="unknown dataset"):
        hydrate_document(doc, {})  # empty map: 'customers.csv' cannot resolve


def test_unknown_field_is_rejected() -> None:
    bad = _valid_doc_dict()
    bad["surprise"] = True
    with pytest.raises(ValidationError):
        DemoFlowDocument.model_validate(bad)


def test_input_node_without_dataset_is_rejected() -> None:
    bad = _valid_doc_dict()
    del bad["nodes"][0]["dataset"]
    with pytest.raises(ValidationError, match="must reference a dataset"):
        DemoFlowDocument.model_validate(bad)


def test_non_input_node_with_dataset_is_rejected() -> None:
    bad = _valid_doc_dict()
    bad["nodes"][1]["dataset"] = "customers.csv"
    with pytest.raises(ValidationError, match="not an input node"):
        DemoFlowDocument.model_validate(bad)


def test_input_node_with_config_is_rejected() -> None:
    bad = _valid_doc_dict()
    bad["nodes"][0]["config"] = {"format": "csv"}
    with pytest.raises(ValidationError, match="must use `dataset`"):
        DemoFlowDocument.model_validate(bad)


def test_duplicate_node_ids_rejected() -> None:
    bad = _valid_doc_dict()
    bad["nodes"][1]["id"] = "in"
    with pytest.raises(ValidationError, match="duplicate node ids"):
        DemoFlowDocument.model_validate(bad)


def test_edge_to_missing_node_rejected() -> None:
    bad = _valid_doc_dict()
    bad["edges"][0]["target"] = "ghost"
    with pytest.raises(ValidationError, match="not a node"):
        DemoFlowDocument.model_validate(bad)


def test_empty_dataset_reference_rejected() -> None:
    bad = _valid_doc_dict()
    bad["nodes"][0]["dataset"] = "   "
    with pytest.raises(ValidationError, match="empty `dataset`"):
        DemoFlowDocument.model_validate(bad)


def test_unknown_engine_rejected() -> None:
    bad = _valid_doc_dict()
    bad["engine"] = "pandaz"
    with pytest.raises(ValidationError):
        DemoFlowDocument.model_validate(bad)


def test_empty_document_rejected() -> None:
    with pytest.raises(ValidationError, match="no nodes"):
        DemoFlowDocument.model_validate({"name": "x", "description": "y", "nodes": [], "edges": []})


def test_malformed_json_file_raises_demo_resource_error(tmp_path, monkeypatch) -> None:
    resources = tmp_path / "resources"
    (resources / "etl").mkdir(parents=True)
    (resources / "etl" / "00_broken.flow.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr("app.demo.loader._RESOURCES", resources)
    load_demo_flow_documents.cache_clear()
    try:
        with pytest.raises(DemoResourceError, match="not valid JSON"):
            load_demo_flow_documents(include_ml=False)
    finally:
        load_demo_flow_documents.cache_clear()


def test_edge_handles_round_trip_into_ids() -> None:
    doc_dict = _valid_doc_dict()
    doc_dict["nodes"].append(
        {"id": "mid", "type": "fillNulls", "position": {"x": 120, "y": 0}, "config": {"columns": ["age"]}}
    )
    doc_dict["edges"] = [
        {"source": "in", "target": "mid", "sourceHandle": "train", "targetHandle": "left"},
        {"source": "mid", "target": "out"},
    ]
    doc = DemoFlowDocument.model_validate(doc_dict)
    _, _, graph = hydrate_document(doc, _ALL_DATASETS)
    handled = next(e for e in graph["edges"] if e["source"] == "in")
    assert handled["id"] == "e-in-mid-train-left"
    assert handled["sourceHandle"] == "train"
    assert handled["targetHandle"] == "left"
    plain = next(e for e in graph["edges"] if e["source"] == "mid")
    assert plain["id"] == "e-mid-out"
    assert "sourceHandle" not in plain and "targetHandle" not in plain


def test_valid_document_loads_from_json_string() -> None:
    doc = DemoFlowDocument.model_validate(json.loads(json.dumps(_valid_doc_dict())))
    assert doc.referenced_datasets() == {"customers.csv"}
