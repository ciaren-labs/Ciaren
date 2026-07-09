# SPDX-License-Identifier: AGPL-3.0-only
"""flow_and_dataset_disabled_reason

Add ``disabled_reason`` to ``flows`` and ``datasets`` so re-enabling a project only
restores the flows/datasets the project cascade itself disabled — not ones the user
disabled or that a broken dataset dependency disabled. Nullable: NULL means
"enabled" (or a legacy row whose disable predates the column).

Backfill: before this feature a project-disable turned off *every* flow/dataset in
the project, so a row that is currently disabled AND sits in a currently-disabled
project was almost certainly disabled by that cascade — tag those ``"project"`` so
re-enabling the project restores them. Rows disabled inside an *enabled* project
were disabled for their own reasons and are left NULL (they stay disabled until
re-enabled directly), which is the safe side: the alternative (blanket-tagging all
disabled rows) would wrongly revive manually-disabled ones.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill(table_name: str) -> None:
    """Tag currently-disabled rows in a currently-disabled project as project-caused."""
    tbl = sa.table(
        table_name,
        sa.column("is_disabled", sa.Boolean),
        sa.column("disabled_reason", sa.String),
        sa.column("project_id", sa.String),
    )
    projects = sa.table("projects", sa.column("id", sa.String), sa.column("is_disabled", sa.Boolean))
    disabled_projects = sa.select(projects.c.id).where(projects.c.is_disabled.is_(True))
    op.execute(
        tbl.update()
        .where(
            tbl.c.is_disabled.is_(True),
            tbl.c.disabled_reason.is_(None),
            tbl.c.project_id.in_(disabled_projects),
        )
        .values(disabled_reason="project")
    )


def upgrade() -> None:
    op.add_column("flows", sa.Column("disabled_reason", sa.String(length=20), nullable=True))
    op.add_column("datasets", sa.Column("disabled_reason", sa.String(length=20), nullable=True))
    _backfill("flows")
    _backfill("datasets")


def downgrade() -> None:
    op.drop_column("datasets", "disabled_reason")
    op.drop_column("flows", "disabled_reason")
