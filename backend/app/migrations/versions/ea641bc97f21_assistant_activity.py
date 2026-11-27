# SPDX-License-Identifier: AGPL-3.0-only
"""Durable, flow-scoped assistant activity."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME as MySQLDateTime

revision = "ea641bc97f21"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_context().dialect.name in {"mysql", "mariadb"}:
        op.alter_column(
            "flows", "updated_at", existing_type=sa.DateTime(), type_=MySQLDateTime(fsp=6), existing_nullable=False
        )
    # Startup create_all can already have introduced this additive table.
    if not op.get_context().as_sql and sa.inspect(op.get_bind()).has_table("assistant_activity"):
        return
    op.create_table(
        "assistant_activity",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("flow_id", sa.String(36), sa.ForeignKey("flows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime().with_variant(MySQLDateTime(fsp=6), "mysql", "mariadb"), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("reverses", sa.String(32), unique=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("inverse", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_assistant_activity_timeline", "assistant_activity", ["flow_id", "project_id", "created_at", "id"]
    )


def downgrade() -> None:
    op.drop_table("assistant_activity")
    if op.get_context().dialect.name in {"mysql", "mariadb"}:
        op.alter_column(
            "flows", "updated_at", existing_type=MySQLDateTime(fsp=6), type_=sa.DateTime(), existing_nullable=False
        )
