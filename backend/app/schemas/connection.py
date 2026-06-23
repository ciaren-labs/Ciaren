from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
    """A connection as returned to clients. Contains no secret — only the *name*
    of the password env var — so it is safe to serialize."""

    id: str
    name: str
    provider: str
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password_env: str | None = None
    options: dict[str, Any] | None = Field(default=None, validation_alias="options_json")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class ConnectionTestResult(BaseModel):
    ok: bool
    message: str


class TableInfo(BaseModel):
    name: str
    schema_name: str | None = None
    qualified: str
