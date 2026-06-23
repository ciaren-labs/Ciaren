import asyncio
from collections.abc import Awaitable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.flow import Flow
from app.db.models.run import FlowRun
from app.engine.backends import available_engines
from app.engine.executor import FlowExecutor, RunResult
from app.engine.process_pool import (
    get_process_pool,
    recycle_process_pool,
    run_graph_in_process,
)
from app.engine.run_context import run_context
from app.schemas.run import FlowRunCreate, FlowRunRead, FlowRunSummary
from app.services.dataset_resolver import build_dataset_paths
from app.services.dataset_service import DatasetService
from app.services.sql_resolver import materialize_sql_inputs, push_sql_outputs
from app.services.storage_resolver import materialize_storage_inputs, push_storage_outputs

_OUTPUT_TYPE_MAP = {"csvOutput": "csv", "excelOutput": "excel", "parquetOutput": "parquet"}
_EXECUTION_MODES = ("thread", "process")


class ExecutionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    async def run(
        self,
        flow_id: str,
        data: FlowRunCreate,
        *,
        schedule_id: str | None = None,
        trigger: str = "manual",
    ) -> FlowRunRead:
        flow = await self._get_flow(flow_id)

        if flow.is_disabled:
            raise ValidationError("This flow is disabled and cannot be run.")

        self._guard_ml_enabled(flow.graph_json)

        engine = data.engine or self.settings.DEFAULT_ENGINE
        if engine not in available_engines():
            raise ValidationError(f"Unknown engine '{engine}'. Available: {', '.join(available_engines())}.")

        execution_mode = self.settings.EXECUTION_MODE
        if execution_mode not in _EXECUTION_MODES:
            raise ValidationError(f"Unknown execution mode '{execution_mode}'. Allowed: {', '.join(_EXECUTION_MODES)}.")

        run = FlowRun(
            flow_id=flow_id,
            input_dataset_id=data.input_dataset_id,
            engine=engine,
            trigger=trigger,
            schedule_id=schedule_id,
            status="running",
            started_at=datetime.now(UTC).replace(tzinfo=None),
            # Snapshot the graph at trigger time: the flow can be edited later, but a
            # run (especially an ML training run) must stay reproducible.
            graph_snapshot_json=flow.graph_json,
        )
        self.db.add(run)
        await self.db.flush()  # assign run.id without committing

        timeout = await self._effective_timeout(data, schedule_id)

        try:
            dataset_paths, resolved_versions = await build_dataset_paths(self.db, flow.graph_json)
            # Record every resolved input so the run view can list them all.
            run.input_datasets_json = resolved_versions
            # Default the run's dataset to the first input so runs are filterable
            # by dataset even when the caller didn't pass one explicitly.
            if run.input_dataset_id is None and resolved_versions:
                run.input_dataset_id = resolved_versions[0]["dataset_id"]

            output_dir = Path(self.settings.DATA_DIR) / "outputs" / run.id
            output_dir.mkdir(parents=True, exist_ok=True)
            # Read any SQL inputs live (in this async parent, which holds the DB
            # session + secrets) and snapshot them to parquet, so the off-loop
            # executor only ever touches plain files.
            sql_input_paths = await materialize_sql_inputs(self.db, flow.graph_json, output_dir)
            storage_input_paths = await materialize_storage_inputs(self.db, flow.graph_json, output_dir)
            # The executor is synchronous (pandas/polars compute); offload it off
            # the event loop so it never blocks — keeping the API responsive while
            # a manual or scheduled run is in flight. It takes no DB session, so
            # running it off-loop (in a thread or a separate process) is safe.
            # Context ML nodes read to tag MLflow runs (back-pointers + dataset link).
            dataset_ids: list[str] = [v["dataset_id"] for v in resolved_versions]
            ctx_data: dict[str, Any] = {"flow_id": flow_id, "run_id": run.id, "dataset_ids": dataset_ids}
            compute: Awaitable[RunResult]
            if execution_mode == "process":
                # True multi-core parallelism: the GIL is not shared across
                # processes. Only the picklable compute crosses the boundary.
                # ContextVars don't cross processes, so pass the context explicitly.
                loop = asyncio.get_running_loop()
                compute = loop.run_in_executor(
                    get_process_pool(),
                    run_graph_in_process,
                    flow.graph_json,
                    dataset_paths,
                    output_dir,
                    engine,
                    sql_input_paths,
                    storage_input_paths,
                    ctx_data,
                )
            else:
                compute = asyncio.to_thread(
                    FlowExecutor().run_with_results,
                    flow.graph_json,
                    dataset_paths,
                    output_dir,
                    engine_name=engine,
                    sql_input_paths=sql_input_paths,
                    storage_input_paths=storage_input_paths,
                )

            # to_thread copies this context into the worker thread (thread mode);
            # process mode re-establishes it from ctx_data inside the worker.
            with run_context(flow_id=flow_id, run_id=run.id, dataset_ids=dataset_ids):
                if timeout > 0:
                    result = await asyncio.wait_for(compute, timeout=timeout)
                else:
                    result = await compute

            run.node_results_json = [r.as_dict() for r in result.node_results]
            if result.error is None:
                # Deliver SQL sinks before declaring success — a write failure
                # must fail the run (the output never reached the database).
                await push_sql_outputs(self.db, flow.graph_json, result.output_paths)
                await push_storage_outputs(self.db, flow.graph_json, result.output_paths)
                run.status = "success"
                # Store a path relative to the outputs dir so we never leak the
                # absolute server filesystem layout in API responses.
                run.output_location = (
                    f"{run.id}/{next(iter(result.output_paths.values())).name}" if result.output_paths else None
                )
                elapsed_ms = None
                if run.started_at:
                    elapsed = datetime.now(UTC).replace(tzinfo=None) - run.started_at
                    elapsed_ms = round(elapsed.total_seconds() * 1000, 2)
                run.logs_json = [
                    {
                        "level": "info",
                        "message": (f"Flow executed in {elapsed_ms} ms, wrote {len(result.output_paths)} output(s)"),
                        "duration_ms": elapsed_ms,
                    },
                    {
                        "level": "info",
                        "message": "Resolved dataset versions",
                        "versions": resolved_versions,
                    },
                ]
                # Register named output nodes as reusable output datasets (best-effort).
                if result.output_paths:
                    dataset_service = DatasetService(self.db)
                    graph_nodes = (flow.graph_json or {}).get("nodes", [])
                    for node_id, out_path in result.output_paths.items():
                        node = next((n for n in graph_nodes if n["id"] == node_id), None)
                        if node:
                            config = node.get("data", {}).get("config", {})
                            dataset_name = (config.get("dataset_name") or "").strip()
                            if dataset_name:
                                src_type = _OUTPUT_TYPE_MAP.get(node.get("type", ""), "csv")
                                try:
                                    await dataset_service.register_output(
                                        name=dataset_name,
                                        source_type=src_type,
                                        file_path=out_path,
                                        project_id=flow.project_id,
                                        run_id=run.id,
                                    )
                                except Exception:  # noqa: BLE001
                                    pass  # Don't fail the run on dataset registration errors
            else:
                run.status = "failed"
                run.error_message = result.error
                run.logs_json = [{"level": "error", "message": result.error}]
        except asyncio.TimeoutError:
            # In process mode, drop the pool so the abandoned worker doesn't starve
            # later runs; in thread mode the thread keeps running but the run is
            # abandoned and the event loop is freed.
            if execution_mode == "process":
                recycle_process_pool()
            run.status = "failed"
            run.error_message = f"Run exceeded the {timeout}s time limit and was abandoned."
            run.logs_json = [{"level": "error", "message": run.error_message}]
        except Exception as exc:  # noqa: BLE001 - capture any failure on the run record
            run.status = "failed"
            run.error_message = str(exc)
            run.logs_json = [{"level": "error", "message": str(exc)}]
        finally:
            run.finished_at = datetime.now(UTC).replace(tzinfo=None)
            await self.db.commit()
            await self.db.refresh(run)

        return FlowRunRead.model_validate(run)

    async def get(self, run_id: str) -> FlowRunRead:
        result = await self.db.execute(select(FlowRun).where(FlowRun.id == run_id))
        run = result.scalar_one_or_none()
        if run is None:
            raise NotFoundError("FlowRun", run_id)
        return FlowRunRead.model_validate(run)

    _SORT_FIELDS = {
        "created_at": FlowRun.created_at,
        "started_at": FlowRun.started_at,
        "status": FlowRun.status,
    }

    async def list_runs(
        self,
        flow_id: str | None = None,
        project_id: str | None = None,
        dataset_id: str | None = None,
        schedule_id: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 100,
        offset: int = 0,
    ) -> list[FlowRunSummary]:
        sort_col = self._SORT_FIELDS.get(sort_by, FlowRun.created_at)
        order_fn = asc if sort_order == "asc" else desc
        stmt = (
            select(FlowRun, Flow.name, Flow.project_id)
            .join(Flow, Flow.id == FlowRun.flow_id, isouter=True)
            .order_by(order_fn(sort_col))
        )
        if flow_id is not None:
            stmt = stmt.where(FlowRun.flow_id == flow_id)
        if project_id is not None:
            stmt = stmt.where(Flow.project_id == project_id)
        if dataset_id is not None:
            stmt = stmt.where(FlowRun.input_dataset_id == dataset_id)
        if schedule_id is not None:
            stmt = stmt.where(FlowRun.schedule_id == schedule_id)
        if status is not None:
            stmt = stmt.where(FlowRun.status == status)
        if started_after is not None:
            stmt = stmt.where(FlowRun.created_at >= started_after)
        if started_before is not None:
            stmt = stmt.where(FlowRun.created_at <= started_before)
        stmt = stmt.offset(offset).limit(limit)

        result = await self.db.execute(stmt)
        return [
            FlowRunSummary(
                id=run.id,
                flow_id=run.flow_id,
                flow_name=flow_name,
                project_id=flow_project_id,
                input_dataset_id=run.input_dataset_id,
                input_datasets=run.input_datasets_json,
                status=run.status,
                engine=run.engine,
                trigger=run.trigger,
                schedule_id=run.schedule_id,
                output_location=run.output_location,
                started_at=run.started_at,
                finished_at=run.finished_at,
                created_at=run.created_at,
            )
            for run, flow_name, flow_project_id in result.all()
        ]

    # -- Internals ------------------------------------------------------

    def _guard_ml_enabled(self, graph: dict[str, Any] | None) -> None:
        """Reject running a graph that uses ML nodes when the ML extension is off.

        ML node types are registered whenever the [ml] libraries are importable, so
        without this a crafted graph could execute ML nodes even with ML_ENABLED
        false. Keeps the feature flag a real gate, not just a UI/palette toggle.
        """
        from app.core.exceptions import MLNotEnabledError
        from app.engine.registry import ml_node_types
        from app.ml.availability import ml_extension_ready

        ml_types = ml_node_types()
        if not ml_types:
            return
        graph_types = {n.get("type") for n in (graph or {}).get("nodes", [])}
        if graph_types & ml_types and not ml_extension_ready():
            raise MLNotEnabledError(
                "This flow uses machine-learning nodes, but ML support is not enabled "
                "on this server (set ML_ENABLED and install the [ml] extra)."
            )

    async def _effective_timeout(self, data: FlowRunCreate, schedule_id: str | None) -> int:
        """Resolve the run timeout (seconds, 0 = no limit) by precedence:
        explicit per-run override > the schedule's override > the global setting."""
        if data.timeout_seconds is not None:
            return data.timeout_seconds
        if schedule_id is not None:
            from app.db.models.schedule import Schedule

            result = await self.db.execute(
                select(Schedule.run_timeout_seconds).where(Schedule.id == schedule_id)
            )
            schedule_timeout = result.scalar_one_or_none()
            if schedule_timeout is not None:
                return schedule_timeout
        return self.settings.RUN_TIMEOUT_SECONDS

    async def _get_flow(self, flow_id: str) -> Flow:
        result = await self.db.execute(select(Flow).where(Flow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        return flow
