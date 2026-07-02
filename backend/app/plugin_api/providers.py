# SPDX-License-Identifier: Apache-2.0
"""Provider interfaces — the stable extension contracts.

A plugin contributes capabilities by implementing one or more of these provider
ABCs and registering them in its :meth:`Plugin.register`. Providers return
serializable *specs* (for the catalog) and, where relevant, opaque
*implementations* (duck-typed by the engine — e.g. a node's
``BaseTransformation``). Keeping implementations opaque is what lets this module
stay free of any engine/app import, so a plugin only ever depends on
``app.plugin_api`` (the future ``ciaren-plugin-api`` package).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from app.plugin_api.specs import (
    AICapabilitySpec,
    AuthMethodSpec,
    ConnectorSpec,
    ExecutionSpec,
    ExporterSpec,
    LicenseStatus,
    ModelTypeSpec,
    NodeSpec,
    PluginMetadata,
    StorageSpec,
    ValidatorSpec,
)

if TYPE_CHECKING:  # avoid a runtime import cycle; the registry imports providers
    from app.plugin_api.registry import ServiceRegistry


class NodeProvider(ABC):
    """Contributes transformation nodes."""

    @abstractmethod
    def nodes(self) -> list[NodeSpec]:
        """Catalog metadata for each contributed node."""

    def node_implementations(self) -> dict[str, Any]:
        """Map node id -> executable implementation (engine-defined, e.g.
        ``BaseTransformation``). Catalog-only providers may return ``{}``; the
        registry then exposes the spec without an executable binding."""
        return {}


class ConnectorProvider(ABC):
    """Contributes data/database connectors."""

    @abstractmethod
    def connectors(self) -> list[ConnectorSpec]: ...

    def connector_implementations(self) -> dict[str, Any]:
        """Map connector id -> executable implementation (a
        :class:`~app.plugin_api.connector_runtime.ConnectorRuntime`). Catalog-only
        providers may return ``{}``; the spec is then listed without a runtime
        (e.g. the core connectors, which execute through their own machinery)."""
        return {}


class ModelProvider(ABC):
    """Contributes trainable model types to the ML model catalog.

    Contributed types show up in the matching core train node's model picker and
    train through the core pipeline (preprocessing, limits, MLflow logging, code
    export) — the provider only supplies the estimator.
    """

    @abstractmethod
    def model_types(self) -> list[ModelTypeSpec]:
        """Catalog metadata for each contributed model type."""

    def model_builders(self) -> dict[str, Any]:
        """Map model-type id -> builder. A builder is
        ``(hyperparameters: dict, seed: int | None) -> estimator`` and must return
        an sklearn-compatible estimator (``fit``/``predict``; ``get_params`` for
        cross-validation cloning). Hyperparameters arrive already sanitized to
        JSON-native values; the builder should raise ``ValueError`` (or let a
        ``TypeError`` surface) on invalid ones."""
        return {}


class StorageProvider(ABC):
    """Contributes object/file storage backends."""

    @abstractmethod
    def storage_backends(self) -> list[StorageSpec]: ...


class ExecutionProvider(ABC):
    """Contributes DataFrame execution engines."""

    @abstractmethod
    def execution_backends(self) -> list[ExecutionSpec]: ...


class ExporterProvider(ABC):
    """Contributes code/artifact exporters."""

    @abstractmethod
    def exporters(self) -> list[ExporterSpec]: ...


class ValidatorProvider(ABC):
    """Contributes data-quality / contract validators."""

    @abstractmethod
    def validators(self) -> list[ValidatorSpec]: ...


class AIProvider(ABC):
    """Contributes AI capabilities (pipeline builder, debugger, optimizer)."""

    @abstractmethod
    def ai_capabilities(self) -> list[AICapabilitySpec]: ...


class AuthProvider(ABC):
    """Contributes authentication methods (enterprise)."""

    @abstractmethod
    def auth_methods(self) -> list[AuthMethodSpec]: ...


class LicenseProvider(ABC):
    """Validates licenses for premium plugins."""

    @abstractmethod
    def validate_license(self, plugin_id: str) -> LicenseStatus: ...


class Plugin(ABC):
    """The entry point a plugin package exposes.

    The loader instantiates this and calls :meth:`register`, where the plugin
    registers its providers on the supplied registry. A plugin must not import
    private internals of the Ciaren app — only ``app.plugin_api`` and the
    public schema package.
    """

    @abstractmethod
    def metadata(self) -> PluginMetadata: ...

    @abstractmethod
    def register(self, registry: ServiceRegistry) -> None: ...
