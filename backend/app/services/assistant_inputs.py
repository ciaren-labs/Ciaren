# SPDX-License-Identifier: AGPL-3.0-only
"""Only schema metadata is loaded. Both preview and confirmation use the project boundary."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.exceptions import ValidationError
from app.db.models.dataset import Dataset
from app.db.models.dataset_version import DatasetVersion
from app.services.assistant_graph import Graph


@dataclass(frozen=True)
class InputVersion:
    dataset: str
    version_id: str
    number: int
    fmt: str
    follows_latest: bool

    def available(self, project: str) -> ColumnElement[bool]:
        exact = (
            select(DatasetVersion.id)
            .join(Dataset)
            .where(
                Dataset.project_id == project,
                Dataset.id == self.dataset,
                Dataset.deleted_at.is_(None),
                Dataset.is_disabled.is_(False),
                Dataset.source_type == self.fmt,
                DatasetVersion.id == self.version_id,
                DatasetVersion.version_number == self.number,
            )
            .exists()
        )
        if self.follows_latest:
            newer = (
                select(DatasetVersion.id)
                .where(DatasetVersion.dataset_id == self.dataset, DatasetVersion.version_number > self.number)
                .exists()
            )
            return exact & ~newer
        return exact


@dataclass
class InputSchema:
    version: InputVersion
    columns: dict[str, str]

    def binding(self) -> Graph:
        return {"dataset_id": self.version.dataset, "dataset_version": self.version.number}

    def shared_columns(self, names: bool) -> list[Graph]:
        known = {
            "int64",
            "float64",
            "object",
            "string",
            "bool",
            "integer",
            "float",
            "boolean",
            "datetime",
            "datetime64[ns]",
        }
        return [
            {"index": i, "type": dtype if dtype in known else "other", **({"name": name[:96]} if names else {})}
            for i, (name, dtype) in enumerate(list(self.columns.items())[:64])
        ]


async def resolve_input(db: AsyncSession, project: str, requested: str | None, node: Graph | None) -> InputSchema:
    cfg = node["data"]["config"] if node else {}
    dataset = cfg.get("dataset_id") if node else requested
    pinned = cfg.get("dataset_version")
    if not isinstance(dataset, str) or not 1 <= len(dataset) <= 64:
        raise ValidationError("Select an available project dataset.")
    if pinned is not None and (type(pinned) is not int or pinned < 1):
        raise ValidationError("Invalid input version.")
    stmt = (
        select(DatasetVersion.id, DatasetVersion.version_number, DatasetVersion.schema_json, Dataset.source_type)
        .join(Dataset)
        .where(
            Dataset.id == dataset,
            Dataset.project_id == project,
            Dataset.is_disabled.is_(False),
            Dataset.deleted_at.is_(None),
        )
    )
    if pinned is not None:
        stmt = stmt.where(DatasetVersion.version_number == pinned)
    row = (await db.execute(stmt.order_by(DatasetVersion.version_number.desc()).limit(1))).first()
    if row is None:
        raise ValidationError("Choose an available dataset in this flow's project.")
    version_id, number, schema, fmt = row
    if (
        node
        and (cfg.get("format", "csv") if node["type"] == "fileInput" else node["type"].removesuffix("Input")) != fmt
    ):
        raise ValidationError("Input node type differs from its dataset format.")
    return InputSchema(
        InputVersion(dataset, version_id, number, fmt, pinned is None),
        {str(c["name"]): str(c.get("type", "other")) for c in schema or []},
    )
