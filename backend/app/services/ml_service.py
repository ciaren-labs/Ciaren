# SPDX-License-Identifier: AGPL-3.0-only
"""ML-specific run operations: reading per-node ML metrics off a finished run and
promoting a run's trained model into the MLflow registry."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import MLNotEnabledError, NotFoundError, ValidationError
from app.db.models.flow import Flow
from app.db.models.run import FlowRun
from app.ml.availability import ml_extension_ready

# mlTrain's default experiment name when a node sets no mlflow_experiment.
_DEFAULT_EXPERIMENT = "ciaren"

# NodeResult keys that make a node "ML" for the metrics view.
_ML_KEYS = ("ml_metrics", "model_uri", "task_type", "cv_scores", "mlflow_run_id")
_ML_NOT_READY = "ML support requires CIAREN_ML_ENABLED=true and the core ML dependencies."


def _ms_to_iso(ms: int | None) -> str | None:
    """MLflow epoch-millis timestamp → ISO-8601 string (UTC), or None."""
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat()


def _lineage_from_tags(tags: dict[str, str]) -> dict[str, Any]:
    """Pull Ciaren back-pointer tags (set by mlTrain) into a small lineage dict
    so the UI can link a model/run back to the flow, run, and datasets."""
    lineage: dict[str, Any] = {}
    if tags.get("ciaren_flow_id"):
        lineage["flow_id"] = tags["ciaren_flow_id"]
    if tags.get("ciaren_run_id"):
        lineage["run_id"] = tags["ciaren_run_id"]
    raw = tags.get("ciaren_dataset_ids")
    if raw:
        try:
            lineage["dataset_ids"] = list(json.loads(raw))
        except (ValueError, TypeError):
            pass
    return lineage


class MLService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_metrics(self, run_id: str) -> list[dict[str, Any]]:
        """Per-node ML results for a run (only nodes that produced ML metadata).

        Pure read of the stored node results — works regardless of ML_ENABLED so
        historical runs remain inspectable even if ML is later turned off.
        """
        run = await self._get_run(run_id)
        results = run.node_results_json or []
        ml_nodes: list[dict[str, Any]] = []
        for r in results:
            if any(r.get(k) is not None for k in _ML_KEYS):
                ml_nodes.append(
                    {
                        "node_id": r.get("node_id"),
                        "type": r.get("type"),
                        "label": r.get("label"),
                        "ml_metrics": r.get("ml_metrics"),
                        "model_uri": r.get("model_uri"),
                        "task_type": r.get("task_type"),
                        "cv_scores": r.get("cv_scores"),
                        "mlflow_run_id": r.get("mlflow_run_id"),
                    }
                )
        return ml_nodes

    async def register_model(self, run_id: str, model_name: str, stage: str | None = None) -> dict[str, Any]:
        """Register the run's trained model in the MLflow registry, optionally
        tagging the new version with an alias (MLflow 3 replaced stages with
        aliases; the ``stage`` value is applied as a lowercase alias)."""
        if not ml_extension_ready():
            raise MLNotEnabledError(f"Model registration requires the ML extension ({_ML_NOT_READY})")
        if not model_name or not model_name.strip():
            raise ValidationError("A non-empty 'model_name' is required to register a model.")

        run = await self._get_run(run_id)
        model_uri = self._model_uri(run)
        if model_uri is None:
            raise ValidationError("This run has no trained model to register (no mlTrain node produced a model_uri).")

        from app.ml.tracking import configure_mlflow, mlflow_tracking_lock, resolve_tracking_uri

        uri = await resolve_tracking_uri(self.db)

        # MLflow registry calls hit a REST server or a file-backed store —
        # blocking IO either way, so keep them off the event loop. The URI is
        # re-applied *inside* the thread (and passed to the client explicitly)
        # because configure_mlflow sets process-global state: configuring on
        # the loop and using it later from a thread would let a concurrently
        # configured request's URI leak in between. mlflow.register_model(...)
        # itself is the fluent (implicit-global) API — unlike this method's
        # sibling reads, which pass an explicit tracking_uri to every client
        # call — so the lock is still needed here for that one call.
        def _register() -> tuple[Any, str | None]:
            with mlflow_tracking_lock():
                mlflow = configure_mlflow(tracking_uri=uri)
                version = mlflow.register_model(model_uri, model_name.strip())
                alias = None
                if stage:
                    alias = stage.strip().lower()
                    client = mlflow.tracking.MlflowClient(tracking_uri=mlflow.get_tracking_uri())
                    client.set_registered_model_alias(model_name.strip(), alias, version.version)
                return version, alias

        version, alias = await asyncio.to_thread(_register)

        return {
            "model_name": version.name,
            "version": version.version,
            "model_uri": model_uri,
            "alias": alias,
        }

    async def list_experiments(self, flow_id: str) -> list[dict[str, Any]]:
        """The MLflow experiments this flow's mlTrain nodes log to.

        Experiment names are derived from the flow graph (each mlTrain node's
        ``mlflow_experiment`` config, or the default), then looked up in MLflow so
        the response reflects what actually exists.
        """
        if not ml_extension_ready():
            raise MLNotEnabledError(f"Listing experiments requires the ML extension ({_ML_NOT_READY})")
        flow = await self._get_flow(flow_id)
        names = self._experiment_names(flow.graph_json or {})
        if not names:
            return []

        from app.ml.tracking import configure_mlflow, resolve_tracking_uri

        mlflow = configure_mlflow(tracking_uri=await resolve_tracking_uri(self.db))
        # Snapshot the normalized URI configure_mlflow just set (same sync
        # block, so no other request can have re-pointed the global yet) and
        # hand it to the client explicitly — the thread runs later, when the
        # global may already belong to someone else.
        uri = mlflow.get_tracking_uri()

        def _lookup() -> list[dict[str, Any]]:
            # Explicit URI: the module-global one may be re-pointed by a
            # concurrent request before this thread runs.
            client = mlflow.tracking.MlflowClient(tracking_uri=uri)
            experiments: list[dict[str, Any]] = []
            for name in sorted(names):
                exp = client.get_experiment_by_name(name)
                if exp is not None:
                    experiments.append(
                        {
                            "name": exp.name,
                            "experiment_id": exp.experiment_id,
                            "lifecycle_stage": exp.lifecycle_stage,
                            "artifact_location": exp.artifact_location,
                        }
                    )
            return experiments

        return await asyncio.to_thread(_lookup)

    async def list_registered_models(self) -> list[dict[str, Any]]:
        """Every registered model with its versions, aliases, key metrics, and the
        Ciaren lineage (flow/run/dataset) that produced each version.

        This is the value-add over MLflow's own UI: each version links back to the
        Ciaren flow and run that trained it via the reproducibility tags."""
        if not ml_extension_ready():
            raise MLNotEnabledError(f"The model registry requires the ML extension ({_ML_NOT_READY})")

        from app.ml.tracking import configure_mlflow, resolve_tracking_uri

        mlflow = configure_mlflow(tracking_uri=await resolve_tracking_uri(self.db))
        # Snapshot the normalized URI configure_mlflow just set (same sync
        # block, so no other request can have re-pointed the global yet) and
        # hand it to the client explicitly — the thread runs later, when the
        # global may already belong to someone else.
        uri = mlflow.get_tracking_uri()

        def _list() -> list[dict[str, Any]]:
            # Explicit URI: the module-global one may be re-pointed by a
            # concurrent request before this thread runs.
            client = mlflow.tracking.MlflowClient(tracking_uri=uri)
            models: list[dict[str, Any]] = []
            for rm in client.search_registered_models():
                versions = []
                for mv in client.search_model_versions(f"name='{rm.name}'"):
                    versions.append(self._model_version_view(client, mv))
                versions.sort(key=lambda v: int(v["version"]), reverse=True)
                models.append(
                    {
                        "name": rm.name,
                        "description": getattr(rm, "description", None) or None,
                        "aliases": dict(getattr(rm, "aliases", {}) or {}),
                        "last_updated": _ms_to_iso(getattr(rm, "last_updated_timestamp", None)),
                        "versions": versions,
                    }
                )
            models.sort(key=lambda m: m["name"].lower())
            return models

        return await asyncio.to_thread(_list)

    def _model_version_view(self, client: Any, mv: Any) -> dict[str, Any]:
        metrics: dict[str, float] = {}
        lineage: dict[str, Any] = {}
        if mv.run_id:
            try:
                run = client.get_run(mv.run_id)
                metrics = {k: float(v) for k, v in run.data.metrics.items()}
                lineage = _lineage_from_tags(run.data.tags)
            except Exception:  # noqa: BLE001 - run may be deleted; version still listable
                pass
        return {
            "version": str(mv.version),
            "run_id": mv.run_id or None,
            "status": getattr(mv, "status", None),
            "aliases": list(getattr(mv, "aliases", []) or []),
            "created": _ms_to_iso(getattr(mv, "creation_timestamp", None)),
            "metrics": metrics,
            "lineage": lineage,
        }

    async def set_model_alias(self, model_name: str, version: str, alias: str) -> dict[str, Any]:
        """Point an alias (e.g. ``production``) at a registered model version."""
        if not ml_extension_ready():
            raise MLNotEnabledError(f"Managing aliases requires the ML extension ({_ML_NOT_READY})")
        alias = (alias or "").strip().lower()
        if not alias:
            raise ValidationError("An alias name is required.")

        from app.ml.tracking import configure_mlflow, resolve_tracking_uri

        mlflow = configure_mlflow(tracking_uri=await resolve_tracking_uri(self.db))
        # Snapshot the normalized URI configure_mlflow just set (same sync
        # block, so no other request can have re-pointed the global yet) and
        # hand it to the client explicitly — the thread runs later, when the
        # global may already belong to someone else.
        uri = mlflow.get_tracking_uri()
        try:
            await asyncio.to_thread(
                mlflow.tracking.MlflowClient(tracking_uri=uri).set_registered_model_alias,
                model_name,
                alias,
                str(version),
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as a 400
            raise ValidationError(f"Could not set alias {alias!r}: {exc}") from None
        return {"model_name": model_name, "alias": alias, "version": str(version)}

    async def clear_model_alias(self, model_name: str, alias: str) -> dict[str, Any]:
        """Remove an alias from a registered model."""
        if not ml_extension_ready():
            raise MLNotEnabledError(f"Managing aliases requires the ML extension ({_ML_NOT_READY})")

        from app.ml.tracking import configure_mlflow, resolve_tracking_uri

        mlflow = configure_mlflow(tracking_uri=await resolve_tracking_uri(self.db))
        # Snapshot the normalized URI configure_mlflow just set (same sync
        # block, so no other request can have re-pointed the global yet) and
        # hand it to the client explicitly — the thread runs later, when the
        # global may already belong to someone else.
        uri = mlflow.get_tracking_uri()
        try:
            await asyncio.to_thread(
                mlflow.tracking.MlflowClient(tracking_uri=uri).delete_registered_model_alias,
                model_name,
                alias.strip().lower(),
            )
        except Exception as exc:  # noqa: BLE001
            raise ValidationError(f"Could not clear alias {alias!r}: {exc}") from None
        return {"model_name": model_name, "alias": alias.strip().lower(), "cleared": True}

    async def list_all_experiments(self) -> list[dict[str, Any]]:
        """All MLflow experiments with a run count and last-run time, for the
        Experiments tab leaderboard navigation."""
        if not ml_extension_ready():
            raise MLNotEnabledError(f"Listing experiments requires the ML extension ({_ML_NOT_READY})")

        from app.ml.tracking import configure_mlflow, resolve_tracking_uri

        mlflow = configure_mlflow(tracking_uri=await resolve_tracking_uri(self.db))
        # Snapshot the normalized URI configure_mlflow just set (same sync
        # block, so no other request can have re-pointed the global yet) and
        # hand it to the client explicitly — the thread runs later, when the
        # global may already belong to someone else.
        uri = mlflow.get_tracking_uri()

        def _list() -> list[dict[str, Any]]:
            # Explicit URI: the module-global one may be re-pointed by a
            # concurrent request before this thread runs.
            client = mlflow.tracking.MlflowClient(tracking_uri=uri)
            experiments: list[dict[str, Any]] = []
            for exp in client.search_experiments():
                runs = client.search_runs([exp.experiment_id], max_results=1, order_by=["start_time DESC"])
                last = runs[0].info.start_time if runs else None
                experiments.append(
                    {
                        "experiment_id": exp.experiment_id,
                        "name": exp.name,
                        "lifecycle_stage": exp.lifecycle_stage,
                        "last_run": _ms_to_iso(last),
                    }
                )
            experiments.sort(key=lambda e: e["last_run"] or "", reverse=True)
            return experiments

        return await asyncio.to_thread(_list)

    async def list_experiment_runs(self, experiment_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Runs in an experiment with metrics, params, and Ciaren lineage — the
        data behind the leaderboard and side-by-side comparison."""
        if not ml_extension_ready():
            raise MLNotEnabledError(f"Listing runs requires the ML extension ({_ML_NOT_READY})")

        from app.ml.tracking import configure_mlflow, resolve_tracking_uri

        mlflow = configure_mlflow(tracking_uri=await resolve_tracking_uri(self.db))
        # Snapshot the normalized URI configure_mlflow just set (same sync
        # block, so no other request can have re-pointed the global yet) and
        # hand it to the client explicitly — the thread runs later, when the
        # global may already belong to someone else.
        uri = mlflow.get_tracking_uri()

        def _list() -> list[dict[str, Any]]:
            # Explicit URI: the module-global one may be re-pointed by a
            # concurrent request before this thread runs.
            client = mlflow.tracking.MlflowClient(tracking_uri=uri)
            runs: list[dict[str, Any]] = []
            for run in client.search_runs([experiment_id], max_results=limit, order_by=["start_time DESC"]):
                runs.append(
                    {
                        "run_id": run.info.run_id,
                        "run_name": run.data.tags.get("mlflow.runName") or run.info.run_id[:8],
                        "status": run.info.status,
                        "start_time": _ms_to_iso(run.info.start_time),
                        "metrics": {k: float(v) for k, v in run.data.metrics.items()},
                        "params": dict(run.data.params),
                        "lineage": _lineage_from_tags(run.data.tags),
                    }
                )
            return runs

        return await asyncio.to_thread(_list)

    def _experiment_names(self, graph: dict[str, Any]) -> set[str]:
        from app.engine.node_kinds import is_model_sink

        names: set[str] = set()
        for node in graph.get("nodes", []):
            if is_model_sink(node.get("type", "")):
                config = node.get("data", {}).get("config", {})
                names.add(config.get("mlflow_experiment") or _DEFAULT_EXPERIMENT)
        return names

    # -- internals -----------------------------------------------------------

    def _model_uri(self, run: FlowRun) -> str | None:
        for r in run.node_results_json or []:
            uri = r.get("model_uri")
            if uri:
                return str(uri)
        return None

    async def _get_run(self, run_id: str) -> FlowRun:
        result = await self.db.execute(select(FlowRun).where(FlowRun.id == run_id))
        run = result.scalar_one_or_none()
        if run is None:
            raise NotFoundError("FlowRun", run_id)
        return run

    async def _get_flow(self, flow_id: str) -> Flow:
        result = await self.db.execute(select(Flow).where(Flow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        return flow
