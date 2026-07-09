# SPDX-License-Identifier: AGPL-3.0-only
"""connection_test_result

Add ``last_test_status`` and ``last_test_error`` to ``connections``. ``last_tested_at``
records only the *attempt* time, so on its own it can be mistaken for a passing
connection; these record the *result* (and its failure detail) of that last test.
Both nullable — Null means "never tested".

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("connections", sa.Column("last_test_status", sa.String(length=20), nullable=True))
    op.add_column("connections", sa.Column("last_test_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("connections", "last_test_error")
    op.drop_column("connections", "last_test_status")
