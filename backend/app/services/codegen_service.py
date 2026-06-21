from sqlalchemy.ext.asyncio import AsyncSession


class CodegenService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def export_python(self, flow_id: str) -> str:
        raise NotImplementedError
