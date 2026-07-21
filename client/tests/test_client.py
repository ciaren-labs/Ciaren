"""Unit tests for the Ciaren Python client.

Uses respx to mock HTTP calls — no running server required.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from ciaren_client import AsyncCiaren, Ciaren, __version__

BASE = "http://localhost:8055"
SECRET = "test-secret"
FLOW_ID = "flow-abc"
RUN_ID = "run-xyz"

MOCK_FLOW = {"id": FLOW_ID, "name": "My Flow"}
MOCK_RUN = {"id": RUN_ID, "flow_id": FLOW_ID, "status": "success", "trigger": "webhook"}
MOCK_RUNS = [MOCK_RUN]
MOCK_PROJECT = {"id": "proj-1", "name": "Default"}
MOCK_DATASET = {"id": "ds-1", "name": "data.csv", "latest_version": 1}
MOCK_SCHEDULE = {"id": "sched-1", "flow_id": FLOW_ID, "cron": "0 9 * * *"}


def test_package_version():
    assert __version__ == "0.2.0"


# ---------------------------------------------------------------------------
# Sync — Ciaren
# ---------------------------------------------------------------------------


def test_sync_list_flows():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/api/flows").mock(return_value=httpx.Response(200, json=[MOCK_FLOW]))
        with Ciaren(BASE) as client:
            flows = client.list_flows()
    assert flows == [MOCK_FLOW]


def test_sync_project_methods():
    with respx.mock(base_url=BASE) as mock:
        create_route = mock.post("/api/projects").mock(return_value=httpx.Response(201, json=MOCK_PROJECT))
        mock.get("/api/projects/proj-1").mock(return_value=httpx.Response(200, json=MOCK_PROJECT))
        mock.put("/api/projects/proj-1").mock(return_value=httpx.Response(200, json={**MOCK_PROJECT, "color": "emerald"}))
        delete_route = mock.delete("/api/projects/proj-1").mock(return_value=httpx.Response(204))

        with Ciaren(BASE) as client:
            created = client.create_project("Default", color="emerald")
            found = client.get_project("proj-1")
            updated = client.update_project("proj-1", color="emerald")
            client.delete_project("proj-1")

    assert created["id"] == "proj-1"
    assert found == MOCK_PROJECT
    assert updated["color"] == "emerald"
    assert json.loads(create_route.calls[0].request.content)["color"] == "emerald"
    assert delete_route.called


def test_sync_dataset_methods(tmp_path):
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("value\n1\n", encoding="utf-8")

    with respx.mock(base_url=BASE) as mock:
        upload_route = mock.post("/api/datasets/upload").mock(return_value=httpx.Response(201, json=MOCK_DATASET))
        list_route = mock.get("/api/datasets").mock(return_value=httpx.Response(200, json=[MOCK_DATASET]))
        mock.get("/api/datasets/ds-1/schema").mock(return_value=httpx.Response(200, json=[{"name": "value"}]))
        mock.get("/api/datasets/ds-1/versions").mock(return_value=httpx.Response(200, json=[{"version_number": 1}]))
        mock.get("/api/datasets/ds-1/versions/1/download").mock(return_value=httpx.Response(200, content=b"value\n1\n"))
        delete_route = mock.delete("/api/datasets/ds-1").mock(return_value=httpx.Response(204))

        with Ciaren(BASE) as client:
            uploaded = client.upload_dataset(csv_path, project_id="proj-1")
            datasets = client.list_datasets(project_id="proj-1", include_deleted=True)
            schema = client.get_dataset_schema("ds-1", version=1)
            versions = client.list_dataset_versions("ds-1")
            content = client.download_dataset_version("ds-1", 1)
            client.delete_dataset("ds-1", purge=True, force=True)

    assert uploaded["id"] == "ds-1"
    assert datasets == [MOCK_DATASET]
    assert schema == [{"name": "value"}]
    assert versions == [{"version_number": 1}]
    assert content == b"value\n1\n"
    assert upload_route.calls[0].request.url.params["project_id"] == "proj-1"
    assert list_route.calls[0].request.url.params["include_deleted"] == "true"
    assert delete_route.calls[0].request.url.params["purge"] == "true"


def test_sync_flow_run_schedule_connection_and_catalog_methods():
    with respx.mock(base_url=BASE) as mock:
        create_flow_route = mock.post("/api/flows").mock(return_value=httpx.Response(201, json=MOCK_FLOW))
        mock.post(f"/api/flows/{FLOW_ID}/runs").mock(return_value=httpx.Response(201, json=MOCK_RUN))
        output_route = mock.get(f"/api/runs/{RUN_ID}/output").mock(return_value=httpx.Response(200, content=b"out"))
        mock.post(f"/api/flows/{FLOW_ID}/schedules").mock(return_value=httpx.Response(201, json=MOCK_SCHEDULE))
        mock.get("/api/schedules").mock(return_value=httpx.Response(200, json=[MOCK_SCHEDULE]))
        mock.post("/api/connections/test-config").mock(return_value=httpx.Response(200, json={"ok": True}))
        mock.get("/api/catalog/nodes").mock(return_value=httpx.Response(200, json=[{"type": "source"}]))
        mock.get("/api/transformations").mock(return_value=httpx.Response(200, json={"groups": []}))
        mock.get("/api/settings/webhook").mock(return_value=httpx.Response(200, json={"configured": True}))

        with Ciaren(BASE) as client:
            flow = client.create_flow("My Flow", project_id="proj-1", graph_json={"nodes": []})
            run = client.create_run(FLOW_ID, engine="polars", parameters={"sample": True})
            output = client.download_run_output(RUN_ID, "node-1")
            schedule = client.create_schedule(FLOW_ID, "0 9 * * *", timezone="UTC")
            schedules = client.list_schedules(flow_id=FLOW_ID)
            connection_test = client.test_connection_config(provider="postgres", config={})
            nodes = client.list_catalog_nodes(category="sources")
            transformations = client.list_transformations(include_ml=False)
            webhook = client.webhook_status()

    assert flow["id"] == FLOW_ID
    assert run == MOCK_RUN
    assert output == b"out"
    assert schedule == MOCK_SCHEDULE
    assert schedules == [MOCK_SCHEDULE]
    assert connection_test["ok"] is True
    assert nodes == [{"type": "source"}]
    assert transformations == {"groups": []}
    assert webhook["configured"] is True
    assert json.loads(create_flow_route.calls[0].request.content)["project_id"] == "proj-1"
    assert output_route.calls[0].request.url.params["node_id"] == "node-1"


def test_sync_ml_plugin_and_marketplace_methods():
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/runs/{RUN_ID}/ml/metrics").mock(return_value=httpx.Response(200, json=[{"node_id": "n1"}]))
        register_route = mock.post(f"/api/runs/{RUN_ID}/ml/register").mock(
            return_value=httpx.Response(200, json={"model_name": "churn"})
        )
        alias_route = mock.post("/api/ml/models/churn/alias").mock(
            return_value=httpx.Response(200, json={"alias": "production"})
        )
        mock.delete("/api/ml/models/churn/alias/production").mock(return_value=httpx.Response(200, json={"ok": True}))
        mock.get("/api/plugins").mock(return_value=httpx.Response(200, json=[{"id": "plugin-1"}]))
        mock.post("/api/plugins/plugin-1/grant").mock(return_value=httpx.Response(200, json={"id": "plugin-1"}))
        activate_route = mock.post("/api/plugins/plugin-1/license").mock(
            return_value=httpx.Response(200, json={"plugin_id": "plugin-1", "valid": True})
        )
        mock.delete("/api/plugins/plugin-1/license").mock(
            return_value=httpx.Response(200, json={"plugin_id": "plugin-1", "valid": False})
        )
        mock.delete("/api/plugins/plugin-1").mock(
            return_value=httpx.Response(200, json={"plugin_id": "plugin-1", "removed": True})
        )
        mock.get("/api/marketplace").mock(return_value=httpx.Response(200, json={"configured": True, "plugins": []}))
        mock.post("/api/marketplace/plugin-1/install").mock(return_value=httpx.Response(200, json={"outcome": "trusted"}))

        with Ciaren(BASE) as client:
            metrics = client.get_run_ml_metrics(RUN_ID)
            registered = client.register_run_model(RUN_ID, "churn", stage="staging")
            alias = client.set_model_alias("churn", 3, "production")
            cleared = client.clear_model_alias("churn", "production")
            plugins = client.list_plugins()
            granted = client.grant_plugin_permissions("plugin-1", ["network"])
            activated = client.activate_plugin_license("plugin-1", {"pluginId": "plugin-1"})
            removed_license = client.remove_plugin_license("plugin-1")
            uninstalled = client.uninstall_plugin("plugin-1")
            marketplace = client.list_marketplace()
            installed = client.install_marketplace_plugin("plugin-1")

    assert metrics == [{"node_id": "n1"}]
    assert registered["model_name"] == "churn"
    assert alias["alias"] == "production"
    assert cleared["ok"] is True
    assert plugins == [{"id": "plugin-1"}]
    assert granted["id"] == "plugin-1"
    assert activated["valid"] is True
    assert removed_license["valid"] is False
    assert uninstalled["removed"] is True
    assert marketplace["configured"] is True
    assert installed["outcome"] == "trusted"
    assert json.loads(register_route.calls[0].request.content)["stage"] == "staging"
    assert json.loads(alias_route.calls[0].request.content)["version"] == 3
    assert json.loads(activate_route.calls[0].request.content)["pluginId"] == "plugin-1"


def test_sync_get_flow():
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/flows/{FLOW_ID}").mock(return_value=httpx.Response(200, json=MOCK_FLOW))
        with Ciaren(BASE) as client:
            flow = client.get_flow(FLOW_ID)
    assert flow["id"] == FLOW_ID


def test_sync_list_runs():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/api/runs").mock(return_value=httpx.Response(200, json=MOCK_RUNS))
        with Ciaren(BASE) as client:
            runs = client.list_runs()
    assert runs == MOCK_RUNS


def test_sync_get_run():
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/runs/{RUN_ID}").mock(return_value=httpx.Response(200, json=MOCK_RUN))
        with Ciaren(BASE) as client:
            run = client.get_run(RUN_ID)
    assert run["id"] == RUN_ID


def test_sync_trigger_sends_secret_header():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post(f"/api/flows/{FLOW_ID}/trigger").mock(
            return_value=httpx.Response(200, json=MOCK_RUN)
        )
        with Ciaren(BASE, webhook_secret=SECRET) as client:
            run = client.trigger(FLOW_ID)
    assert run["status"] == "success"
    assert route.calls[0].request.headers["x-ciaren-secret"] == SECRET


def test_sync_trigger_raises_without_secret():
    with Ciaren(BASE) as client:
        with pytest.raises(ValueError, match="webhook_secret"):
            client.trigger(FLOW_ID)


def test_sync_trigger_with_engine():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post(f"/api/flows/{FLOW_ID}/trigger").mock(
            return_value=httpx.Response(200, json=MOCK_RUN)
        )
        with Ciaren(BASE, webhook_secret=SECRET) as client:
            client.trigger(FLOW_ID, engine="pandas")
    body = json.loads(route.calls[0].request.content)
    assert body["engine"] == "pandas"


def test_sync_trigger_http_error_raises():
    with respx.mock(base_url=BASE) as mock:
        mock.post(f"/api/flows/{FLOW_ID}/trigger").mock(
            return_value=httpx.Response(403, json={"detail": "Invalid secret"})
        )
        with Ciaren(BASE, webhook_secret=SECRET) as client:
            with pytest.raises(httpx.HTTPStatusError):
                client.trigger(FLOW_ID)


def test_sync_api_token_sends_bearer_header():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/api/flows").mock(return_value=httpx.Response(200, json=[MOCK_FLOW]))
        with Ciaren(BASE, api_token="tok-123") as client:
            client.list_flows()
    assert route.calls[0].request.headers["authorization"] == "Bearer tok-123"


def test_sync_list_runs_with_filters_and_pagination():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/api/runs").mock(return_value=httpx.Response(200, json=MOCK_RUNS))
        with Ciaren(BASE) as client:
            client.list_runs(
                project_id="proj-1",
                dataset_id="ds-1",
                schedule_id="sched-1",
                status="failed",
                started_after="2026-06-01T00:00:00",
                sort_by="status",
                sort_order="asc",
                offset=50,
            )
    params = route.calls[0].request.url.params
    assert params["project_id"] == "proj-1"
    assert params["dataset_id"] == "ds-1"
    assert params["schedule_id"] == "sched-1"
    assert params["status"] == "failed"
    assert params["started_after"] == "2026-06-01T00:00:00"
    assert params["sort_by"] == "status"
    assert params["sort_order"] == "asc"
    assert params["offset"] == "50"


def test_sync_retry_run():
    with respx.mock(base_url=BASE) as mock:
        mock.post(f"/api/runs/{RUN_ID}/retry").mock(return_value=httpx.Response(201, json=MOCK_RUN))
        with Ciaren(BASE) as client:
            run = client.retry_run(RUN_ID)
    assert run == MOCK_RUN


def test_sync_stream_logs():
    sse_body = (
        'data: {"level": "info", "message": "done"}\n\n'
        "event: done\n"
        'data: {"status": "success", "run_id": "run-xyz"}\n\n'
    )
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/runs/{RUN_ID}/logs/stream").mock(
            return_value=httpx.Response(200, text=sse_body, headers={"content-type": "text/event-stream"})
        )
        with Ciaren(BASE) as client:
            entries = list(client.stream_logs(RUN_ID))
    assert entries == [{"level": "info", "message": "done"}]


# ---------------------------------------------------------------------------
# Async — AsyncCiaren
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_list_flows():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/api/flows").mock(return_value=httpx.Response(200, json=[MOCK_FLOW]))
        async with AsyncCiaren(BASE) as client:
            flows = await client.list_flows()
    assert flows == [MOCK_FLOW]


@pytest.mark.asyncio
async def test_async_project_dataset_flow_and_schedule_methods(tmp_path):
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("value\n1\n", encoding="utf-8")

    with respx.mock(base_url=BASE) as mock:
        mock.post("/api/projects").mock(return_value=httpx.Response(201, json=MOCK_PROJECT))
        mock.post("/api/datasets/upload").mock(return_value=httpx.Response(201, json=MOCK_DATASET))
        mock.post("/api/flows/import").mock(return_value=httpx.Response(201, json=MOCK_FLOW))
        mock.post(f"/api/flows/{FLOW_ID}/export/python").mock(return_value=httpx.Response(200, json={"code": "print(1)"}))
        mock.post(f"/api/flows/{FLOW_ID}/schedules").mock(return_value=httpx.Response(201, json=MOCK_SCHEDULE))
        mock.post("/api/transformations/preview").mock(return_value=httpx.Response(200, json={"rows": []}))

        async with AsyncCiaren(BASE) as client:
            project = await client.create_project("Default")
            dataset = await client.upload_dataset(csv_path)
            flow = await client.import_flow({"nodes": []}, name="Imported")
            export = await client.export_flow_python(FLOW_ID)
            schedule = await client.create_schedule(FLOW_ID, "0 9 * * *")
            preview = await client.preview_transformation(type="select", config={})

    assert project == MOCK_PROJECT
    assert dataset == MOCK_DATASET
    assert flow == MOCK_FLOW
    assert export["code"] == "print(1)"
    assert schedule == MOCK_SCHEDULE
    assert preview == {"rows": []}


@pytest.mark.asyncio
async def test_async_connection_catalog_and_download_methods(tmp_path):
    target = tmp_path / "output.csv"

    with respx.mock(base_url=BASE) as mock:
        mock.get("/api/connections/providers").mock(return_value=httpx.Response(200, json=[{"name": "postgres"}]))
        mock.get("/api/connections/conn-1/objects").mock(return_value=httpx.Response(200, json=["raw/events"]))
        mock.get("/api/catalog/categories").mock(return_value=httpx.Response(200, json=[{"id": "sources"}]))
        mock.get("/api/datasets/ds-1/versions/1/download").mock(return_value=httpx.Response(200, content=b"value\n1\n"))
        mock.get("/api/settings/webhook").mock(return_value=httpx.Response(200, json={"configured": False}))

        async with AsyncCiaren(BASE) as client:
            providers = await client.list_connection_providers()
            objects = await client.list_connection_objects("conn-1", prefix="raw/")
            categories = await client.list_catalog_categories()
            downloaded = await client.download_dataset_version("ds-1", 1, target)
            webhook = await client.webhook_status()

    assert providers == [{"name": "postgres"}]
    assert objects == ["raw/events"]
    assert categories == [{"id": "sources"}]
    assert downloaded == target
    assert target.read_bytes() == b"value\n1\n"
    assert webhook["configured"] is False


@pytest.mark.asyncio
async def test_async_ml_plugin_and_marketplace_methods():
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/flows/{FLOW_ID}/ml/experiments").mock(return_value=httpx.Response(200, json=[{"id": "exp-1"}]))
        mock.get("/api/ml/models").mock(return_value=httpx.Response(200, json=[{"name": "churn"}]))
        mock.get("/api/ml/model-catalog").mock(return_value=httpx.Response(200, json=[{"id": "random_forest"}]))
        mock.get("/api/ml/experiments").mock(return_value=httpx.Response(200, json=[{"id": "exp-1"}]))
        runs_route = mock.get("/api/ml/experiments/exp-1/runs").mock(return_value=httpx.Response(200, json=[{"run_id": RUN_ID}]))
        mock.get("/api/plugins/diagnostics").mock(return_value=httpx.Response(200, json={"loaded": [], "gated": [], "errors": []}))
        mock.post("/api/plugins/plugin-1/disable").mock(return_value=httpx.Response(200, json={"id": "plugin-1"}))
        mock.get("/api/plugins/plugin-1/license").mock(
            return_value=httpx.Response(200, json={"plugin_id": "plugin-1", "valid": True})
        )
        mock.delete("/api/plugins/plugin-1").mock(
            return_value=httpx.Response(200, json={"plugin_id": "plugin-1", "removed": True})
        )

        async with AsyncCiaren(BASE) as client:
            flow_experiments = await client.list_flow_ml_experiments(FLOW_ID)
            models = await client.list_registered_models()
            catalog = await client.list_model_catalog()
            experiments = await client.list_ml_experiments()
            experiment_runs = await client.list_ml_experiment_runs("exp-1", limit=10)
            diagnostics = await client.plugin_diagnostics()
            disabled = await client.disable_plugin("plugin-1")
            license_status = await client.get_plugin_license("plugin-1")
            uninstalled = await client.uninstall_plugin("plugin-1")

    assert flow_experiments == [{"id": "exp-1"}]
    assert models == [{"name": "churn"}]
    assert catalog == [{"id": "random_forest"}]
    assert experiments == [{"id": "exp-1"}]
    assert experiment_runs == [{"run_id": RUN_ID}]
    assert diagnostics["loaded"] == []
    assert disabled["id"] == "plugin-1"
    assert license_status["valid"] is True
    assert uninstalled["removed"] is True
    assert runs_route.calls[0].request.url.params["limit"] == "10"


@pytest.mark.asyncio
async def test_async_get_flow():
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/flows/{FLOW_ID}").mock(return_value=httpx.Response(200, json=MOCK_FLOW))
        async with AsyncCiaren(BASE) as client:
            flow = await client.get_flow(FLOW_ID)
    assert flow["id"] == FLOW_ID


@pytest.mark.asyncio
async def test_async_list_runs():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/api/runs").mock(return_value=httpx.Response(200, json=MOCK_RUNS))
        async with AsyncCiaren(BASE) as client:
            runs = await client.list_runs()
    assert runs == MOCK_RUNS


@pytest.mark.asyncio
async def test_async_get_run():
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/runs/{RUN_ID}").mock(return_value=httpx.Response(200, json=MOCK_RUN))
        async with AsyncCiaren(BASE) as client:
            run = await client.get_run(RUN_ID)
    assert run["id"] == RUN_ID


@pytest.mark.asyncio
async def test_async_trigger_sends_secret_header():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post(f"/api/flows/{FLOW_ID}/trigger").mock(
            return_value=httpx.Response(200, json=MOCK_RUN)
        )
        async with AsyncCiaren(BASE, webhook_secret=SECRET) as client:
            run = await client.trigger(FLOW_ID)
    assert run["status"] == "success"
    assert route.calls[0].request.headers["x-ciaren-secret"] == SECRET


@pytest.mark.asyncio
async def test_async_trigger_raises_without_secret():
    async with AsyncCiaren(BASE) as client:
        with pytest.raises(ValueError, match="webhook_secret"):
            await client.trigger(FLOW_ID)


@pytest.mark.asyncio
async def test_async_trigger_with_parameters():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post(f"/api/flows/{FLOW_ID}/trigger").mock(
            return_value=httpx.Response(200, json=MOCK_RUN)
        )
        async with AsyncCiaren(BASE, webhook_secret=SECRET) as client:
            await client.trigger(FLOW_ID, parameters={"env": "prod"})
    body = json.loads(route.calls[0].request.content)
    assert body["parameters"] == {"env": "prod"}


@pytest.mark.asyncio
async def test_async_api_token_sends_bearer_header():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/api/flows").mock(return_value=httpx.Response(200, json=[MOCK_FLOW]))
        async with AsyncCiaren(BASE, api_token="tok-123") as client:
            await client.list_flows()
    assert route.calls[0].request.headers["authorization"] == "Bearer tok-123"


@pytest.mark.asyncio
async def test_async_list_runs_with_filters_and_pagination():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/api/runs").mock(return_value=httpx.Response(200, json=MOCK_RUNS))
        async with AsyncCiaren(BASE) as client:
            await client.list_runs(schedule_id="sched-1", status="success", offset=10)
    params = route.calls[0].request.url.params
    assert params["schedule_id"] == "sched-1"
    assert params["status"] == "success"
    assert params["offset"] == "10"


@pytest.mark.asyncio
async def test_async_retry_run():
    with respx.mock(base_url=BASE) as mock:
        mock.post(f"/api/runs/{RUN_ID}/retry").mock(return_value=httpx.Response(201, json=MOCK_RUN))
        async with AsyncCiaren(BASE) as client:
            run = await client.retry_run(RUN_ID)
    assert run == MOCK_RUN


def test_sync_flow_run_settings_and_keyring_methods():
    with respx.mock(base_url=BASE) as mock:
        duplicate_route = mock.post(f"/api/flows/{FLOW_ID}/duplicate").mock(
            return_value=httpx.Response(201, json={**MOCK_FLOW, "id": "flow-copy"})
        )
        mock.post("/api/flows/migrate-document").mock(
            return_value=httpx.Response(
                200, json={"document": {"v": 2}, "migrated": True, "from_version": "1", "to_version": "2"}
            )
        )
        mock.post(f"/api/runs/{RUN_ID}/cancel").mock(
            return_value=httpx.Response(202, json={"status": "cancelling"})
        )
        mock.get("/api/settings").mock(return_value=httpx.Response(200, json=[{"key": "poll_interval"}]))
        update_route = mock.put("/api/settings/poll_interval").mock(
            return_value=httpx.Response(200, json={"key": "poll_interval", "value": 5})
        )
        reset_route = mock.delete("/api/settings/poll_interval").mock(
            return_value=httpx.Response(200, json={"key": "poll_interval", "value": 1})
        )
        mock.get("/api/connections/keyring").mock(return_value=httpx.Response(200, json={"available": True}))
        store_route = mock.post("/api/connections/keyring").mock(
            return_value=httpx.Response(201, json={"name": "db-pass", "exists": True, "reference": "keyring:db-pass"})
        )
        mock.get("/api/connections/keyring/db-pass").mock(
            return_value=httpx.Response(200, json={"name": "db-pass", "exists": True, "reference": "keyring:db-pass"})
        )
        delete_secret_route = mock.delete("/api/connections/keyring/db-pass").mock(return_value=httpx.Response(204))
        delete_conn_route = mock.delete("/api/connections/conn-1").mock(return_value=httpx.Response(204))

        with Ciaren(BASE) as client:
            duplicated = client.duplicate_flow(FLOW_ID, name="Copy")
            migrated = client.migrate_flow_document({"v": 1})
            cancelled = client.cancel_run(RUN_ID)
            settings = client.list_settings()
            updated_setting = client.update_setting("poll_interval", 5)
            reset = client.reset_setting("poll_interval")
            availability = client.keyring_availability()
            stored = client.store_keyring_secret("db-pass", "s3cr3t", overwrite=True)
            status_ = client.get_keyring_secret_status("db-pass")
            client.delete_keyring_secret("db-pass")
            client.delete_connection("conn-1", force=True)

    assert duplicated["id"] == "flow-copy"
    assert migrated["migrated"] is True
    assert cancelled["status"] == "cancelling"
    assert settings == [{"key": "poll_interval"}]
    assert updated_setting["value"] == 5
    assert reset["value"] == 1
    assert availability["available"] is True
    assert stored["reference"] == "keyring:db-pass"
    assert status_["exists"] is True
    assert duplicate_route.calls[0].request.url.params["name"] == "Copy"
    assert json.loads(update_route.calls[0].request.content)["value"] == 5
    assert reset_route.called
    assert json.loads(store_route.calls[0].request.content)["overwrite"] is True
    assert delete_secret_route.called
    assert delete_conn_route.calls[0].request.url.params["force"] == "true"


@pytest.mark.asyncio
async def test_async_stream_logs():
    sse_body = (
        'data: {"level": "info", "message": "step 1"}\n\n'
        'data: {"level": "info", "message": "step 2"}\n\n'
        "event: done\n"
        'data: {"status": "success", "run_id": "run-xyz"}\n\n'
    )
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/runs/{RUN_ID}/logs/stream").mock(
            return_value=httpx.Response(200, text=sse_body, headers={"content-type": "text/event-stream"})
        )
        async with AsyncCiaren(BASE) as client:
            entries = [entry async for entry in client.stream_logs(RUN_ID)]
    assert entries == [
        {"level": "info", "message": "step 1"},
        {"level": "info", "message": "step 2"},
    ]


@pytest.mark.asyncio
async def test_async_flow_run_settings_and_keyring_methods():
    with respx.mock(base_url=BASE) as mock:
        mock.post(f"/api/flows/{FLOW_ID}/duplicate").mock(
            return_value=httpx.Response(201, json={**MOCK_FLOW, "id": "flow-copy"})
        )
        mock.post("/api/flows/migrate-document").mock(
            return_value=httpx.Response(
                200, json={"document": {"v": 2}, "migrated": True, "from_version": "1", "to_version": "2"}
            )
        )
        mock.post(f"/api/runs/{RUN_ID}/cancel").mock(return_value=httpx.Response(202, json={"status": "cancelling"}))
        mock.get("/api/settings").mock(return_value=httpx.Response(200, json=[{"key": "poll_interval"}]))
        mock.put("/api/settings/poll_interval").mock(
            return_value=httpx.Response(200, json={"key": "poll_interval", "value": 5})
        )
        mock.delete("/api/settings/poll_interval").mock(
            return_value=httpx.Response(200, json={"key": "poll_interval", "value": 1})
        )
        mock.get("/api/connections/keyring").mock(return_value=httpx.Response(200, json={"available": True}))
        mock.post("/api/connections/keyring").mock(
            return_value=httpx.Response(201, json={"name": "db-pass", "exists": True, "reference": "keyring:db-pass"})
        )
        mock.delete("/api/connections/keyring/db-pass").mock(return_value=httpx.Response(204))
        delete_conn_route = mock.delete("/api/connections/conn-1").mock(return_value=httpx.Response(204))

        async with AsyncCiaren(BASE) as client:
            duplicated = await client.duplicate_flow(FLOW_ID, name="Copy")
            migrated = await client.migrate_flow_document({"v": 1})
            cancelled = await client.cancel_run(RUN_ID)
            settings = await client.list_settings()
            updated_setting = await client.update_setting("poll_interval", 5)
            reset = await client.reset_setting("poll_interval")
            availability = await client.keyring_availability()
            stored = await client.store_keyring_secret("db-pass", "s3cr3t")
            await client.delete_keyring_secret("db-pass")
            await client.delete_connection("conn-1", force=True)

    assert duplicated["id"] == "flow-copy"
    assert migrated["migrated"] is True
    assert cancelled["status"] == "cancelling"
    assert settings == [{"key": "poll_interval"}]
    assert updated_setting["value"] == 5
    assert reset["value"] == 1
    assert availability["available"] is True
    assert stored["reference"] == "keyring:db-pass"
    assert delete_conn_route.calls[0].request.url.params["force"] == "true"
