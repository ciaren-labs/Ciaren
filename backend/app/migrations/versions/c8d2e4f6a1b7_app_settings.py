# SPDX-License-Identifier: AGPL-3.0-only
"""app_settings

Runtime overrides for the editable subset of ``Settings`` (see
``app.core.runtime_settings``). One row per overridden key; deleting the row
falls back to the environment variable / built-in default.

Revision ID: c8d2e4f6a1b7
Revises: a1f2c3d4e5b6
Create Date: 2026-07-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d2e4f6a1b7"
down_revision: Union[str, None] = "a1f2c3d4e5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
