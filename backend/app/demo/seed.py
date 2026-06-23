"""Idempotent seeding of the built-in demo project.

:func:`seed_demo` creates a ``Demo`` project containing four sample datasets and
several example flows. It is safe to call on every boot: if a project named
``Demo`` already exists it returns immediately without touching anything.

Datasets are registered exactly like a real upload — the CSV file is written
under ``DATA_DIR/uploads`` and a :class:`Dataset` + :class:`DatasetVersion` row
(with ``schema_json``, ``sample_json`` and ``profile_json``) is created — by
reusing the helper functions in :mod:`app.services.dataset_service`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.dataset import Dataset
from app.db.models.dataset_version import DatasetVersion
from app.db.models.flow import Flow
from app.db.models.project import Project
from app.demo.datasets import build_demo_frames
from app.demo.flows import build_demo_flows
from app.services.dataset_service import (
    _df_to_records,
    _extract_schema,
    _profile_dataframe,
    _storage_filename,
)

DEMO_PROJECT_NAME = "Demo"
_SAMPLE_ROWS = 100


async def seed_demo(db: AsyncSession) -> Project | None:
    """Create the demo project if it does not already exist.

    Returns the created :class:`Project`, or ``None`` when seeding was skipped
    because the demo project (or a name clash) already exists. Idempotent.
    """
    if await _demo_exists(db):
        return None

    project = Project(
        name=DEMO_PROJECT_NAME,
        description="A built-in tour of FlowFrame: sample data and example "
        "cleaning, aggregation, and join pipelines.",
        color="emerald",
        is_default=False,
    )
    db.add(project)
    await db.flush()  # assign project.id

    dataset_ids = await _seed_datasets(db, project.id)
    _seed_flows(db, project.id, dataset_ids)

    await db.commit()
    return project


async def _demo_exists(db: AsyncSession) -> bool:
    result = await db.execute(
        select(Project).where(func.lower(Project.name) == DEMO_PROJECT_NAME.lower())
    )
    return result.scalar_one_or_none() is not None


async def _seed_datasets(db: AsyncSession, project_id: str) -> dict[str, str]:
    """Write each demo CSV and register it as a versioned dataset.

    Returns a map of CSV file name -> dataset id so flows can wire their inputs.
    """
    settings = get_settings()
    upload_dir = Path(settings.DATA_DIR) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    dataset_ids: dict[str, str] = {}
    for filename, df in build_demo_frames().items():
        dataset = Dataset(
            name=filename,
            source_type="csv",
            project_id=project_id,
            dataset_kind="input",
        )
        db.add(dataset)
        await db.flush()  # assign dataset.id

        version = DatasetVersion(
            dataset_id=dataset.id,
            version_number=1,
            location="",  # set once we know the version id
            schema_json=_extract_schema(df),
            sample_json=_df_to_records(df, _SAMPLE_ROWS),
            profile_json=_profile_dataframe(df),
            row_count=int(len(df)),
        )
        db.add(version)
        await db.flush()  # assign version.id

        save_path = upload_dir / _storage_filename(version.id, filename)
        _write_csv(df, save_path)
        version.location = str(save_path)

        dataset_ids[filename] = dataset.id

    return dataset_ids


def _seed_flows(db: AsyncSession, project_id: str, dataset_ids: dict[str, str]) -> None:
    for name, description, graph in build_demo_flows(dataset_ids):
        db.add(
            Flow(
                name=name,
                description=description,
                project_id=project_id,
                graph_json=graph,
            )
        )


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)
