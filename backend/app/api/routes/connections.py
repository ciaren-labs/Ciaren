# SPDX-License-Identifier: AGPL-3.0-only
from fastapi import APIRouter, status

from app.api.deps import ConnectionServiceDep
from app.schemas.connection import (
    ConnectionCreate,
    ConnectionRead,
    ConnectionTestResult,
    ConnectionUpdate,
    KeyringAvailability,
    KeyringSecretStatus,
    KeyringSecretWrite,
    TableInfo,
)

router = APIRouter()


@router.get("", response_model=list[ConnectionRead])
async def list_connections(service: ConnectionServiceDep) -> list[ConnectionRead]:
    return await service.list_all()


@router.post("", response_model=ConnectionRead, status_code=status.HTTP_201_CREATED)
async def create_connection(body: ConnectionCreate, service: ConnectionServiceDep) -> ConnectionRead:
    return await service.create(body)


@router.get("/providers")
async def list_providers(service: ConnectionServiceDep) -> list[dict[str, object]]:
    """Supported providers and whether each driver is installed (for the UI)."""
    return service.providers()


@router.post("/test-config", response_model=ConnectionTestResult)
async def test_connection_config(body: ConnectionCreate, service: ConnectionServiceDep) -> ConnectionTestResult:
    """Test an unsaved connection payload before saving it."""
    return await service.test_config(body)


# -- OS keychain secrets (static paths declared before /{connection_id}) --------


@router.get("/keyring", response_model=KeyringAvailability)
async def keyring_availability(service: ConnectionServiceDep) -> KeyringAvailability:
    """Whether this host has a usable OS keychain (so the UI can offer or hide
    the 'save to keychain' action)."""
    return await service.keyring_status()


@router.post("/keyring", response_model=KeyringSecretStatus, status_code=status.HTTP_201_CREATED)
async def store_keyring_secret(body: KeyringSecretWrite, service: ConnectionServiceDep) -> KeyringSecretStatus:
    """Store a secret in the OS keychain and return its ``keyring:NAME`` reference.

    The value is written to the platform keychain and never persisted by Ciaren,
    returned, or logged. Refused with 409 if the name is already taken unless
    ``overwrite`` is set.
    """
    return await service.store_keyring_secret(body)


@router.get("/keyring/{name}", response_model=KeyringSecretStatus)
async def keyring_secret_status(name: str, service: ConnectionServiceDep) -> KeyringSecretStatus:
    """Whether a keychain secret exists — never returns its value."""
    return await service.keyring_secret_status(name)


@router.delete("/keyring/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyring_secret(name: str, service: ConnectionServiceDep) -> None:
    await service.remove_keyring_secret(name)


@router.get("/{connection_id}", response_model=ConnectionRead)
async def get_connection(connection_id: str, service: ConnectionServiceDep) -> ConnectionRead:
    return await service.get(connection_id)


@router.patch("/{connection_id}", response_model=ConnectionRead)
async def update_connection(
    connection_id: str, body: ConnectionUpdate, service: ConnectionServiceDep
) -> ConnectionRead:
    return await service.update(connection_id, body)


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(connection_id: str, service: ConnectionServiceDep, force: bool = False) -> None:
    """Delete a connection. Refused with 409 while flows still reference it,
    unless ``?force=true`` (those flows then fail at run time until repointed)."""
    await service.delete(connection_id, force=force)


@router.post("/{connection_id}/test", response_model=ConnectionTestResult)
async def test_connection(connection_id: str, service: ConnectionServiceDep) -> ConnectionTestResult:
    return await service.test(connection_id)


@router.get("/{connection_id}/tables", response_model=list[TableInfo])
async def list_connection_tables(connection_id: str, service: ConnectionServiceDep) -> list[TableInfo]:
    return await service.list_tables(connection_id)


@router.get("/{connection_id}/objects", response_model=list[str])
async def list_connection_objects(connection_id: str, service: ConnectionServiceDep, prefix: str = "") -> list[str]:
    """List files/objects in a storage connection (S3 bucket, local folder, …)."""
    return await service.list_objects(connection_id, prefix)
