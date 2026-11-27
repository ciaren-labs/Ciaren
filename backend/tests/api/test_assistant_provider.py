"""Provider tool-calling codecs, the shared transport guards and the call budget.

Envelopes come from tests/api/fixtures/assistant_provider_steps.json; nothing
here reaches the network.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, SecretStr

from app.api.routes import assistant as assistant_route
from app.core.assistant_profiles import PROFILES, supports_tools
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.services import assistant_provider as provider_mod
from app.services.assistant_provider import BudgetExhausted, ProviderNoTools, ToolCall, Usage

KEY = "synthetic-assistant-credential-55120"
FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "assistant_provider_steps.json").read_text("utf-8"))
TOOLS = [
    {
        "name": "get_dataset_schema",
        "description": "Columns of one dataset.",
        "parameters": {
            "type": "object",
            "properties": {"dataset": {"type": "string"}},
            "required": ["dataset"],
        },
    }
]


@pytest.fixture
def settings(client, monkeypatch):
    cfg = get_settings()
    provider_mod._turns.clear()
    provider_mod._tokens.clear()
    monkeypatch.setattr(cfg, "ASSISTANT_TURNS_PER_HOUR", 20)
    return cfg


def _use(cfg, monkeypatch, provider: str, effort: str = "default") -> None:
    monkeypatch.setattr(cfg, "ASSISTANT_PROVIDER", provider)
    monkeypatch.setattr(cfg, f"ASSISTANT_{provider.upper()}_KEY_SOURCE", "env")
    monkeypatch.setattr(cfg, f"ASSISTANT_{provider.upper()}_API_KEY", SecretStr(KEY))
    if effort != "default":
        monkeypatch.setattr(cfg, f"ASSISTANT_{provider.upper()}_EFFORT", effort)


class Wire:
    """aiohttp.ClientSession stand-in that replays envelopes and records bodies."""

    def __init__(self, replies: list[Any], status: int = 200) -> None:
        self.replies = replies
        self.status = status
        self.bodies: list[dict[str, Any]] = []
        wire = self

        class Session:
            def __init__(self, **options):
                assert options["trust_env"] is False and options["timeout"].total == 35
                self.content = self
                self.status = wire.status

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                pass

            def post(self, url, *, json, headers, allow_redirects):
                assert allow_redirects is False
                wire.bodies.append(json)
                return self

            async def iter_chunked(self, size):
                reply = wire.replies.pop(0)
                yield reply if isinstance(reply, bytes) else __import__("json").dumps(reply).encode()

        self.session = Session


def _wire(monkeypatch, *replies: Any, status: int = 200) -> Wire:
    wire = Wire(list(replies), status)
    monkeypatch.setattr(provider_mod.aiohttp, "ClientSession", wire.session)
    return wire


@pytest.mark.parametrize("provider", ["openai", "anthropic", "deepseek"])
async def test_tool_step_round_trip(provider, settings, monkeypatch):
    _use(settings, monkeypatch, provider, PROFILES[provider].efforts[0])
    fixture = FIXTURES[provider]
    wire = _wire(monkeypatch, fixture["tool"], fixture["final"])
    messages: list[dict[str, Any]] = [{"role": "user", "content": "Limit rows"}]

    async with provider_mod.turn_budget() as budget:
        first = await provider_mod.step(provider, "system rules", messages, TOOLS, budget)
        assert first.text is None
        assert first.tool_calls == [
            ToolCall(first.tool_calls[0].id, "get_dataset_schema", {"dataset": "d0"}),
            ToolCall(first.tool_calls[1].id, "validate", None),
        ]
        messages.append({"role": "assistant", "echo": first.echo})
        for call in first.tool_calls:
            messages.append({"role": "tool", "call_id": call.id, "name": call.name, "content": '{"ok":true}'})
        final = await provider_mod.step(provider, "system rules", messages, TOOLS, budget)

    assert final.text == "Added a limit step." and final.tool_calls == []
    assert first.usage == Usage(120, 30) and budget.usage == {"calls": 2, "input_tokens": 320, "output_tokens": 42}
    tool_body, follow_up = wire.bodies
    assert "response_format" not in tool_body and KEY not in json.dumps(wire.bodies)
    ids = [c.id for c in first.tool_calls]
    if provider == "openai":
        assert tool_body["store"] is False and tool_body["include"] == ["reasoning.encrypted_content"]
        assert tool_body["tools"][0]["strict"] is True and tool_body["max_output_tokens"] == 4096
        echoed = [i for i in follow_up["input"] if i.get("type") == "reasoning"]
        assert echoed[0]["encrypted_content"] == "encrypted-reasoning-fixture"
        assert [i["call_id"] for i in follow_up["input"] if i.get("type") == "function_call_output"] == ids
    elif provider == "anthropic":
        assert tool_body["tools"][0]["input_schema"] == TOOLS[0]["parameters"] and tool_body["system"] == "system rules"
        assistant, results = follow_up["messages"][1:]
        assert assistant["content"][0] == {
            "type": "thinking",
            "thinking": "Look up the schema first.",
            "signature": "signature-fixture",
        }
        assert results["role"] == "user" and [b["tool_use_id"] for b in results["content"]] == ids
    else:
        assert tool_body["tools"][0]["function"]["name"] == "get_dataset_schema"
        assistant = follow_up["messages"][2]
        assert assistant["reasoning_content"] == "Look up the schema first."
        assert [m["tool_call_id"] for m in follow_up["messages"][3:]] == ids


async def test_opencode_tools_stay_off_until_verified(settings, monkeypatch):
    _use(settings, monkeypatch, "opencode")
    wire = _wire(monkeypatch)
    assert not supports_tools("opencode", settings.ASSISTANT_OPENCODE_MODEL)
    assert supports_tools("deepseek", settings.ASSISTANT_DEEPSEEK_MODEL)
    async with provider_mod.turn_budget() as budget:
        with pytest.raises(ProviderNoTools) as refused:
            await provider_mod.step("opencode", "system", [{"role": "user", "content": "x"}], TOOLS, budget)
    assert refused.value.reason == "provider_no_tools" and wire.bodies == []


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        (b"x" * (provider_mod.MAX_REPLY_BYTES + 1), "incomplete"),
        ({"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]}, "incomplete"),
        ({"choices": [{"finish_reason": "stop", "message": {"content": KEY}}]}, "incomplete"),
    ],
    ids=["oversized", "truncated", "credential-echo"],
)
async def test_step_keeps_transport_guards(reply, message, settings, monkeypatch):
    _use(settings, monkeypatch, "deepseek")
    _wire(monkeypatch, reply)
    async with provider_mod.turn_budget() as budget:
        with pytest.raises(ValidationError, match=message):
            await provider_mod.step("deepseek", "system", [{"role": "user", "content": "x"}], TOOLS, budget)
        # A credential in the outgoing transcript never leaves the process.
        with pytest.raises(ValidationError, match="credential"):
            await provider_mod.step("deepseek", "system", [{"role": "user", "content": KEY}], TOOLS, budget)


def test_strict_schema_normalisation():
    class Args(BaseModel):
        title: str
        limit: int | None = None
        mode: str = "fast"

    schema = Args.model_json_schema()
    schema["properties"]["title"]["x-ciaren"] = "column"
    strict = provider_mod.strict_schema(schema)

    assert strict is not None and strict["additionalProperties"] is False
    assert strict["required"] == ["title", "limit", "mode"]
    assert strict["properties"]["title"] == {"type": "string"}
    assert {"type": "null"} in strict["properties"]["limit"]["anyOf"]
    assert strict["properties"]["mode"] == {"type": ["string", "null"]}
    # Free-form maps cannot be strict; such tools are sent non-strict instead.
    assert provider_mod.strict_schema({"type": "object", "additionalProperties": {"type": "string"}}) is None


async def test_hourly_budget_reserves_and_refuses(settings, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(provider_mod, "monotonic", lambda: clock[0])
    monkeypatch.setattr(settings, "ASSISTANT_TURNS_PER_HOUR", 11)

    first = provider_mod.reserve()
    second = provider_mod.reserve()
    assert (first.calls, second.calls) == (8, 3)
    with pytest.raises(BudgetExhausted) as exhausted:
        provider_mod.reserve()
    assert exhausted.value.reason == "budget_exhausted"
    second.release()  # finished without using its calls
    assert provider_mod.reserve().calls == 3
    clock[0] += 3601
    assert provider_mod.reserve().calls == 8


async def test_token_budget_refuses_new_turns(settings, monkeypatch):
    _use(settings, monkeypatch, "deepseek")
    _wire(monkeypatch, FIXTURES["deepseek"]["final"])
    async with provider_mod.turn_budget(tokens_per_hour=200) as budget:
        await provider_mod.step("deepseek", "system", [{"role": "user", "content": "x"}], TOOLS, budget)
        with pytest.raises(BudgetExhausted):
            await provider_mod.step("deepseek", "system", [{"role": "user", "content": "x"}], TOOLS, budget)
    with pytest.raises(BudgetExhausted):
        provider_mod.reserve(tokens_per_hour=200)
    assert provider_mod.reserve(tokens_per_hour=500).calls == 8


async def test_cancelled_turn_keeps_its_reservation(settings, monkeypatch):
    monkeypatch.setattr(settings, "ASSISTANT_TURNS_PER_HOUR", 10)
    entered = asyncio.Event()

    async def turn() -> None:
        async with provider_mod.turn_budget():
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(turn())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(provider_mod._turns) == 8
    async with provider_mod.turn_budget() as budget:
        assert budget.calls == 2
    # A turn that ends normally returns the calls it did not use.
    assert len(provider_mod._turns) == 8


async def test_concurrent_turn_cap(client, settings, monkeypatch):
    release = asyncio.Event()
    started = 0

    async def blocked(self, flow_id, body):
        nonlocal started
        started += 1
        await release.wait()
        return {"message": "ok"}

    monkeypatch.setattr("app.services.assistant_service.AssistantService.turn", blocked)
    flow = (await client.post("/api/flows", json={"name": "Cap"})).json()
    url = f"/api/assistant/flows/{flow['id']}/turn"

    def body(i: int) -> dict[str, Any]:
        return {
            "mode": "docs",
            "provider": "openai",
            "question": "q",
            "revision": flow["updated_at"],
            "request_id": f"00000000-0000-4000-8000-{i:012d}",
        }

    running = [asyncio.create_task(client.post(url, json=body(i))) for i in range(8)]
    try:
        while started < 8:
            await asyncio.sleep(0)
        # A ninth turn must be refused at once, not queued behind the blocked ones.
        refused = await asyncio.wait_for(client.post(url, json=body(99)), 5)
    finally:
        release.set()
    assert refused.status_code == 400 and "Another assistant turn" in refused.json()["detail"]
    assert [r.status_code for r in await asyncio.gather(*running)] == [200] * 8
    assert not assistant_route._active
