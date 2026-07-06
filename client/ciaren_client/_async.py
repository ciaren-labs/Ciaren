"""Async Ciaren client backed by httpx.AsyncClient."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from ciaren_client._types import (
    AppSetting,
    CodeExport,
    Connection,
    ConnectionTestResult,
    Dataset,
    DatasetVersion,
    Flow,
    FlowMigrationResult,
    JsonDict,
    KeyringAvailability,
    KeyringSecretStatus,
    Project,
    Run,
    Schedule,
    WebhookStatus,
)


class AsyncCiaren:
    """Async client for the Ciaren API.

    Can be used as an async context manager::

        async with AsyncCiaren(base_url, webhook_secret=secret) as client:
            run = await client.trigger(flow_id)

    Or managed manually::

        client = AsyncCiaren(base_url)
        await client.aclose()
    """

    def __init__(
        self,
        base_url: str,
        *,
        webhook_secret: str | None = None,
        api_token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret = webhook_secret
        headers = {"Authorization": f"Bearer {api_token}"} if api_token else None
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout, headers=headers)

    # ------------------------------------------------------------------
    # Raw HTTP helpers
    # ------------------------------------------------------------------

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send a raw request against the Ciaren server and raise on HTTP errors."""
        r = await self._client.request(method, url, **kwargs)
        r.raise_for_status()
        return r

    async def get(self, url: str, **kwargs: Any) -> Any:
        return (await self.request("GET", url, **kwargs)).json()

    async def post(self, url: str, **kwargs: Any) -> Any:
        return (await self.request("POST", url, **kwargs)).json()

    async def put(self, url: str, **kwargs: Any) -> Any:
        return (await self.request("PUT", url, **kwargs)).json()

    async def patch(self, url: str, **kwargs: Any) -> Any:
        return (await self.request("PATCH", url, **kwargs)).json()

    async def delete(self, url: str, **kwargs: Any) -> None:
        await self.request("DELETE", url, **kwargs)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> AsyncCiaren:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    async def list_projects(self) -> list[Project]:
        return await self.get("/api/projects")

    async def create_project(self, name: str, *, description: str | None = None, color: str = "violet") -> Project:
        return await self.post("/api/projects", json={"name": name, "description": description, "color": color})

    async def get_project(self, project_id: str) -> Project:
        return await self.get(f"/api/projects/{project_id}")

    async def update_project(self, project_id: str, **fields: Any) -> Project:
        return await self.put(f"/api/projects/{project_id}", json=fields)

    async def delete_project(self, project_id: str) -> None:
        await self.delete(f"/api/projects/{project_id}")

    # ------------------------------------------------------------------
    # Datasets
    # ------------------------------------------------------------------

    async def upload_dataset(self, path: str | Path, *, project_id: str | None = None) -> Dataset:
        file_path = Path(path)
        params = {"project_id": project_id} if project_id else None
        with file_path.open("rb") as handle:
            r = await self._client.post(
                "/api/datasets/upload",
                params=params,
                files={"file": (file_path.name, handle, "application/octet-stream")},
            )
        r.raise_for_status()
        return r.json()

    async def list_datasets(self, *, project_id: str | None = None, include_deleted: bool = False) -> list[Dataset]:
        params: dict[str, Any] = {"include_deleted": include_deleted}
        if project_id:
            params["project_id"] = project_id
        return await self.get("/api/datasets", params=params)

    async def get_dataset(self, dataset_id: str) -> Dataset:
        return await self.get(f"/api/datasets/{dataset_id}")

    async def update_dataset(self, dataset_id: str, **fields: Any) -> Dataset:
        return await self.patch(f"/api/datasets/{dataset_id}", json=fields)

    async def delete_dataset(self, dataset_id: str, *, purge: bool = False, force: bool = False) -> None:
        await self.delete(f"/api/datasets/{dataset_id}", params={"purge": purge, "force": force})

    async def restore_dataset(self, dataset_id: str) -> Dataset:
        return await self.post(f"/api/datasets/{dataset_id}/restore")

    async def purge_expired_datasets(self) -> dict[str, int]:
        return await self.post("/api/datasets/purge-expired")

    async def list_dataset_flows(self, dataset_id: str) -> list[Flow]:
        return await self.get(f"/api/datasets/{dataset_id}/flows")

    async def list_dataset_versions(
        self, dataset_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[DatasetVersion]:
        return await self.get(f"/api/datasets/{dataset_id}/versions", params={"limit": limit, "offset": offset})

    async def get_dataset_schema(self, dataset_id: str, *, version: int | None = None) -> Any:
        return await self.get(f"/api/datasets/{dataset_id}/schema", params={"version": version} if version else None)

    async def get_dataset_sample(self, dataset_id: str, *, version: int | None = None) -> Any:
        return await self.get(f"/api/datasets/{dataset_id}/sample", params={"version": version} if version else None)

    async def get_dataset_profile(self, dataset_id: str, *, version: int | None = None) -> Any:
        return await self.get(f"/api/datasets/{dataset_id}/profile", params={"version": version} if version else None)

    async def download_dataset_version(
        self, dataset_id: str, version_number: int, path: str | Path | None = None
    ) -> bytes | Path:
        r = await self.request("GET", f"/api/datasets/{dataset_id}/versions/{version_number}/download")
        if path is None:
            return r.content
        target = Path(path)
        target.write_bytes(r.content)
        return target

    # ------------------------------------------------------------------
    # Flows
    # ------------------------------------------------------------------

    async def list_flows(self, *, project_id: str | None = None) -> list[Flow]:
        return await self.get("/api/flows", params={"project_id": project_id} if project_id else None)

    async def create_flow(
        self,
        name: str,
        *,
        description: str | None = None,
        project_id: str | None = None,
        graph_json: JsonDict | None = None,
    ) -> Flow:
        return await self.post(
            "/api/flows",
            json={"name": name, "description": description, "project_id": project_id, "graph_json": graph_json or {}},
        )

    async def import_flow(
        self,
        graph_json: JsonDict,
        *,
        format: str | None = None,
        name: str | None = None,
        description: str | None = None,
        project_id: str | None = None,
    ) -> Flow:
        return await self.post(
            "/api/flows/import",
            json={
                "format": format,
                "name": name,
                "description": description,
                "project_id": project_id,
                "graph_json": graph_json,
            },
        )

    async def duplicate_flow(self, flow_id: str, *, name: str | None = None) -> Flow:
        return await self.post(f"/api/flows/{flow_id}/duplicate", params={"name": name} if name else None)

    async def get_flow(self, flow_id: str) -> Flow:
        return await self.get(f"/api/flows/{flow_id}")

    async def update_flow(self, flow_id: str, **fields: Any) -> Flow:
        return await self.put(f"/api/flows/{flow_id}", json=fields)

    async def delete_flow(self, flow_id: str) -> None:
        await self.delete(f"/api/flows/{flow_id}")

    async def preview_flow(self, flow_id: str, **payload: Any) -> Any:
        return await self.post(f"/api/flows/{flow_id}/preview", json=payload)

    async def export_flow_python(self, flow_id: str, *, free_intermediates: bool = True) -> CodeExport:
        return await self.post(f"/api/flows/{flow_id}/export/python", params={"free_intermediates": free_intermediates})

    async def migrate_flow_document(self, document: JsonDict) -> FlowMigrationResult:
        """Migrate/validate a raw .flow document to the current schema version
        without persisting or importing it."""
        return await self.post("/api/flows/migrate-document", json={"document": document})

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    async def list_runs(
        self,
        *,
        flow_id: str | None = None,
        project_id: str | None = None,
        dataset_id: str | None = None,
        schedule_id: str | None = None,
        status: str | None = None,
        started_after: str | datetime | None = None,
        started_before: str | datetime | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 100,
        offset: int = 0,
    ) -> list[Run]:
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }
        if flow_id:
            params["flow_id"] = flow_id
        if project_id:
            params["project_id"] = project_id
        if dataset_id:
            params["dataset_id"] = dataset_id
        if schedule_id:
            params["schedule_id"] = schedule_id
        if status:
            params["status"] = status
        if started_after:
            params["started_after"] = started_after.isoformat() if isinstance(started_after, datetime) else started_after
        if started_before:
            params["started_before"] = started_before.isoformat() if isinstance(started_before, datetime) else started_before
        return await self.get("/api/runs", params=params)

    async def create_run(
        self,
        flow_id: str,
        *,
        input_dataset_id: str | None = None,
        engine: str | None = None,
        timeout_seconds: int | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> Run:
        return await self.post(
            f"/api/flows/{flow_id}/runs",
            json={
                "input_dataset_id": input_dataset_id,
                "engine": engine,
                "timeout_seconds": timeout_seconds,
                "parameters": parameters,
            },
        )

    async def get_run(self, run_id: str) -> Run:
        return await self.get(f"/api/runs/{run_id}")

    async def cancel_run(self, run_id: str) -> dict[str, str]:
        """Stop a running run: cooperatively at the next node boundary (thread
        mode) or by abandoning the worker (process mode)."""
        return await self.post(f"/api/runs/{run_id}/cancel")

    async def retry_run(self, run_id: str) -> Run:
        """Retry a run via POST /api/runs/{id}/retry.

        Re-runs the same flow with the original run's config, creating a new
        run with a new id. Returns the newly created run dict.
        """
        return await self.post(f"/api/runs/{run_id}/retry")

    async def download_run_output(self, run_id: str, node_id: str, path: str | Path | None = None) -> bytes | Path:
        r = await self.request("GET", f"/api/runs/{run_id}/output", params={"node_id": node_id})
        if path is None:
            return r.content
        target = Path(path)
        target.write_bytes(r.content)
        return target

    # ------------------------------------------------------------------
    # Schedules
    # ------------------------------------------------------------------

    async def create_schedule(self, flow_id: str, cron: str, **fields: Any) -> Schedule:
        return await self.post(f"/api/flows/{flow_id}/schedules", json={"cron": cron, **fields})

    async def list_flow_schedules(self, flow_id: str) -> list[Schedule]:
        return await self.get(f"/api/flows/{flow_id}/schedules")

    async def list_schedules(self, *, flow_id: str | None = None) -> list[Schedule]:
        return await self.get("/api/schedules", params={"flow_id": flow_id} if flow_id else None)

    async def get_schedule(self, schedule_id: str) -> Schedule:
        return await self.get(f"/api/schedules/{schedule_id}")

    async def update_schedule(self, schedule_id: str, **fields: Any) -> Schedule:
        return await self.patch(f"/api/schedules/{schedule_id}", json=fields)

    async def delete_schedule(self, schedule_id: str) -> None:
        await self.delete(f"/api/schedules/{schedule_id}")

    async def run_schedule_now(self, schedule_id: str) -> Run:
        return await self.post(f"/api/schedules/{schedule_id}/run-now")

    async def list_schedule_runs(self, schedule_id: str, *, limit: int = 50, offset: int = 0) -> list[Run]:
        return await self.get(f"/api/schedules/{schedule_id}/runs", params={"limit": limit, "offset": offset})

    # ------------------------------------------------------------------
    # ML
    # ------------------------------------------------------------------

    async def get_run_ml_metrics(self, run_id: str) -> list[dict[str, Any]]:
        return await self.get(f"/api/runs/{run_id}/ml/metrics")

    async def register_run_model(self, run_id: str, model_name: str, *, stage: str | None = None) -> dict[str, Any]:
        return await self.post(f"/api/runs/{run_id}/ml/register", json={"model_name": model_name, "stage": stage})

    async def list_flow_ml_experiments(self, flow_id: str) -> list[dict[str, Any]]:
        return await self.get(f"/api/flows/{flow_id}/ml/experiments")

    async def list_registered_models(self) -> list[dict[str, Any]]:
        return await self.get("/api/ml/models")

    async def list_model_catalog(self) -> list[dict[str, Any]]:
        return await self.get("/api/ml/model-catalog")

    async def set_model_alias(self, model_name: str, version: str | int, alias: str) -> dict[str, Any]:
        return await self.post(f"/api/ml/models/{model_name}/alias", json={"version": version, "alias": alias})

    async def clear_model_alias(self, model_name: str, alias: str) -> dict[str, Any]:
        return (await self.request("DELETE", f"/api/ml/models/{model_name}/alias/{alias}")).json()

    async def list_ml_experiments(self) -> list[dict[str, Any]]:
        return await self.get("/api/ml/experiments")

    async def list_ml_experiment_runs(self, experiment_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        return await self.get(f"/api/ml/experiments/{experiment_id}/runs", params={"limit": limit})

    # ------------------------------------------------------------------
    # Connections
    # ------------------------------------------------------------------

    async def list_connections(self) -> list[Connection]:
        return await self.get("/api/connections")

    async def create_connection(self, **payload: Any) -> Connection:
        return await self.post("/api/connections", json=payload)

    async def list_connection_providers(self) -> list[dict[str, Any]]:
        return await self.get("/api/connections/providers")

    async def test_connection_config(self, **payload: Any) -> ConnectionTestResult:
        return await self.post("/api/connections/test-config", json=payload)

    async def keyring_availability(self) -> KeyringAvailability:
        """Whether this host has a usable OS keychain (headless servers have none)."""
        return await self.get("/api/connections/keyring")

    async def store_keyring_secret(
        self, name: str, value: str, *, overwrite: bool = False
    ) -> KeyringSecretStatus:
        """Store a secret in the OS keychain, returning its ``keyring:NAME`` reference.

        The value is written to the platform keychain and never persisted, returned,
        or logged by Ciaren. Refused with 409 if the name is taken unless ``overwrite``.
        """
        return await self.post(
            "/api/connections/keyring", json={"name": name, "value": value, "overwrite": overwrite}
        )

    async def get_keyring_secret_status(self, name: str) -> KeyringSecretStatus:
        """Whether a keychain secret exists — never returns its value."""
        return await self.get(f"/api/connections/keyring/{name}")

    async def delete_keyring_secret(self, name: str) -> None:
        await self.delete(f"/api/connections/keyring/{name}")

    async def get_connection(self, connection_id: str) -> Connection:
        return await self.get(f"/api/connections/{connection_id}")

    async def update_connection(self, connection_id: str, **fields: Any) -> Connection:
        return await self.patch(f"/api/connections/{connection_id}", json=fields)

    async def delete_connection(self, connection_id: str, *, force: bool = False) -> None:
        """Delete a connection. Refused with 409 while flows still reference it,
        unless ``force=True`` (those flows then fail at run time until repointed)."""
        await self.delete(f"/api/connections/{connection_id}", params={"force": force})

    async def test_connection(self, connection_id: str) -> ConnectionTestResult:
        return await self.post(f"/api/connections/{connection_id}/test")

    async def list_connection_tables(self, connection_id: str) -> list[dict[str, Any]]:
        return await self.get(f"/api/connections/{connection_id}/tables")

    async def list_connection_objects(self, connection_id: str, *, prefix: str = "") -> list[str]:
        return await self.get(f"/api/connections/{connection_id}/objects", params={"prefix": prefix})

    # ------------------------------------------------------------------
    # Catalog / transformations / webhook settings
    # ------------------------------------------------------------------

    async def list_catalog_nodes(self, *, category: str | None = None) -> list[dict[str, Any]]:
        return await self.get("/api/catalog/nodes", params={"category": category} if category else None)

    async def list_catalog_connectors(self) -> list[dict[str, Any]]:
        return await self.get("/api/catalog/connectors")

    async def list_catalog_exporters(self) -> list[dict[str, Any]]:
        return await self.get("/api/catalog/exporters")

    async def list_catalog_categories(self) -> list[dict[str, Any]]:
        return await self.get("/api/catalog/categories")

    async def list_transformations(self, *, include_ml: bool = True) -> Any:
        return await self.get("/api/transformations", params={"include_ml": include_ml})

    async def preview_transformation(self, **payload: Any) -> Any:
        return await self.post("/api/transformations/preview", json=payload)

    async def webhook_status(self) -> WebhookStatus:
        return await self.get("/api/settings/webhook")

    # ------------------------------------------------------------------
    # Runtime app settings (Settings page allowlist)
    # ------------------------------------------------------------------

    async def list_settings(self) -> list[AppSetting]:
        return await self.get("/api/settings")

    async def update_setting(self, key: str, value: int | str) -> AppSetting:
        return await self.put(f"/api/settings/{key}", json={"value": value})

    async def reset_setting(self, key: str) -> AppSetting:
        """Remove ``key``'s override, falling back to the environment/default."""
        return (await self.request("DELETE", f"/api/settings/{key}")).json()

    # ------------------------------------------------------------------
    # Plugins / marketplace
    # ------------------------------------------------------------------

    async def list_plugins(self) -> list[dict[str, Any]]:
        return await self.get("/api/plugins")

    async def plugin_diagnostics(self) -> dict[str, Any]:
        return await self.get("/api/plugins/diagnostics")

    async def install_plugin(self, path: str | Path, *, require_trusted: bool | None = None) -> dict[str, Any]:
        package_path = Path(path)
        data = {"require_trusted": str(require_trusted).lower()} if require_trusted is not None else None
        with package_path.open("rb") as handle:
            r = await self._client.post(
                "/api/plugins/install",
                data=data,
                files={"file": (package_path.name, handle, "application/octet-stream")},
            )
        r.raise_for_status()
        return r.json()

    async def get_plugin_license(self, plugin_id: str) -> dict[str, Any]:
        return await self.get(f"/api/plugins/{plugin_id}/license")

    async def activate_plugin_license(self, plugin_id: str, token: dict[str, Any]) -> dict[str, Any]:
        """Activate a license: send the pasted/downloaded token JSON (marketplace wire
        format). The server vets it against the trusted issuer keys before caching."""
        return await self.post(f"/api/plugins/{plugin_id}/license", json=token)

    async def remove_plugin_license(self, plugin_id: str) -> dict[str, Any]:
        r = await self.request("DELETE", f"/api/plugins/{plugin_id}/license")
        return r.json()

    async def enable_plugin(self, plugin_id: str) -> dict[str, Any]:
        return await self.post(f"/api/plugins/{plugin_id}/enable")

    async def disable_plugin(self, plugin_id: str) -> dict[str, Any]:
        return await self.post(f"/api/plugins/{plugin_id}/disable")

    async def uninstall_plugin(self, plugin_id: str) -> dict[str, Any]:
        r = await self.request("DELETE", f"/api/plugins/{plugin_id}")
        return r.json()

    async def grant_plugin_permissions(self, plugin_id: str, permissions: list[str] | None = None) -> dict[str, Any]:
        return await self.post(f"/api/plugins/{plugin_id}/grant", json={"permissions": permissions or []})

    async def revoke_plugin_permissions(self, plugin_id: str, permissions: list[str] | None = None) -> dict[str, Any]:
        return await self.post(f"/api/plugins/{plugin_id}/revoke", json={"permissions": permissions or []})

    async def list_marketplace(self) -> dict[str, Any]:
        return await self.get("/api/marketplace")

    async def install_marketplace_plugin(self, plugin_id: str) -> dict[str, Any]:
        return await self.post(f"/api/marketplace/{plugin_id}/install")

    # ------------------------------------------------------------------
    # Webhook trigger
    # ------------------------------------------------------------------

    def _trigger_headers(self) -> dict[str, str]:
        if self._secret is None:
            raise ValueError(
                "webhook_secret is required to call trigger(). "
                "Pass it when constructing AsyncCiaren(webhook_secret=...)."
            )
        return {"X-Ciaren-Secret": self._secret}

    async def trigger(
        self,
        flow_id: str,
        *,
        engine: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> Run:
        """Trigger a flow run via the webhook endpoint.

        Returns the completed run dict (blocks until the server finishes).
        """
        body: dict[str, Any] = {}
        if engine:
            body["engine"] = engine
        if parameters:
            body["parameters"] = parameters
        r = await self._client.post(
            f"/api/flows/{flow_id}/trigger",
            json=body or None,
            headers=self._trigger_headers(),
        )
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # SSE log streaming
    # ------------------------------------------------------------------

    async def stream_logs(self, run_id: str) -> AsyncGenerator[dict[str, Any], None]:
        """Yield log entry dicts from GET /api/runs/{id}/logs/stream (SSE).

        Yields each ``data:`` event payload as a dict. Stops after the
        ``event: done`` frame arrives (that frame itself is not yielded).
        """
        async with self._client.stream("GET", f"/api/runs/{run_id}/logs/stream") as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    import json

                    payload = line[len("data:"):].strip()
                    try:
                        yield json.loads(payload)
                    except Exception:
                        yield {"raw": payload}
                elif line.startswith("event: done"):
                    return
