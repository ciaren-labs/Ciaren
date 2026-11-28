# SPDX-License-Identifier: AGPL-3.0-only
"""Assistant API keys saved from the Connections page. Secrets stay in the OS keychain."""

import sqlalchemy as sa
from alembic import op

revision = "b2c4d6e8f0a1"
down_revision = "ea641bc97f21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Startup create_all can already have introduced this additive table.
    if not op.get_context().as_sql and sa.inspect(op.get_bind()).has_table("assistant_keys"):
        return
    op.create_table(
        "assistant_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("effort", sa.String(16), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("assistant_keys")
