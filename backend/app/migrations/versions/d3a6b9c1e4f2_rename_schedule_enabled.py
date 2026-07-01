# SPDX-License-Identifier: AGPL-3.0-only
"""rename schedules.enabled to is_enabled

Every other boolean flag in the schema (projects/flows/datasets.is_disabled)
uses the ``is_`` prefix; ``schedules.enabled`` was the one holdout.

Revision ID: d3a6b9c1e4f2
Revises: c7f2a4d8e1b9
Create Date: 2026-07-01 09:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3a6b9c1e4f2"
down_revision: Union[str, None] = "c7f2a4d8e1b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("schedules") as batch_op:
        batch_op.alter_column(
            "enabled", new_column_name="is_enabled", existing_type=sa.Boolean(), existing_nullable=False
        )


def downgrade() -> None:
    with op.batch_alter_table("schedules") as batch_op:
        batch_op.alter_column(
            "is_enabled", new_column_name="enabled", existing_type=sa.Boolean(), existing_nullable=False
        )
