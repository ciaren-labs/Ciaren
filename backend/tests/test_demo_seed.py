"""Tests for the built-in demo project seeding.

Seeds against the in-memory test DB and asserts the project/datasets/flows are
created, every flow graph validates, every flow actually executes end-to-end,
and the seeder is idempotent.
"""

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.dataset import Dataset
from app.db.models.dataset_version import DatasetVersion
from app.db.models.flow import Flow
from app.db.models.project import Project
from app.demo import DEMO_PROJECT_NAME, seed_demo
from app.engine.executor import FlowExecutor, dataset_ref_key
from app.engine.graph import validate_graph
from app.services.dataset_resolver import build_dataset_paths

_EXPECTED_DATASETS = {"customers.csv", "orders.csv", "products.csv", "order_items.csv"}
_EXPECTED_FLOWS = {
    "Clean Customers",
    "Order Revenue by Month",
    "Customer Orders Join",
    "Full Sales Mart",
}


@pytest.fixture
async def demo_db(db_session: AsyncSession, tmp_path, monkeypatch):
    """Seed the demo project with DATA_DIR pointed at an isolated temp dir."""
    from app.core.config import get_settings

    monkeypatch.setenv("FLOWFRAME_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    (tmp_path / "uploads").mkdir(parents=True, exist_ok=True)

    await seed_demo(db_session)
    yield db_session

    get_settings.cache_clear()


async def _project(db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(func.lower(Project.name) == DEMO_PROJECT_NAME.lower())
    )
    return result.scalar_one()


async def test_demo_project_created(demo_db: AsyncSession) -> None:
    project = await _project(demo_db)
    assert project.name == DEMO_PROJECT_NAME
    assert project.is_default is False
    assert project.description


async def test_four_datasets_created(demo_db: AsyncSession) -> None:
    project = await _project(demo_db)
    result = await demo_db.execute(
        select(Dataset).where(Dataset.project_id == project.id)
    )
    datasets = result.scalars().all()
    assert {d.name for d in datasets} == _EXPECTED_DATASETS

    # Each dataset has exactly one version with a real, readable file + profile.
    for dataset in datasets:
        vresult = await demo_db.execute(
            select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id)
        )
        versions = vresult.scalars().all()
        assert len(versions) == 1
        version = versions[0]
        assert version.version_number == 1
        assert version.row_count > 0
        assert version.schema_json
        assert version.sample_json
        assert version.profile_json
        assert Path(version.location).is_file()


async def test_flows_created_and_valid(demo_db: AsyncSession) -> None:
    project = await _project(demo_db)
    result = await demo_db.execute(select(Flow).where(Flow.project_id == project.id))
    flows = result.scalars().all()
    assert {f.name for f in flows} == _EXPECTED_FLOWS

    for flow in flows:
        # Each graph is correctly wired (raises on any wiring/structure error).
        validate_graph(flow.graph_json, require_output=True)


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
async def test_every_flow_executes_end_to_end(
    demo_db: AsyncSession, tmp_path, engine_name: str
) -> None:
    project = await _project(demo_db)
    result = await demo_db.execute(select(Flow).where(Flow.project_id == project.id))
    flows = result.scalars().all()
    assert flows

    out_dir = tmp_path / f"out_{engine_name}"
    out_dir.mkdir()

    for flow in flows:
        dataset_paths, _ = await build_dataset_paths(demo_db, flow.graph_json)
        run = FlowExecutor().run_with_results(
            flow.graph_json, dataset_paths, out_dir, engine_name=engine_name
        )
        assert run.error is None, f"{flow.name} ({engine_name}) failed: {run.error}"
        assert run.output_paths, f"{flow.name} produced no output"
        for path in run.output_paths.values():
            assert path.is_file()


async def test_dataset_paths_resolve_to_pinned_version(demo_db: AsyncSession) -> None:
    """Input nodes pin version 1, so resolution keys must match that pin."""
    result = await demo_db.execute(select(Flow).where(Flow.name == "Clean Customers"))
    flow = result.scalar_one()
    paths, resolved = await build_dataset_paths(demo_db, flow.graph_json)
    assert paths
    assert all(r["version_number"] == 1 for r in resolved)
    # Keys are the engine's (dataset_id, version) ref keys.
    for node in flow.graph_json["nodes"]:
        if node["type"] == "csvInput":
            config = node["data"]["config"]
            key = dataset_ref_key(config["dataset_id"], config.get("dataset_version"))
            assert key in paths


async def test_seeder_is_idempotent(demo_db: AsyncSession) -> None:
    # A second call must not create a duplicate project / datasets / flows.
    second = await seed_demo(demo_db)
    assert second is None

    project_count = await demo_db.scalar(
        select(func.count()).select_from(Project).where(
            func.lower(Project.name) == DEMO_PROJECT_NAME.lower()
        )
    )
    assert project_count == 1

    project = await _project(demo_db)
    dataset_count = await demo_db.scalar(
        select(func.count()).select_from(Dataset).where(Dataset.project_id == project.id)
    )
    flow_count = await demo_db.scalar(
        select(func.count()).select_from(Flow).where(Flow.project_id == project.id)
    )
    assert dataset_count == len(_EXPECTED_DATASETS)
    assert flow_count == len(_EXPECTED_FLOWS)
