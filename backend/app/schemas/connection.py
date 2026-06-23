from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

# Provider names mapped to their kind — kept in sync with providers.py.
_STORAGE_PROVIDERS = frozenset({"local", "s3", "azure_blob", "gcs"})
_MONGO_PROVIDERS = frozenset({"mongodb"})


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


class ConnectionRead(BaseModel):
    """A connection as returned to clients.

    Contains no secret — only the *name* of the password env var — so it is
    safe to serialize. ``connection_type`` is derived from the provider name and
    tells the frontend which form to show (sql | mongo | storage).
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

    model_config = {"from_attributes": True, "populate_by_name": True}

    @model_validator(mode="after")
    def _infer_connection_type(self) -> "ConnectionRead":
        if self.provider in _STORAGE_PROVIDERS:
            self.connection_type = "storage"
        elif self.provider in _MONGO_PROVIDERS:
            self.connection_type = "mongo"
        else:
            self.connection_type = "sql"
        return self


class ConnectionTestResult(BaseModel):
    ok: bool
    message: str


class TableInfo(BaseModel):
    name: str
    schema_name: str | None = None
    qualified: str
