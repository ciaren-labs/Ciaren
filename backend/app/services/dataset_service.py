from __future__ import annotations

import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import aiofiles
import pandas as pd
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import (
    ConflictError,
    DatasetParseError,
    FileTooLargeError,
    NotFoundError,
    UnsupportedFileTypeError,
)
from app.db.models.dataset import Dataset
from app.db.models.dataset_version import DatasetVersion
from app.engine.backends import get_engine
from app.engine.profile import profile_frame
from app.schemas.dataset import DatasetRead, DatasetUpdate, DatasetVersionRead
from app.services.project_service import ProjectService

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

    async def upload(self, file: UploadFile, project_id: str | None = None) -> DatasetRead:
        """Store an upload as a new version.

        A new name creates a dataset at version 1; an existing name appends the
        next version (immutably), so flows pinned to an earlier version are
        unaffected. The file type must match the dataset's existing type.
        ``project_id`` only applies when creating a new dataset.
        """
        filename = file.filename or "upload"
        source_type = _validate_extension(filename)
        name = Path(filename).name

        content = await file.read()
        if len(content) > self.max_upload_bytes:
            settings = get_settings()
            raise FileTooLargeError(settings.MAX_UPLOAD_SIZE_MB)

        df = _parse_dataframe(content, source_type, filename)
        schema = _extract_schema(df)
        sample = _df_to_records(df, _SAMPLE_ROWS)
        profile = _profile_dataframe(df)

        dataset = await self._get_by_name(name)
        if dataset is None:
            resolved_project_id = await ProjectService(self.db).resolve_id(project_id)
            dataset = Dataset(
                name=name,
                source_type=source_type,
                project_id=resolved_project_id,
                dataset_kind="input",
            )
            self.db.add(dataset)
            await self.db.flush()  # populate dataset.id
            version_number = 1
        else:
            if dataset.source_type != source_type:
                raise ConflictError(
                    f"'{name}' is a {dataset.source_type.upper()} dataset; a new "
                    f"version must be {dataset.source_type.upper()}, not "
                    f"{source_type.upper()}. Use a different name for a new dataset."
                )
            version_number = await self._next_version_number(dataset.id)
            dataset.updated_at = datetime.now(UTC).replace(tzinfo=None)

        version = DatasetVersion(
            dataset_id=dataset.id,
            version_number=version_number,
            location="",  # filled in after we know the version id
            schema_json=schema,
            sample_json=sample,
            profile_json=profile,
            row_count=int(len(df)),
        )
        self.db.add(version)
        await self.db.flush()

        save_path = self.upload_dir / _storage_filename(version.id, filename)
        await _write_file(content, save_path)
        version.location = str(save_path)

        await self.db.commit()
        return await self._read(dataset.id)

    async def list_all(self, project_id: str | None = None) -> list[DatasetRead]:
        stmt = select(Dataset).options(selectinload(Dataset.versions)).order_by(Dataset.created_at.desc())
        if project_id is not None:
            stmt = stmt.where(Dataset.project_id == project_id)
        result = await self.db.execute(stmt)
        return [self._to_read(d) for d in result.scalars().all()]

    async def get(self, dataset_id: str) -> DatasetRead:
        return await self._read(dataset_id)

    async def get_schema(self, dataset_id: str, version: int | None = None) -> list[dict[str, Any]]:
        return (await self._version(dataset_id, version)).schema_json or []

    async def get_sample(self, dataset_id: str, version: int | None = None) -> list[dict[str, Any]]:
        return (await self._version(dataset_id, version)).sample_json or []

    async def get_profile(self, dataset_id: str, version: int | None = None) -> list[dict[str, Any]]:
        """Per-column statistics for a version. Computed at upload time; for
        versions created before profiling existed, it's computed on demand from
        the stored file and backfilled so later reads are instant."""
        ver = await self._version(dataset_id, version)
        if ver.profile_json:
            return ver.profile_json
        dataset = await self._get_or_raise(dataset_id)
        try:
            content = Path(ver.location).read_bytes()
            df = _parse_dataframe(content, dataset.source_type, ver.location)
        except Exception:  # noqa: BLE001 - missing/unreadable file → no profile
            return []
        profile = _profile_dataframe(df)
        ver.profile_json = profile
        await self.db.commit()
        return profile

    async def update(self, dataset_id: str, data: DatasetUpdate) -> DatasetRead:
        dataset = await self._get_or_raise(dataset_id)
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(dataset, field, value)
        dataset.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.db.commit()
        return await self._read(dataset.id)

    async def delete(self, dataset_id: str) -> None:
        result = await self.db.execute(
            select(Dataset).options(selectinload(Dataset.versions)).where(Dataset.id == dataset_id)
        )
        dataset = result.scalar_one_or_none()
        if dataset is None:
            raise NotFoundError("Dataset", dataset_id)
        await self.db.delete(dataset)
        await self.db.commit()

    async def list_versions(self, dataset_id: str) -> list[DatasetVersionRead]:
        await self._get_or_raise(dataset_id)
        result = await self.db.execute(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version_number.desc())
        )
        return [DatasetVersionRead.model_validate(v) for v in result.scalars().all()]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def get_version_location(self, dataset_id: str, version_number: int) -> Path:
        """Return the filesystem path for a specific dataset version."""
        version = await self._version(dataset_id, version_number)
        return Path(version.location)

    async def register_output(
        self,
        name: str,
        source_type: str,
        file_path: Path,
        project_id: str | None,
        run_id: str | None = None,
    ) -> DatasetRead:
        """Register a flow-generated output file as a versioned output dataset."""
        content = file_path.read_bytes()
        df = _parse_dataframe(content, source_type, str(file_path))
        schema = _extract_schema(df)
        sample = _df_to_records(df, _SAMPLE_ROWS)
        profile = _profile_dataframe(df)

        dataset = await self._get_by_name(name)
        if dataset is None:
            resolved_project_id = await ProjectService(self.db).resolve_id(project_id)
            dataset = Dataset(
                name=name,
                source_type=source_type,
                project_id=resolved_project_id,
                dataset_kind="output",
            )
            self.db.add(dataset)
            await self.db.flush()
            version_number = 1
        else:
            if dataset.source_type != source_type:
                raise ConflictError(
                    f"'{name}' is a {dataset.source_type.upper()} dataset; the output "
                    f"produces {source_type.upper()}. Use a different dataset name."
                )
            version_number = await self._next_version_number(dataset.id)
            dataset.updated_at = datetime.now(UTC).replace(tzinfo=None)

        version = DatasetVersion(
            dataset_id=dataset.id,
            version_number=version_number,
            location=str(file_path),
            schema_json=schema,
            sample_json=sample,
            profile_json=profile,
            row_count=int(len(df)),
            source_run_id=run_id,
        )
        self.db.add(version)
        await self.db.flush()
        return await self._read(dataset.id)

    def _to_read(self, dataset: Dataset) -> DatasetRead:
        """Build a DatasetRead, surfacing the latest version's schema/sample."""
        versions = sorted(dataset.versions, key=lambda v: v.version_number)
        latest = versions[-1] if versions else None
        return DatasetRead(
            id=dataset.id,
            name=dataset.name,
            source_type=dataset.source_type,
            dataset_kind=dataset.dataset_kind or "input",
            is_disabled=bool(dataset.is_disabled),
            project_id=dataset.project_id,
            latest_version=latest.version_number if latest else 0,
            version_count=len(versions),
            column_schema=latest.schema_json if latest else None,
            data_sample=latest.sample_json if latest else None,
            column_profile=latest.profile_json if latest else None,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
        )

    async def _read(self, dataset_id: str) -> DatasetRead:
        result = await self.db.execute(
            select(Dataset).options(selectinload(Dataset.versions)).where(Dataset.id == dataset_id)
        )
        dataset = result.scalar_one_or_none()
        if dataset is None:
            raise NotFoundError("Dataset", dataset_id)
        return self._to_read(dataset)

    async def _get_by_name(self, name: str) -> Dataset | None:
        result = await self.db.execute(select(Dataset).where(func.lower(Dataset.name) == name.lower()))
        return result.scalar_one_or_none()

    async def _next_version_number(self, dataset_id: str) -> int:
        result = await self.db.execute(
            select(func.max(DatasetVersion.version_number)).where(DatasetVersion.dataset_id == dataset_id)
        )
        return (result.scalar_one_or_none() or 0) + 1

    async def _version(self, dataset_id: str, version: int | None) -> DatasetVersion:
        await self._get_or_raise(dataset_id)
        stmt = select(DatasetVersion).where(DatasetVersion.dataset_id == dataset_id)
        if version is not None:
            stmt = stmt.where(DatasetVersion.version_number == version)
        else:
            stmt = stmt.order_by(DatasetVersion.version_number.desc())
        result = await self.db.execute(stmt.limit(1))
        found = result.scalar_one_or_none()
        if found is None:
            raise NotFoundError("Dataset version", f"{dataset_id}:{version if version is not None else 'latest'}")
        return found

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


def _profile_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Per-column statistics for a freshly parsed dataset version."""
    return profile_frame(get_engine("pandas"), df)


def _storage_filename(dataset_id: str, original_filename: str) -> str:
    safe = re.sub(r"[^\w.\-]", "_", Path(original_filename).name)
    return f"{dataset_id}_{safe}"


async def _write_file(content: bytes, path: Path) -> None:
    async with aiofiles.open(path, "wb") as f:
        await f.write(content)
