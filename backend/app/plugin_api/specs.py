# SPDX-License-Identifier: Apache-2.0
"""Serializable specifications exchanged across the plugin boundary.

These describe *what* a plugin contributes (nodes, connectors, engines, …) in a
form that is JSON-serializable for the backend catalog endpoints and stable
enough to commit to a public contract. They deliberately carry no executable
behavior — the opaque implementations live behind
:class:`~app.plugin_api.registry.ServiceRegistry` and are duck-typed by the
engine, so this module never imports anything from the FlowFrame app, engine, or
FastAPI. Its only dependency is Pydantic.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Permission(str, Enum):
    """Capabilities a plugin may request in its manifest.

    The permission model is a *trust and UX boundary*, not a hard sandbox: Python
    plugins are not isolated by default. The UI surfaces these before enabling a
    plugin so the user understands what it can do.
    """

    filesystem_read = "filesystem_read"
    filesystem_write = "filesystem_write"
    network = "network"
    credentials = "credentials"
    subprocess = "subprocess"
    shell = "shell"
    docker = "docker"
    local_model_load = "local_model_load"
    joblib_load = "joblib_load"
    database_access = "database_access"
    cloud_access = "cloud_access"
    llm_access = "llm_access"
    telemetry = "telemetry"


#: A port carries either a dataframe or a trained model. A model output may only
#: feed a model input (graph validation enforces this).
PortKind = Literal["dataframe", "model"]
BUILTIN_NODE_CATEGORIES = {
    "input",
    "clean",
    "columns",
    "reshape",
    "analytics",
    "quality",
    "ml",
    "output",
    "plugins",
}
DEFAULT_PLUGIN_NODE_CATEGORY = "plugins"


class PortSpec(BaseModel):
    """A single named input/output handle on a node."""

    model_config = ConfigDict(frozen=True)

    id: str
    type: PortKind = "dataframe"
    #: Whether an incoming edge is required for graph validity (inputs only).
    required: bool = True
    #: Whether this handle accepts an arbitrary number of incoming edges (concat).
    multi: bool = False


class NodeSpec(BaseModel):
    """Everything the catalog and the editor need to render and place a node.

    Presentational fields (``label``, ``category``, ``default_config``,
    ``description``) plus the handle topology and capability/permission
    requirements. The executable behavior is registered separately and keyed by
    :attr:`id`.
    """

    #: Node type, e.g. ``"filterRows"`` — unique within the catalog.
    id: str
    label: str
    #: UI grouping, e.g. ``"input"``, ``"clean"``, ``"reshape"``, ``"ml"``.
    category: str = DEFAULT_PLUGIN_NODE_CATEGORY
    description: str = ""
    #: Namespaced provider id, e.g. ``"flowframe.core"`` or ``"flowframe.ml"``.
    provider: str = "flowframe.core"
    version: str = "1.0.0"
    inputs: tuple[PortSpec, ...] = ()
    outputs: tuple[PortSpec, ...] = ()
    #: Default config object for a freshly-created node.
    default_config: dict[str, Any] = Field(default_factory=dict)
    #: Capabilities this node needs at run time (e.g. ``"engine.polars"``).
    capabilities: tuple[str, ...] = ()
    permissions: tuple[Permission, ...] = ()
    #: True for nodes only available when the ML extension is installed + enabled.
    requires_ml: bool = False
    #: A terminal that persists a result without a file-output node (e.g. mlTrain).
    is_model_sink: bool = False
    #: A node that completes a flow on its own (no downstream output node needed) —
    #: a model sink (mlTrain) or a report node like cross-validation. The editor uses
    #: this to decide whether the "add an output node" check applies.
    is_flow_terminal: bool = False
    #: Reserved for schema-driven config forms (JSON schema). Empty for now.
    config_schema: dict[str, Any] = Field(default_factory=dict)

    @field_validator("category")
    @classmethod
    def _normalize_category(cls, value: str) -> str:
        category = value.strip() or DEFAULT_PLUGIN_NODE_CATEGORY
        return category if category in BUILTIN_NODE_CATEGORIES else DEFAULT_PLUGIN_NODE_CATEGORY


class ConnectorSpec(BaseModel):
    """A data/storage connector contributed by a provider."""

    #: Provider name, e.g. ``"postgresql"``, ``"s3"``.
    id: str
    label: str
    #: High-level kind: ``"sql"`` | ``"mongo"`` | ``"storage"`` | ``"mlflow"``.
    kind: str
    available: bool = True
    driver_module: str | None = None
    #: pip extra that installs the driver (for the UI install hint).
    extra: str | None = None
    capabilities: tuple[str, ...] = ()
    permissions: tuple[Permission, ...] = ()
    provider: str = "flowframe.core"
    #: Raw provider flags the connection form needs (host/port/auth/bucket/…).
    metadata: dict[str, Any] = Field(default_factory=dict)


class StorageSpec(BaseModel):
    """An object/file storage backend (a specialization of a connector)."""

    id: str
    label: str
    available: bool = True
    capabilities: tuple[str, ...] = ()
    permissions: tuple[Permission, ...] = ()
    provider: str = "flowframe.core"


class ExecutionSpec(BaseModel):
    """A DataFrame execution engine (pandas, polars, …)."""

    #: Engine name as understood by the executor, e.g. ``"polars"``.
    id: str
    label: str
    available: bool = True
    capabilities: tuple[str, ...] = ()
    provider: str = "flowframe.core"


class ExporterSpec(BaseModel):
    """A code/artifact exporter (python, polars, notebook, …)."""

    id: str
    label: str
    #: Output format identifier, e.g. ``"python"``.
    format: str
    file_extension: str = ""
    capabilities: tuple[str, ...] = ()
    provider: str = "flowframe.core"


class ValidatorSpec(BaseModel):
    """A data-quality / contract validator."""

    id: str
    label: str
    description: str = ""
    capabilities: tuple[str, ...] = ()
    provider: str = "flowframe.core"


class AICapabilitySpec(BaseModel):
    """An AI capability (pipeline builder, debugger, optimizer, …)."""

    id: str
    label: str
    description: str = ""
    capabilities: tuple[str, ...] = ()
    provider: str = "flowframe.core"


class AuthMethodSpec(BaseModel):
    """An authentication method contributed by an enterprise auth plugin."""

    id: str
    label: str
    provider: str = "flowframe.core"


class LicenseStatus(BaseModel):
    """Result of a license check for a (premium) plugin."""

    plugin_id: str
    valid: bool
    license_type: str | None = None
    expires_at: str | None = None
    reason: str | None = None


class PluginMetadata(BaseModel):
    """Identity and headline contributions of a plugin instance."""

    id: str
    name: str
    version: str = "0.0.0"
    publisher: str = "community"
    description: str = ""
    capabilities: tuple[str, ...] = ()
    permissions: tuple[Permission, ...] = ()
