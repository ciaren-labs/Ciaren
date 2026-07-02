# SPDX-License-Identifier: Apache-2.0
"""Ciaren plugin API — the stable extension contract.

This package is intentionally self-contained (only Pydantic as a dependency) so
it can become the independently published ``ciaren-plugin-api`` package. A
plugin depends on this and on the public schema; it never imports private
internals of the Ciaren app, engine, or FastAPI layer.
"""

from app.plugin_api.connector_runtime import ConnectorRuntime, ConnectorTestResult
from app.plugin_api.events import EventBus, Hook
from app.plugin_api.manifest import (
    PluginManifest,
    PluginUI,
    validate_manifest,
)
from app.plugin_api.model_ref import MODEL_REF_COLUMNS, ModelRef, is_model_ref_frame
from app.plugin_api.node_runtime import (
    EMPTY_NODE_CONTEXT,
    ModelStore,
    NodeContext,
    NodeRuntime,
)
from app.plugin_api.providers import (
    AIProvider,
    AuthProvider,
    ConnectorProvider,
    ExecutionProvider,
    ExporterProvider,
    LicenseProvider,
    ModelProvider,
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
    ConfigFieldSpec,
    ConnectorSpec,
    ExecutionSpec,
    ExporterSpec,
    LicenseStatus,
    ModelTypeSpec,
    NodeSpec,
    Permission,
    PluginMetadata,
    PortSpec,
    StorageSpec,
    ValidatorSpec,
    validate_config_schema,
)

#: Version of the plugin *contract* (this package), independent of the app
#: version. Bump the minor for compatible additions and the major for breaking
#: changes; plugins can pin against this instead of coupling to app releases
#: once the contract ships as the standalone ``ciaren-plugin-api`` package.
#:
#: 1.1 (additive): ``ModelRef`` + model wires, ``ModelProvider``/``ModelTypeSpec``,
#: ``NodeContext``/``ModelStore`` (``NodeRuntime.execute_with_context``),
#: ``ConnectorRuntime`` implementations, and ``config_schema`` driven forms.
PLUGIN_API_VERSION = "1.1"

__all__ = [
    "PLUGIN_API_VERSION",
    # registry
    "ServiceRegistry",
    "DuplicateRegistrationError",
    # providers
    "Plugin",
    "NodeProvider",
    "ConnectorProvider",
    "ModelProvider",
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
    "ConfigFieldSpec",
    "validate_config_schema",
    "ModelTypeSpec",
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
    "NodeContext",
    "ModelStore",
    "EMPTY_NODE_CONTEXT",
    # models
    "ModelRef",
    "MODEL_REF_COLUMNS",
    "is_model_ref_frame",
    # connectors
    "ConnectorRuntime",
    "ConnectorTestResult",
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
