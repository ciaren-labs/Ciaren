import json

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
    assert m.api_version == "1.0"
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
        (">=0.1", "0.1.0a1", True),  # a pre-release of the floor version itself still satisfies it
    ],
)
def test_compatibility_check(spec, version, expected):
    m = PluginManifest(id="x", name="X", ciaren=spec)
    assert m.is_compatible_with(version) is expected


def test_compatibility_with_garbage_version_is_false():
    m = PluginManifest(id="x", name="X", ciaren=">=0.1")
    assert m.is_compatible_with("not-a-version") is False


def test_invalid_api_version_rejected():
    with pytest.raises(ValidationError):
        validate_manifest({"id": "x", "name": "X", "api_version": "not-a-version"})


@pytest.mark.parametrize(
    "plugin_api,backend_api,expected",
    [
        ("1.0", "1.1", True),  # older plugin on newer backend (additive minor)
        ("1.1", "1.1", True),  # exact match
        ("1.0", "1.0", True),
        ("1.2", "1.1", False),  # plugin needs a minor the backend lacks
        ("2.0", "1.1", False),  # plugin built for a newer major (breaking)
        ("1.0", "2.0", False),  # backend dropped the plugin's major (breaking)
    ],
)
def test_api_compatibility_check(plugin_api, backend_api, expected):
    m = PluginManifest(id="x", name="X", api_version=plugin_api)
    assert m.is_api_compatible_with(backend_api) is expected


def test_api_compatibility_with_garbage_version_is_false():
    m = PluginManifest(id="x", name="X", api_version="1.0")
    assert m.is_api_compatible_with("not-a-version") is False


@pytest.mark.parametrize(
    "plugin_api,backend_api,expected",
    [
        ("1.1.0", "1.1", True),  # a patch component is ignored — only major/minor decide
        ("1", "1.1", True),  # bare major means minor 0 → compatible with any 1.x backend
        ("1.1", "1.1.9", True),  # backend patch component is likewise ignored
        ("2", "1.9", False),  # bare newer major is still a breaking mismatch
    ],
)
def test_api_compatibility_ignores_patch_and_handles_bare_major(plugin_api, backend_api, expected):
    m = PluginManifest(id="x", name="X", api_version=plugin_api)
    assert m.is_api_compatible_with(backend_api) is expected


def test_empty_api_version_rejected():
    with pytest.raises(ValidationError):
        validate_manifest({"id": "x", "name": "X", "api_version": ""})


def test_api_version_round_trips_through_json():
    m = validate_manifest({"id": "x", "name": "X", "api_version": "1.1"})
    reparsed = validate_manifest(json.loads(m.model_dump_json(by_alias=True)))
    assert reparsed.api_version == "1.1"
    assert reparsed == m
