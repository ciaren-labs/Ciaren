# SPDX-License-Identifier: AGPL-3.0-only
"""flow_run_input_dataset_set_null

Give ``flow_runs.input_dataset_id`` an ``ON DELETE SET NULL`` rule. The column
is already nullable; the baseline schema created its foreign key with no
``ondelete`` action, which means RESTRICT-like behavior once enforcement is on.
SQLite historically ran with ``PRAGMA foreign_keys`` OFF (so purging a dataset
left the run's ``input_dataset_id`` dangling); the app engine now turns
enforcement ON (see ``app.core.database.enable_sqlite_foreign_keys``), and
without this rule ``dataset_service.purge_expired`` — which hard-deletes
soft-deleted datasets still referenced by *completed* runs — would raise
instead of purging. SET NULL keeps the run history row and clears the link.

SQLite cannot alter a foreign key in place, and the baseline FK is unnamed so
it cannot be dropped by name either. Batch mode (``batch_alter_table``, the
pattern this repo already uses for SQLite) rebuilds the table; passing a
``naming_convention`` gives the reflected unnamed FK a deterministic name we
can drop and recreate — the Alembic-documented recipe for exactly this case.
On PostgreSQL/MySQL the constraint got a server-generated name at create time,
so it is looked up via inspection and altered with plain DDL.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Applied to reflected unnamed constraints during the SQLite batch rebuild so
# the baseline's nameless FK becomes droppable.
_NAMING_CONVENTION = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
_FK_NAME = "fk_flow_runs_input_dataset_id_datasets"


def _existing_fk_name() -> str:
    """Name of the ``flow_runs.input_dataset_id`` FK on this database (non-SQLite:
    the server auto-named the baseline's unnamed constraint)."""
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys("flow_runs"):
        if fk.get("constrained_columns") == ["input_dataset_id"] and fk.get("name"):
            return str(fk["name"])
    return _FK_NAME


def _recreate_fk(ondelete: Union[str, None]) -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("flow_runs", naming_convention=_NAMING_CONVENTION) as batch_op:
            batch_op.drop_constraint(_FK_NAME, type_="foreignkey")
            batch_op.create_foreign_key(_FK_NAME, "datasets", ["input_dataset_id"], ["id"], ondelete=ondelete)
    else:
        name = _existing_fk_name()
        op.drop_constraint(name, "flow_runs", type_="foreignkey")
        op.create_foreign_key(name, "flow_runs", "datasets", ["input_dataset_id"], ["id"], ondelete=ondelete)


def upgrade() -> None:
    _recreate_fk("SET NULL")


def downgrade() -> None:
    _recreate_fk(None)
