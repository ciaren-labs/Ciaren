from sqlalchemy.ext.asyncio import AsyncSession


class CodegenService:
    async def export_python(self, db: AsyncSession, flow_id: str) -> str:
        raise NotImplementedError
