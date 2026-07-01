import json

import pytest

from app.plugin_api import (
    ConnectorSpec,
    NodeSpec,
    Permission,
    PortSpec,
)


def test_node_spec_serializes_to_json():
    spec = NodeSpec(
        id="filterRows",
        label="Filter Rows",
        category="clean",
        description="Keep rows matching a condition.",
        inputs=(PortSpec(id="in"),),
        outputs=(PortSpec(id="out"),),
        default_config={"column": "", "operator": "==", "value": ""},
    )
    payload = spec.model_dump(mode="json")
    # Round-trips through JSON cleanly (catalog endpoint relies on this).
    restored = NodeSpec.model_validate(json.loads(json.dumps(payload)))
    assert restored == spec
    assert restored.provider == "ciaren.core"
    assert restored.inputs[0].type == "dataframe"


def test_port_spec_is_frozen():
    port = PortSpec(id="in")
    with pytest.raises(Exception):  # pydantic raises on frozen mutation
        port.id = "other"  # type: ignore[misc]


def test_node_spec_defaults():
    spec = NodeSpec(id="x", label="X")
    assert spec.category == "plugins"
    assert spec.requires_ml is False
    assert spec.is_model_sink is False
    assert spec.inputs == ()
    assert spec.default_config == {}


def test_node_spec_invalid_category_defaults_to_plugins():
    spec = NodeSpec(id="x", label="X", category="unknown")
    assert spec.category == "plugins"


def test_connector_spec_permissions_are_enums():
    spec = ConnectorSpec(
        id="s3",
        label="AWS S3",
        kind="storage",
        permissions=(Permission.network, Permission.credentials),
        capabilities=("storage.s3",),
    )
    dumped = spec.model_dump(mode="json")
    assert dumped["permissions"] == ["network", "credentials"]
    assert dumped["capabilities"] == ["storage.s3"]


def test_model_ports_distinguish_kind():
    out = PortSpec(id="model", type="model")
    assert out.type == "model"
    assert PortSpec(id="in").type == "dataframe"
