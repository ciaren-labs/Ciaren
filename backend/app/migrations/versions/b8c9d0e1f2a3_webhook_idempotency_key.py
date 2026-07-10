# SPDX-License-Identifier: AGPL-3.0-only
"""flow_run_webhook_idempotency_key

Add ``webhook_idempotency_key`` to ``flow_runs`` plus a unique (flow_id,
webhook_idempotency_key) constraint. POST /flows/{id}/trigger blocks until the
run completes; a caller (CI/CD pipeline, Airflow) that times out waiting and
retries would previously start a second full run of the same flow with no way
to detect the retry. A caller can now send an ``Idempotency-Key`` header; a
retry with the same key on the same flow returns the original run instead of
starting a new one. NULL (no header sent) never collides with anything, so
this is fully opt-in and does not change behavior for existing callers.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("flow_runs", sa.Column("webhook_idempotency_key", sa.String(length=255), nullable=True))
    with op.batch_alter_table("flow_runs") as batch_op:
        batch_op.create_unique_constraint(
            "uq_flow_run_webhook_idempotency_key", ["flow_id", "webhook_idempotency_key"]
        )


def downgrade() -> None:
    with op.batch_alter_table("flow_runs") as batch_op:
        batch_op.drop_constraint("uq_flow_run_webhook_idempotency_key", type_="unique")
    op.drop_column("flow_runs", "webhook_idempotency_key")
