"""add profile_json to dataset_versions

Revision ID: b2f1a9c4d7e3
Revises: 58ef4348266a
Create Date: 2026-06-22 18:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2f1a9c4d7e3"
down_revision: Union[str, None] = "58ef4348266a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable JSON column — additive and non-destructive on SQLite/Postgres/MySQL.
    op.add_column(
        "dataset_versions",
        sa.Column("profile_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("dataset_versions", "profile_json")
