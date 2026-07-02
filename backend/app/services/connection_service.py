# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors import (
    ConnectionSpec,
    ConnectorError,
    StorageSpec,
    driver_available,
    get_connector,
    get_provider,
    is_mlflow_provider,
    is_storage_provider,
    list_providers,
)
from app.connectors.base import DataConnector
from app.connectors.storage_base import StorageConnector
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.secrets import resolve_secret
from app.db.models.connection import Connection
from app.plugin_api import ConnectorRuntime
from app.plugin_api import ConnectorSpec as PluginConnectorSpec
from app.plugins.connectors import (
    connection_config,
    connector_config,
    guard_plugin_host,
    plugin_connector,
    plugin_connector_specs,
    provider_entry,
    validate_plugin_connection,
)
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
        self._validate(data.provider, data.host, data.database, data.options)
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
        self._validate(conn.provider, conn.host, conn.database, conn.options_json)
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
        """Core providers plus any plugin-contributed connectors (same dict shape,
        with ``plugin``/``config_schema`` extras so the UI can render their forms)."""
        entries = list_providers()
        try:
            entries += [provider_entry(spec) for spec in plugin_connector_specs()]
        except Exception:  # noqa: BLE001 — a broken plugin must not hide core providers
            pass
        return entries

    async def test_config(self, data: ConnectionCreate) -> ConnectionTestResult:
        """Test an unsaved connection payload so the UI can validate before saving."""
        plugin = plugin_connector(data.provider)
        if plugin is not None:
            plugin_spec, plugin_runtime = plugin
            return await self._test_plugin(
                plugin_spec,
                plugin_runtime,
                host=data.host,
                port=data.port,
                database=data.database,
                username=data.username,
                password_env=data.password_env,
                options=data.options,
            )
        try:
            provider = get_provider(data.provider)
            self._validate(data.provider, data.host, data.database, data.options)
        except ValidationError as exc:
            return ConnectionTestResult(ok=False, message=str(exc))
        if not driver_available(provider):
            return ConnectionTestResult(
                ok=False,
                message=f"The {provider.label} driver isn't installed (pip install ciaren[{provider.extra}]).",
            )
        if is_mlflow_provider(provider):
            return await self._test_mlflow(data.database)
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
        # Record the attempt time regardless of outcome, so the UI can show when a
        # connection was last checked.
        conn.last_tested_at = datetime.now(UTC).replace(tzinfo=None)
        await self.db.commit()
        plugin = plugin_connector(conn.provider)
        if plugin is not None:
            plugin_spec, plugin_runtime = plugin
            return await self._test_plugin(
                plugin_spec,
                plugin_runtime,
                host=conn.host,
                port=conn.port,
                database=conn.database,
                username=conn.username,
                password_env=conn.password_env,
                options=conn.options_json,
            )
        provider = get_provider(conn.provider)
        if not driver_available(provider):
            return ConnectionTestResult(
                ok=False,
                message=f"The {provider.label} driver isn't installed (pip install ciaren[{provider.extra}]).",
            )
        if is_mlflow_provider(provider):
            return await self._test_mlflow(conn.database)
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
        plugin = plugin_connector(conn.provider)
        if plugin is not None:
            return await self._list_plugin_tables(plugin[0], plugin[1], conn)
        provider = get_provider(conn.provider)
        if is_storage_provider(provider):
            raise ValidationError(f"'{provider.label}' is a storage connection — use list_objects instead.")
        if not driver_available(provider):
            raise ValidationError(
                f"The {provider.label} driver isn't installed (pip install ciaren[{provider.extra}])."
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
        plugin = plugin_connector(conn.provider)
        if plugin is not None:
            return await self._list_plugin_objects(plugin[0], plugin[1], conn, prefix)
        provider = get_provider(conn.provider)
        if not is_storage_provider(provider):
            raise ValidationError(f"'{provider.label}' is not a storage connection — use list_tables instead.")
        if not driver_available(provider):
            raise ValidationError(
                f"The {provider.label} driver isn't installed (pip install ciaren[{provider.extra}])."
            )
        connector = cast(StorageConnector, get_connector(provider))  # storage (guarded above)
        try:
            spec = build_storage_spec(conn)
            return await asyncio.to_thread(connector.list_objects, spec, prefix)
        except ConnectorError as exc:
            raise ValidationError(str(exc)) from None

    # -- Plugin connectors ------------------------------------------------

    async def _test_plugin(
        self,
        spec: PluginConnectorSpec,
        runtime: ConnectorRuntime,
        *,
        host: str | None,
        port: int | None,
        database: str | None,
        username: str | None,
        password_env: str | None,
        options: dict[str, object] | None,
    ) -> ConnectionTestResult:
        opts = dict(options or {})
        try:
            validate_plugin_connection(spec, host, opts)
            guard_plugin_host(host)
            config = connector_config(
                host=host,
                port=port,
                database=database,
                username=username,
                password_env=password_env,
                options=opts,
            )
        except (ValidationError, ConnectorError) as exc:
            return ConnectionTestResult(ok=False, message=str(exc))
        if not spec.available:
            hint = f" (pip install {spec.extra})" if spec.extra else ""
            return ConnectionTestResult(ok=False, message=f"The {spec.label} driver isn't installed{hint}.")
        try:
            result = await asyncio.to_thread(runtime.test, config)
        except NotImplementedError:
            return ConnectionTestResult(ok=True, message=f"{spec.label} does not support connection tests.")
        except Exception as exc:  # noqa: BLE001 — a plugin failure must surface, not 500
            return ConnectionTestResult(ok=False, message=str(exc))
        message = result.message or ("Connection successful." if result.ok else "Connection failed.")
        return ConnectionTestResult(ok=result.ok, message=message)

    async def _list_plugin_tables(
        self, spec: PluginConnectorSpec, runtime: ConnectorRuntime, conn: Connection
    ) -> list[TableInfo]:
        guard_plugin_host(conn.host)
        try:
            rows = await asyncio.to_thread(runtime.list_tables, connection_config(conn))
        except NotImplementedError:
            raise ValidationError(f"'{spec.label}' does not support listing tables.") from None
        except Exception as exc:  # noqa: BLE001
            raise ValidationError(str(exc)) from None
        tables: list[TableInfo] = []
        for row in rows:
            name = str(row.get("name", ""))
            schema = row.get("schema")
            qualified = f"{schema}.{name}" if schema else name
            tables.append(TableInfo(name=name, schema_name=schema, qualified=qualified))
        return tables

    async def _list_plugin_objects(
        self, spec: PluginConnectorSpec, runtime: ConnectorRuntime, conn: Connection, prefix: str
    ) -> list[str]:
        guard_plugin_host(conn.host)
        try:
            objects = await asyncio.to_thread(runtime.list_objects, connection_config(conn), prefix)
        except NotImplementedError:
            raise ValidationError(f"'{spec.label}' does not support listing objects.") from None
        except Exception as exc:  # noqa: BLE001
            raise ValidationError(str(exc)) from None
        return [str(o) for o in objects]

    # -- Internals ------------------------------------------------------

    async def _test_mlflow(self, uri: str | None) -> ConnectionTestResult:
        """Verify an MLflow tracking URI by listing one experiment (off the loop)."""
        from app.ml.tracking import test_tracking_uri

        try:
            await asyncio.to_thread(test_tracking_uri, uri or "")
        except (ValueError, ConnectorError) as exc:
            return ConnectionTestResult(ok=False, message=str(exc))
        return ConnectionTestResult(ok=True, message="MLflow tracking store reachable.")

    def _validate(
        self,
        provider: str,
        host: str | None,
        database: str | None,
        options: dict[str, Any] | None = None,
    ) -> None:
        plugin = plugin_connector(provider)
        if plugin is not None:
            validate_plugin_connection(plugin[0], host, options)
            return
        p = get_provider(provider)
        if is_mlflow_provider(p):
            if not database:
                raise ValidationError("MLflow needs a tracking URI (a folder path, sqlite:///…, or http://host:5000).")
            return
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
        result = await self.db.execute(select(Connection).where(func.lower(Connection.name) == name.lower()))
        return result.scalar_one_or_none()

    async def _get_or_raise(self, connection_id: str) -> Connection:
        result = await self.db.execute(select(Connection).where(Connection.id == connection_id))
        conn = result.scalar_one_or_none()
        if conn is None:
            raise NotFoundError("Connection", connection_id)
        return conn
