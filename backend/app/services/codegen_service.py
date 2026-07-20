# SPDX-License-Identifier: AGPL-3.0-only
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.connection import Connection
from app.db.models.dataset import Dataset
from app.db.models.dataset_version import DatasetVersion
from app.db.models.flow import Flow
from app.engine.codegen import CodeGenerator
from app.engine.codegen_params import parameter_block_lines, substitute_for_codegen
from app.engine.graph import GraphValidationError
from app.engine.node_kinds import FILE_INPUT_TYPE
from app.engine.node_kinds import INPUT_SOURCE_TYPES as _LEGACY_FILE_INPUT_TYPES
from app.engine.notebook_codegen import script_to_notebook_json
from app.engine.parameters import ParameterError, apply_parameters
from app.engine.polars_codegen import PolarsCodeGenerator
from app.engine.sql_codegen import SQL_NODE_TYPES
from app.plugin_api.events import Hook
from app.schemas.flow import FlowDocument


class CodegenService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def export_python(self, flow_id: str) -> str:
        return str((await self.export(flow_id))["pandas"])

    async def export(self, flow_id: str, *, free_intermediates: bool = False) -> dict[str, Any]:
        """Generate the pandas, eager-polars and lazy-polars equivalents of a flow,
        plus Jupyter notebook (``.ipynb``) variants of each.

        ``free_intermediates`` adds ``del`` statements to the materializing
        (pandas / eager-polars) scripts to lower peak memory; the lazy script is
        unaffected since its variables are query plans, not data.
        """
        flow = await self._get_flow(flow_id)
        graph = flow.graph_json
        self._emit_export_requested(flow_id)
        # Use readable dataset filenames rather than absolute local paths so the
        # exported script is portable and we don't leak the server filesystem.
        # dataset_id / connection_id bindings are never parameterized, so the raw
        # graph is fine for resolving those names.
        dataset_names = await self._dataset_filenames(graph)
        # The stored copies are normalized at ingest, but the exported script
        # reads the user's ORIGINAL files by name — emit their real dialect.
        parse_options = await self._dataset_parse_options(dataset_names)
        connections = await self._connection_meta(graph)

        # Flow parameters render as real variables: a `name = default` prelude plus
        # `{{ name }}` references rewritten to CodeRefs. If a node's code generator
        # can't handle a substituted value, fall back to inlining resolved defaults
        # so export never fails on a parameterized flow.
        try:
            param_lines = parameter_block_lines(graph)
            code_graph = substitute_for_codegen(graph)
            fallback_graph, _ = apply_parameters(graph, {})
        except ParameterError as exc:
            raise ValidationError(str(exc)) from exc

        def safe(generate: Any) -> str:
            try:
                return str(generate(code_graph, param_lines))
            except (GraphValidationError, KeyError):
                raise
            except Exception:  # noqa: BLE001 - a CodeRef a node can't handle; inline defaults
                return str(generate(fallback_graph, []))

        try:
            pandas_script = safe(
                lambda g, p: CodeGenerator().generate(
                    g,
                    dataset_names,
                    connections,
                    free_intermediates=free_intermediates,
                    parameter_lines=p,
                    dataset_parse_options=parse_options,
                )
            )
            polars_script = safe(
                lambda g, p: PolarsCodeGenerator().generate(
                    g,
                    dataset_names,
                    connections,
                    free_intermediates=free_intermediates,
                    parameter_lines=p,
                    dataset_parse_options=parse_options,
                )
            )
            polars_lazy_script = safe(
                lambda g, p: PolarsCodeGenerator().generate(
                    g,
                    dataset_names,
                    connections,
                    lazy=True,
                    parameter_lines=p,
                    dataset_parse_options=parse_options,
                )
            )
            flow_name = flow.name
            return {
                "pandas": pandas_script,
                "polars": polars_script,
                "polars_lazy": polars_lazy_script,
                "notebook": script_to_notebook_json(pandas_script, flow_name=flow_name),
                "notebook_polars": script_to_notebook_json(polars_script, flow_name=flow_name),
                "notebook_polars_lazy": script_to_notebook_json(polars_lazy_script, flow_name=flow_name),
                "flow_document": FlowDocument(name=flow.name, description=flow.description, graph_json=graph),
            }
        except GraphValidationError as exc:
            raise ValidationError(str(exc)) from exc
        except KeyError as exc:
            raise ValidationError(f"Unknown node type: {exc}") from exc

    async def _dataset_filenames(self, graph: dict[str, Any]) -> dict[str, str]:
        # Use .get throughout: an input node may have no dataset bound yet (e.g. a
        # freshly imported flow), in which case codegen falls back to a placeholder
        # filename rather than crashing.
        dataset_ids = {
            ds_id
            for n in graph.get("nodes", [])
            if (
                (n.get("type") in _LEGACY_FILE_INPUT_TYPES or n.get("type") == FILE_INPUT_TYPE)
                and (ds_id := n.get("data", {}).get("config", {}).get("dataset_id"))
            )
        }
        if not dataset_ids:
            return {}
        result = await self.db.execute(select(Dataset).where(Dataset.id.in_(dataset_ids)))
        datasets = {d.id: d for d in result.scalars().all()}
        missing = dataset_ids - datasets.keys()
        if missing:
            raise NotFoundError("Dataset", ", ".join(sorted(missing)))
        return {ds_id: ds.name for ds_id, ds in datasets.items()}

    async def _dataset_parse_options(self, dataset_names: dict[str, str]) -> dict[str, dict[str, Any]]:
        """Latest-version parse options per referenced dataset (only entries whose
        original upload had a non-default dialect)."""
        if not dataset_names:
            return {}
        result = await self.db.execute(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id.in_(dataset_names.keys()))
            .order_by(DatasetVersion.dataset_id, DatasetVersion.version_number)
        )
        options: dict[str, dict[str, Any]] = {}
        for ver in result.scalars().all():
            # Ordered ascending: the last row per dataset wins (latest version).
            if ver.parse_options_json:
                options[ver.dataset_id] = ver.parse_options_json
            else:
                options.pop(ver.dataset_id, None)
        return options

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

    def _emit_export_requested(self, flow_id: str) -> None:
        """Best-effort ``on_export_requested`` hook for plugins (lineage, audit, …)."""
        try:
            from app.plugins import get_registry

            get_registry().events.emit(Hook.export_requested, flow_id=flow_id)
        except Exception:  # noqa: BLE001 — plugin hooks must never break export
            pass

    async def _get_flow(self, flow_id: str) -> Flow:
        result = await self.db.execute(select(Flow).where(Flow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        return flow
