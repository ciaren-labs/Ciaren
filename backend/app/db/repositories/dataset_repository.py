from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.dataset import Dataset


class DatasetRepository:
    async def get_all(self, db: AsyncSession) -> list[Dataset]:
        raise NotImplementedError

    async def get_by_id(self, db: AsyncSession, dataset_id: str) -> Dataset | None:
        raise NotImplementedError

    async def create(self, db: AsyncSession, dataset: Dataset) -> Dataset:
        raise NotImplementedError

    async def delete(self, db: AsyncSession, dataset_id: str) -> None:
        raise NotImplementedError
