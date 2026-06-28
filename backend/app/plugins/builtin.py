"""Built-in providers: the open-source core's contributions to the registry.

These bridge the existing static registries (``app.engine.registry``,
``app.engine.node_kinds``, ``app.connectors.providers``, the engine backends, and
the codegen exporters) into the plugin ``ServiceRegistry`` without changing how
any of them execute. The engine keeps running through its own registry; these
providers only *describe* the built-ins (and hand the same transformation
singletons to the registry as opaque implementations).
"""

from __future__ import annotations

from typing import Any, Literal

from app.connectors.providers import PROVIDERS, Provider, driver_available
from app.engine import node_kinds
from app.engine.backends.base import available_engines
from app.engine.node_metadata import NODE_META_BY_TYPE
from app.engine.registry import (
    get_transformation,
    is_ml_node,
    list_transformation_types,
)
from app.plugin_api import (
    ConnectorProvider,
    ConnectorSpec,
    ExecutionProvider,
    ExecutionSpec,
    ExporterProvider,
    ExporterSpec,
    NodeProvider,
    NodeSpec,
    Permission,
    PortSpec,
    StorageProvider,
    StorageSpec,
    ValidatorProvider,
    ValidatorSpec,
)

CORE_PROVIDER = "flowframe.core"
ML_PROVIDER = "flowframe.ml"


def _port(handle: str, model_handles: frozenset[str], *, required: bool = True, multi: bool = False) -> PortSpec:
    kind: Literal["dataframe", "model"] = "model" if handle in model_handles else "dataframe"
    return PortSpec(id=handle, type=kind, required=required, multi=multi)


def _input_node_spec(node_type: str) -> NodeSpec:
    meta = NODE_META_BY_TYPE[node_type]
    return NodeSpec(
        id=node_type,
        label=meta.label,
        category=meta.category,
        description=meta.description,
        provider=CORE_PROVIDER,
        inputs=(),
        outputs=(PortSpec(id="out"),),
        default_config=dict(meta.default_config),
    )


def _output_node_spec(node_type: str) -> NodeSpec:
    meta = NODE_META_BY_TYPE[node_type]
    return NodeSpec(
        id=node_type,
        label=meta.label,
        category=meta.category,
        description=meta.description,
        provider=CORE_PROVIDER,
        inputs=(PortSpec(id="in"),),
        outputs=(),
        default_config=dict(meta.default_config),
    )


def _transform_node_spec(node_type: str) -> NodeSpec:
    meta = NODE_META_BY_TYPE[node_type]
    transform = get_transformation(node_type)
    model_in = node_kinds.MODEL_INPUT_HANDLES.get(node_type, frozenset())
    model_out = node_kinds.MODEL_OUTPUT_HANDLES.get(node_type, frozenset())

    inputs = [
        _port(h, model_in, required=True, multi=transform.multi_input and h == "in") for h in transform.input_handles
    ]
    inputs += [_port(h, model_in, required=False) for h in transform.optional_input_handles]
    outputs = [_port(h, model_out) for h in node_kinds.output_handles(node_type)]

    ml = is_ml_node(node_type)
    return NodeSpec(
        id=node_type,
        label=meta.label,
        category=meta.category,
        description=meta.description,
        provider=ML_PROVIDER if ml else CORE_PROVIDER,
        inputs=tuple(inputs),
        outputs=tuple(outputs),
        default_config=dict(meta.default_config),
        requires_ml=ml,
        is_model_sink=node_type in node_kinds.ML_OUTPUT_NODES,
    )


def build_node_spec(node_type: str) -> NodeSpec:
    """Build a :class:`NodeSpec` for any built-in node type (input, output, or
    transform), combining presentational metadata with handle topology derived
    from the engine."""
    if node_type in node_kinds.INPUT_TYPES:
        return _input_node_spec(node_type)
    if node_type in node_kinds.OUTPUT_TYPES:
        return _output_node_spec(node_type)
    return _transform_node_spec(node_type)


def builtin_node_types() -> list[str]:
    """Every node type the core contributes: I/O kinds plus registered transforms
    (transforms include ML nodes only when the ``[ml]`` extra is installed)."""
    return [*node_kinds.INPUT_TYPES, *node_kinds.OUTPUT_TYPES, *list_transformation_types()]


def _core_transform_types() -> list[str]:
    """Registered transforms that are *not* ML nodes."""
    return [t for t in list_transformation_types() if not is_ml_node(t)]


def _ml_transform_types() -> list[str]:
    """Registered ML transforms (non-empty only when the ``[ml]`` extra is present)."""
    return [t for t in list_transformation_types() if is_ml_node(t)]


class BuiltinNodeProvider(NodeProvider):
    """The open-source ETL core: I/O nodes plus every non-ML transform. ML nodes
    are contributed separately by :class:`MlNodeProvider`, so the core node set is
    independent of whether the ML extension is installed."""

    def nodes(self) -> list[NodeSpec]:
        types = [*node_kinds.INPUT_TYPES, *node_kinds.OUTPUT_TYPES, *_core_transform_types()]
        return [build_node_spec(t) for t in types]

    def node_implementations(self) -> dict[str, Any]:
        # Only transforms have an engine implementation; I/O nodes are resolved by
        # the executor/service layer, not by a BaseTransformation.
        return {t: get_transformation(t) for t in _core_transform_types()}


class MlNodeProvider(NodeProvider):
    """The optional ML node set, isolated as its own provider. Registered only when
    the ``[ml]`` extra is importable (see ``runtime.build_registry``), so the
    open-source core never depends on it — exactly how a third-party plugin would
    contribute nodes. Mirrors the "ML basic stays community, but optional" split in
    the architecture plan."""

    def nodes(self) -> list[NodeSpec]:
        return [build_node_spec(t) for t in _ml_transform_types()]

    def node_implementations(self) -> dict[str, Any]:
        return {t: get_transformation(t) for t in _ml_transform_types()}


def _connector_permissions(p: Provider) -> tuple[Permission, ...]:
    perms: list[Permission] = []
    if p.needs_auth:
        perms.append(Permission.credentials)
    if p.kind in ("sql", "mongo"):
        perms.append(Permission.database_access)
        perms.append(Permission.network)
    if p.kind == "storage" and p.name != "local":
        perms.append(Permission.cloud_access)
        perms.append(Permission.network)
    if p.kind == "storage" and p.name == "local":
        perms.append(Permission.filesystem_read)
        perms.append(Permission.filesystem_write)
    return tuple(dict.fromkeys(perms))  # de-dup, preserve order


def _connector_metadata(p: Provider) -> dict[str, Any]:
    return {
        "default_port": p.default_port,
        "needs_host": p.needs_host,
        "needs_auth": p.needs_auth,
        "supports_query": p.supports_query,
        "needs_bucket": p.needs_bucket,
        "needs_region": p.needs_region,
        "needs_endpoint": p.needs_endpoint,
    }


class BuiltinConnectorProvider(ConnectorProvider):
    def connectors(self) -> list[ConnectorSpec]:
        return [
            ConnectorSpec(
                id=p.name,
                label=p.label,
                kind=p.kind,
                available=driver_available(p),
                driver_module=p.driver_module,
                extra=p.extra,
                capabilities=(f"connector.{p.kind}", f"connector.{p.name}"),
                permissions=_connector_permissions(p),
                provider=CORE_PROVIDER,
                metadata=_connector_metadata(p),
            )
            for p in PROVIDERS.values()
        ]


class BuiltinStorageProvider(StorageProvider):
    def storage_backends(self) -> list[StorageSpec]:
        return [
            StorageSpec(
                id=p.name,
                label=p.label,
                available=driver_available(p),
                capabilities=(f"storage.{p.name}",),
                permissions=_connector_permissions(p),
                provider=CORE_PROVIDER,
            )
            for p in PROVIDERS.values()
            if p.kind == "storage"
        ]


class BuiltinExecutionProvider(ExecutionProvider):
    def execution_backends(self) -> list[ExecutionSpec]:
        return [
            ExecutionSpec(
                id=name,
                label=name.capitalize(),
                available=True,
                capabilities=(f"engine.{name}",),
                provider=CORE_PROVIDER,
            )
            for name in available_engines()
        ]


class BuiltinExporterProvider(ExporterProvider):
    def exporters(self) -> list[ExporterSpec]:
        return [
            ExporterSpec(
                id="python",
                label="Python (pandas)",
                format="python",
                file_extension=".py",
                capabilities=("exporter.python",),
                provider=CORE_PROVIDER,
            ),
            ExporterSpec(
                id="polars",
                label="Python (polars)",
                format="python",
                file_extension=".py",
                capabilities=("exporter.polars",),
                provider=CORE_PROVIDER,
            ),
            ExporterSpec(
                id="polars-lazy",
                label="Python (polars, lazy)",
                format="python",
                file_extension=".py",
                capabilities=("exporter.polars_lazy",),
                provider=CORE_PROVIDER,
            ),
        ]


class BuiltinValidatorProvider(ValidatorProvider):
    def validators(self) -> list[ValidatorSpec]:
        # The quality assertion nodes double as data-contract validators.
        quality_types = [
            t
            for t in list_transformation_types()
            if NODE_META_BY_TYPE.get(t) and NODE_META_BY_TYPE[t].category == "quality"
        ]
        return [
            ValidatorSpec(
                id=t,
                label=NODE_META_BY_TYPE[t].label,
                description=NODE_META_BY_TYPE[t].description,
                capabilities=("validator.quality",),
                provider=CORE_PROVIDER,
            )
            for t in quality_types
        ]
