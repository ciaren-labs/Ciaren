from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.flow import Flow
from app.db.models.run import FlowRun
from app.engine.backends import available_engines
from app.engine.executor import FlowExecutor
from app.schemas.run import FlowRunCreate, FlowRunRead, FlowRunSummary
from app.services.dataset_resolver import build_dataset_paths


class ExecutionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    async def run(self, flow_id: str, data: FlowRunCreate) -> FlowRunRead:
        flow = await self._get_flow(flow_id)

        engine = data.engine or "pandas"
        if engine not in available_engines():
            raise ValidationError(
                f"Unknown engine '{engine}'. Available: {', '.join(available_engines())}."
            )

        run = FlowRun(
            flow_id=flow_id,
            input_dataset_id=data.input_dataset_id,
            engine=engine,
            status="running",
            started_at=datetime.utcnow(),
        )
        self.db.add(run)
        await self.db.flush()  # assign run.id without committing

        try:
            dataset_paths, resolved_versions = await build_dataset_paths(self.db, flow.graph_json)
            # Default the run's dataset to the first input so runs are filterable
            # by dataset even when the caller didn't pass one explicitly.
            if run.input_dataset_id is None and resolved_versions:
                run.input_dataset_id = resolved_versions[0]["dataset_id"]

            output_dir = Path(self.settings.DATA_DIR) / "outputs" / run.id
            output_dir.mkdir(parents=True, exist_ok=True)
            result = FlowExecutor().run_with_results(
                flow.graph_json, dataset_paths, output_dir, engine_name=engine
            )

            run.node_results_json = [r.as_dict() for r in result.node_results]
            if result.error is None:
                run.status = "success"
                # Store a path relative to the outputs dir so we never leak the
                # absolute server filesystem layout in API responses.
                run.output_location = (
                    f"{run.id}/{next(iter(result.output_paths.values())).name}"
                    if result.output_paths
                    else None
                )
                run.logs_json = [
                    {
                        "level": "info",
                        "message": f"Flow executed, wrote {len(result.output_paths)} output(s)",
                    },
                    {
                        "level": "info",
                        "message": "Resolved dataset versions",
                        "versions": resolved_versions,
                    },
                ]
            else:
                run.status = "failed"
                run.error_message = result.error
                run.logs_json = [{"level": "error", "message": result.error}]
        except Exception as exc:  # noqa: BLE001 - capture any failure on the run record
            run.status = "failed"
            run.error_message = str(exc)
            run.logs_json = [{"level": "error", "message": str(exc)}]
        finally:
            run.finished_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(run)

        return FlowRunRead.model_validate(run)

    async def get(self, run_id: str) -> FlowRunRead:
        result = await self.db.execute(select(FlowRun).where(FlowRun.id == run_id))
        run = result.scalar_one_or_none()
        if run is None:
            raise NotFoundError("FlowRun", run_id)
        return FlowRunRead.model_validate(run)

    async def list_runs(
        self,
        flow_id: str | None = None,
        project_id: str | None = None,
        dataset_id: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        limit: int = 100,
    ) -> list[FlowRunSummary]:
        """Run history, newest first, with optional filters for the runs page.

        Joins the flow so each row carries the flow name and project even though
        runs only store ``flow_id``.
        """
        stmt = (
            select(FlowRun, Flow.name, Flow.project_id)
            .join(Flow, Flow.id == FlowRun.flow_id, isouter=True)
            .order_by(FlowRun.created_at.desc())
        )
        if flow_id is not None:
            stmt = stmt.where(FlowRun.flow_id == flow_id)
        if project_id is not None:
            stmt = stmt.where(Flow.project_id == project_id)
        if dataset_id is not None:
            stmt = stmt.where(FlowRun.input_dataset_id == dataset_id)
        if status is not None:
            stmt = stmt.where(FlowRun.status == status)
        if started_after is not None:
            stmt = stmt.where(FlowRun.created_at >= started_after)
        if started_before is not None:
            stmt = stmt.where(FlowRun.created_at <= started_before)
        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return [
            FlowRunSummary(
                id=run.id,
                flow_id=run.flow_id,
                flow_name=flow_name,
                project_id=flow_project_id,
                input_dataset_id=run.input_dataset_id,
                status=run.status,
                engine=run.engine,
                output_location=run.output_location,
                started_at=run.started_at,
                finished_at=run.finished_at,
                created_at=run.created_at,
            )
            for run, flow_name, flow_project_id in result.all()
        ]

    # -- Internals ------------------------------------------------------

    async def _get_flow(self, flow_id: str) -> Flow:
        result = await self.db.execute(select(Flow).where(Flow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        return flow
