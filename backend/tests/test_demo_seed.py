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
    """Seed the demo project with DATA_DIR pointed at an isolated temp dir.

    ML is pinned OFF here so the base ETL datasets/flows are seeded deterministically
    regardless of whether the [ml] extra is installed in the test environment.
    """
    from app.core.config import get_settings

    monkeypatch.setenv("FLOWFRAME_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLOWFRAME_ML_ENABLED", "false")
    get_settings.cache_clear()
    (tmp_path / "uploads").mkdir(parents=True, exist_ok=True)

    await seed_demo(db_session)
    yield db_session

    get_settings.cache_clear()


_EXPECTED_ML_DATASETS = {"iris.csv", "house_prices.csv"}
_EXPECTED_ML_FLOWS = {
    "Iris — Quick Classifier",
    "Iris — Train, Validate & Evaluate",
    "House Prices — Regression",
    "Iris — PCA Explore",
}


@pytest.fixture
async def ml_demo_db(db_session: AsyncSession, tmp_path, monkeypatch):
    """Seed the demo project with ML enabled, so the ML datasets/flows are added."""
    pytest.importorskip("mlflow")
    pytest.importorskip("sklearn")
    from app.core.config import get_settings

    monkeypatch.setenv("FLOWFRAME_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLOWFRAME_ML_ENABLED", "true")
    monkeypatch.setenv("FLOWFRAME_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    get_settings.cache_clear()
    (tmp_path / "uploads").mkdir(parents=True, exist_ok=True)

    await seed_demo(db_session)
    yield db_session

    get_settings.cache_clear()


async def _project(db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(func.lower(Project.name) == DEMO_PROJECT_NAME.lower()))
    return result.scalar_one()


async def test_demo_project_created(demo_db: AsyncSession) -> None:
    project = await _project(demo_db)
    assert project.name == DEMO_PROJECT_NAME
    assert project.is_default is False
    assert project.description


async def test_four_datasets_created(demo_db: AsyncSession) -> None:
    project = await _project(demo_db)
    result = await demo_db.execute(select(Dataset).where(Dataset.project_id == project.id))
    datasets = result.scalars().all()
    assert {d.name for d in datasets} == _EXPECTED_DATASETS

    # Each dataset has exactly one version with a real, readable file + profile.
    for dataset in datasets:
        vresult = await demo_db.execute(select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id))
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
async def test_every_flow_executes_end_to_end(demo_db: AsyncSession, tmp_path, engine_name: str) -> None:
    project = await _project(demo_db)
    result = await demo_db.execute(select(Flow).where(Flow.project_id == project.id))
    flows = result.scalars().all()
    assert flows

    out_dir = tmp_path / f"out_{engine_name}"
    out_dir.mkdir()

    import json

    for flow in flows:
        dataset_paths, _ = await build_dataset_paths(demo_db, flow.graph_json)
        run = FlowExecutor().run_with_results(flow.graph_json, dataset_paths, out_dir, engine_name=engine_name)
        assert run.error is None, f"{flow.name} ({engine_name}) failed: {run.error}"
        assert run.output_paths, f"{flow.name} produced no output"
        for path in run.output_paths.values():
            assert path.is_file()
        # Node results are persisted to a JSON column — they must serialize
        # (e.g. date-parsing flows produce datetime samples).
        json.dumps([r.as_dict() for r in run.node_results])


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


async def test_no_ml_content_when_ml_disabled(demo_db: AsyncSession) -> None:
    project = await _project(demo_db)
    datasets = (await demo_db.execute(select(Dataset).where(Dataset.project_id == project.id))).scalars().all()
    flows = (await demo_db.execute(select(Flow).where(Flow.project_id == project.id))).scalars().all()
    assert {d.name for d in datasets} == _EXPECTED_DATASETS
    assert {f.name for f in flows} == _EXPECTED_FLOWS


async def test_ml_datasets_and_flows_seeded(ml_demo_db: AsyncSession) -> None:
    project = await _project(ml_demo_db)
    datasets = (await ml_demo_db.execute(select(Dataset).where(Dataset.project_id == project.id))).scalars().all()
    flows = (await ml_demo_db.execute(select(Flow).where(Flow.project_id == project.id))).scalars().all()
    assert _EXPECTED_ML_DATASETS <= {d.name for d in datasets}
    assert _EXPECTED_ML_FLOWS <= {f.name for f in flows}
    # ML flow graphs are correctly wired (multi-output split + model handles).
    for flow in flows:
        if flow.name in _EXPECTED_ML_FLOWS:
            validate_graph(flow.graph_json, require_output=True)


async def test_ml_demo_flows_execute_end_to_end(ml_demo_db: AsyncSession, tmp_path) -> None:
    project = await _project(ml_demo_db)
    result = await ml_demo_db.execute(
        select(Flow).where(Flow.project_id == project.id, Flow.name.in_(_EXPECTED_ML_FLOWS))
    )
    flows = result.scalars().all()
    assert {f.name for f in flows} == _EXPECTED_ML_FLOWS

    out_dir = tmp_path / "ml_out"
    out_dir.mkdir()
    for flow in flows:
        dataset_paths, _ = await build_dataset_paths(ml_demo_db, flow.graph_json)
        engine = flow.graph_json.get("engine", "pandas")
        run = FlowExecutor().run_with_results(flow.graph_json, dataset_paths, out_dir, engine_name=engine)
        assert run.error is None, f"{flow.name} failed: {run.error}"
        # Every ML demo produces a result: either a file output or a trained model
        # (a train-only flow like "Quick Classifier" persists a model, no file).
        trained = any(r.model_uri for r in run.node_results)
        assert run.output_paths or trained, f"{flow.name} produced no output"


async def test_seed_run_creates_runs_with_seed_trigger(demo_db: AsyncSession) -> None:
    """The run-on-seed path runs each demo flow once, tagged trigger='seed'."""
    from app.db.models.run import FlowRun
    from app.schemas.run import FlowRunCreate
    from app.services.execution_service import ExecutionService

    project = await _project(demo_db)
    flows = (await demo_db.execute(select(Flow).where(Flow.project_id == project.id))).scalars().all()

    for flow in flows:
        run = await ExecutionService(demo_db).run(flow.id, FlowRunCreate(), trigger="seed")
        assert run.trigger == "seed"
        assert run.status == "success"

    seed_runs = (await demo_db.execute(select(FlowRun).where(FlowRun.trigger == "seed"))).scalars().all()
    assert len(seed_runs) == len(flows)


async def test_seeder_is_idempotent(demo_db: AsyncSession) -> None:
    # A second call must not create a duplicate project / datasets / flows.
    second = await seed_demo(demo_db)
    assert second is None

    project_count = await demo_db.scalar(
        select(func.count()).select_from(Project).where(func.lower(Project.name) == DEMO_PROJECT_NAME.lower())
    )
    assert project_count == 1

    project = await _project(demo_db)
    dataset_count = await demo_db.scalar(
        select(func.count()).select_from(Dataset).where(Dataset.project_id == project.id)
    )
    flow_count = await demo_db.scalar(select(func.count()).select_from(Flow).where(Flow.project_id == project.id))
    assert dataset_count == len(_EXPECTED_DATASETS)
    assert flow_count == len(_EXPECTED_FLOWS)
