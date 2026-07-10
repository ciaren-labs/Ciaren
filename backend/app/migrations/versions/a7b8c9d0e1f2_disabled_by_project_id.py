# SPDX-License-Identifier: AGPL-3.0-only
"""flow_and_dataset_disabled_by_project_id

Add ``disabled_by_project_id`` to ``flows`` and ``datasets``. ``disabled_reason``
alone only recorded *that* a project cascade disabled a row, not *which* project —
so if the row's ``project_id`` later changed (the project was deleted and the row
reassigned to Default, or the row was moved to another project directly) while
``disabled_reason`` stayed ``"project"``, an unrelated later disable/re-enable of
whatever project the row now sits in would wrongly revive it. This column pins the
cascade to the project that actually caused it; re-enabling only ever restores rows
where both the reason *and* the originating project match.

Backfill: a currently-disabled row tagged ``disabled_reason="project"`` was, before
this column existed, disabled by whichever project it's *currently* in (the bug this
migration fixes only bites on a *subsequent* project change, so at migration time the
current project_id is still the correct origin) — tag those with their current
project_id. Rows with any other reason (or none) are left NULL.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill(table_name: str) -> None:
    tbl = sa.table(
        table_name,
        sa.column("disabled_reason", sa.String),
        sa.column("disabled_by_project_id", sa.String),
        sa.column("project_id", sa.String),
    )
    op.execute(
        tbl.update().where(tbl.c.disabled_reason == "project").values(disabled_by_project_id=tbl.c.project_id)
    )


def upgrade() -> None:
    op.add_column("flows", sa.Column("disabled_by_project_id", sa.String(length=36), nullable=True))
    op.add_column("datasets", sa.Column("disabled_by_project_id", sa.String(length=36), nullable=True))
    _backfill("flows")
    _backfill("datasets")


def downgrade() -> None:
    op.drop_column("datasets", "disabled_by_project_id")
    op.drop_column("flows", "disabled_by_project_id")
