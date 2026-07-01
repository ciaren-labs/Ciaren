import pytest
from pydantic import ValidationError

from app.plugin_api import Permission, PluginManifest, validate_manifest

VALID = {
    "id": "ciaren.databricks",
    "name": "Databricks Connector",
    "version": "1.0.0",
    "publisher": "ciaren",
    "license": "commercial",
    "ciaren": ">=0.1,<1.0",
    "entrypoint": "ciaren_databricks.plugin:DatabricksPlugin",
    "permissions": ["network", "credentials"],
    "capabilities": ["connector.databricks"],
    "ui": {"nodes": ["databricks.read_table"], "nodeCategories": {"databricks.read_table": "input"}},
    "license_required": True,
    "trust": "verified",
}


def test_valid_manifest_parses():
    m = validate_manifest(VALID)
    assert m.id == "ciaren.databricks"
    assert m.license == "commercial"
    assert Permission.network in m.permissions
    assert m.ui.nodes == ["databricks.read_table"]
    assert m.ui.node_categories == {"databricks.read_table": "input"}
    assert m.license_required is True


def test_manifest_defaults():
    m = validate_manifest({"id": "x", "name": "X"})
    assert m.version == "0.0.0"
    assert m.publisher == "community"
    assert m.license == "community"
    assert m.ciaren == ">=0.1"
    assert m.permissions == []
    assert m.trust == "community"


def test_manifest_ui_node_category_defaults_invalid_categories_to_plugins():
    m = validate_manifest(
        {
            "id": "x",
            "name": "X",
            "ui": {"nodes": ["x.node"], "nodeCategories": {"x.node": "not-real"}},
        }
    )
    assert m.ui.node_categories == {"x.node": "plugins"}


def test_missing_required_fields_rejected():
    with pytest.raises(ValidationError):
        validate_manifest({"name": "no id"})


def test_invalid_version_rejected():
    with pytest.raises(ValidationError):
        validate_manifest({"id": "x", "name": "X", "version": "not-a-version"})


def test_invalid_compat_spec_rejected():
    with pytest.raises(ValidationError):
        validate_manifest({"id": "x", "name": "X", "ciaren": ">>>bad"})


def test_invalid_entrypoint_rejected():
    with pytest.raises(ValidationError):
        validate_manifest({"id": "x", "name": "X", "entrypoint": "no-colon-here"})


@pytest.mark.parametrize(
    "spec,version,expected",
    [
        (">=0.1", "0.1.0", True),
        (">=0.1,<1.0", "0.5.0", True),
        (">=0.1,<1.0", "1.0.0", False),
        (">=2.0", "0.1.0", False),
        (">=0.1", "0.2.0a1", True),  # prereleases allowed
    ],
)
def test_compatibility_check(spec, version, expected):
    m = PluginManifest(id="x", name="X", ciaren=spec)
    assert m.is_compatible_with(version) is expected


def test_compatibility_with_garbage_version_is_false():
    m = PluginManifest(id="x", name="X", ciaren=">=0.1")
    assert m.is_compatible_with("not-a-version") is False
