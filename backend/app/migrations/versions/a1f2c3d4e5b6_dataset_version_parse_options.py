# SPDX-License-Identifier: AGPL-3.0-only
"""dataset_versions.parse_options_json

The dialect the original upload used (delimiter/encoding/decimal/sheet), kept
for UI transparency and exported-script generation; the stored file itself is
normalized at ingest so engines keep reading with defaults.

Revision ID: a1f2c3d4e5b6
Revises: 013616b14a34
Create Date: 2026-07-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f2c3d4e5b6"
down_revision: Union[str, None] = "013616b14a34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("dataset_versions", sa.Column("parse_options_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("dataset_versions", "parse_options_json")
