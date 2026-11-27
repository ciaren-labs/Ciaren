import json
from unittest.mock import AsyncMock

import pytest
from opentelemetry import context as otel
from sqlalchemy import select

from app.core import assistant_keys
from app.core.assistant_profiles import PROFILES
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.core.secrets import ensure_permitted_secret_ref
from app.db.models.app_setting import AppSetting
from app.db.models.run import FlowRun
from app.services import assistant_provider

KEY = "synthetic-assistant-credential-87432"
ROW = "private-row-sentinel"


@pytest.fixture
def enabled(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ASSISTANT_PROVIDER", "openai")
    assistant_provider._turns.clear()
    return settings


@pytest.mark.parametrize("provider", PROFILES)
async def test_wire_contract(provider, enabled, monkeypatch, caplog):
    from pydantic import SecretStr

    profile = PROFILES[provider]
    monkeypatch.setattr(enabled, "ASSISTANT_PROVIDER", provider)
    monkeypatch.setattr(enabled, f"ASSISTANT_{provider.upper()}_KEY_SOURCE", "env")
    monkeypatch.setattr(enabled, f"ASSISTANT_{provider.upper()}_API_KEY", SecretStr(KEY))
    if profile.efforts:
        monkeypatch.setattr(enabled, f"ASSISTANT_{provider.upper()}_EFFORT", profile.efforts[0])
    result = '{"steps":[{"kind":"limitRows","count":2}]}'
    wire = {
        "openai": {
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": result}]}],
        },
        "anthropic": {
            "stop_reason": "end_turn",
            "content": [{"type": "thinking", "thinking": ROW}, {"type": "text", "text": result}],
        },
        "deepseek": {"choices": [{"finish_reason": "stop", "message": {"content": result, "reasoning_content": ROW}}]},
        "opencode": {"choices": [{"finish_reason": "stop", "message": {"content": result}}]},
    }[provider]
    calls = []

    class MockSession:
        status = 200

        def __init__(self, **options):
            assert options["trust_env"] is False
            self.content = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            pass

        def post(self, url, *, json, headers, allow_redirects):
            calls.append(url)
            assert not allow_redirects and url == profile.url
            assert otel.get_value(otel._SUPPRESS_HTTP_INSTRUMENTATION_KEY)
            assert otel.get_value(otel._SUPPRESS_INSTRUMENTATION_KEY)
            assert headers.get("x-api-key", headers.get("Authorization")) in (KEY, f"Bearer {KEY}")
            assert "tools" not in json and KEY not in repr(json)
            assert json["model"] == profile.models[0]
            if provider == "openai":
                assert (
                    json["store"] is False
                    and json["reasoning"] == {"effort": "low"}
                    and json["max_output_tokens"] == 2048
                )
            elif provider == "anthropic":
                assert json["thinking"]["type"] == "adaptive" and json["output_config"]["effort"] == "low"
                assert headers["anthropic-version"] == "2023-06-01"
            elif provider == "deepseek":
                assert json["reasoning_effort"] == "low"
            else:
                assert "reasoning_effort" not in json
            return self

        async def iter_chunked(self, size):
            yield json.dumps(wire).encode()

    monkeypatch.setattr(assistant_provider.aiohttp, "ClientSession", MockSession)
    assert await assistant_provider.complete(provider, "instructions", {"question": "limit rows"}) == json.loads(result)
    MockSession.status = 429
    with pytest.raises(ValidationError, match="HTTP 429"):
        await assistant_provider.complete(provider, "instructions", {})
    assert calls == [profile.url, profile.url]
    if provider in ("opencode", "deepseek"):
        MockSession.status = 200
        wire["choices"][0]["message"] = None
        with pytest.raises(ValidationError, match="structured answer"):
            await assistant_provider.complete(provider, "instructions", {})
    assert KEY not in caplog.text and ROW not in caplog.text


async def test_credentials_and_boundaries(client, enabled, monkeypatch, db_session, caplog, tmp_path):
    entries = {}

    class Keychain:
        def set_password(self, service, name, value):
            entries[service, name] = value

        def get_password(self, service, name):
            return entries.get((service, name))

        def delete_password(self, service, name):
            entries.pop((service, name))

    monkeypatch.setattr(assistant_keys, "_backend", Keychain)
    url = "/api/assistant/credentials/openai"
    for key in (KEY, KEY + "rotated"):
        r = await client.put(url, json={"key": key})
        assert r.status_code == 204 and not r.content
        assert (await client.get("/api/assistant/status")).json()["state"] == "configured"
    assert len(entries) == 1 and next(iter(entries))[0] != "ciaren"
    assert (await client.put("/api/assistant/credentials/deepseek", json={"key": KEY})).status_code == 400
    invalid = await client.put(url, json={"key": {KEY: KEY}})
    assert invalid.status_code == 422 and KEY not in invalid.text
    assert (
        await client.put(url, json={"key": KEY}, headers={"Origin": "https://untrusted.invalid"})
    ).status_code == 403
    assert (await client.put(url, content=b"x" * 9000)).status_code == 413
    monkeypatch.setattr(enabled, "API_TOKEN", "ciaren-test-token")
    assert (await client.get("/api/assistant/status")).status_code == 401
    assert (await client.delete(url)).status_code == 401
    assert (await client.delete(url, headers={"Authorization": "Bearer ciaren-test-token"})).status_code == 204
    assert not entries
    for provider in PROFILES:
        with pytest.raises(ValidationError):
            ensure_permitted_secret_ref(f"CIAREN_ASSISTANT_{provider.upper()}_API_KEY")
    monkeypatch.setattr(enabled, "SECRET_FILE_DIRS", [str(tmp_path)])
    monkeypatch.setattr(enabled, "ASSISTANT_SECRET_DIR", str(tmp_path / "private"))
    with pytest.raises(ValidationError):
        ensure_permitted_secret_ref(f"file:{tmp_path}/private/openai")
    assert not (await db_session.scalars(select(AppSetting))).all()
    assert KEY not in caplog.text


async def test_review_apply_replay_export_and_diagnosis(client, enabled, db_session, monkeypatch):
    flow = (await client.post("/api/flows", json={"name": "Review"})).json()
    other = (await client.post("/api/flows", json={"name": "Other"})).json()
    dataset = (
        await client.post("/api/datasets/upload", files={"file": ("hidden.csv", f"private_column\n{ROW}\n")})
    ).json()
    url = f"/api/assistant/flows/{flow['id']}"
    completion = AsyncMock(return_value={"steps": [{"kind": "limitRows", "count": 1}]})
    monkeypatch.setattr(assistant_provider, "complete", completion)
    body = {
        "mode": "build",
        "provider": "openai",
        "question": "Limit rows",
        "revision": flow["updated_at"],
        "graph": {"nodes": [], "edges": [], "engine": "polars"},
        "dataset_id": dataset["id"],
    }
    r = await client.post(url + "/turn", json=body)
    assert r.status_code == 200, r.text
    confirmation = {"proposal": r.json()["proposal"]}
    context = repr(completion.await_args.args[-1])
    assert not any(s in context for s in (dataset["id"], "hidden.csv", ROW, "private_column"))
    assert not (await client.get(f"/api/flows/{flow['id']}")).json()["graph_json"]
    assert (await client.post(f"/api/assistant/flows/{other['id']}/apply", json=confirmation)).status_code == 409
    assert (await client.post(url + "/apply", json=confirmation)).status_code == 200
    assert (await client.post(url + "/apply", json=confirmation)).status_code == 409
    flow = (await client.get(f"/api/flows/{flow['id']}")).json()
    graph = flow["graph_json"]
    assert graph["engine"] == "polars" and [n["type"] for n in graph["nodes"]] == [
        "fileInput",
        "limitRows",
        "fileOutput",
    ]
    exported = await client.post(f"/api/flows/{flow['id']}/export/python")
    assert exported.status_code == 200 and exported.json()["code"] and exported.json()["polars"]
    assert KEY not in exported.text
    db_session.add(FlowRun(flow_id=flow["id"], status="failed", error_message="column error: " + ROW))
    await db_session.commit()
    body.update(mode="diagnose", revision=flow["updated_at"], graph=graph)
    completion.return_value = {"replace": 1, "steps": [{"kind": "limitRows", "count": 2}]}
    r = await client.post(url + "/turn", json=body)
    assert r.status_code == 200 and "column" in r.json()["message"]
    assert ROW not in repr(completion.await_args.args[-1])
    assert r.json()["delta"]["changed"][0]["data"]["config"]["n"] == 2
    await client.put(f"/api/flows/{flow['id']}", json={"name": "Concurrent rename"})
    assert (await client.post(url + "/apply", json={"proposal": r.json()["proposal"]})).status_code == 409


async def test_docs_citation_abstention(client, enabled, monkeypatch):
    flow = (await client.post("/api/flows", json={"name": "Guide"})).json()
    url = f"/api/assistant/flows/{flow['id']}/turn"
    body = dict(mode="docs", provider="openai", question="How do I export Polars code?", revision=flow["updated_at"])
    completion = AsyncMock(return_value={"passage": 0, "url": "https://untrusted.invalid"})
    monkeypatch.setattr(assistant_provider, "complete", completion)
    r = (await client.post(url, json=body)).json()
    assert "github.com/ciaren-labs/Ciaren/blob/" in r["citation"]["url"]
    assert r["message"] in completion.await_args.args[-1]["passages"]
    body["question"] = "¿Cómo conecto las dos entradas de Join?"
    join = (await client.post(url, json=body)).json()
    assert "/docs/transformations/join.md#L" in join["citation"]["url"]
    assert "**left** handle" in join["message"] and "**right** handle" in join["message"]
    body["question"] = "zzzzzzqx"
    assert "citation" not in (await client.post(url, json=body)).json()
    assert completion.await_count == 2


async def test_scope_resources_before_provider_call(client, enabled, monkeypatch):
    flow = (await client.post("/api/flows", json={"name": "Scope"})).json()
    project = (await client.post("/api/projects", json={"name": "Separate"})).json()
    dataset = (
        await client.post(
            "/api/datasets/upload",
            params={"project_id": project["id"]},
            files={"file": ("separate.csv", b"amount\n8\n")},
        )
    ).json()
    assert dataset["project_id"] != flow["project_id"]
    complete = AsyncMock()
    monkeypatch.setattr(assistant_provider, "complete", complete)
    url = f"/api/assistant/flows/{flow['id']}/turn"
    body = {
        "revision": flow["updated_at"],
        "graph": {},
        "provider": "openai",
        "mode": "build",
        "question": "Limit rows",
        "dataset_id": dataset["id"],
    }
    assert (await client.post(url, json=body)).status_code == 400
    body["mode"] = "diagnose"
    body["graph"] = {
        "nodes": [{"id": ROW, "type": "pythonTransform", "data": {"label": ROW, "config": {"code": ROW}}}],
        "edges": [],
    }
    complete.return_value = {"check": "schema", "unexpected": ROW}
    result = await client.post(url, json=body)
    assert result.status_code == 200 and "manual edit" in result.text
    assert ROW not in result.text and ROW not in repr(complete.await_args.args)
    assert complete.await_count == 1
    monkeypatch.setattr(enabled, "ASSISTANT_ENABLED", False)
    assert (await client.post(url, json=body)).status_code == 400
    assert (await client.put("/api/assistant/credentials/openai", json={"key": KEY})).status_code == 400


def test_projected_columns_and_typed_steps():
    from app.schemas.assistant import Plan
    from app.services.assistant_graph import compile_plan

    graph = {"nodes": [], "edges": [], "engine": "pandas"}
    binding = {"dataset_id": "fixture", "dataset_version": 1}
    steps = [
        {"kind": "selectColumns", "columns": [0]},
        {"kind": "filterRows", "columns": [0], "operator": ">", "value": 2},
    ]
    types = {"amount": "integer", "city": "string"}
    result, delta = compile_plan(graph, Plan(steps=steps), types, binding, "csv")
    assert result["nodes"][2]["data"]["config"] == {"column": "amount", "operator": ">", "value": 2}
    assert len(delta["connected"]) == 3 and not graph["nodes"]
    steps[1]["columns"] = [1]
    with pytest.raises(ValidationError, match="failed Ciaren validation"):
        compile_plan(graph, Plan(steps=steps), types, binding, "csv")
    steps[1].update(columns=[0], value="many")
    with pytest.raises(ValidationError, match="failed Ciaren validation"):
        compile_plan(graph, Plan(steps=steps), types, binding, "csv")
    # Existing columns outside the provider's 64-column window remain valid locally.
    wide_types = {f"column_{i}": "integer" for i in range(65)}
    result["nodes"][1]["data"]["config"]["columns"] = ["column_64"]
    result["nodes"][2]["data"]["config"]["column"] = "column_64"
    compile_plan(result, Plan(steps=[{"kind": "limitRows", "count": 1}]), wide_types, binding, "csv")


def test_file_source_rotation_and_isolation(enabled, monkeypatch, tmp_path):
    from app.connectors.base import ConnectorError
    from app.connectors.confinement import ensure_allowed_path
    from app.connectors.local_storage import LocalStorageConnector
    from app.connectors.storage_base import StorageSpec

    mount = tmp_path / "assistant-private"
    mount.mkdir()
    slot = mount / "openai"
    slot.write_text(KEY)
    monkeypatch.setattr(enabled, "ASSISTANT_SECRET_DIR", str(mount))
    monkeypatch.setattr(enabled, "ASSISTANT_OPENAI_KEY_SOURCE", "file")
    assert assistant_keys.read_key("openai").get_secret_value() == KEY
    slot.write_text(KEY + "rotated")
    assert assistant_keys.read_key("openai").get_secret_value() == KEY + "rotated"
    with pytest.raises(ValidationError):
        assistant_keys.write_key("openai", None)
    with pytest.raises(ConnectorError):
        ensure_allowed_path(slot, "Object")
    spec = StorageSpec(provider="local", bucket=str(tmp_path))
    with pytest.raises(ConnectorError):
        LocalStorageConnector().read_sample(spec, "assistant-private/openai", 16)
    slot.unlink()
    with pytest.raises(ValidationError, match="source unavailable"):
        assistant_keys.read_key("openai")
