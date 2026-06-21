from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class PreviewService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def preview_transformation(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def preview_flow(self, flow_id: str, node_id: str | None = None) -> dict[str, Any]:
        raise NotImplementedError
