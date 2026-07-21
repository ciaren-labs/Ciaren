# SPDX-License-Identifier: Apache-2.0
"""Serializable specifications exchanged across the plugin boundary.

These describe *what* a plugin contributes (nodes, connectors, engines, …) in a
form that is JSON-serializable for the backend catalog endpoints and stable
enough to commit to a public contract. They deliberately carry no executable
behavior — the opaque implementations live behind
:class:`~app.plugin_api.registry.ServiceRegistry` and are duck-typed by the
engine, so this module never imports anything from the Ciaren app, engine, or
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

#: Field kinds a config-schema form can render. ``column``/``column_list`` are
#: resolved against the columns arriving on the node's wire (node forms only).
ConfigFieldKind = Literal[
    "string",
    "number",
    "integer",
    "boolean",
    "select",
    "string_list",
    "column",
    "column_list",
]


class ConfigFieldSpec(BaseModel):
    """One field of a schema-driven config form.

    This is a deliberately small, UI-oriented dialect (not full JSON Schema),
    shared by plugin node config forms, connector connection forms, and model
    hyperparameter forms. Validated at registration so a typo fails the plugin
    load with a clear error instead of rendering a broken form.
    """

    model_config = ConfigDict(frozen=True)

    #: Config key the field reads/writes (e.g. ``"base_url"``).
    key: str = Field(..., min_length=1)
    #: Human label; defaults to the key when empty.
    label: str = ""
    type: ConfigFieldKind = "string"
    required: bool = False
    #: Initial value for a fresh config (must be JSON-native).
    default: Any = None
    placeholder: str = ""
    #: Short help text shown under the field.
    help: str = ""
    #: Choices for ``select`` fields.
    options: tuple[str, ...] = ()
    #: Bounds for ``number`` / ``integer`` fields.
    min: float | None = None
    max: float | None = None
    #: Render as a masked input (for tokens/keys — note Ciaren stores secrets as
    #: environment-variable *names*, never values; use this for the env-var name).
    secret: bool = False

    @field_validator("options")
    @classmethod
    def _options_only_for_select(cls, value: tuple[str, ...], info: Any) -> tuple[str, ...]:
        if value and info.data.get("type") not in (None, "select"):
            raise ValueError("'options' is only valid for fields of type 'select'")
        return value


def validate_config_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Validate a ``config_schema`` mapping: empty, or ``{"fields": [...]}`` where
    every entry parses as :class:`ConfigFieldSpec`. Returns the input unchanged so
    the stored value stays plain JSON. Raises ``ValueError`` on anything else."""
    if not schema:
        return schema
    fields = schema.get("fields")
    if not isinstance(fields, list):
        raise ValueError("config_schema must be {} or {'fields': [...]} (a list of field specs)")
    seen: set[str] = set()
    for raw in fields:
        field = ConfigFieldSpec.model_validate(raw)
        if field.key in seen:
            raise ValueError(f"config_schema has a duplicate field key {field.key!r}")
        seen.add(field.key)
    return schema


BUILTIN_NODE_CATEGORIES = {
    "input",
    "clean",
    "columns",
    "reshape",
    "analytics",
    "quality",
    "chart",
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
    #: Namespaced provider id, e.g. ``"ciaren.core"`` or ``"ciaren.ml"``.
    provider: str = "ciaren.core"
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
    #: Schema-driven config form: ``{}`` (no form) or ``{"fields": [...]}`` of
    #: :class:`ConfigFieldSpec` entries. The editor renders this for plugin nodes
    #: instead of needing a hand-written form per node type.
    config_schema: dict[str, Any] = Field(default_factory=dict)

    @field_validator("category")
    @classmethod
    def _normalize_category(cls, value: str) -> str:
        category = value.strip() or DEFAULT_PLUGIN_NODE_CATEGORY
        return category if category in BUILTIN_NODE_CATEGORIES else DEFAULT_PLUGIN_NODE_CATEGORY

    @field_validator("config_schema")
    @classmethod
    def _valid_config_schema(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_config_schema(value)


class ConnectorSpec(BaseModel):
    """A data/storage connector contributed by a provider."""

    #: Provider name, e.g. ``"postgresql"``, ``"s3"``.
    id: str
    label: str
    #: High-level kind: ``"sql"`` | ``"mongo"`` | ``"storage"`` | ``"mlflow"`` | ``"api"``.
    kind: str
    available: bool = True
    driver_module: str | None = None
    #: pip extra that installs the driver (for the UI install hint).
    extra: str | None = None
    capabilities: tuple[str, ...] = ()
    permissions: tuple[Permission, ...] = ()
    provider: str = "ciaren.core"
    #: Raw provider flags the connection form needs (host/port/auth/bucket/…).
    metadata: dict[str, Any] = Field(default_factory=dict)
    #: Extra, connector-specific form fields (``{"fields": [...]}`` of
    #: :class:`ConfigFieldSpec`), rendered by the connection dialog and stored in
    #: the connection's ``options``. Lets a plugin connector drive its own form
    #: instead of relying on the fixed core flag set.
    config_schema: dict[str, Any] = Field(default_factory=dict)

    @field_validator("config_schema")
    @classmethod
    def _valid_config_schema(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_config_schema(value)


class StorageSpec(BaseModel):
    """An object/file storage backend (a specialization of a connector)."""

    id: str
    label: str
    available: bool = True
    capabilities: tuple[str, ...] = ()
    permissions: tuple[Permission, ...] = ()
    provider: str = "ciaren.core"


class ExecutionSpec(BaseModel):
    """A DataFrame execution engine (pandas, polars, …)."""

    #: Engine name as understood by the executor, e.g. ``"polars"``.
    id: str
    label: str
    available: bool = True
    capabilities: tuple[str, ...] = ()
    provider: str = "ciaren.core"


class ExporterSpec(BaseModel):
    """A code/artifact exporter (python, polars, notebook, …)."""

    id: str
    label: str
    #: Output format identifier, e.g. ``"python"``.
    format: str
    file_extension: str = ""
    capabilities: tuple[str, ...] = ()
    provider: str = "ciaren.core"


class ValidatorSpec(BaseModel):
    """A data-quality / contract validator."""

    id: str
    label: str
    description: str = ""
    capabilities: tuple[str, ...] = ()
    provider: str = "ciaren.core"


#: Learning tasks the ML train nodes understand. Mirrors ``app.ml.models.TASKS``;
#: kept literal here so the contract package stays free of any app import.
MODEL_TASKS = (
    "classification",
    "regression",
    "clustering",
    "dimensionality_reduction",
    "timeseries",
)


class ModelTypeSpec(BaseModel):
    """A trainable model type contributed to the ML model catalog.

    A plugin's model type appears in the matching core train node's model picker
    (e.g. a ``classification`` type shows up in **Train Classifier**) and trains
    through the exact same pipeline as a built-in: preprocessing bundled into an
    sklearn ``Pipeline``, hyperparameter sanitization, size limits, MLflow
    logging, and code export. The executable *builder* is registered separately
    (see :class:`~app.plugin_api.providers.ModelProvider.model_builders`) and must
    return an sklearn-compatible estimator (``fit``/``predict``).
    """

    #: The ``model_type`` id used in train-node configs — unique across the catalog.
    id: str = Field(..., min_length=1)
    label: str
    task: str
    supervised: bool = True
    provider: str = "ciaren.ml"
    description: str = ""
    #: Importable modules the builder needs at run time (e.g. ``("sklearn",)``).
    #: The catalog marks the type unavailable when one is missing.
    requires: tuple[str, ...] = ()
    #: Install hint shown when a required module is missing
    #: (e.g. ``"pip install scikit-learn"``).
    install_hint: str = ""
    #: Defaults merged *under* the user's hyperparameters before the builder is
    #: called, so an untouched form trains with what the catalog advertises.
    default_hyperparameters: dict[str, Any] = Field(default_factory=dict)
    #: Hyperparameter form: ``{}`` or ``{"fields": [...]}`` of :class:`ConfigFieldSpec`.
    hyperparameter_schema: dict[str, Any] = Field(default_factory=dict)
    #: Top-level import lines exported training scripts use for the estimator
    #: (e.g. ``("from sklearn.neural_network import MLPClassifier",)``). When
    #: empty, the import is derived from the estimator's class module — declare
    #: them whenever the estimator's ``repr`` needs anything beyond that.
    import_lines: tuple[str, ...] = ()
    permissions: tuple[Permission, ...] = ()

    @field_validator("task")
    @classmethod
    def _known_task(cls, value: str) -> str:
        if value not in MODEL_TASKS:
            raise ValueError(f"unknown model task {value!r}; expected one of {MODEL_TASKS}")
        return value

    @field_validator("hyperparameter_schema")
    @classmethod
    def _valid_hyperparameter_schema(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_config_schema(value)


class AICapabilitySpec(BaseModel):
    """An AI capability (pipeline builder, debugger, optimizer, …)."""

    id: str
    label: str
    description: str = ""
    capabilities: tuple[str, ...] = ()
    provider: str = "ciaren.core"


class AuthMethodSpec(BaseModel):
    """An authentication method contributed by an enterprise auth plugin."""

    id: str
    label: str
    provider: str = "ciaren.core"


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
