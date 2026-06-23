"""add ML run fields: flow_runs.graph_snapshot_json, schedules.run_timeout_seconds

Revision ID: d4e7b1f9a2c5
Revises: c3d8e5f1a042
Create Date: 2026-06-23 12:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e7b1f9a2c5"
down_revision: Union[str, None] = "c3d8e5f1a042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Both columns are nullable — additive and non-destructive on every backend.
    # ETL and ML runs both benefit from graph_snapshot_json (reproducibility).
    op.add_column("flow_runs", sa.Column("graph_snapshot_json", sa.JSON(), nullable=True))
    op.add_column("schedules", sa.Column("run_timeout_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("schedules", "run_timeout_seconds")
    op.drop_column("flow_runs", "graph_snapshot_json")
