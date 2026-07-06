# SPDX-License-Identifier: AGPL-3.0-only
"""dataset_name_unique_per_project

``datasets.name`` was globally unique, so two different projects could never
each have a dataset called e.g. "customers.csv" — uploading the same filename
to a second project silently matched the first project's dataset and
appended a new version to it there instead of creating an isolated dataset.
Replace the global unique constraint with one scoped to (project_id, name).

Revision ID: d4e5f6a7b8c9
Revises: c8d2e4f6a1b7
Create Date: 2026-07-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c8d2e4f6a1b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_CONSTRAINT_NAME = "uq_datasets_project_id_name"
OLD_CONSTRAINT_SNAPSHOT_NAME = "_datasets_name_unique_pre_fix"


def _find_name_only_unique_constraint(bind) -> str | None:
    """Find the (dialect-assigned) name of the unique constraint covering
    exactly ``name``, where the dialect actually reports one."""
    inspector = sa.inspect(bind)
    for uc in inspector.get_unique_constraints("datasets"):
        if uc["column_names"] == ["name"]:
            return uc["name"]
    return None


def _sqlite_pre_fix_snapshot() -> sa.Table:
    """The table shape as of revision c8d2e4f6a1b7, with the anonymous
    ``UNIQUE (name)`` constraint given an explicit name.

    SQLite reflects that constraint with `name=None` (it's a bare
    column-level UNIQUE, not a named one), so ``batch_alter_table`` has
    nothing to `drop_constraint` by name against the live reflection. Passing
    this snapshot via ``copy_from`` tells batch mode the constraint exists
    (under a name we choose) so it can be recreated without it.
    """
    return sa.Table(
        "datasets",
        sa.MetaData(),
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("dataset_kind", sa.String(length=20), nullable=True),
        sa.Column("is_disabled", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name", name=OLD_CONSTRAINT_SNAPSHOT_NAME),
    )


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    old_name = _find_name_only_unique_constraint(bind)

    if dialect == "sqlite" and old_name is None:
        with op.batch_alter_table("datasets", copy_from=_sqlite_pre_fix_snapshot()) as batch_op:
            batch_op.drop_constraint(OLD_CONSTRAINT_SNAPSHOT_NAME, type_="unique")
            batch_op.create_unique_constraint(NEW_CONSTRAINT_NAME, ["project_id", "name"])
    else:
        with op.batch_alter_table("datasets") as batch_op:
            if old_name:
                batch_op.drop_constraint(old_name, type_="unique")
            batch_op.create_unique_constraint(NEW_CONSTRAINT_NAME, ["project_id", "name"])


def downgrade() -> None:
    with op.batch_alter_table("datasets") as batch_op:
        batch_op.drop_constraint(NEW_CONSTRAINT_NAME, type_="unique")
        batch_op.create_unique_constraint("datasets_name_key", ["name"])
