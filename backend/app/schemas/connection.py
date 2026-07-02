# SPDX-License-Identifier: AGPL-3.0-only
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# Provider names mapped to their kind — kept in sync with providers.py.
_STORAGE_PROVIDERS = frozenset({"local", "s3", "azure_blob", "gcs"})
_MONGO_PROVIDERS = frozenset({"mongodb"})
_MLFLOW_PROVIDERS = frozenset({"mlflow"})
_API_PROVIDERS = frozenset({"rest_api"})

# Valid POSIX env var names: start with letter or underscore, then letters/digits/underscores.
_ENV_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _empty_to_none(v: str | None) -> str | None:
    """Normalize empty strings from HTML forms to None."""
    return v or None


def _normalize_path(v: str | None) -> str | None:
    """Accept Windows or POSIX paths; store with forward slashes for consistency."""
    if not v:
        return None
    # Replace backslashes so pathlib parses Windows paths on any OS.
    return v.replace("\\", "/")


def _plugin_connector_kind(provider: str) -> str | None:
    """The kind a plugin connector declared for ``provider``, or None. Lazy and
    fault-tolerant: schema validation must never fail because of a plugin."""
    try:
        from app.plugins.connectors import plugin_connection_kind

        return plugin_connection_kind(provider)
    except Exception:  # noqa: BLE001
        return None


class ConnectionBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    provider: str
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    # The NAME of an environment variable holding the password (never the secret).
    password_env: str | None = None
    options: dict[str, Any] | None = None

    # Normalize blank form fields → None so the DB never stores empty strings.
    @field_validator("host", "username", mode="before")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return _empty_to_none(v)

    # Accept Windows (C:\…) or POSIX paths; store with forward slashes.
    @field_validator("database", mode="before")
    @classmethod
    def _normalise_path(cls, v: str | None) -> str | None:
        return _normalize_path(v)

    @field_validator("password_env", mode="before")
    @classmethod
    def validate_password_env(cls, v: str | None) -> str | None:
        v = _empty_to_none(v)
        if v is not None and not _ENV_VAR_RE.match(v):
            raise ValueError(
                f"password_env must be a valid environment variable name "
                f"(letters, digits, underscores; must not start with a digit). Got: {v!r}"
            )
        return v


class ConnectionCreate(ConnectionBase):
    pass


class ConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    provider: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password_env: str | None = None
    options: dict[str, Any] | None = None

    @field_validator("host", "username", mode="before")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return _empty_to_none(v)

    @field_validator("database", mode="before")
    @classmethod
    def _normalise_path(cls, v: str | None) -> str | None:
        return _normalize_path(v)

    @field_validator("password_env", mode="before")
    @classmethod
    def validate_password_env(cls, v: str | None) -> str | None:
        v = _empty_to_none(v)
        if v is not None and not _ENV_VAR_RE.match(v):
            raise ValueError(
                f"password_env must be a valid environment variable name "
                f"(letters, digits, underscores; must not start with a digit). Got: {v!r}"
            )
        return v


class ConnectionRead(BaseModel):
    """A connection as returned to clients.

    Contains no secret — only the *name* of the password env var — so it is
    safe to serialize. ``connection_type`` is derived from the provider name and
    tells the frontend which form to show (sql | mongo | storage | mlflow).
    """

    id: str
    name: str
    provider: str
    connection_type: str = "sql"
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password_env: str | None = None
    options: dict[str, Any] | None = Field(default=None, validation_alias="options_json")
    created_at: datetime
    updated_at: datetime
    last_tested_at: datetime | None = None

    model_config = {"from_attributes": True, "populate_by_name": True}

    @model_validator(mode="after")
    def _infer_connection_type(self) -> "ConnectionRead":
        if self.provider in _STORAGE_PROVIDERS:
            self.connection_type = "storage"
        elif self.provider in _MONGO_PROVIDERS:
            self.connection_type = "mongo"
        elif self.provider in _MLFLOW_PROVIDERS:
            self.connection_type = "mlflow"
        elif self.provider in _API_PROVIDERS:
            self.connection_type = "api"
        else:
            # A plugin connector reports its own kind (e.g. "storage" routes it to
            # the storage nodes, "api"/"sql" to the SQL nodes). Unknown/core-SQL
            # providers stay "sql".
            self.connection_type = _plugin_connector_kind(self.provider) or "sql"
        return self


class ConnectionTestResult(BaseModel):
    ok: bool
    message: str


class TableInfo(BaseModel):
    name: str
    schema_name: str | None = None
    qualified: str
