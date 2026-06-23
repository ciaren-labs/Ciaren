from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.connection import Connection
from app.db.models.dataset import Dataset
from app.db.models.flow import Flow
from app.engine.codegen import CodeGenerator
from app.engine.graph import GraphValidationError
from app.engine.node_kinds import INPUT_SOURCE_TYPES as _FILE_INPUT_TYPES
from app.engine.polars_codegen import PolarsCodeGenerator
from app.engine.sql_codegen import SQL_NODE_TYPES


class CodegenService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def export_python(self, flow_id: str) -> str:
        return (await self.export(flow_id))["pandas"]

    async def export(self, flow_id: str, *, free_intermediates: bool = False) -> dict[str, str]:
        """Generate the pandas, eager-polars and lazy-polars equivalents of a flow.

        ``free_intermediates`` adds ``del`` statements to the materializing
        (pandas / eager-polars) scripts to lower peak memory; the lazy script is
        unaffected since its variables are query plans, not data.
        """
        flow = await self._get_flow(flow_id)
        graph = flow.graph_json
        # Use readable dataset filenames rather than absolute local paths so the
        # exported script is portable and we don't leak the server filesystem.
        dataset_names = await self._dataset_filenames(graph)
        connections = await self._connection_meta(graph)
        try:
            return {
                "pandas": CodeGenerator().generate(
                    graph, dataset_names, connections, free_intermediates=free_intermediates
                ),
                "polars": PolarsCodeGenerator().generate(
                    graph, dataset_names, connections, free_intermediates=free_intermediates
                ),
                "polars_lazy": PolarsCodeGenerator().generate(graph, dataset_names, connections, lazy=True),
            }
        except GraphValidationError as exc:
            raise ValidationError(str(exc)) from exc
        except KeyError as exc:
            raise ValidationError(f"Unknown node type: {exc}") from exc

    async def _dataset_filenames(self, graph: dict[str, Any]) -> dict[str, str]:
        dataset_ids = {
            n["data"]["config"]["dataset_id"] for n in graph.get("nodes", []) if n["type"] in _FILE_INPUT_TYPES
        }
        if not dataset_ids:
            return {}
        result = await self.db.execute(select(Dataset).where(Dataset.id.in_(dataset_ids)))
        datasets = {d.id: d for d in result.scalars().all()}
        missing = dataset_ids - datasets.keys()
        if missing:
            raise NotFoundError("Dataset", ", ".join(sorted(missing)))
        return {ds_id: ds.name for ds_id, ds in datasets.items()}

    async def _connection_meta(self, graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Connection details for SQL nodes — provider/host/.../password_env only.
        Never the secret itself; the generated code reads it from ``os.environ``."""
        ids = {
            n.get("data", {}).get("config", {}).get("connection_id")
            for n in graph.get("nodes", [])
            if n.get("type") in SQL_NODE_TYPES
        }
        ids.discard(None)
        if not ids:
            return {}
        result = await self.db.execute(select(Connection).where(Connection.id.in_(ids)))
        return {
            c.id: {
                "provider": c.provider,
                "host": c.host,
                "port": c.port,
                "database": c.database,
                "username": c.username,
                "password_env": c.password_env,
            }
            for c in result.scalars().all()
        }

    async def _get_flow(self, flow_id: str) -> Flow:
        result = await self.db.execute(select(Flow).where(Flow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        return flow
