import json
from unittest.mock import AsyncMock, MagicMock

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
# These tests cover the structured fallback planners, which serve models without tool calling.
pytestmark = pytest.mark.usefixtures("structured_planner")


async def failed_run(db_session, flow_id):
    """Diagnose explains the latest failed run, so diagnosis tests record one first."""
    db_session.add(FlowRun(flow_id=flow_id, status="failed", error_message="column error: " + ROW))
    await db_session.commit()


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
                assert json["response_format"] == {"type": "json_object"}
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
    if provider == "deepseek":
        for malformed in ("   ", "```json\n{}\n```", json.dumps([ROW])):
            wire["choices"][0]["message"] = {"content": malformed}
            with pytest.raises(ValidationError, match="incomplete structured answer"):
                await assistant_provider.complete(provider, "Return JSON.", {})
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
    empty = {"nodes": [], "edges": [], "engine": "polars"}
    flow = (await client.post("/api/flows", json={"name": "Review"})).json()
    flow = (await client.put(f"/api/flows/{flow['id']}", json={"graph_json": empty})).json()
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
        "graph": empty,
        "dataset_id": dataset["id"],
    }
    r = await client.post(url + "/turn", json=body)
    assert r.status_code == 200, r.text
    confirmation = {"proposal": r.json()["proposal"]}
    context = repr(completion.await_args.args[-1])
    assert not any(s in context for s in (dataset["id"], "hidden.csv", ROW, "private_column"))
    assert (await client.get(f"/api/flows/{flow['id']}")).json()["graph_json"] == empty
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


@pytest.mark.parametrize(
    "variant",
    ["config", "label", "extra_node", "edge", "parameters", "omitted", "position", "engine", "utc", "offset"],
)
async def test_stored_graph_is_the_proposal_base(client, enabled, monkeypatch, variant):
    from copy import deepcopy
    from datetime import datetime, timedelta, timezone

    flow = (await client.post("/api/flows", json={"name": "Stored base"})).json()
    dataset = (await client.post("/api/datasets/upload", files={"file": ("base.csv", "amount\n1\n2\n")})).json()
    ids = ["a" * 32, "b" * 32, "c" * 32]
    configs = [
        {"dataset_id": dataset["id"], "format": "csv"},
        {"n": 5, "offset": 0},
        {"format": "csv", "dataset_name": "Base result"},
    ]
    stored = {
        "engine": "pandas",
        "nodes": [
            {"id": i, "type": kind, "position": {"x": x, "y": 0}, "data": {"label": kind, "config": cfg}}
            for x, (i, kind, cfg) in enumerate(zip(ids, ["fileInput", "limitRows", "fileOutput"], configs))
        ],
        "edges": [
            {"id": "e1", "source": ids[0], "target": ids[1], "sourceHandle": "out", "targetHandle": "in"},
            {"id": "e2", "source": ids[1], "target": ids[2], "sourceHandle": "out", "targetHandle": "in"},
        ],
    }
    path = f"/api/flows/{flow['id']}"
    flow = (await client.put(path, json={"graph_json": stored})).json()
    draft = deepcopy(stored)
    revision = flow["updated_at"]
    if variant == "config":
        draft["nodes"][1]["data"]["config"]["n"] = 99
    elif variant == "label":
        draft["nodes"][1]["data"]["label"] = "Renamed"
    elif variant == "extra_node":
        draft["nodes"].append({"id": ROW, "type": "pythonTransform", "data": {"label": "x", "config": {"code": ROW}}})
    elif variant == "edge":
        draft["edges"].pop()
    elif variant == "parameters":
        draft["parameters"] = [{"name": "limit", "type": "integer", "default": 1}]
    elif variant == "position":
        draft["nodes"][1]["position"] = {"x": 900, "y": 900}
    elif variant == "engine":
        draft["engine"] = "polars"
    elif variant in {"utc", "offset"}:
        instant = datetime.fromisoformat(revision).replace(tzinfo=timezone.utc)
        zone = timezone(timedelta(hours=2)) if variant == "offset" else timezone.utc
        revision = instant.astimezone(zone).isoformat()
    complete = AsyncMock(return_value={"steps": [{"kind": "limitRows", "count": 1}]})
    monkeypatch.setattr(assistant_provider, "complete", complete)
    body = {"mode": "build", "provider": "openai", "question": "Limit rows", "revision": revision, "graph": draft}
    if variant == "omitted":
        del body["graph"]
    url = f"/api/assistant/flows/{flow['id']}"
    r = await client.post(url + "/turn", json=body)
    if variant in {"config", "label", "extra_node", "edge", "parameters"}:
        assert r.status_code == 409 and r.json()["reason"] == "unsaved_changes", r.text
        assert ROW not in r.text and complete.await_count == 0
        assert (await client.get(path)).json()["graph_json"] == stored
    else:
        assert r.status_code == 200 and r.json()["expires_in"] == 180, r.text
        applied = await client.post(url + "/apply", json={"proposal": r.json()["proposal"]})
        assert applied.status_code == 200, applied.text
        saved = (await client.get(path)).json()["graph_json"]
        assert applied.json()["graph"] == saved
        assert saved["engine"] == "pandas" and len(saved["nodes"]) == 4
        # Only the stored base reaches the saved graph: draft presentation edits are not written.
        assert [n for n in saved["nodes"] if n["id"] in ids] == stored["nodes"]


@pytest.mark.parametrize(
    ("case", "reason", "action"),
    [
        ("no_dataset", "no_dataset", "manual_edit"),
        ("no_input", "no_dataset", "manual_edit"),
        ("multiple_inputs", "multiple_inputs", "manual_edit"),
        ("unsupported_node", "unsupported_node", "manual_edit"),
        ("no_failed_run", "no_failed_run", "switch_mode"),
        ("disabled_flow", "disabled_flow", None),
        ("canvas_limit", "canvas_limit", "manual_edit"),
    ],
)
async def test_preflight_refuses_before_any_provider_call(client, enabled, monkeypatch, case, reason, action):
    flow = (await client.post("/api/flows", json={"name": "Preflight"})).json()
    dataset = (await client.post("/api/datasets/upload", files={"file": ("pre.csv", "amount\n1\n")})).json()

    def node(i, kind, config):
        return {"id": f"n{i}", "type": kind, "position": {"x": 0, "y": 0}, "data": {"label": kind, "config": config}}

    source = {"dataset_id": dataset["id"], "format": "csv"}
    graph = {
        "no_dataset": {"nodes": [], "edges": []},
        "no_input": {"nodes": [node(0, "limitRows", {"n": 1, "offset": 0})], "edges": []},
        "multiple_inputs": {"nodes": [node(0, "fileInput", source), node(1, "fileInput", source)], "edges": []},
        "unsupported_node": {"nodes": [node(0, "pythonTransform", {"code": ROW})], "edges": []},
        "canvas_limit": {"nodes": [node(i, "limitRows", {"n": 1, "offset": 0}) for i in range(81)], "edges": []},
    }.get(case, {"nodes": [node(0, "fileInput", source)], "edges": []})
    update = {"graph_json": graph, **({"is_disabled": True} if case == "disabled_flow" else {})}
    flow = (await client.put(f"/api/flows/{flow['id']}", json=update)).json()
    complete = AsyncMock(return_value={"steps": [{"kind": "limitRows", "count": 1}]})
    monkeypatch.setattr(assistant_provider, "complete", complete)
    body = {
        "mode": "diagnose" if case == "no_failed_run" else "build",
        "provider": "openai",
        "question": "Limit rows",
        "revision": flow["updated_at"],
    }
    r = await client.post(f"/api/assistant/flows/{flow['id']}/turn", json=body)
    assert complete.await_count == 0
    assert r.json()["reason"] == reason and ROW not in r.text
    if action is None:
        assert r.status_code == 409
        from app.main import app

        documented = app.openapi()["paths"]["/api/assistant/flows/{flow_id}/turn"]["post"]["responses"]["409"]
        refusal = documented["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]
        reasons = app.openapi()["components"]["schemas"][refusal]["properties"]["reason"]["anyOf"][0]["enum"]
        assert {"unsaved_changes", "disabled_flow"} <= set(reasons)
    else:
        reply = r.json()
        assert r.status_code == 200 and "proposal" not in reply and reply["message"]
        assert action in {s["action"] for s in reply["suggestions"]}
        assert case != "unsupported_node" or "limitRows" in reply["supported"]


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


@pytest.mark.parametrize(
    ("question", "excerpt", "source"),
    [
        ("How do I set up an API key?", "**New API key**", "flow-assistant-quick-start"),
        ("Where can I see the history of assistant changes?", "**Preview reversal**", "flow-assistant-quick-start"),
        ("Do I need an API key to use Ciaren?", "visual pipeline builder without an API key", "quick-start"),
        ("Can Ciaren build a pipeline from a prompt?", "supported CSV operations", "flow-assistant-quick-start"),
        ("How do I train a shipping cost model from three CSVs?", "seeded train/test split", "flow-assistant"),
        ("Can I connect my agent via MCP?", "does not ship a Model Context Protocol", "external-agent"),
    ],
)
async def test_guides_retrieve_onboarding_passages(client, enabled, monkeypatch, question, excerpt, source):
    from re import fullmatch

    def choose(_provider, _instruction, context):
        assert set(context) == {"question", "passages"}
        return {"passage": next((i for i, passage in enumerate(context["passages"]) if excerpt in passage), None)}

    monkeypatch.setattr(assistant_provider, "complete", AsyncMock(side_effect=choose))
    flow = (await client.post("/api/flows", json={"name": "Guides"})).json()
    response = await client.post(
        f"/api/assistant/flows/{flow['id']}/turn",
        json={"mode": "docs", "provider": "openai", "question": question, "revision": flow["updated_at"]},
    )
    assert response.status_code == 200
    answer = response.json()
    assert excerpt in answer["message"]
    assert fullmatch(
        rf"https://github\.com/ciaren-labs/Ciaren/blob/[a-f0-9]{{40}}/docs/guide/{source}\.md#L\d+",
        answer["citation"]["url"],
    )


async def test_scope_resources_before_provider_call(client, enabled, monkeypatch, db_session):
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
    await failed_run(db_session, flow["id"])
    body["mode"] = "diagnose"
    body["graph"] = {
        "nodes": [{"id": ROW, "type": "pythonTransform", "data": {"label": ROW, "config": {"code": ROW}}}],
        "edges": [],
    }
    saved = await client.put(f"/api/flows/{flow['id']}", json={"graph_json": body["graph"]})
    body["revision"] = saved.json()["updated_at"]
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


@pytest.fixture
async def join_case(client, enabled):
    flow = (await client.post("/api/flows", json={"name": "Two sources"})).json()
    datasets = []
    for name, content in (
        ("left-hidden.csv", "order,private_key\n104,never-share-this-row\n"),
        ("right-hidden.csv", "private_key,status\nnever-share-this-row,active\n"),
    ):
        r = await client.post("/api/datasets/upload", files={"file": (name, content)})
        assert r.status_code == 201
        datasets.append(r.json())
    url = f"/api/assistant/flows/{flow['id']}"
    body = dict(
        mode="build",
        provider="openai",
        question="Keep left rows",
        revision=flow["updated_at"],
        graph={"nodes": [], "edges": [], "engine": "polars"},
        dataset_id=datasets[0]["id"],
        second_dataset_id=datasets[1]["id"],
    )
    return flow, url, body, datasets


def join_answer(provider, instruction, ctx):
    left, right = ctx["inputs"]
    a, b = ctx["shared_keys"][0]
    assert set(ctx) == {"question", "inputs", "shared_keys"}
    for side in (left, right):
        assert all(set(c) == {"type", "index"} for c in side["columns"])
    return {
        "left": {"source": left["source"], "port": left["port"], "column": a},
        "right": {"source": right["source"], "port": right["port"], "column": b},
        "how": "inner",
    }


@pytest.mark.parametrize("side", [0, 1])
async def test_join_latest_conflict_on_either_input(client, join_case, monkeypatch, side):
    flow, url, body, datasets = join_case
    complete = AsyncMock(side_effect=join_answer)
    monkeypatch.setattr(assistant_provider, "complete", complete)
    r = await client.post(url + "/turn", json=body)
    assert r.status_code == 200, r.text
    sent = repr(complete.await_args.args[-1])
    for private in ("left-hidden", "right-hidden", "private_key", "never-share-this-row", *(d["id"] for d in datasets)):
        assert private not in sent
    r2 = await client.post("/api/datasets/upload", files={"file": (datasets[side]["name"], "private_key\nnew\n")})
    assert r2.json()["latest_version"] == 2
    assert (await client.post(url + "/apply", json={"proposal": r.json()["proposal"]})).status_code == 409
    assert not (await client.get("/api/flows/" + flow["id"])).json()["graph_json"]


@pytest.mark.parametrize("fault", ["same", "project", "type", "ports", "column", "swapped", "extra"])
async def test_join_rejects_unavailable_inputs_and_plan(client, join_case, monkeypatch, fault):
    flow, url, body, _ = join_case

    def response(*args):
        answer = join_answer(*args)
        if fault == "ports":
            answer["right"]["port"] = answer["left"]["port"]
        elif fault == "column":
            answer["left"]["column"] = 0
        elif fault == "swapped":
            answer["left"], answer["right"] = answer["right"], answer["left"]
        elif fault == "extra":
            answer["left"]["config"] = {"unapproved": True}
        return answer

    complete = AsyncMock(side_effect=response)
    monkeypatch.setattr(assistant_provider, "complete", complete)
    if fault == "same":
        body["second_dataset_id"] = body["dataset_id"]
    if fault in {"project", "type"}:
        project = (
            (await client.post("/api/projects", json={"name": "Other project"})).json() if fault == "project" else flow
        )
        params = {"project_id": project["id"] if fault == "project" else flow["project_id"]}
        dataset = await client.post(
            "/api/datasets/upload", params=params, files={"file": ("other.csv", "private_key\n123\n")}
        )
        body["second_dataset_id"] = dataset.json()["id"]
    assert (await client.post(url + "/turn", json=body)).status_code == 400
    assert complete.await_count == int(fault not in {"same", "project", "type"})


@pytest.mark.parametrize("outcome", ["valid", "abstain", "wrong_ref", "wrong_mode", "extra_field", "malformed"])
async def test_deepseek_join_repair_contract(client, join_case, enabled, monkeypatch, db_session, outcome):
    from pydantic import SecretStr

    flow, url, body, _ = join_case
    with monkeypatch.context() as setup:
        setup.setattr(assistant_provider, "complete", AsyncMock(side_effect=join_answer))
        created = (await client.post(url + "/turn", json=body)).json()
    assert (await client.post(url + "/apply", json={"proposal": created["proposal"]})).status_code == 200
    path = "/api/flows/" + flow["id"]
    current = (await client.get(path)).json()
    activity = (await client.get(url + "/activity")).json()
    await failed_run(db_session, flow["id"])
    runs = (await client.get("/api/runs")).json()
    body.update(
        mode="diagnose",
        provider="deepseek",
        graph=current["graph_json"],
        revision=current["updated_at"],
        second_dataset_id=None,
    )
    monkeypatch.setattr(enabled, "ASSISTANT_PROVIDER", "deepseek")
    monkeypatch.setattr(enabled, "ASSISTANT_DEEPSEEK_KEY_SOURCE", "env")
    monkeypatch.setattr(enabled, "ASSISTANT_DEEPSEEK_API_KEY", SecretStr(KEY))

    def post(session, destination, **kwargs):
        assert destination == PROFILES["deepseek"].url
        payload = kwargs["json"]
        assert payload["response_format"] == {"type": "json_object"}
        system, user = payload["messages"]
        context = json.loads(user["content"])
        assert set(context) == {"question", "join", "how", "failure"}
        permitted = json.loads(system["content"].splitlines()[-1])
        assert permitted == {"join": context["join"], "how": "left"}
        answer = permitted.copy()
        if outcome == "abstain":
            answer = {}
        elif outcome == "wrong_ref":
            answer["join"] = ("0" if context["join"][0] != "0" else "1") + context["join"][1:]
        elif outcome == "wrong_mode":
            answer["how"] = context["how"]
        elif outcome == "extra_field":
            answer["explanation"] = ROW
        content = ROW if outcome == "malformed" else json.dumps(answer)

        async def chunks(size):
            yield json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": content}}]}).encode()

        result = MagicMock()
        result.__aenter__.return_value.status = 200
        result.__aenter__.return_value.content.iter_chunked = chunks
        return result

    monkeypatch.setattr(assistant_provider.aiohttp.ClientSession, "post", post)
    response = await client.post(url + "/turn", json=body)
    if outcome == "valid":
        assert response.status_code == 200 and response.json()["proposal"]
        original_join = next(n for n in current["graph_json"]["nodes"] if n["type"] == "join")
        (changed,) = response.json()["delta"]["changed"]
        assert changed["id"] == original_join["id"] and changed["data"]["config"]["how"] == "left"
    elif outcome == "abstain":
        assert response.status_code == 200 and "proposal" not in response.json()
    else:
        assert response.status_code == 400
        expected = {
            "wrong_ref": "The repair references an unavailable Join.",
            "malformed": "The provider returned an incomplete structured answer.",
        }.get(outcome, "The provider returned an unsupported Join proposal.")
        assert response.json() == {"detail": expected}
    assert (await client.get(path)).json() == current
    assert (await client.get(url + "/activity")).json() == activity
    assert (await client.get("/api/runs")).json() == runs


@pytest.mark.parametrize("side", [0, 1])
async def test_join_repair_preserves_graph_and_checks_pinned_versions(client, join_case, monkeypatch, db_session, side):
    from copy import deepcopy

    from app.db.models.dataset_version import DatasetVersion

    flow, url, body, datasets = join_case
    complete = AsyncMock(side_effect=join_answer)
    monkeypatch.setattr(assistant_provider, "complete", complete)
    created = (await client.post(url + "/turn", json=body)).json()
    assert (await client.post(url + "/apply", json={"proposal": created["proposal"]})).status_code == 200
    path = "/api/flows/" + flow["id"]
    current = (await client.get(path)).json()
    graph = current["graph_json"]
    join = next(n for n in graph["nodes"] if n["type"] == "join")
    join["data"]["config"]["suffixes"] = ["_a", "_b"]
    join["data"]["label"] = "private label"
    current = (await client.put(path, json={"graph_json": graph})).json()
    await failed_run(db_session, flow["id"])
    body.update(mode="diagnose", graph=graph, revision=current["updated_at"], second_dataset_id=None)

    def repair(provider, instruction, context):
        assert set(context) == {"question", "join", "how", "failure"} and context["how"] == "inner"
        permitted = {"join": context["join"], "how": "left"}
        assert json.loads(instruction.splitlines()[-1]) == permitted
        return permitted

    complete.side_effect = repair
    proposal = (await client.post(url + "/turn", json=body)).json()
    expected = deepcopy(join)
    expected["data"]["config"]["how"] = "left"
    assert proposal["delta"] == {"added": [], "changed": [expected], "connected": [], "disconnected": []}
    assert (await client.get(path)).json()["graph_json"] == graph
    # Appending a version to an explicitly pinned input does not change what was approved.
    newer = await client.post("/api/datasets/upload", files={"file": (datasets[side]["name"], "private_key\nnew\n")})
    assert newer.json()["latest_version"] == 2
    second = (await client.post(url + "/turn", json=body)).json()
    assert second["delta"] == proposal["delta"]
    if side == 0:
        assert (await client.post(url + "/apply", json={"proposal": second["proposal"]})).status_code == 200
        assert (await client.post(url + "/apply", json={"proposal": proposal["proposal"]})).status_code == 409
        saved_left = (await client.get(path)).json()
        complete.side_effect = None
        complete.return_value = {"check": "wiring"}
        body.update(graph=saved_left["graph_json"], revision=saved_left["updated_at"])
        readonly = (await client.post(url + "/turn", json=body)).json()
        assert "manual edit" in readonly["message"] and "proposal" not in readonly
        # Restore the original inner graph to exercise loss of either pinned version independently.
        restored = (await client.put(path, json={"graph_json": graph})).json()
        body.update(graph=graph, revision=restored["updated_at"])
        complete.side_effect = repair
        proposal = (await client.post(url + "/turn", json=body)).json()
    pinned = await db_session.scalar(
        select(DatasetVersion).where(
            DatasetVersion.dataset_id == datasets[side]["id"], DatasetVersion.version_number == 1
        )
    )
    await db_session.delete(pinned)
    await db_session.commit()
    assert (await client.post(url + "/apply", json={"proposal": proposal["proposal"]})).status_code == 409
    assert (await client.get(path)).json()["graph_json"] == graph
