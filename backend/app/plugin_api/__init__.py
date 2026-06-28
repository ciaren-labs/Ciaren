"""FlowFrame plugin API — the stable extension contract.

This package is intentionally self-contained (only Pydantic as a dependency) so
it can become the independently published ``flowframe-plugin-api`` package. A
plugin depends on this and on the public schema; it never imports private
internals of the FlowFrame app, engine, or FastAPI layer.
"""

from app.plugin_api.events import EventBus, Hook
from app.plugin_api.manifest import (
    PluginManifest,
    PluginUI,
    validate_manifest,
)
from app.plugin_api.node_runtime import NodeRuntime
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
from app.plugin_api.registry import DuplicateRegistrationError, ServiceRegistry
from app.plugin_api.signing import (
    SigningUnavailableError,
    generate_keypair,
    sha256_hex,
    sign,
    signing_available,
    verify,
)
from app.plugin_api.specs import (
    AICapabilitySpec,
    AuthMethodSpec,
    ConnectorSpec,
    ExecutionSpec,
    ExporterSpec,
    LicenseStatus,
    NodeSpec,
    Permission,
    PluginMetadata,
    PortSpec,
    StorageSpec,
    ValidatorSpec,
)

__all__ = [
    # registry
    "ServiceRegistry",
    "DuplicateRegistrationError",
    # providers
    "Plugin",
    "NodeProvider",
    "ConnectorProvider",
    "StorageProvider",
    "ExecutionProvider",
    "ExporterProvider",
    "ValidatorProvider",
    "AIProvider",
    "AuthProvider",
    "LicenseProvider",
    # specs
    "NodeSpec",
    "PortSpec",
    "ConnectorSpec",
    "StorageSpec",
    "ExecutionSpec",
    "ExporterSpec",
    "ValidatorSpec",
    "AICapabilitySpec",
    "AuthMethodSpec",
    "LicenseStatus",
    "PluginMetadata",
    "Permission",
    # manifest
    "PluginManifest",
    "PluginUI",
    "validate_manifest",
    # execution
    "NodeRuntime",
    # events
    "EventBus",
    "Hook",
    # signing
    "sha256_hex",
    "sign",
    "verify",
    "generate_keypair",
    "signing_available",
    "SigningUnavailableError",
]
