"""Synchronous Ciaren client backed by httpx.Client."""

from __future__ import annotations

from collections.abc import Generator
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


class Ciaren:
    """Synchronous client for the Ciaren API.

    Can be used as a context manager::

        with Ciaren(base_url, webhook_secret=secret) as client:
            run = client.trigger(flow_id)

    Or managed manually::

        client = Ciaren(base_url)
        client.close()
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
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout, headers=headers)

    # ------------------------------------------------------------------
    # Raw HTTP helpers
    # ------------------------------------------------------------------

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send a raw request against the Ciaren server and raise on HTTP errors."""
        r = self._client.request(method, url, **kwargs)
        r.raise_for_status()
        return r

    def get(self, url: str, **kwargs: Any) -> Any:
        return self.request("GET", url, **kwargs).json()

    def post(self, url: str, **kwargs: Any) -> Any:
        return self.request("POST", url, **kwargs).json()

    def put(self, url: str, **kwargs: Any) -> Any:
        return self.request("PUT", url, **kwargs).json()

    def patch(self, url: str, **kwargs: Any) -> Any:
        return self.request("PATCH", url, **kwargs).json()

    def delete(self, url: str, **kwargs: Any) -> None:
        self.request("DELETE", url, **kwargs)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> Ciaren:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def list_projects(self) -> list[Project]:
        return self.get("/api/projects")

    def create_project(self, name: str, *, description: str | None = None, color: str = "violet") -> Project:
        return self.post("/api/projects", json={"name": name, "description": description, "color": color})

    def get_project(self, project_id: str) -> Project:
        return self.get(f"/api/projects/{project_id}")

    def update_project(self, project_id: str, **fields: Any) -> Project:
        return self.put(f"/api/projects/{project_id}", json=fields)

    def delete_project(self, project_id: str) -> None:
        self.delete(f"/api/projects/{project_id}")

    # ------------------------------------------------------------------
    # Datasets
    # ------------------------------------------------------------------

    def upload_dataset(self, path: str | Path, *, project_id: str | None = None) -> Dataset:
        file_path = Path(path)
        params = {"project_id": project_id} if project_id else None
        with file_path.open("rb") as handle:
            r = self._client.post(
                "/api/datasets/upload",
                params=params,
                files={"file": (file_path.name, handle, "application/octet-stream")},
            )
        r.raise_for_status()
        return r.json()

    def list_datasets(self, *, project_id: str | None = None, include_deleted: bool = False) -> list[Dataset]:
        params: dict[str, Any] = {"include_deleted": include_deleted}
        if project_id:
            params["project_id"] = project_id
        return self.get("/api/datasets", params=params)

    def get_dataset(self, dataset_id: str) -> Dataset:
        return self.get(f"/api/datasets/{dataset_id}")

    def update_dataset(self, dataset_id: str, **fields: Any) -> Dataset:
        return self.patch(f"/api/datasets/{dataset_id}", json=fields)

    def delete_dataset(self, dataset_id: str, *, purge: bool = False, force: bool = False) -> None:
        self.delete(f"/api/datasets/{dataset_id}", params={"purge": purge, "force": force})

    def restore_dataset(self, dataset_id: str) -> Dataset:
        return self.post(f"/api/datasets/{dataset_id}/restore")

    def purge_expired_datasets(self) -> dict[str, int]:
        return self.post("/api/datasets/purge-expired")

    def list_dataset_flows(self, dataset_id: str) -> list[Flow]:
        return self.get(f"/api/datasets/{dataset_id}/flows")

    def list_dataset_versions(
        self, dataset_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[DatasetVersion]:
        return self.get(f"/api/datasets/{dataset_id}/versions", params={"limit": limit, "offset": offset})

    def get_dataset_schema(self, dataset_id: str, *, version: int | None = None) -> Any:
        return self.get(f"/api/datasets/{dataset_id}/schema", params={"version": version} if version else None)

    def get_dataset_sample(self, dataset_id: str, *, version: int | None = None) -> Any:
        return self.get(f"/api/datasets/{dataset_id}/sample", params={"version": version} if version else None)

    def get_dataset_profile(self, dataset_id: str, *, version: int | None = None) -> Any:
        return self.get(f"/api/datasets/{dataset_id}/profile", params={"version": version} if version else None)

    def download_dataset_version(
        self, dataset_id: str, version_number: int, path: str | Path | None = None
    ) -> bytes | Path:
        r = self.request("GET", f"/api/datasets/{dataset_id}/versions/{version_number}/download")
        if path is None:
            return r.content
        target = Path(path)
        target.write_bytes(r.content)
        return target

    # ------------------------------------------------------------------
    # Flows
    # ------------------------------------------------------------------

    def list_flows(self, *, project_id: str | None = None) -> list[Flow]:
        return self.get("/api/flows", params={"project_id": project_id} if project_id else None)

    def create_flow(
        self,
        name: str,
        *,
        description: str | None = None,
        project_id: str | None = None,
        graph_json: JsonDict | None = None,
    ) -> Flow:
        return self.post(
            "/api/flows",
            json={"name": name, "description": description, "project_id": project_id, "graph_json": graph_json or {}},
        )

    def import_flow(
        self,
        graph_json: JsonDict,
        *,
        format: str | None = None,
        name: str | None = None,
        description: str | None = None,
        project_id: str | None = None,
    ) -> Flow:
        return self.post(
            "/api/flows/import",
            json={
                "format": format,
                "name": name,
                "description": description,
                "project_id": project_id,
                "graph_json": graph_json,
            },
        )

    def duplicate_flow(self, flow_id: str, *, name: str | None = None) -> Flow:
        return self.post(f"/api/flows/{flow_id}/duplicate", params={"name": name} if name else None)

    def get_flow(self, flow_id: str) -> Flow:
        return self.get(f"/api/flows/{flow_id}")

    def update_flow(self, flow_id: str, **fields: Any) -> Flow:
        return self.put(f"/api/flows/{flow_id}", json=fields)

    def delete_flow(self, flow_id: str) -> None:
        self.delete(f"/api/flows/{flow_id}")

    def preview_flow(self, flow_id: str, **payload: Any) -> Any:
        return self.post(f"/api/flows/{flow_id}/preview", json=payload)

    def export_flow_python(self, flow_id: str, *, free_intermediates: bool = True) -> CodeExport:
        return self.post(f"/api/flows/{flow_id}/export/python", params={"free_intermediates": free_intermediates})

    def migrate_flow_document(self, document: JsonDict) -> FlowMigrationResult:
        """Migrate/validate a raw .flow document to the current schema version
        without persisting or importing it."""
        return self.post("/api/flows/migrate-document", json={"document": document})

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def list_runs(
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
        return self.get("/api/runs", params=params)

    def create_run(
        self,
        flow_id: str,
        *,
        input_dataset_id: str | None = None,
        engine: str | None = None,
        timeout_seconds: int | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> Run:
        return self.post(
            f"/api/flows/{flow_id}/runs",
            json={
                "input_dataset_id": input_dataset_id,
                "engine": engine,
                "timeout_seconds": timeout_seconds,
                "parameters": parameters,
            },
        )

    def get_run(self, run_id: str) -> Run:
        return self.get(f"/api/runs/{run_id}")

    def cancel_run(self, run_id: str) -> dict[str, str]:
        """Stop a running run: cooperatively at the next node boundary (thread
        mode) or by abandoning the worker (process mode)."""
        return self.post(f"/api/runs/{run_id}/cancel")

    def retry_run(self, run_id: str) -> Run:
        """Retry a run via POST /api/runs/{id}/retry.

        Re-runs the same flow with the original run's config, creating a new
        run with a new id. Returns the newly created run dict.
        """
        return self.post(f"/api/runs/{run_id}/retry")

    def download_run_output(self, run_id: str, node_id: str, path: str | Path | None = None) -> bytes | Path:
        r = self.request("GET", f"/api/runs/{run_id}/output", params={"node_id": node_id})
        if path is None:
            return r.content
        target = Path(path)
        target.write_bytes(r.content)
        return target

    # ------------------------------------------------------------------
    # Schedules
    # ------------------------------------------------------------------

    def create_schedule(self, flow_id: str, cron: str, **fields: Any) -> Schedule:
        return self.post(f"/api/flows/{flow_id}/schedules", json={"cron": cron, **fields})

    def list_flow_schedules(self, flow_id: str) -> list[Schedule]:
        return self.get(f"/api/flows/{flow_id}/schedules")

    def list_schedules(self, *, flow_id: str | None = None) -> list[Schedule]:
        return self.get("/api/schedules", params={"flow_id": flow_id} if flow_id else None)

    def get_schedule(self, schedule_id: str) -> Schedule:
        return self.get(f"/api/schedules/{schedule_id}")

    def update_schedule(self, schedule_id: str, **fields: Any) -> Schedule:
        return self.patch(f"/api/schedules/{schedule_id}", json=fields)

    def delete_schedule(self, schedule_id: str) -> None:
        self.delete(f"/api/schedules/{schedule_id}")

    def run_schedule_now(self, schedule_id: str) -> Run:
        return self.post(f"/api/schedules/{schedule_id}/run-now")

    def list_schedule_runs(self, schedule_id: str, *, limit: int = 50, offset: int = 0) -> list[Run]:
        return self.get(f"/api/schedules/{schedule_id}/runs", params={"limit": limit, "offset": offset})

    # ------------------------------------------------------------------
    # ML
    # ------------------------------------------------------------------

    def get_run_ml_metrics(self, run_id: str) -> list[dict[str, Any]]:
        return self.get(f"/api/runs/{run_id}/ml/metrics")

    def register_run_model(self, run_id: str, model_name: str, *, stage: str | None = None) -> dict[str, Any]:
        return self.post(f"/api/runs/{run_id}/ml/register", json={"model_name": model_name, "stage": stage})

    def list_flow_ml_experiments(self, flow_id: str) -> list[dict[str, Any]]:
        return self.get(f"/api/flows/{flow_id}/ml/experiments")

    def list_registered_models(self) -> list[dict[str, Any]]:
        return self.get("/api/ml/models")

    def list_model_catalog(self) -> list[dict[str, Any]]:
        return self.get("/api/ml/model-catalog")

    def set_model_alias(self, model_name: str, version: str | int, alias: str) -> dict[str, Any]:
        return self.post(f"/api/ml/models/{model_name}/alias", json={"version": version, "alias": alias})

    def clear_model_alias(self, model_name: str, alias: str) -> dict[str, Any]:
        return self.request("DELETE", f"/api/ml/models/{model_name}/alias/{alias}").json()

    def list_ml_experiments(self) -> list[dict[str, Any]]:
        return self.get("/api/ml/experiments")

    def list_ml_experiment_runs(self, experiment_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.get(f"/api/ml/experiments/{experiment_id}/runs", params={"limit": limit})

    # ------------------------------------------------------------------
    # Connections
    # ------------------------------------------------------------------

    def list_connections(self) -> list[Connection]:
        return self.get("/api/connections")

    def create_connection(self, **payload: Any) -> Connection:
        return self.post("/api/connections", json=payload)

    def list_connection_providers(self) -> list[dict[str, Any]]:
        return self.get("/api/connections/providers")

    def test_connection_config(self, **payload: Any) -> ConnectionTestResult:
        return self.post("/api/connections/test-config", json=payload)

    def keyring_availability(self) -> KeyringAvailability:
        """Whether this host has a usable OS keychain (headless servers have none)."""
        return self.get("/api/connections/keyring")

    def store_keyring_secret(self, name: str, value: str, *, overwrite: bool = False) -> KeyringSecretStatus:
        """Store a secret in the OS keychain, returning its ``keyring:NAME`` reference.

        The value is written to the platform keychain and never persisted, returned,
        or logged by Ciaren. Refused with 409 if the name is taken unless ``overwrite``.
        """
        return self.post("/api/connections/keyring", json={"name": name, "value": value, "overwrite": overwrite})

    def get_keyring_secret_status(self, name: str) -> KeyringSecretStatus:
        """Whether a keychain secret exists — never returns its value."""
        return self.get(f"/api/connections/keyring/{name}")

    def delete_keyring_secret(self, name: str) -> None:
        self.delete(f"/api/connections/keyring/{name}")

    def get_connection(self, connection_id: str) -> Connection:
        return self.get(f"/api/connections/{connection_id}")

    def update_connection(self, connection_id: str, **fields: Any) -> Connection:
        return self.patch(f"/api/connections/{connection_id}", json=fields)

    def delete_connection(self, connection_id: str, *, force: bool = False) -> None:
        """Delete a connection. Refused with 409 while flows still reference it,
        unless ``force=True`` (those flows then fail at run time until repointed)."""
        self.delete(f"/api/connections/{connection_id}", params={"force": force})

    def test_connection(self, connection_id: str) -> ConnectionTestResult:
        return self.post(f"/api/connections/{connection_id}/test")

    def list_connection_tables(self, connection_id: str) -> list[dict[str, Any]]:
        return self.get(f"/api/connections/{connection_id}/tables")

    def list_connection_objects(self, connection_id: str, *, prefix: str = "") -> list[str]:
        return self.get(f"/api/connections/{connection_id}/objects", params={"prefix": prefix})

    # ------------------------------------------------------------------
    # Catalog / transformations / webhook settings
    # ------------------------------------------------------------------

    def list_catalog_nodes(self, *, category: str | None = None) -> list[dict[str, Any]]:
        return self.get("/api/catalog/nodes", params={"category": category} if category else None)

    def list_catalog_connectors(self) -> list[dict[str, Any]]:
        return self.get("/api/catalog/connectors")

    def list_catalog_exporters(self) -> list[dict[str, Any]]:
        return self.get("/api/catalog/exporters")

    def list_catalog_categories(self) -> list[dict[str, Any]]:
        return self.get("/api/catalog/categories")

    def list_transformations(self, *, include_ml: bool = True) -> Any:
        return self.get("/api/transformations", params={"include_ml": include_ml})

    def preview_transformation(self, **payload: Any) -> Any:
        return self.post("/api/transformations/preview", json=payload)

    def webhook_status(self) -> WebhookStatus:
        return self.get("/api/settings/webhook")

    # ------------------------------------------------------------------
    # Runtime app settings (Settings page allowlist)
    # ------------------------------------------------------------------

    def list_settings(self) -> list[AppSetting]:
        return self.get("/api/settings")

    def update_setting(self, key: str, value: int | str) -> AppSetting:
        return self.put(f"/api/settings/{key}", json={"value": value})

    def reset_setting(self, key: str) -> AppSetting:
        """Remove ``key``'s override, falling back to the environment/default."""
        return self.request("DELETE", f"/api/settings/{key}").json()

    # ------------------------------------------------------------------
    # Plugins / marketplace
    # ------------------------------------------------------------------

    def list_plugins(self) -> list[dict[str, Any]]:
        return self.get("/api/plugins")

    def plugin_diagnostics(self) -> dict[str, Any]:
        return self.get("/api/plugins/diagnostics")

    def install_plugin(self, path: str | Path, *, require_trusted: bool | None = None) -> dict[str, Any]:
        package_path = Path(path)
        data = {"require_trusted": str(require_trusted).lower()} if require_trusted is not None else None
        with package_path.open("rb") as handle:
            r = self._client.post(
                "/api/plugins/install",
                data=data,
                files={"file": (package_path.name, handle, "application/octet-stream")},
            )
        r.raise_for_status()
        return r.json()

    def get_plugin_license(self, plugin_id: str) -> dict[str, Any]:
        return self.get(f"/api/plugins/{plugin_id}/license")

    def activate_plugin_license(self, plugin_id: str, token: dict[str, Any]) -> dict[str, Any]:
        """Activate a license: send the pasted/downloaded token JSON (marketplace wire
        format). The server vets it against the trusted issuer keys before caching."""
        return self.post(f"/api/plugins/{plugin_id}/license", json=token)

    def remove_plugin_license(self, plugin_id: str) -> dict[str, Any]:
        return self.request("DELETE", f"/api/plugins/{plugin_id}/license").json()

    def enable_plugin(self, plugin_id: str) -> dict[str, Any]:
        return self.post(f"/api/plugins/{plugin_id}/enable")

    def disable_plugin(self, plugin_id: str) -> dict[str, Any]:
        return self.post(f"/api/plugins/{plugin_id}/disable")

    def uninstall_plugin(self, plugin_id: str) -> dict[str, Any]:
        return self.request("DELETE", f"/api/plugins/{plugin_id}").json()

    def grant_plugin_permissions(self, plugin_id: str, permissions: list[str] | None = None) -> dict[str, Any]:
        return self.post(f"/api/plugins/{plugin_id}/grant", json={"permissions": permissions or []})

    def revoke_plugin_permissions(self, plugin_id: str, permissions: list[str] | None = None) -> dict[str, Any]:
        return self.post(f"/api/plugins/{plugin_id}/revoke", json={"permissions": permissions or []})

    def list_marketplace(self) -> dict[str, Any]:
        return self.get("/api/marketplace")

    def install_marketplace_plugin(self, plugin_id: str) -> dict[str, Any]:
        return self.post(f"/api/marketplace/{plugin_id}/install")

    # ------------------------------------------------------------------
    # Webhook trigger
    # ------------------------------------------------------------------

    def _trigger_headers(self) -> dict[str, str]:
        if self._secret is None:
            raise ValueError(
                "webhook_secret is required to call trigger(). "
                "Pass it when constructing Ciaren(webhook_secret=...)."
            )
        return {"X-Ciaren-Secret": self._secret}

    def trigger(
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
        r = self._client.post(
            f"/api/flows/{flow_id}/trigger",
            json=body or None,
            headers=self._trigger_headers(),
        )
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # SSE log streaming
    # ------------------------------------------------------------------

    def stream_logs(self, run_id: str) -> Generator[dict[str, Any], None, None]:
        """Yield log entry dicts from GET /api/runs/{id}/logs/stream (SSE).

        Yields each ``data:`` event payload as a dict. Stops after the
        ``event: done`` frame arrives (that frame itself is not yielded).
        """
        import json

        with self._client.stream("GET", f"/api/runs/{run_id}/logs/stream") as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith("data:"):
                    payload = line[len("data:"):].strip()
                    try:
                        yield json.loads(payload)
                    except Exception:
                        yield {"raw": payload}
                elif line.startswith("event: done"):
                    return
