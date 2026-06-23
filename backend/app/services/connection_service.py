from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors import (
    ConnectionSpec,
    ConnectorError,
    StorageSpec,
    driver_available,
    get_connector,
    get_provider,
    is_storage_provider,
    list_providers,
)
from app.connectors.base import DataConnector
from app.connectors.storage_base import StorageConnector
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.secrets import resolve_secret
from app.db.models.connection import Connection
from app.schemas.connection import (
    ConnectionCreate,
    ConnectionRead,
    ConnectionTestResult,
    ConnectionUpdate,
    TableInfo,
)


def build_connection_spec(conn: Connection) -> ConnectionSpec:
    """Assemble a ConnectionSpec from a Connection row, resolving the password
    from the environment (never stored). Raises ValidationError if the named env
    var is unset. Shared by the connection service and the SQL node resolver."""
    return ConnectionSpec(
        provider=conn.provider,
        host=conn.host,
        port=conn.port,
        database=conn.database,
        username=conn.username,
        password=resolve_secret(conn.password_env),
        options=conn.options_json or {},
    )


def build_storage_spec(conn: Connection) -> StorageSpec:
    """Assemble a StorageSpec from a Connection row for storage providers.

    Field mapping:
    - database  → bucket / container / folder path (root scope)
    - username  → AWS Access Key ID or Azure account name (public identifiers)
    - password_env → env var for secret key, account key, or GCS credentials path
    - host      → custom endpoint URL for S3-compatible stores (optional)
    - options   → region, project_id, and other provider-specific options
    """
    options = conn.options_json or {}
    return StorageSpec(
        provider=conn.provider,
        bucket=conn.database or options.get("path", ""),
        access_key=conn.username,
        secret=resolve_secret(conn.password_env),
        region=options.get("region"),
        endpoint_url=conn.host or None,
        extra=options,
    )


class ConnectionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -- CRUD -----------------------------------------------------------

    async def list_all(self) -> list[ConnectionRead]:
        result = await self.db.execute(select(Connection).order_by(Connection.created_at.desc()))
        return [ConnectionRead.model_validate(c) for c in result.scalars().all()]

    async def get(self, connection_id: str) -> ConnectionRead:
        return ConnectionRead.model_validate(await self._get_or_raise(connection_id))

    async def create(self, data: ConnectionCreate) -> ConnectionRead:
        self._validate(data.provider, data.host, data.database)
        if await self._by_name(data.name):
            raise ConflictError(f"A connection named '{data.name}' already exists.")
        conn = Connection(
            name=data.name,
            provider=data.provider,
            host=data.host,
            port=data.port,
            database=data.database,
            username=data.username,
            password_env=data.password_env,
            options_json=data.options,
        )
        self.db.add(conn)
        await self.db.commit()
        await self.db.refresh(conn)
        return ConnectionRead.model_validate(conn)

    async def update(self, connection_id: str, data: ConnectionUpdate) -> ConnectionRead:
        conn = await self._get_or_raise(connection_id)
        updates = data.model_dump(exclude_unset=True)
        if "options" in updates:
            conn.options_json = updates.pop("options")
        for field_name, value in updates.items():
            setattr(conn, field_name, value)
        self._validate(conn.provider, conn.host, conn.database)
        if "name" in updates:
            existing = await self._by_name(conn.name)
            if existing and existing.id != conn.id:
                raise ConflictError(f"A connection named '{conn.name}' already exists.")
        conn.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.db.commit()
        await self.db.refresh(conn)
        return ConnectionRead.model_validate(conn)

    async def delete(self, connection_id: str) -> None:
        conn = await self._get_or_raise(connection_id)
        await self.db.delete(conn)
        await self.db.commit()

    # -- Connectivity ---------------------------------------------------

    def providers(self) -> list[dict[str, object]]:
        return list_providers()

    async def test_config(self, data: ConnectionCreate) -> ConnectionTestResult:
        """Test an unsaved connection payload so the UI can validate before saving."""
        try:
            provider = get_provider(data.provider)
            self._validate(data.provider, data.host, data.database)
        except ValidationError as exc:
            return ConnectionTestResult(ok=False, message=str(exc))
        if not driver_available(provider):
            return ConnectionTestResult(
                ok=False,
                message=f"The {provider.label} driver isn't installed (pip install flowframe[{provider.extra}]).",
            )
        connector = get_connector(provider)
        try:
            if is_storage_provider(provider):
                options = data.options or {}
                spec: StorageSpec | ConnectionSpec = StorageSpec(
                    provider=data.provider,
                    bucket=data.database or options.get("path", ""),
                    access_key=data.username,
                    secret=resolve_secret(data.password_env),
                    region=options.get("region"),
                    endpoint_url=data.host or None,
                    extra=options,
                )
            else:
                spec = ConnectionSpec(
                    provider=data.provider,
                    host=data.host,
                    port=data.port,
                    database=data.database,
                    username=data.username,
                    password=resolve_secret(data.password_env),
                    options=data.options or {},
                )
            # The connector and spec always match by provider kind (dispatched above).
            await asyncio.to_thread(connector.test_connection, spec)  # type: ignore[arg-type]
        except (ConnectorError, ValidationError) as exc:
            return ConnectionTestResult(ok=False, message=str(exc))
        return ConnectionTestResult(ok=True, message="Connection successful.")

    async def test(self, connection_id: str) -> ConnectionTestResult:
        conn = await self._get_or_raise(connection_id)
        provider = get_provider(conn.provider)
        if not driver_available(provider):
            return ConnectionTestResult(
                ok=False,
                message=f"The {provider.label} driver isn't installed (pip install flowframe[{provider.extra}]).",
            )
        connector = get_connector(provider)
        try:
            spec: StorageSpec | ConnectionSpec
            if is_storage_provider(provider):
                spec = build_storage_spec(conn)
            else:
                spec = build_connection_spec(conn)
            # connector and spec always match by provider kind (dispatched above).
            await asyncio.to_thread(connector.test_connection, spec)  # type: ignore[arg-type]
        except (ConnectorError, ValidationError) as exc:
            return ConnectionTestResult(ok=False, message=str(exc))
        return ConnectionTestResult(ok=True, message="Connection successful.")

    async def list_tables(self, connection_id: str) -> list[TableInfo]:
        conn = await self._get_or_raise(connection_id)
        provider = get_provider(conn.provider)
        if is_storage_provider(provider):
            raise ValidationError(
                f"'{provider.label}' is a storage connection — use list_objects instead."
            )
        if not driver_available(provider):
            raise ValidationError(
                f"The {provider.label} driver isn't installed (pip install flowframe[{provider.extra}])."
            )
        connector = cast(DataConnector, get_connector(provider))  # SQL/Mongo (guarded above)
        try:
            spec = build_connection_spec(conn)
            refs = await asyncio.to_thread(connector.list_tables, spec)
        except ConnectorError as exc:
            raise ValidationError(str(exc)) from None
        return [TableInfo(name=r.name, schema_name=r.schema, qualified=r.qualified) for r in refs]

    async def list_objects(self, connection_id: str, prefix: str = "") -> list[str]:
        conn = await self._get_or_raise(connection_id)
        provider = get_provider(conn.provider)
        if not is_storage_provider(provider):
            raise ValidationError(
                f"'{provider.label}' is not a storage connection — use list_tables instead."
            )
        if not driver_available(provider):
            raise ValidationError(
                f"The {provider.label} driver isn't installed (pip install flowframe[{provider.extra}])."
            )
        connector = cast(StorageConnector, get_connector(provider))  # storage (guarded above)
        try:
            spec = build_storage_spec(conn)
            return await asyncio.to_thread(connector.list_objects, spec, prefix)
        except ConnectorError as exc:
            raise ValidationError(str(exc)) from None

    # -- Internals ------------------------------------------------------

    def _validate(self, provider: str, host: str | None, database: str | None) -> None:
        p = get_provider(provider)
        if is_storage_provider(p):
            if p.name == "local":
                if not database:
                    raise ValidationError("Local Storage requires a folder path (set in 'Folder path').")
            elif p.needs_bucket and not database:
                raise ValidationError(f"{p.label} requires a bucket / container name.")
            return
        if p.name in ("sqlite", "duckdb"):
            if not database:
                raise ValidationError(f"{p.label} needs a database file path.")
            return
        if p.needs_host and not host:
            raise ValidationError(f"{p.label} needs a host.")
        if not database:
            raise ValidationError(f"{p.label} needs a database name.")

    async def _by_name(self, name: str) -> Connection | None:
        result = await self.db.execute(
            select(Connection).where(func.lower(Connection.name) == name.lower())
        )
        return result.scalar_one_or_none()

    async def _get_or_raise(self, connection_id: str) -> Connection:
        result = await self.db.execute(select(Connection).where(Connection.id == connection_id))
        conn = result.scalar_one_or_none()
        if conn is None:
            raise NotFoundError("Connection", connection_id)
        return conn
