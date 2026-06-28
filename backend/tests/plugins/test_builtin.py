"""The built-in providers must describe every core node/connector/engine the app
actually has, without changing how the engine executes them."""

from __future__ import annotations

from app.engine import node_kinds
from app.engine.node_metadata import NODE_META_BY_TYPE
from app.engine.registry import get_transformation, list_transformation_types, ml_node_types
from app.plugins.builtin import builtin_node_types
from app.plugins.runtime import build_registry


def test_every_builtin_node_has_metadata():
    missing = [t for t in builtin_node_types() if t not in NODE_META_BY_TYPE]
    assert missing == [], f"node types without metadata: {missing}"


def test_metadata_has_no_stragglers_beyond_ml():
    # Any metadata entry not currently built must be an ML node (ML metadata is
    # static but the transform only registers when the [ml] extra is installed).
    built = set(builtin_node_types())
    extra = set(NODE_META_BY_TYPE) - built
    assert all(NODE_META_BY_TYPE[t].category == "ml" for t in extra), f"unexpected stragglers: {extra}"


def test_registry_exposes_a_spec_for_every_node():
    reg = build_registry()
    spec_ids = {s.id for s in reg.node_specs()}
    assert spec_ids == set(builtin_node_types())


def test_node_implementations_match_engine_registry():
    reg = build_registry()
    for node_type in list_transformation_types():
        assert reg.node_implementation(node_type) is get_transformation(node_type)
    # I/O nodes have no transformation implementation.
    assert reg.node_implementation("csvInput") is None
    assert reg.node_implementation("csvOutput") is None


def test_input_node_handles():
    reg = build_registry()
    spec = reg.node_spec("csvInput")
    assert spec is not None
    assert spec.inputs == ()
    assert [p.id for p in spec.outputs] == ["out"]
    assert spec.category == "input"
    assert spec.default_config == {"dataset_id": "", "dataset_version": None}


def test_output_node_handles():
    reg = build_registry()
    spec = reg.node_spec("csvOutput")
    assert spec is not None
    assert [p.id for p in spec.inputs] == ["in"]
    assert spec.outputs == ()


def test_join_has_left_right_inputs():
    spec = build_registry().node_spec("join")
    assert spec is not None
    assert [p.id for p in spec.inputs] == ["left", "right"]
    assert [p.id for p in spec.outputs] == ["out"]


def test_concat_input_is_variadic():
    spec = build_registry().node_spec("concatRows")
    assert spec is not None
    assert len(spec.inputs) == 1
    assert spec.inputs[0].id == "in"
    assert spec.inputs[0].multi is True


def test_ml_train_emits_model_output_and_is_sink():
    if "mlTrain" not in list_transformation_types():
        return  # ML extra not installed
    spec = build_registry().node_spec("mlTrain")
    assert spec is not None
    model_outputs = [p for p in spec.outputs if p.type == "model"]
    assert [p.id for p in model_outputs] == ["model"]
    assert spec.is_model_sink is True
    assert spec.requires_ml is True
    assert spec.provider == "flowframe.ml"


def test_ml_predict_has_optional_model_input():
    if "mlPredict" not in list_transformation_types():
        return
    spec = build_registry().node_spec("mlPredict")
    assert spec is not None
    model_inputs = {p.id: p for p in spec.inputs if p.type == "model"}
    assert "model" in model_inputs
    assert model_inputs["model"].required is False


def test_core_nodes_not_flagged_ml():
    spec = build_registry().node_spec("filterRows")
    assert spec is not None
    assert spec.requires_ml is False
    assert spec.provider == "flowframe.core"


def test_connector_specs_and_capabilities():
    reg = build_registry()
    ids = {c.id for c in reg.connector_specs()}
    assert {"postgresql", "sqlite", "mongodb", "s3"} <= ids
    assert reg.has_capability("connector.sql")
    assert reg.has_capability("connector.s3")
    pg = next(c for c in reg.connector_specs() if c.id == "postgresql")
    assert pg.kind == "sql"
    assert pg.metadata["default_port"] == 5432


def test_storage_specs():
    reg = build_registry()
    ids = {s.id for s in reg.storage_specs()}
    assert {"local", "s3", "azure_blob", "gcs"} <= ids
    assert reg.has_capability("storage.s3")


def test_execution_specs_include_engines():
    reg = build_registry()
    ids = {e.id for e in reg.execution_specs()}
    assert "pandas" in ids
    assert "polars" in ids  # polars is installed in dev/CI
    assert reg.has_capability("engine.polars")


def test_exporter_specs():
    reg = build_registry()
    ids = {e.id for e in reg.exporter_specs()}
    assert ids == {"python", "polars", "polars-lazy"}
    assert reg.has_capability("exporter.python")


def test_validator_specs_cover_quality_nodes():
    reg = build_registry()
    ids = {v.id for v in reg.validator_specs()}
    assert {"assertNotNull", "assertUnique", "assertRowCount"} <= ids
    assert reg.has_capability("validator.quality")


def test_ml_provider_only_tags_registered_ml_nodes():
    reg = build_registry()
    ml = ml_node_types()
    for spec in reg.node_specs():
        if spec.id in ml:
            assert spec.requires_ml is True
        elif spec.id in node_kinds.INPUT_TYPES or spec.id in node_kinds.OUTPUT_TYPES:
            assert spec.requires_ml is False
