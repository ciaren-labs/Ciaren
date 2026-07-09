"""Orphaned-run recovery runs at app startup, decoupled from the scheduler.

A run left in ``running`` by a crash/restart can never complete (single-process),
so startup marks it failed. This must happen even when ``SCHEDULER_ENABLED`` is
false — the whole point of the decoupling.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.models.flow import Flow
from app.db.models.run import FlowRun
from app.services.project_service import ProjectService
from app.services.run_recovery import recover_orphaned_runs


def _factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def _seed_runs(factory: async_sessionmaker[AsyncSession], statuses: list[str]) -> list[str]:
    async with factory() as db:
        pid = (await ProjectService(db).ensure_default()).id
        flow = Flow(name="f", project_id=pid, graph_json={})
        db.add(flow)
        await db.flush()
        runs = [FlowRun(flow_id=flow.id, status=s, started_at=datetime.now(UTC).replace(tzinfo=None)) for s in statuses]
        db.add_all(runs)
        await db.commit()
        return [r.id for r in runs]


async def test_recovers_running_and_leaves_others(engine: AsyncEngine) -> None:
    factory = _factory(engine)
    running_id, success_id, failed_id = await _seed_runs(factory, ["running", "success", "failed"])

    count = await recover_orphaned_runs(factory)
    assert count == 1

    async with factory() as db:
        recovered = await db.get(FlowRun, running_id)
        assert recovered is not None
        assert recovered.status == "failed"
        assert recovered.error_message == "Run interrupted by a server restart."
        assert recovered.finished_at is not None
        # untouched terminal runs keep their status
        assert (await db.get(FlowRun, success_id)).status == "success"
        assert (await db.get(FlowRun, failed_id)).status == "failed"


async def test_no_running_runs_is_noop(engine: AsyncEngine) -> None:
    factory = _factory(engine)
    await _seed_runs(factory, ["success", "cancelled"])
    assert await recover_orphaned_runs(factory) == 0


async def test_idempotent_second_call_recovers_nothing(engine: AsyncEngine) -> None:
    factory = _factory(engine)
    await _seed_runs(factory, ["running", "running"])
    assert await recover_orphaned_runs(factory) == 2
    assert await recover_orphaned_runs(factory) == 0


async def test_lifespan_recovers_even_when_scheduler_disabled(engine: AsyncEngine, monkeypatch) -> None:
    """The lifespan invokes recovery unconditionally, before (and regardless of)
    the scheduler — the regression this decoupling fixes."""
    import app.main as main

    factory = _factory(engine)
    (running_id,) = await _seed_runs(factory, ["running"])

    # Neutralize the heavy, DB/global-engine-bound startup steps so the test
    # exercises only the recovery wiring. Point recovery at the test engine.
    async def _noop(*args, **kwargs):  # noqa: ANN002, ANN003
        return None

    monkeypatch.setattr(main, "init_db", _noop)
    monkeypatch.setattr(main, "_seed_local_storage_safe", _noop)
    monkeypatch.setattr(main, "_seed_mlflow_connection_safe", _noop)
    monkeypatch.setattr(main, "_seed_demo_safe", _noop)
    monkeypatch.setattr(main, "AsyncSessionLocal", factory)
    monkeypatch.setattr("app.core.runtime_settings.load_and_apply_overrides", _noop)
    monkeypatch.setattr("app.plugins.ensure_plugins_loaded", lambda *a, **k: None)

    settings = main.get_settings()
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", False, raising=False)
    monkeypatch.setattr(settings, "SEED_DEMO", False, raising=False)
    monkeypatch.setattr(settings, "ML_ENABLED", False, raising=False)
    monkeypatch.setattr(main, "get_settings", lambda: settings)

    async with main.lifespan(main.app):
        pass

    async with factory() as db:
        recovered = await db.get(FlowRun, running_id)
        assert recovered is not None
        assert recovered.status == "failed"
