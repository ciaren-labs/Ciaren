# SPDX-License-Identifier: AGPL-3.0-only
"""add flow parameters: flow_runs.parameters_json, schedules.parameters_json

Revision ID: b8d2c6e1f3a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-24 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d2c6e1f3a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Both nullable JSON columns — additive and non-destructive on every backend.
    # flow_runs.parameters_json: the resolved parameter values a run executed with.
    # schedules.parameters_json: per-schedule parameter overrides for fired runs.
    op.add_column("flow_runs", sa.Column("parameters_json", sa.JSON(), nullable=True))
    op.add_column("schedules", sa.Column("parameters_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("schedules", "parameters_json")
    op.drop_column("flow_runs", "parameters_json")
