# SPDX-License-Identifier: AGPL-3.0-only
"""fix datasets/flows project_id FK to ondelete=RESTRICT

The baseline migration created ``datasets.project_id`` / ``flows.project_id``
with ``ondelete='SET NULL'``, back when the column was nullable. A later
migration (a1b2c3d4e5f6) made the column NOT NULL but never updated the FK
action, leaving a live schema where a project delete would try to null out a
NOT NULL column instead of being blocked outright. The models have always
declared ``ondelete="RESTRICT"`` (matching what ``create_all`` produces on a
fresh database) — this migration brings Alembic-provisioned databases in line
with that.

Revision ID: c7f2a4d8e1b9
Revises: b8d2c6e1f3a7
Create Date: 2026-07-01 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7f2a4d8e1b9"
down_revision: Union[str, None] = "b8d2c6e1f3a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _datasets_table(metadata: sa.MetaData, ondelete: str) -> sa.Table:
    return sa.Table(
        "datasets",
        metadata,
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("dataset_kind", sa.String(length=20), nullable=True),
        sa.Column("is_disabled", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete=ondelete, name="fk_datasets_project_id_projects"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def _flows_table(metadata: sa.MetaData, ondelete: str) -> sa.Table:
    return sa.Table(
        "flows",
        metadata,
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete=ondelete, name="fk_flows_project_id_projects"),
            nullable=False,
        ),
        sa.Column("graph_json", sa.JSON(), nullable=False),
        sa.Column("is_disabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def _apply_sqlite(ondelete: str) -> None:
    # SQLite can't ALTER a FK's ondelete action in place; batch mode rebuilds
    # the table. copy_from must fully describe the target schema (indexes are
    # not replayed automatically and are re-added below).
    metadata = sa.MetaData()
    with op.batch_alter_table("datasets", copy_from=_datasets_table(metadata, ondelete), recreate="always"):
        pass
    op.create_index("ix_datasets_project_id", "datasets", ["project_id"])

    with op.batch_alter_table("flows", copy_from=_flows_table(metadata, ondelete), recreate="always"):
        pass
    op.create_index("ix_flows_project_id", "flows", ["project_id"])


def _apply_direct(ondelete: str) -> None:
    inspector = sa.inspect(op.get_bind())
    for table, constraint_name in (
        ("datasets", "fk_datasets_project_id_projects"),
        ("flows", "fk_flows_project_id_projects"),
    ):
        for fk in inspector.get_foreign_keys(table):
            if fk["constrained_columns"] == ["project_id"]:
                if fk["name"]:
                    op.drop_constraint(fk["name"], table, type_="foreignkey")
                break
        op.create_foreign_key(constraint_name, table, "projects", ["project_id"], ["id"], ondelete=ondelete)


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        _apply_sqlite("RESTRICT")
    else:
        _apply_direct("RESTRICT")


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        _apply_sqlite("SET NULL")
    else:
        _apply_direct("SET NULL")
