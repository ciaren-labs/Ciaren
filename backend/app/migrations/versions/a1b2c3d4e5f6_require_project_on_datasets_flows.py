"""require a project on datasets and flows

Backfills any project-less datasets/flows into the (auto-created) Default project,
then makes ``project_id`` NOT NULL on both tables so a dataset or flow can never
exist without a project.

Revision ID: a1b2c3d4e5f6
Revises: f6a0d3b2c915
Create Date: 2026-06-24 10:00:00.000000

"""
import uuid
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f6a0d3b2c915"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _default_project_id(bind: sa.engine.Connection) -> str:
    """Return the default project's id, creating it if the DB has none yet."""
    row = bind.execute(
        sa.text("SELECT id FROM projects WHERE is_default ORDER BY created_at LIMIT 1")
    ).first()
    if row is None:  # fall back to a project literally named "Default"
        row = bind.execute(sa.text("SELECT id FROM projects WHERE name = 'Default' LIMIT 1")).first()
    if row is not None:
        return row[0]

    project_id = str(uuid.uuid4())
    now = datetime.utcnow()
    bind.execute(
        sa.text(
            "INSERT INTO projects "
            "(id, name, description, color, is_default, is_disabled, created_at, updated_at) "
            "VALUES (:id, :name, :description, :color, :is_default, :is_disabled, :now, :now)"
        ),
        {
            "id": project_id,
            "name": "Default",
            "description": "Your default workspace.",
            "color": "violet",
            "is_default": True,
            "is_disabled": False,
            "now": now,
        },
    )
    return project_id


def upgrade() -> None:
    bind = op.get_bind()
    default_id = _default_project_id(bind)

    # Adopt any orphaned rows before tightening the constraint.
    bind.execute(
        sa.text("UPDATE datasets SET project_id = :pid WHERE project_id IS NULL"), {"pid": default_id}
    )
    bind.execute(
        sa.text("UPDATE flows SET project_id = :pid WHERE project_id IS NULL"), {"pid": default_id}
    )

    with op.batch_alter_table("datasets") as batch:
        batch.alter_column("project_id", existing_type=sa.String(length=36), nullable=False)
    with op.batch_alter_table("flows") as batch:
        batch.alter_column("project_id", existing_type=sa.String(length=36), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("flows") as batch:
        batch.alter_column("project_id", existing_type=sa.String(length=36), nullable=True)
    with op.batch_alter_table("datasets") as batch:
        batch.alter_column("project_id", existing_type=sa.String(length=36), nullable=True)
