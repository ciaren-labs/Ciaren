"""Contract additions in plugin API 1.1: config-schema fields, model type specs,
model/connector provider registration, and the NodeContext execution path."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest
from pydantic import ValidationError

from app.plugin_api import (
    EMPTY_NODE_CONTEXT,
    ConfigFieldSpec,
    ConnectorProvider,
    ConnectorRuntime,
    ConnectorSpec,
    ConnectorTestResult,
    DuplicateRegistrationError,
    ModelProvider,
    ModelTypeSpec,
    NodeContext,
    NodeRuntime,
    NodeSpec,
    Permission,
    ServiceRegistry,
    validate_config_schema,
)

# -- config schema -------------------------------------------------------------


def test_config_field_spec_defaults():
    field = ConfigFieldSpec(key="base_url")
    assert field.type == "string"
    assert field.required is False
    assert field.options == ()


def test_config_field_options_only_for_select():
    ConfigFieldSpec(key="auth", type="select", options=("none", "bearer"))
    with pytest.raises(ValidationError, match="options"):
        ConfigFieldSpec(key="auth", type="string", options=("a",))


def test_validate_config_schema_accepts_empty_and_fields():
    assert validate_config_schema({}) == {}
    schema = {"fields": [{"key": "url", "required": True}, {"key": "n", "type": "integer", "min": 1}]}
    assert validate_config_schema(schema) == schema


def test_validate_config_schema_rejects_bad_shapes():
    with pytest.raises(ValueError, match="fields"):
        validate_config_schema({"properties": {}})
    with pytest.raises(ValueError, match="duplicate"):
        validate_config_schema({"fields": [{"key": "a"}, {"key": "a"}]})
    with pytest.raises(ValidationError):
        validate_config_schema({"fields": [{"key": "a", "type": "wat"}]})


def test_node_and_connector_specs_validate_config_schema():
    schema = {"fields": [{"key": "column", "type": "column"}]}
    node = NodeSpec(id="x", label="X", config_schema=schema)
    assert node.config_schema == schema
    with pytest.raises(ValidationError):
        NodeSpec(id="x", label="X", config_schema={"fields": "nope"})

    conn = ConnectorSpec(id="c", label="C", kind="api", config_schema=schema)
    assert conn.config_schema == schema
    with pytest.raises(ValidationError):
        ConnectorSpec(id="c", label="C", kind="api", config_schema={"oops": 1})


# -- model type specs ------------------------------------------------------------


def test_model_type_spec_valid_and_serializable():
    spec = ModelTypeSpec(
        id="mlp_classifier",
        label="MLP Classifier",
        task="classification",
        requires=("sklearn",),
        import_lines=("from sklearn.neural_network import MLPClassifier",),
        default_hyperparameters={"max_iter": 200},
        hyperparameter_schema={"fields": [{"key": "max_iter", "type": "integer", "min": 1}]},
    )
    dumped = spec.model_dump(mode="json")
    assert ModelTypeSpec.model_validate(dumped) == spec


def test_model_type_spec_rejects_unknown_task():
    with pytest.raises(ValidationError, match="task"):
        ModelTypeSpec(id="m", label="M", task="astrology")


# -- registry: model + connector implementation stores ---------------------------


class _Estimatorish:
    def fit(self, x, y=None):  # pragma: no cover - never called here
        return self


def _builder(params: dict[str, Any], seed: int | None) -> Any:
    return _Estimatorish()


class _Models(ModelProvider):
    def model_types(self) -> list[ModelTypeSpec]:
        return [ModelTypeSpec(id="fancy_forest", label="Fancy Forest", task="classification")]

    def model_builders(self) -> dict[str, Any]:
        return {"fancy_forest": _builder}


class _Runtime(ConnectorRuntime):
    def test(self, config: dict[str, Any]) -> ConnectorTestResult:
        return ConnectorTestResult(ok=True, message="hi")

    def read(self, config: dict[str, Any], options: dict[str, Any]) -> Any:
        return pd.DataFrame({"a": [1]})


class _Connectors(ConnectorProvider):
    def connectors(self) -> list[ConnectorSpec]:
        return [ConnectorSpec(id="rest-api", label="REST API", kind="api")]

    def connector_implementations(self) -> dict[str, Any]:
        return {"rest-api": _Runtime()}


def test_registry_stores_model_types_and_builders():
    registry = ServiceRegistry()
    registry.register_model_provider(_Models())
    assert [s.id for s in registry.model_type_specs()] == ["fancy_forest"]
    assert registry.model_type_spec("fancy_forest") is not None
    assert registry.model_builder("fancy_forest") is _builder
    assert registry.has_capability("model.fancy_forest")
    with pytest.raises(DuplicateRegistrationError):
        registry.register_model_provider(_Models())


def test_registry_stores_connector_implementations():
    registry = ServiceRegistry()
    registry.register_connector_provider(_Connectors())
    impl = registry.connector_implementation("rest-api")
    assert isinstance(impl, ConnectorRuntime)
    assert registry.connector_spec("rest-api") is not None
    assert registry.connector_implementation("unknown") is None


def test_failed_plugin_rolls_back_model_and_connector_stores():
    from app.plugin_api import Plugin, PluginMetadata

    class _Bad(Plugin):
        def metadata(self) -> PluginMetadata:
            return PluginMetadata(id="bad", name="Bad")

        def register(self, registry: ServiceRegistry) -> None:
            registry.register_model_provider(_Models())
            registry.register_connector_provider(_Connectors())
            raise RuntimeError("boom")

    registry = ServiceRegistry()
    with pytest.raises(RuntimeError):
        registry.register_plugin(_Bad())
    assert registry.model_type_specs() == []
    assert registry.model_builder("fancy_forest") is None
    assert registry.connector_specs() == []
    assert registry.connector_implementation("rest-api") is None


# -- connector runtime defaults ---------------------------------------------------


def test_connector_runtime_optional_methods_default_to_not_implemented():
    runtime = _Runtime()
    with pytest.raises(NotImplementedError):
        runtime.list_tables({})
    with pytest.raises(NotImplementedError):
        runtime.list_objects({})
    with pytest.raises(NotImplementedError):
        runtime.write(pd.DataFrame(), {}, {})
    assert runtime.test({}).ok


# -- node context -----------------------------------------------------------------


def test_execute_with_context_defaults_to_execute():
    class _Legacy(NodeRuntime):
        def execute(self, inputs, config):
            return {"out": inputs["in"]}

    frame = pd.DataFrame({"a": [1]})
    result = _Legacy().execute_with_context({"in": frame}, {}, EMPTY_NODE_CONTEXT)
    assert result["out"] is frame


def test_context_only_runtime_needs_no_execute():
    class _Contextual(NodeRuntime):
        def execute_with_context(self, inputs, config, context: NodeContext):
            assert context.plugin_id == "p"
            return {"out": inputs["in"]}

    frame = pd.DataFrame({"a": [1]})
    ctx = NodeContext(plugin_id="p", permissions=frozenset({Permission.network}))
    assert _Contextual().execute_with_context({"in": frame}, {}, ctx)["out"] is frame
    # The base execute is a clear error, not a silent no-op.
    with pytest.raises(NotImplementedError):
        _Contextual().execute({"in": frame}, {})


def test_empty_context_has_no_grants_or_services():
    assert EMPTY_NODE_CONTEXT.permissions == frozenset()
    assert EMPTY_NODE_CONTEXT.models is None
