"""add datasets.deleted_at for soft-delete

Revision ID: e5f9c2a31b88
Revises: d4e7b1f9a2c5
Create Date: 2026-06-23 13:45:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f9c2a31b88"
down_revision: Union[str, None] = "d4e7b1f9a2c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable timestamp: set when a dataset is soft-deleted; files are retained
    # until the retention window elapses and the dataset is purged.
    op.add_column("datasets", sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("datasets", "deleted_at")
