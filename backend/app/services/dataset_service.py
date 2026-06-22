from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any, cast

import aiofiles
import pandas as pd
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    ConflictError,
    DatasetParseError,
    FileTooLargeError,
    NotFoundError,
    UnsupportedFileTypeError,
)
from app.db.models.dataset import Dataset
from app.schemas.dataset import DatasetRead

_ALLOWED_EXTENSIONS: dict[str, str] = {
    ".csv": "csv",
    ".xlsx": "excel",
    ".xls": "excel",
    ".parquet": "parquet",
}

_SAMPLE_ROWS = 100


class DatasetService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        settings = get_settings()
        self.upload_dir = Path(settings.DATA_DIR) / "uploads"
        self.max_upload_bytes = settings.max_upload_bytes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def upload(self, file: UploadFile) -> DatasetRead:
        filename = file.filename or "upload"
        source_type = _validate_extension(filename)

        name = Path(filename).name
        await self._ensure_name_available(name)

        content = await file.read()
        if len(content) > self.max_upload_bytes:
            settings = get_settings()
            raise FileTooLargeError(settings.MAX_UPLOAD_SIZE_MB)

        df = _parse_dataframe(content, source_type, filename)
        schema = _extract_schema(df)
        sample = _df_to_records(df, _SAMPLE_ROWS)

        dataset = Dataset(
            name=name,
            source_type=source_type,
            location="",  # filled in after we know the id
            schema_json=schema,
            sample_json=sample,
        )
        self.db.add(dataset)
        await self.db.flush()  # populate dataset.id without committing

        save_path = self.upload_dir / _storage_filename(dataset.id, filename)
        await _write_file(content, save_path)

        dataset.location = str(save_path)
        await self.db.commit()
        await self.db.refresh(dataset)
        return DatasetRead.model_validate(dataset)

    async def list_all(self) -> list[DatasetRead]:
        result = await self.db.execute(select(Dataset).order_by(Dataset.created_at.desc()))
        return [DatasetRead.model_validate(d) for d in result.scalars().all()]

    async def get(self, dataset_id: str) -> DatasetRead:
        dataset = await self._get_or_raise(dataset_id)
        return DatasetRead.model_validate(dataset)

    async def get_schema(self, dataset_id: str) -> list[dict[str, Any]]:
        dataset = await self._get_or_raise(dataset_id)
        return dataset.schema_json or []

    async def get_sample(self, dataset_id: str) -> list[dict[str, Any]]:
        dataset = await self._get_or_raise(dataset_id)
        return dataset.sample_json or []

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _ensure_name_available(self, name: str) -> None:
        """Reject a duplicate dataset name (case-insensitive) with a clean 409.

        We pre-check rather than relying on the DB unique constraint so the
        client gets a helpful message instead of an opaque IntegrityError, and
        so the match is case-insensitive across dialects.
        """
        result = await self.db.execute(
            select(Dataset.id).where(func.lower(Dataset.name) == name.lower())
        )
        if result.scalar_one_or_none() is not None:
            raise ConflictError(
                f"A dataset named '{name}' already exists. "
                "Rename the file or delete the existing dataset first."
            )

    async def _get_or_raise(self, dataset_id: str) -> Dataset:
        result = await self.db.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset = result.scalar_one_or_none()
        if dataset is None:
            raise NotFoundError("Dataset", dataset_id)
        return dataset


# ---------------------------------------------------------------------------
# Pure helpers (no I/O, no DB — easy to unit test)
# ---------------------------------------------------------------------------


def _validate_extension(filename: str) -> str:
    """Return source_type string or raise UnsupportedFileTypeError."""
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(filename)
    return _ALLOWED_EXTENSIONS[ext]


def _parse_dataframe(content: bytes, source_type: str, filename: str) -> pd.DataFrame:
    buf = io.BytesIO(content)
    try:
        if source_type == "csv":
            return pd.read_csv(buf)
        if source_type == "excel":
            return pd.read_excel(buf)
        if source_type == "parquet":
            return pd.read_parquet(buf)
    except Exception as exc:
        raise DatasetParseError(filename, str(exc)) from exc
    raise DatasetParseError(filename, f"unknown source_type '{source_type}'")


def _extract_schema(df: pd.DataFrame) -> list[dict[str, Any]]:
    mapping = {
        "integer": pd.api.types.is_integer_dtype,
        "float": pd.api.types.is_float_dtype,
        "boolean": pd.api.types.is_bool_dtype,
        "datetime": pd.api.types.is_datetime64_any_dtype,
    }
    schema = []
    for col in df.columns:
        col_type = "string"
        for type_name, check in mapping.items():
            if check(df[col].dtype):
                col_type = type_name
                break
        schema.append({"name": col, "type": col_type})
    return schema


def _df_to_records(df: pd.DataFrame, n: int) -> list[dict[str, Any]]:
    """Serialize top-n rows to JSON-safe dicts (NaN → None, timestamps → ISO strings)."""
    records = json.loads(df.head(n).to_json(orient="records", date_format="iso"))
    return cast(list[dict[str, Any]], records)


def _storage_filename(dataset_id: str, original_filename: str) -> str:
    safe = re.sub(r"[^\w.\-]", "_", Path(original_filename).name)
    return f"{dataset_id}_{safe}"


async def _write_file(content: bytes, path: Path) -> None:
    async with aiofiles.open(path, "wb") as f:
        await f.write(content)
