from __future__ import annotations

import asyncio
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors import (
    ConnectionSpec,
    ConnectorError,
    driver_available,
    get_connector,
    get_provider,
    list_providers,
)
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
        for field, value in updates.items():
            setattr(conn, field, value)
        self._validate(conn.provider, conn.host, conn.database)
        if "name" in updates:
            existing = await self._by_name(conn.name)
            if existing and existing.id != conn.id:
                raise ConflictError(f"A connection named '{conn.name}' already exists.")
        conn.updated_at = datetime.utcnow()
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
        """Test an unsaved connection payload, so the UI can validate before saving."""
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
            spec = ConnectionSpec(
                provider=data.provider,
                host=data.host,
                port=data.port,
                database=data.database,
                username=data.username,
                password=resolve_secret(data.password_env),
                options=data.options or {},
            )
            await asyncio.to_thread(connector.test_connection, spec)
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
            spec = self._spec(conn)
            # Driver calls are blocking I/O — keep them off the event loop.
            await asyncio.to_thread(connector.test_connection, spec)
        except (ConnectorError, ValidationError) as exc:
            return ConnectionTestResult(ok=False, message=str(exc))
        return ConnectionTestResult(ok=True, message="Connection successful.")

    async def list_tables(self, connection_id: str) -> list[TableInfo]:
        conn = await self._get_or_raise(connection_id)
        provider = get_provider(conn.provider)
        if not driver_available(provider):
            raise ValidationError(
                f"The {provider.label} driver isn't installed (pip install flowframe[{provider.extra}])."
            )
        connector = get_connector(provider)
        try:
            spec = self._spec(conn)
            refs = await asyncio.to_thread(connector.list_tables, spec)
        except ConnectorError as exc:
            raise ValidationError(str(exc)) from None
        return [TableInfo(name=r.name, schema_name=r.schema, qualified=r.qualified) for r in refs]

    # -- Internals ------------------------------------------------------

    def _spec(self, conn: Connection) -> ConnectionSpec:
        return build_connection_spec(conn)

    def _validate(self, provider: str, host: str | None, database: str | None) -> None:
        p = get_provider(provider)
        if p.name == "sqlite":
            if not database:
                raise ValidationError("SQLite needs a database file path.")
            return
        if p.needs_host and not host:
            raise ValidationError(f"{p.label} needs a host.")
        if not database:
            raise ValidationError(f"{p.label} needs a database name.")

    async def _by_name(self, name: str) -> Connection | None:
        result = await self.db.execute(select(Connection).where(func.lower(Connection.name) == name.lower()))
        return result.scalar_one_or_none()

    async def _get_or_raise(self, connection_id: str) -> Connection:
        result = await self.db.execute(select(Connection).where(Connection.id == connection_id))
        conn = result.scalar_one_or_none()
        if conn is None:
            raise NotFoundError("Connection", connection_id)
        return conn
