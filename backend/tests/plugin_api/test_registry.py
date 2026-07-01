import pytest

from app.plugin_api import (
    ConnectorProvider,
    ConnectorSpec,
    DuplicateRegistrationError,
    LicenseProvider,
    LicenseStatus,
    NodeProvider,
    NodeSpec,
    Plugin,
    PluginMetadata,
    ServiceRegistry,
)


class _Node:
    """Stand-in for an engine transformation (registry treats it as opaque)."""

    def __init__(self, type_: str) -> None:
        self.type = type_


class _NodeProvider(NodeProvider):
    def __init__(self, specs, impls=None):
        self._specs = specs
        self._impls = impls or {}

    def nodes(self):
        return self._specs

    def node_implementations(self):
        return self._impls


class _ConnectorProvider(ConnectorProvider):
    def __init__(self, specs):
        self._specs = specs

    def connectors(self):
        return self._specs


def test_register_node_provider_collects_specs_and_impls():
    reg = ServiceRegistry()
    impl = _Node("filterRows")
    reg.register_node_provider(
        _NodeProvider(
            [NodeSpec(id="filterRows", label="Filter", category="clean")],
            {"filterRows": impl},
        )
    )
    assert [s.id for s in reg.node_specs()] == ["filterRows"]
    assert reg.node_implementation("filterRows") is impl
    assert reg.node_implementation("missing") is None


def test_node_specs_returned_sorted():
    reg = ServiceRegistry()
    reg.register_node_provider(
        _NodeProvider(
            [
                NodeSpec(id="zeta", label="Z", category="clean"),
                NodeSpec(id="alpha", label="A", category="clean"),
            ]
        )
    )
    assert [s.id for s in reg.node_specs()] == ["alpha", "zeta"]


def test_duplicate_node_registration_raises():
    reg = ServiceRegistry()
    reg.register_node_provider(_NodeProvider([NodeSpec(id="dup", label="D", category="clean")]))
    with pytest.raises(DuplicateRegistrationError):
        reg.register_node_provider(_NodeProvider([NodeSpec(id="dup", label="D2", category="clean")]))


def test_capabilities_aggregated_from_connectors():
    reg = ServiceRegistry()
    reg.register_connector_provider(
        _ConnectorProvider(
            [
                ConnectorSpec(
                    id="postgresql",
                    label="PostgreSQL",
                    kind="sql",
                    capabilities=("connector.sql",),
                    provider="ciaren.core",
                )
            ]
        )
    )
    assert reg.has_capability("connector.sql")
    assert reg.provider_for_capability("connector.sql") == "ciaren.core"
    assert reg.provided_capabilities() == {"connector.sql"}
    assert reg.has_capability("connector.snowflake") is False


def test_register_plugin_records_metadata_and_runs_register():
    reg = ServiceRegistry()

    class MyPlugin(Plugin):
        def metadata(self):
            return PluginMetadata(id="demo", name="Demo", version="1.2.3")

        def register(self, registry):
            registry.register_node_provider(_NodeProvider([NodeSpec(id="demoNode", label="Demo", category="clean")]))

    meta = reg.register_plugin(MyPlugin())
    assert meta.id == "demo"
    assert [p.id for p in reg.plugins()] == ["demo"]
    assert reg.node_spec("demoNode") is not None


def test_failing_plugin_register_propagates_and_skips_metadata():
    reg = ServiceRegistry()

    class BadPlugin(Plugin):
        def metadata(self):
            return PluginMetadata(id="bad", name="Bad")

        def register(self, registry):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        reg.register_plugin(BadPlugin())
    # Metadata is only recorded on a clean registration.
    assert reg.plugins() == []


def test_license_defaults_to_valid_without_providers():
    reg = ServiceRegistry()
    status = reg.validate_license("anything")
    assert status.valid is True
    assert reg.has_license_provider() is False


def test_license_provider_can_reject():
    reg = ServiceRegistry()

    class DenyProvider(LicenseProvider):
        def validate_license(self, plugin_id):
            return LicenseStatus(plugin_id=plugin_id, valid=False, reason="unpaid")

    reg.register_license_provider(DenyProvider())
    assert reg.has_license_provider() is True
    status = reg.validate_license("premium.plugin")
    assert status.valid is False
    assert status.reason == "unpaid"


def test_license_provider_valid_wins_over_invalid():
    reg = ServiceRegistry()

    class Deny(LicenseProvider):
        def validate_license(self, plugin_id):
            return LicenseStatus(plugin_id=plugin_id, valid=False)

    class Allow(LicenseProvider):
        def validate_license(self, plugin_id):
            return LicenseStatus(plugin_id=plugin_id, valid=True, license_type="pro")

    reg.register_license_provider(Deny())
    reg.register_license_provider(Allow())
    status = reg.validate_license("p")
    assert status.valid is True
    assert status.license_type == "pro"
