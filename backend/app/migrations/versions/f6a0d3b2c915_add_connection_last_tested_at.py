# SPDX-License-Identifier: AGPL-3.0-only
"""add connections.last_tested_at

Revision ID: f6a0d3b2c915
Revises: e5f9c2a31b88
Create Date: 2026-06-23 18:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a0d3b2c915"
down_revision: Union[str, None] = "e5f9c2a31b88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable timestamp: set whenever a connection is tested (pass or fail).
    op.add_column("connections", sa.Column("last_tested_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("connections", "last_tested_at")
