# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import asyncio
import io
import json
import logging
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import aiofiles
import pandas as pd
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.enums import DatasetKind
from app.core.exceptions import (
    ConflictError,
    DatasetParseError,
    FileTooLargeError,
    NotFoundError,
    UnsupportedFileTypeError,
)
from app.db.models.dataset import Dataset
from app.db.models.dataset_version import DatasetVersion
from app.db.models.flow import DISABLED_MANUAL, Flow
from app.db.models.run import FlowRun
from app.engine.backends import get_engine
from app.engine.ingest import (
    ParseOptionsError,
    detect_csv_options,
    is_default_dialect,
    validate_parse_options,
)
from app.engine.profile import profile_frame
from app.schemas.dataset import DatasetRead, DatasetUpdate, DatasetVersionRead
from app.services.project_service import ProjectService

logger = logging.getLogger("ciaren.datasets")

# Runs that may still read a dataset's files. "pending" covers the brief window
# between a FlowRun row being created and dataset paths actually being resolved.
_LIVE_RUN_STATUSES = ("pending", "running")

_ALLOWED_EXTENSIONS: dict[str, str] = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".xlsx": "excel",
    ".xls": "excel",
    ".parquet": "parquet",
    ".json": "json",
    ".jsonl": "jsonl",
    ".txt": "text",
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

    async def upload(
        self,
        file: UploadFile,
        project_id: str | None = None,
        parse_options: dict[str, Any] | None = None,
    ) -> DatasetRead:
        """Store an upload as a new version.

        A new name (within ``project_id``) creates a dataset at version 1; an
        existing name in that same project appends the next version
        (immutably), so flows pinned to an earlier version are unaffected. A
        name that collides with a dataset in a *different* project never
        matches — each project keeps its own isolated namespace. The file
        type must match the dataset's existing type.

        ``parse_options`` (delimiter/encoding/decimal for CSV/TSV, sheet for
        Excel) override auto-detection; whatever ends up used is recorded on
        the version, and the stored file is *normalized* to the default
        dialect so all later readers work with plain default reads.
        """
        filename = file.filename or "upload"
        source_type = _validate_extension(filename)
        name = Path(filename).name

        try:
            explicit = validate_parse_options(parse_options or {}, source_type)
        except ParseOptionsError as exc:
            raise DatasetParseError(filename, str(exc)) from exc

        content = await self._read_within_limit(file)

        # Parsing + profiling an upload (up to MAX_UPLOAD_SIZE_MB) is heavy
        # pandas work: run it in a worker thread so a big file can't stall the
        # event loop (and with it every other request and the scheduler).
        def _ingest() -> tuple[
            pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]
        ]:
            options: dict[str, Any] = {}
            if source_type in ("csv", "tsv"):
                options = {**detect_csv_options(content, source_type), **explicit}
            elif source_type == "excel":
                options = dict(explicit)
                sheet = options.get("sheet")
                if isinstance(sheet, str) and sheet.isdigit():
                    # Name first, index fallback: a sheet literally named "2"
                    # wins over the 0-based index reading. Record whichever
                    # interpretation succeeded so exported code matches.
                    try:
                        _parse_dataframe(content, source_type, filename, {"sheet": sheet})
                    except DatasetParseError:
                        options["sheet"] = int(sheet)
            frame, schema_, sample_, profile_ = _parse_and_describe(content, source_type, filename, options)
            return frame, schema_, sample_, profile_, options

        df, schema, sample, profile, used_options = await asyncio.to_thread(_ingest)
        normalized = not is_default_dialect(used_options, source_type)

        resolved_project_id = await ProjectService(self.db).resolve_id(project_id)
        dataset = await self._get_by_name(name, resolved_project_id)
        if dataset is None:
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
            # Re-uploading to a soft-deleted dataset revives it.
            dataset.is_disabled = False
            dataset.disabled_reason = None
            dataset.disabled_by_project_id = None
            dataset.deleted_at = None

        version = DatasetVersion(
            dataset_id=dataset.id,
            version_number=version_number,
            location="",  # filled in after we know the version id
            schema_json=schema,
            sample_json=sample,
            profile_json=profile,
            parse_options_json=used_options if normalized else None,
            row_count=int(len(df)),
        )
        self.db.add(version)
        await self.db.flush()

        save_path = self.upload_dir / _storage_filename(version.id, filename)
        if normalized:
            # Store the canonical form (UTF-8, default separators, the chosen
            # sheet) so both engines, previews, runs, and lazy scans read this
            # version with plain defaults — the original dialect can never
            # produce a different frame at run time than the upload showed.
            await asyncio.to_thread(_write_normalized, df, save_path, source_type)
        else:
            await _write_file(content, save_path)
        version.location = str(save_path)

        await self.db.commit()
        return await self._read(dataset.id)

    async def list_all(self, project_id: str | None = None, include_deleted: bool = False) -> list[DatasetRead]:
        stmt = select(Dataset).options(selectinload(Dataset.versions)).order_by(Dataset.created_at.desc())
        if project_id is not None:
            stmt = stmt.where(Dataset.project_id == project_id)
        if not include_deleted:
            stmt = stmt.where(Dataset.deleted_at.is_(None))
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

        # Read + parse + profile off the event loop — same reasoning as upload().
        def _backfill() -> list[dict[str, Any]]:
            content = Path(ver.location).read_bytes()
            df = _parse_dataframe(content, dataset.source_type, ver.location)
            return _profile_dataframe(df)

        try:
            profile = await asyncio.to_thread(_backfill)
        except Exception:  # noqa: BLE001 - missing/unreadable file → no profile
            return []
        ver.profile_json = profile
        await self.db.commit()
        return profile

    async def update(self, dataset_id: str, data: DatasetUpdate) -> DatasetRead:
        dataset = await self._get_or_raise(dataset_id)
        updates = data.model_dump(exclude_unset=True)
        # A direct is_disabled *change* is the user's own decision — tag it MANUAL
        # (or clear on enable) so a later project re-enable doesn't revive a dataset
        # the user turned off. Guard on an actual change so an unrelated PATCH that
        # echoes is_disabled doesn't overwrite a project-cascade reason.
        disabled_changed = "is_disabled" in updates and updates["is_disabled"] != dataset.is_disabled
        for field, value in updates.items():
            setattr(dataset, field, value)
        if disabled_changed:
            dataset.disabled_reason = DISABLED_MANUAL if updates["is_disabled"] else None
            dataset.disabled_by_project_id = None
        # Re-enabling a soft-deleted dataset is a restore — leaving deleted_at set
        # would make it purgeable while appearing live.
        if updates.get("is_disabled") is False:
            dataset.deleted_at = None
        dataset.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.db.commit()
        return await self._read(dataset.id)

    async def delete(self, dataset_id: str, purge: bool = False, force: bool = False) -> None:
        """Soft-delete by default: mark the dataset deleted but retain its rows and
        files so it can be restored and historical runs still resolve. ``purge=True``
        hard-deletes the dataset, its versions, and their files immediately.

        Refuses (409) if a Production-aliased registered model was trained on this
        dataset, or a run is currently reading it, unless ``force=True``."""
        result = await self.db.execute(
            select(Dataset).options(selectinload(Dataset.versions)).where(Dataset.id == dataset_id)
        )
        dataset = result.scalar_one_or_none()
        if dataset is None:
            raise NotFoundError("Dataset", dataset_id)
        if not force:
            await self._guard_production_dependency(dataset_id)
            if purge:
                await self._guard_active_run_dependency(dataset_id)
        if purge:
            self._remove_version_files(dataset)
            await self.db.delete(dataset)
        else:
            dataset.is_disabled = True
            dataset.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        await self.db.commit()

    async def _guard_active_run_dependency(self, dataset_id: str) -> None:
        """Raise ConflictError (409) if a pending/running run is currently reading
        this dataset. Purging unlinks version files immediately (unlike soft-delete),
        so a run in the middle of reading one would fail with a raw filesystem error
        instead of the clean "purged" message a *pre-run* purge produces."""
        flows = await self._flows_with_active_run_on_dataset(dataset_id)
        if flows:
            shown = ", ".join(f"'{name}'" for name in flows[:5])
            more = f" and {len(flows) - 5} more" if len(flows) > 5 else ""
            raise ConflictError(
                f"This dataset is being read by an in-progress run of {len(flows)} flow(s): "
                f"{shown}{more}. Wait for the run to finish, or purge with force=true "
                "(the run will fail)."
            )

    async def _flows_with_active_run_on_dataset(self, dataset_id: str) -> list[str]:
        """Names of flows with a pending/running run whose resolved inputs include
        this dataset. Checked in Python (not a JSON-column query) since
        ``input_datasets_json`` shape isn't portable across SQLite/Postgres, and the
        number of concurrently active runs is always small."""
        result = await self.db.execute(
            select(FlowRun, Flow.name)
            .join(Flow, Flow.id == FlowRun.flow_id)
            .where(FlowRun.status.in_(_LIVE_RUN_STATUSES))
        )
        names = []
        for run, flow_name in result.all():
            dataset_ids = {run.input_dataset_id} if run.input_dataset_id else set()
            for entry in run.input_datasets_json or []:
                if isinstance(entry, dict) and entry.get("dataset_id"):
                    dataset_ids.add(entry["dataset_id"])
            if dataset_id in dataset_ids:
                names.append(flow_name)
        return names

    async def restore(self, dataset_id: str) -> DatasetRead:
        """Undo a soft-delete, bringing the dataset back to live."""
        dataset = await self._get_or_raise(dataset_id)
        dataset.is_disabled = False
        dataset.disabled_reason = None
        dataset.disabled_by_project_id = None
        dataset.deleted_at = None
        dataset.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.db.commit()
        return await self._read(dataset.id)

    async def purge_expired(self, now: datetime | None = None) -> int:
        """Hard-delete soft-deleted datasets whose retention window has elapsed,
        removing their files. Returns the number purged."""
        retention_days = get_settings().DATASET_RETENTION_DAYS
        cutoff = (now or datetime.now(UTC).replace(tzinfo=None)) - timedelta(days=retention_days)
        result = await self.db.execute(
            select(Dataset)
            .options(selectinload(Dataset.versions))
            .where(Dataset.deleted_at.is_not(None), Dataset.deleted_at < cutoff)
        )
        expired = list(result.scalars().all())
        purged = 0
        for dataset in expired:
            flows = await self._flows_with_active_run_on_dataset(dataset.id)
            if flows:
                # Deferred, not skipped: it stays past retention and is retried
                # on the next sweep once the run(s) using it have finished.
                logger.warning("Deferring purge of dataset %s: in use by an active run of %s", dataset.id, flows)
                continue
            self._remove_version_files(dataset)
            await self.db.delete(dataset)
            purged += 1
        if purged:
            await self.db.commit()
        return purged

    async def _guard_production_dependency(self, dataset_id: str) -> None:
        """Raise ConflictError (409) if a Production model was trained on this
        dataset. No-op when the ML extension isn't active (no registry to check)."""
        from app.ml.availability import ml_extension_ready

        if not ml_extension_ready():
            return
        from app.ml.registry_deps import production_models_for_dataset
        from app.ml.tracking import resolve_tracking_uri

        tracking_uri = await resolve_tracking_uri(self.db)
        models = await asyncio.to_thread(production_models_for_dataset, dataset_id, tracking_uri)
        if models:
            raise ConflictError(
                f"A Production model ({', '.join(models)}) was trained on this dataset. "
                f"Demote it from Production before deleting, or delete with force=true."
            )

    def _remove_version_files(self, dataset: Dataset) -> None:
        """Best-effort removal of each version's file from disk."""
        for version in dataset.versions:
            if not version.location:
                continue
            try:
                Path(version.location).unlink(missing_ok=True)
            except OSError:
                pass  # never fail a purge on a stray filesystem error

    async def list_versions(self, dataset_id: str, limit: int = 100, offset: int = 0) -> list[DatasetVersionRead]:
        """Newest-first page of a dataset's versions. Output datasets accrue one
        version per run, so this is paginated to stay bounded in production."""
        await self._get_or_raise(dataset_id)
        result = await self.db.execute(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version_number.desc())
            .offset(offset)
            .limit(limit)
        )
        return [DatasetVersionRead.model_validate(v) for v in result.scalars().all()]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _read_within_limit(self, file: UploadFile) -> bytes:
        """Read the upload in bounded chunks, rejecting once it exceeds the limit.

        Reading the whole body first and *then* checking ``len()`` would let a
        large upload exhaust memory before the limit is ever applied. Streaming in
        chunks caps memory at roughly the limit plus one chunk and fails fast.
        """
        chunk_size = 1024 * 1024  # 1 MiB
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > self.max_upload_bytes:
                raise FileTooLargeError(get_settings().MAX_UPLOAD_SIZE_MB)
            chunks.append(chunk)
        return b"".join(chunks)

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

        # Runs when a flow finishes: the read + parse + profile of a possibly
        # large output must not stall the event loop — same reasoning as upload().
        def _describe_output() -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
            return _parse_and_describe(file_path.read_bytes(), source_type, str(file_path))

        df, schema, sample, profile = await asyncio.to_thread(_describe_output)

        resolved_project_id = await ProjectService(self.db).resolve_id(project_id)
        dataset = await self._get_by_name(name, resolved_project_id)
        if dataset is None:
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
            # A run writing to this output name again revives a soft-deleted /
            # disabled output dataset — same revive-on-write semantics as upload().
            # Otherwise the new version would be born already-deleted and later
            # purged, and the resolver would refuse to reuse it as an input.
            dataset.is_disabled = False
            dataset.disabled_reason = None
            dataset.disabled_by_project_id = None
            dataset.deleted_at = None

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
            dataset_kind=DatasetKind(dataset.dataset_kind or DatasetKind.INPUT),
            is_disabled=bool(dataset.is_disabled),
            deleted_at=dataset.deleted_at,
            project_id=dataset.project_id,
            latest_version=latest.version_number if latest else 0,
            version_count=len(versions),
            column_schema=latest.schema_json if latest else None,
            data_sample=latest.sample_json if latest else None,
            column_profile=latest.profile_json if latest else None,
            parse_options=latest.parse_options_json if latest else None,
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

    async def _get_by_name(self, name: str, project_id: str) -> Dataset | None:
        result = await self.db.execute(
            select(Dataset).where(
                func.lower(Dataset.name) == name.lower(),
                Dataset.project_id == project_id,
            )
        )
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


def _parse_dataframe(
    content: bytes, source_type: str, filename: str, options: dict[str, Any] | None = None
) -> pd.DataFrame:
    """Parse upload bytes. ``options`` describe the original dialect (see
    app/engine/ingest.py); omitted keys fall back to the format's defaults."""
    opts = options or {}
    buf = io.BytesIO(content)
    try:
        if source_type == "csv":
            return pd.read_csv(
                buf,
                sep=opts.get("delimiter", ","),
                encoding=opts.get("encoding", "utf-8"),
                decimal=opts.get("decimal", "."),
            )
        if source_type == "tsv":
            return pd.read_csv(
                buf,
                sep="\t",
                encoding=opts.get("encoding", "utf-8"),
                decimal=opts.get("decimal", "."),
            )
        if source_type == "excel":
            frame = pd.read_excel(buf, sheet_name=opts.get("sheet", 0))
            assert isinstance(frame, pd.DataFrame)  # single sheet requested, never a dict
            return frame
        if source_type == "parquet":
            return pd.read_parquet(buf)
        if source_type == "json":
            return pd.read_json(buf)
        if source_type == "jsonl":
            return pd.read_json(buf, lines=True)
        if source_type == "text":
            # splitlines() is robust — newer pandas rejects sep="\n".
            return pd.DataFrame({"text": content.decode("utf-8").splitlines()})
    except Exception as exc:
        raise DatasetParseError(filename, str(exc)) from exc
    raise DatasetParseError(filename, f"unknown source_type '{source_type}'")


def _write_normalized(df: pd.DataFrame, path: Path, source_type: str) -> None:
    """Persist the parsed frame in the format's default dialect."""
    if source_type == "csv":
        df.to_csv(path, index=False)
    elif source_type == "tsv":
        df.to_csv(path, index=False, sep="\t")
    elif source_type == "excel":
        df.to_excel(path, index=False)
    else:  # pragma: no cover - only dialect-bearing types are ever normalized
        raise ValueError(f"cannot normalize source_type {source_type!r}")


def _parse_and_describe(
    content: bytes, source_type: str, filename: str, options: dict[str, Any] | None = None
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse a file and derive its schema, sample, and profile in one go.

    Bundled so callers can push the whole CPU-bound pipeline into a single
    ``asyncio.to_thread`` call instead of blocking the event loop per step.
    """
    df = _parse_dataframe(content, source_type, filename, options)
    return df, _extract_schema(df), _df_to_records(df, _SAMPLE_ROWS), _profile_dataframe(df)


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
