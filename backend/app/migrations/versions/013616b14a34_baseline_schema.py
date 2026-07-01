# SPDX-License-Identifier: AGPL-3.0-only
"""baseline schema

Single consolidated baseline replacing the prior migration chain. Ciaren has no
production deployments yet, so instead of carrying forward incremental history
this captures the current models directly (including the project_id
ondelete=RESTRICT fix and the schedules.is_enabled rename that used to be
separate migrations).

Revision ID: 013616b14a34
Revises:
Create Date: 2026-07-01 15:52:56.568477

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "013616b14a34"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("database", sa.Text(), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("password_env", sa.String(length=255), nullable=True),
        sa.Column("options_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(length=32), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_disabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("dataset_kind", sa.String(length=20), nullable=True),
        sa.Column("is_disabled", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_datasets_project_id"), "datasets", ["project_id"], unique=False)
    op.create_table(
        "flows",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("graph_json", sa.JSON(), nullable=False),
        sa.Column("is_disabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_flows_project_id"), "flows", ["project_id"], unique=False)
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=True),
        sa.Column("sample_json", sa.JSON(), nullable=True),
        sa.Column("profile_json", sa.JSON(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("source_run_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "version_number", name="uq_dataset_version"),
    )
    op.create_index(op.f("ix_dataset_versions_dataset_id"), "dataset_versions", ["dataset_id"], unique=False)
    op.create_table(
        "flow_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("flow_id", sa.String(length=36), nullable=False),
        sa.Column("input_dataset_id", sa.String(length=36), nullable=True),
        sa.Column("input_datasets_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("engine", sa.String(length=20), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("schedule_id", sa.String(length=36), nullable=True),
        sa.Column("output_location", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("logs_json", sa.JSON(), nullable=True),
        sa.Column("node_results_json", sa.JSON(), nullable=True),
        sa.Column("graph_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("parameters_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["flow_id"], ["flows.id"]),
        sa.ForeignKeyConstraint(["input_dataset_id"], ["datasets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_flow_runs_schedule_id"), "flow_runs", ["schedule_id"], unique=False)
    op.create_table(
        "schedules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("flow_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("cron", sa.String(length=255), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("engine", sa.String(length=20), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("catch_up", sa.Boolean(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("retry_delay_seconds", sa.Integer(), nullable=False),
        sa.Column("run_timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("parameters_json", sa.JSON(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_fired_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_id", sa.String(length=36), nullable=True),
        sa.Column("last_status", sa.String(length=20), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("disabled_reason", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["flow_id"], ["flows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_schedules_flow_id"), "schedules", ["flow_id"], unique=False)
    op.create_index(op.f("ix_schedules_next_run_at"), "schedules", ["next_run_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_schedules_next_run_at"), table_name="schedules")
    op.drop_index(op.f("ix_schedules_flow_id"), table_name="schedules")
    op.drop_table("schedules")
    op.drop_index(op.f("ix_flow_runs_schedule_id"), table_name="flow_runs")
    op.drop_table("flow_runs")
    op.drop_index(op.f("ix_dataset_versions_dataset_id"), table_name="dataset_versions")
    op.drop_table("dataset_versions")
    op.drop_index(op.f("ix_flows_project_id"), table_name="flows")
    op.drop_table("flows")
    op.drop_index(op.f("ix_datasets_project_id"), table_name="datasets")
    op.drop_table("datasets")
    op.drop_table("projects")
    op.drop_table("connections")
