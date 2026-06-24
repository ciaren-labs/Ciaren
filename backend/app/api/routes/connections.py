from fastapi import APIRouter, status

from app.api.deps import ConnectionServiceDep
from app.schemas.connection import (
    ConnectionCreate,
    ConnectionRead,
    ConnectionTestResult,
    ConnectionUpdate,
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


@router.get("/{connection_id}", response_model=ConnectionRead)
async def get_connection(connection_id: str, service: ConnectionServiceDep) -> ConnectionRead:
    return await service.get(connection_id)


@router.patch("/{connection_id}", response_model=ConnectionRead)
async def update_connection(
    connection_id: str, body: ConnectionUpdate, service: ConnectionServiceDep
) -> ConnectionRead:
    return await service.update(connection_id, body)


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(connection_id: str, service: ConnectionServiceDep) -> None:
    await service.delete(connection_id)


@router.post("/{connection_id}/test", response_model=ConnectionTestResult)
async def test_connection(connection_id: str, service: ConnectionServiceDep) -> ConnectionTestResult:
    return await service.test(connection_id)


@router.get("/{connection_id}/tables", response_model=list[TableInfo])
async def list_connection_tables(connection_id: str, service: ConnectionServiceDep) -> list[TableInfo]:
    return await service.list_tables(connection_id)


@router.get("/{connection_id}/objects", response_model=list[str])
async def list_connection_objects(
    connection_id: str, service: ConnectionServiceDep, prefix: str = ""
) -> list[str]:
    """List files/objects in a storage connection (S3 bucket, local folder, …)."""
    return await service.list_objects(connection_id, prefix)
