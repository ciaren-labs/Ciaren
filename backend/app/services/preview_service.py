from typing import Any


class PreviewService:
    async def preview_transformation(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def preview_flow(self, flow_id: str, node_id: str | None = None) -> dict[str, Any]:
        raise NotImplementedError
