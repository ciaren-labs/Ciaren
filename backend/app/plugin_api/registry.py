# SPDX-License-Identifier: Apache-2.0
"""The capability/service registry plugins register into.

This replaces scattered global registries and ``import``-time wiring with one
object that accepts provider registration and answers catalog/capability
queries. The open-source core registers its built-ins here; the plugin loader
registers discovered plugins here. Nothing in this module knows about specific
connectors, engines, or premium features — only interfaces and specs.
"""

from __future__ import annotations

from typing import Any

from app.plugin_api.events import EventBus
from app.plugin_api.providers import (
    AIProvider,
    AuthProvider,
    ConnectorProvider,
    ExecutionProvider,
    ExporterProvider,
    LicenseProvider,
    NodeProvider,
    Plugin,
    StorageProvider,
    ValidatorProvider,
)
from app.plugin_api.specs import (
    AICapabilitySpec,
    AuthMethodSpec,
    ConnectorSpec,
    ExecutionSpec,
    ExporterSpec,
    LicenseStatus,
    NodeSpec,
    PluginMetadata,
    StorageSpec,
    ValidatorSpec,
)


class DuplicateRegistrationError(ValueError):
    """Raised when two providers contribute the same id (e.g. a plugin tries to
    shadow a core node). The loader catches this and records it as a plugin error
    rather than letting one bad plugin corrupt the catalog."""


class ServiceRegistry:
    """Aggregates everything providers contribute and answers catalog queries."""

    def __init__(self) -> None:
        self._node_specs: dict[str, NodeSpec] = {}
        self._node_impls: dict[str, Any] = {}
        self._connectors: dict[str, ConnectorSpec] = {}
        self._storage: dict[str, StorageSpec] = {}
        self._execution: dict[str, ExecutionSpec] = {}
        self._exporters: dict[str, ExporterSpec] = {}
        self._validators: dict[str, ValidatorSpec] = {}
        self._ai: dict[str, AICapabilitySpec] = {}
        self._auth: dict[str, AuthMethodSpec] = {}
        self._license_providers: list[LicenseProvider] = []
        #: capability string -> id of the provider/spec that first declared it.
        self._capability_source: dict[str, str] = {}
        self._plugins: list[PluginMetadata] = []
        #: Hooks plugins subscribe to in ``register()`` and the core emits.
        self.events = EventBus()

    # -- registration ---------------------------------------------------------

    def register_plugin(self, plugin: Plugin) -> PluginMetadata:
        """Register a whole plugin atomically: record its metadata and run
        :meth:`Plugin.register`. If registration raises (e.g. a duplicate-id
        collision with a core node), every partial contribution from this plugin
        is rolled back and the exception propagates, so one bad plugin can never
        leave the catalog half-populated. Metadata is only recorded on success."""
        meta = plugin.metadata()
        snapshot = self._snapshot()
        try:
            plugin.register(self)
        except Exception:
            self._restore(snapshot)
            raise
        self._plugins.append(meta)
        return meta

    def register_node_provider(self, provider: NodeProvider) -> None:
        impls = provider.node_implementations()
        for spec in provider.nodes():
            self._put(self._node_specs, spec.id, spec, "node")
            if spec.id in impls:
                self._node_impls[spec.id] = impls[spec.id]

    def register_connector_provider(self, provider: ConnectorProvider) -> None:
        for spec in provider.connectors():
            self._put(self._connectors, spec.id, spec, "connector")
            self._record_capabilities(spec.capabilities, spec.provider)

    def register_storage_provider(self, provider: StorageProvider) -> None:
        for spec in provider.storage_backends():
            self._put(self._storage, spec.id, spec, "storage")
            self._record_capabilities(spec.capabilities, spec.provider)

    def register_execution_provider(self, provider: ExecutionProvider) -> None:
        for spec in provider.execution_backends():
            self._put(self._execution, spec.id, spec, "execution")
            self._record_capabilities(spec.capabilities, spec.provider)

    def register_exporter_provider(self, provider: ExporterProvider) -> None:
        for spec in provider.exporters():
            self._put(self._exporters, spec.id, spec, "exporter")
            self._record_capabilities(spec.capabilities, spec.provider)

    def register_validator_provider(self, provider: ValidatorProvider) -> None:
        for spec in provider.validators():
            self._put(self._validators, spec.id, spec, "validator")
            self._record_capabilities(spec.capabilities, spec.provider)

    def register_ai_provider(self, provider: AIProvider) -> None:
        for spec in provider.ai_capabilities():
            self._put(self._ai, spec.id, spec, "ai")
            self._record_capabilities(spec.capabilities, spec.provider)

    def register_auth_provider(self, provider: AuthProvider) -> None:
        for spec in provider.auth_methods():
            self._put(self._auth, spec.id, spec, "auth")

    def register_license_provider(self, provider: LicenseProvider) -> None:
        self._license_providers.append(provider)

    def has_license_provider(self) -> bool:
        """Whether at least one license provider can validate premium plugins."""
        return bool(self._license_providers)

    # -- catalog queries ------------------------------------------------------

    def node_specs(self) -> list[NodeSpec]:
        return [self._node_specs[k] for k in sorted(self._node_specs)]

    def node_spec(self, node_id: str) -> NodeSpec | None:
        return self._node_specs.get(node_id)

    def node_implementation(self, node_id: str) -> Any | None:
        return self._node_impls.get(node_id)

    def connector_specs(self) -> list[ConnectorSpec]:
        return [self._connectors[k] for k in sorted(self._connectors)]

    def storage_specs(self) -> list[StorageSpec]:
        return [self._storage[k] for k in sorted(self._storage)]

    def execution_specs(self) -> list[ExecutionSpec]:
        return [self._execution[k] for k in sorted(self._execution)]

    def exporter_specs(self) -> list[ExporterSpec]:
        return [self._exporters[k] for k in sorted(self._exporters)]

    def validator_specs(self) -> list[ValidatorSpec]:
        return [self._validators[k] for k in sorted(self._validators)]

    def ai_capabilities(self) -> list[AICapabilitySpec]:
        return [self._ai[k] for k in sorted(self._ai)]

    def auth_methods(self) -> list[AuthMethodSpec]:
        return [self._auth[k] for k in sorted(self._auth)]

    def plugins(self) -> list[PluginMetadata]:
        return list(self._plugins)

    # -- capabilities ---------------------------------------------------------

    def provided_capabilities(self) -> set[str]:
        return set(self._capability_source)

    def has_capability(self, capability: str) -> bool:
        return capability in self._capability_source

    def provider_for_capability(self, capability: str) -> str | None:
        return self._capability_source.get(capability)

    # -- licensing ------------------------------------------------------------

    def validate_license(self, plugin_id: str) -> LicenseStatus:
        """Ask each license provider in turn; the first valid result wins. With no
        license provider registered everything is treated as licensed (the
        open-source default for plugins that do not require a license)."""
        last: LicenseStatus | None = None
        for provider in self._license_providers:
            status = provider.validate_license(plugin_id)
            if status.valid:
                return status
            last = status
        if last is not None:
            return last
        return LicenseStatus(plugin_id=plugin_id, valid=True, reason="no license provider")

    # -- internals ------------------------------------------------------------

    def _put(self, store: dict[str, Any], key: str, value: Any, kind: str) -> None:
        if key in store:
            raise DuplicateRegistrationError(f"{kind} {key!r} is already registered")
        store[key] = value

    def _record_capabilities(self, capabilities: tuple[str, ...], source: str) -> None:
        for cap in capabilities:
            self._capability_source.setdefault(cap, source)

    # The mutable stores, captured/restored for atomic plugin registration.
    _MUTABLE_STORES = (
        "_node_specs",
        "_node_impls",
        "_connectors",
        "_storage",
        "_execution",
        "_exporters",
        "_validators",
        "_ai",
        "_auth",
        "_capability_source",
    )

    def _snapshot(self) -> dict[str, Any]:
        snap: dict[str, Any] = {name: dict(getattr(self, name)) for name in self._MUTABLE_STORES}
        snap["_license_providers"] = list(self._license_providers)
        # Capture event subscriptions too, so a plugin that subscribes in
        # register() and then fails has its hooks rolled back as well.
        snap["_events"] = {hook: list(cbs) for hook, cbs in self.events._subscribers.items()}
        return snap

    def _restore(self, snapshot: dict[str, Any]) -> None:
        for name in self._MUTABLE_STORES:
            getattr(self, name).clear()
            getattr(self, name).update(snapshot[name])
        self._license_providers[:] = snapshot["_license_providers"]
        self.events._subscribers.clear()
        for hook, cbs in snapshot["_events"].items():
            self.events._subscribers[hook] = list(cbs)
