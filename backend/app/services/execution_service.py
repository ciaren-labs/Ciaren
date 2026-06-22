from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.db.models.dataset import Dataset
from app.db.models.flow import Flow
from app.db.models.run import FlowRun
from app.engine.executor import FlowExecutor
from app.schemas.run import FlowRunCreate, FlowRunRead

_INPUT_TYPES = {"csvInput", "excelInput", "parquetInput"}


class ExecutionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    async def run(self, flow_id: str, data: FlowRunCreate) -> FlowRunRead:
        flow = await self._get_flow(flow_id)

        run = FlowRun(
            flow_id=flow_id,
            input_dataset_id=data.input_dataset_id,
            status="running",
            started_at=datetime.utcnow(),
        )
        self.db.add(run)
        await self.db.flush()  # assign run.id without committing

        try:
            dataset_paths = await self._dataset_paths(flow.graph_json)
            output_dir = Path(self.settings.DATA_DIR) / "outputs" / run.id
            output_dir.mkdir(parents=True, exist_ok=True)
            outputs = FlowExecutor().execute(flow.graph_json, dataset_paths, output_dir)

            run.status = "success"
            # Store a path relative to the outputs dir so we never leak the
            # absolute server filesystem layout in API responses.
            run.output_location = (
                f"{run.id}/{next(iter(outputs.values())).name}" if outputs else None
            )
            run.logs_json = [
                {"level": "info", "message": f"Flow executed, wrote {len(outputs)} output(s)"}
            ]
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

    # -- Internals ------------------------------------------------------

    async def _dataset_paths(self, graph: dict[str, Any]) -> dict[str, Path]:
        dataset_ids = {
            n["data"]["config"]["dataset_id"]
            for n in graph.get("nodes", [])
            if n["type"] in _INPUT_TYPES
        }
        if not dataset_ids:
            return {}
        result = await self.db.execute(
            select(Dataset).where(Dataset.id.in_(dataset_ids))
        )
        datasets = {d.id: d for d in result.scalars().all()}
        missing = dataset_ids - datasets.keys()
        if missing:
            raise NotFoundError("Dataset", ", ".join(sorted(missing)))
        return {ds_id: Path(ds.location) for ds_id, ds in datasets.items()}

    async def _get_flow(self, flow_id: str) -> Flow:
        result = await self.db.execute(select(Flow).where(Flow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        return flow
