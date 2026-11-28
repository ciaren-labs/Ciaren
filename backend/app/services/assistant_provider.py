# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded provider calls. No redirects, ambient proxies or automatic retry.

``complete()`` is the one-shot structured completion the planners use. ``step()``
is one tool-calling round of an agent turn; a turn first takes a call reservation
from ``turn_budget()``. Transcripts are provider-neutral messages:

- ``{"role": "user", "content": str}``
- ``{"role": "assistant", "echo": Step.echo}``: the provider's own reply items,
  sent back verbatim so reasoning and thinking state survive stateless calls
- ``{"role": "tool", "call_id": str, "name": str, "content": str}``

Tools are ``{"name", "description", "parameters": <JSON schema>}``.
"""

import asyncio
import json
from collections import deque
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Protocol, TypeVar

import aiohttp
from opentelemetry import context as otel_context

from app.core.assistant_keys import read_key
from app.core.assistant_profiles import PROFILES, Provider, supports_tools
from app.core.config import get_settings
from app.core.exceptions import ValidationError

MAX_OUTPUT = 2048
MAX_STEP_OUTPUT = 4096
MAX_REPLY_BYTES = 128 * 1024
MAX_CALL_BYTES = 48 * 1024
MAX_CALLS = 14
# One timestamp per reserved provider call, shared by every turn in the process.
_turns: deque[float] = deque()
# (timestamp, input + output tokens) per completed call, for the optional token budget.
_tokens: deque[tuple[float, int]] = deque()

T = TypeVar("T")
Message = dict[str, Any]
Tool = dict[str, Any]


class BudgetExhausted(ValidationError):
    reason = "budget_exhausted"

    def __init__(self) -> None:
        super().__init__("Assistant hourly budget reached. Try again later.")


class ProviderNoTools(ValidationError):
    reason = "provider_no_tools"

    def __init__(self) -> None:
        super().__init__("The selected assistant model does not support tool calling.")


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    # None when the provider sent arguments that are not a JSON object.
    arguments: dict[str, Any] | None


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class Step:
    text: str | None
    tool_calls: list[ToolCall]
    usage: Usage
    echo: Any


def profile(provider: Provider) -> tuple[str, str]:
    cfg = get_settings()
    if not cfg.ASSISTANT_ENABLED or cfg.ASSISTANT_PROVIDER != provider:
        raise ValidationError("The assistant is disabled or the provider has changed. Check Settings.")
    spec = PROFILES[provider]
    model = getattr(cfg, f"ASSISTANT_{provider.upper()}_MODEL")
    effort = getattr(cfg, f"ASSISTANT_{provider.upper()}_EFFORT", "default")
    if model not in spec.models or effort not in ("default", *spec.efforts):
        raise ValidationError("Unsupported assistant model or effort. Check Settings.")
    return model, effort


# -- Budget ---------------------------------------------------------------


def _prune(now: float) -> None:
    while _turns and _turns[0] <= now - 3600:
        _turns.popleft()
    while _tokens and _tokens[0][0] <= now - 3600:
        _tokens.popleft()


def _tokens_spent() -> int:
    return sum(n for _, n in _tokens)


@dataclass
class Reservation:
    """Provider calls held for one turn. Calls are never refunded once used."""

    calls: int
    stamp: float
    used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    released: bool = field(default=False, repr=False)

    @property
    def usage(self) -> dict[str, int]:
        return {"calls": self.used, "input_tokens": self.input_tokens, "output_tokens": self.output_tokens}

    def take(self) -> None:
        _prune(monotonic())
        if self.released or self.used >= self.calls:
            raise BudgetExhausted()
        if _tokens_exhausted():
            raise BudgetExhausted()
        self.used += 1

    def record(self, usage: Usage) -> None:
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        _tokens.append((monotonic(), usage.input_tokens + usage.output_tokens))

    def release(self) -> None:
        """Return the calls this turn did not use."""
        if self.released:
            return
        self.released = True
        for _ in range(self.calls - self.used):
            try:
                _turns.remove(self.stamp)
            except ValueError:
                # The reservation already aged out of the hourly window.
                break


def _tokens_exhausted() -> bool:
    limit = get_settings().ASSISTANT_TOKENS_PER_HOUR
    return limit is not None and _tokens_spent() >= limit


def _reserve(wanted: int, minimum: int) -> Reservation:
    now = monotonic()
    _prune(now)
    remaining = get_settings().ASSISTANT_TURNS_PER_HOUR - len(_turns)
    if remaining < minimum or _tokens_exhausted():
        raise BudgetExhausted()
    calls = min(wanted, remaining)
    _turns.extend([now] * calls)
    return Reservation(calls, now)


def reserve(max_calls: int = MAX_CALLS) -> Reservation:
    """Hold ``min(max_calls, remaining)`` calls; refuse when fewer than two remain
    or when ``ASSISTANT_TOKENS_PER_HOUR`` is set and spent."""
    return _reserve(max_calls, 2)


@asynccontextmanager
async def turn_budget(max_calls: int = MAX_CALLS) -> AsyncIterator[Reservation]:
    """Reserve calls for one turn. Unused calls return when the turn ends, except
    on cancellation: a cancelled turn keeps its whole reservation, so cancelling
    and retrying cannot exceed the hourly budget."""
    reservation = reserve(max_calls)
    try:
        yield reservation
    except asyncio.CancelledError:
        raise
    except BaseException:
        reservation.release()
        raise
    reservation.release()


# -- Codecs ---------------------------------------------------------------


class Codec(Protocol):
    def build(
        self, model: str, effort: str, system: str, messages: list[Message], tools: list[Tool] | None, max_output: int
    ) -> dict[str, Any]: ...

    def parse(self, envelope: dict[str, Any]) -> Step: ...


def _arguments(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    return raw if isinstance(raw, dict) else None


def _tokens_of(usage: Any, inputs: tuple[str, ...], output: str) -> Usage:
    usage = usage if isinstance(usage, dict) else {}
    return Usage(sum(int(usage.get(k) or 0) for k in inputs), int(usage.get(output) or 0))


_DROPPED_KEYWORDS = {"default", "title"}
_SCHEMA_MAPS = {"properties", "$defs", "definitions"}


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    kind = schema.get("type")
    if kind == "null" or (isinstance(kind, list) and "null" in kind):
        return schema
    if any(s == {"type": "null"} for s in schema.get("anyOf", [])):
        return schema
    if isinstance(kind, str) and "enum" not in schema and "const" not in schema:
        return {**schema, "type": [kind, "null"]}
    return {"anyOf": [schema, {"type": "null"}]}


def _strict(node: Any) -> Any:
    if isinstance(node, list):
        return [_strict(n) for n in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _DROPPED_KEYWORDS or key.startswith("x-"):
            continue
        if key in _SCHEMA_MAPS and isinstance(value, dict):
            out[key] = {name: _strict(sub) for name, sub in value.items()}
        else:
            out[key] = _strict(value)
    if out.get("type") == "object" or "properties" in out:
        if isinstance(out.get("additionalProperties"), dict) or "patternProperties" in out:
            raise ValueError("free-form object")
        props = out.setdefault("properties", {})
        required = set(node.get("required", []))
        for name in props:
            if name not in required:
                props[name] = _nullable(props[name])
        out["required"] = list(props)
        out["additionalProperties"] = False
    return out


def strict_schema(schema: dict[str, Any]) -> dict[str, Any] | None:
    """OpenAI strict form of a tool schema: every property required, optional ones
    nullable, no extra properties, no ``default``/``title``/``x-*`` keywords.

    Returns None when the schema has a free-form map, which strict mode cannot express.
    """
    try:
        result = _strict(schema)
    except ValueError:
        return None
    return result if isinstance(result, dict) else None


class OpenAIResponses:
    def build(
        self, model: str, effort: str, system: str, messages: list[Message], tools: list[Tool] | None, max_output: int
    ) -> dict[str, Any]:
        items: list[Any] = []
        for m in messages:
            if m["role"] == "assistant":
                items.extend(m["echo"])
            elif m["role"] == "tool":
                items.append({"type": "function_call_output", "call_id": m["call_id"], "output": m["content"]})
            else:
                items.append({"role": "user", "content": m["content"]})
        body: dict[str, Any] = dict(
            model=model, instructions=system, input=items, max_output_tokens=max_output, store=False
        )
        if effort != "default":
            body["reasoning"] = {"effort": effort}
        if tools is not None:
            # Without server-side storage, reasoning survives only as echoed encrypted items.
            body["include"] = ["reasoning.encrypted_content"]
            if tools:
                body["tools"] = [self._tool(t) for t in tools]
        return body

    @staticmethod
    def _tool(tool: Tool) -> dict[str, Any]:
        strict = strict_schema(tool["parameters"])
        return {
            "type": "function",
            "name": tool["name"],
            "description": tool["description"],
            "parameters": strict if strict is not None else tool["parameters"],
            "strict": strict is not None,
        }

    def parse(self, envelope: dict[str, Any]) -> Step:
        if envelope.get("status") != "completed":
            raise ValueError("Incomplete completion")
        output = envelope["output"]
        text: list[str] = []
        calls: list[ToolCall] = []
        for item in output:
            if item["type"] == "message":
                text.extend(p["text"] for p in item["content"] if p["type"] == "output_text")
            elif item["type"] == "function_call":
                calls.append(ToolCall(item["call_id"], item["name"], _arguments(item["arguments"])))
        usage = _tokens_of(envelope.get("usage"), ("input_tokens",), "output_tokens")
        return Step("".join(text) if text and not calls else None, calls, usage, output)


class AnthropicMessages:
    def build(
        self, model: str, effort: str, system: str, messages: list[Message], tools: list[Tool] | None, max_output: int
    ) -> dict[str, Any]:
        wire: list[dict[str, Any]] = []
        for m in messages:
            if m["role"] == "assistant":
                wire.append({"role": "assistant", "content": m["echo"]})
            elif m["role"] == "tool":
                result = {"type": "tool_result", "tool_use_id": m["call_id"], "content": m["content"]}
                # All results for one assistant reply travel in a single user message.
                if wire and wire[-1]["role"] == "user" and isinstance(wire[-1]["content"], list):
                    wire[-1]["content"].append(result)
                else:
                    wire.append({"role": "user", "content": [result]})
            else:
                wire.append({"role": "user", "content": m["content"]})
        body: dict[str, Any] = {"model": model, "messages": wire, "max_tokens": max_output, "system": system}
        if effort != "default":
            body.update(thinking={"type": "adaptive"}, output_config={"effort": effort})
        if tools:
            body["tools"] = [
                {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools
            ]
        return body

    def parse(self, envelope: dict[str, Any]) -> Step:
        stop = envelope.get("stop_reason")
        if stop not in ("end_turn", "tool_use"):
            raise ValueError("Incomplete completion")
        content = envelope["content"]
        calls = [ToolCall(p["id"], p["name"], _arguments(p["input"])) for p in content if p["type"] == "tool_use"]
        if stop == "tool_use" and not calls:
            raise ValueError("Incomplete completion")
        text = "".join(p["text"] for p in content if p["type"] == "text")
        usage = _tokens_of(
            envelope.get("usage"),
            ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"),
            "output_tokens",
        )
        return Step(None if calls else text, calls, usage, content)


class ChatCompletions:
    """OpenAI-compatible chat completions (DeepSeek, OpenCode)."""

    def __init__(self, provider: Provider) -> None:
        self.provider = provider

    def build(
        self, model: str, effort: str, system: str, messages: list[Message], tools: list[Tool] | None, max_output: int
    ) -> dict[str, Any]:
        wire: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for m in messages:
            if m["role"] == "assistant":
                wire.append(m["echo"])
            elif m["role"] == "tool":
                wire.append({"role": "tool", "tool_call_id": m["call_id"], "content": m["content"]})
            else:
                wire.append({"role": "user", "content": m["content"]})
        body: dict[str, Any] = {"model": model, "messages": wire, "max_tokens": max_output}
        if self.provider == "deepseek":
            # JSON mode and tool calls are mutually exclusive; JSON mode serves complete().
            if tools is None:
                body["response_format"] = {"type": "json_object"}
            if effort == "none":
                body["thinking"] = {"type": "disabled"}
            elif effort != "default":
                body["reasoning_effort"] = effort
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]},
                }
                for t in tools
            ]
        return body

    def parse(self, envelope: dict[str, Any]) -> Step:
        choice = envelope["choices"][0]
        message = choice["message"]
        if not isinstance(message, dict):
            raise ValueError("Incomplete completion")
        usage = _tokens_of(envelope.get("usage"), ("prompt_tokens",), "completion_tokens")
        if choice["finish_reason"] == "tool_calls":
            raw_calls = message.get("tool_calls")
            if not isinstance(raw_calls, list) or not raw_calls:
                raise ValueError("Incomplete completion")
            calls = [
                ToolCall(c["id"], c["function"]["name"], _arguments(c["function"]["arguments"])) for c in raw_calls
            ]
            # DeepSeek thinking mode needs reasoning_content echoed within the turn.
            echo = {
                "role": "assistant",
                "content": message.get("content") or "",
                "tool_calls": raw_calls,
                **({"reasoning_content": message["reasoning_content"]} if "reasoning_content" in message else {}),
            }
            return Step(None, calls, usage, echo)
        value = message.get("content")
        if choice["finish_reason"] != "stop" or not isinstance(value, str):
            raise ValueError("Incomplete completion")
        return Step(value, [], usage, {"role": "assistant", "content": value})


CODECS: dict[str, Codec] = {
    "openai": OpenAIResponses(),
    "anthropic": AnthropicMessages(),
    "deepseek": ChatCompletions("deepseek"),
    "opencode": ChatCompletions("opencode"),
}


# -- Transport -------------------------------------------------------------


async def _credential(provider: Provider) -> str:
    secret = await asyncio.to_thread(read_key, provider)
    if not secret:
        raise ValidationError("Configure an API key for this provider in Settings.")
    return secret.get_secret_value()


async def _transport(provider: Provider, body: dict[str, Any], key: str) -> dict[str, Any]:
    """POST one request body and return the decoded envelope.

    Raises ValidationError for HTTP failures; ``ValueError``-family errors for an
    oversized, malformed or credential-bearing reply; aiohttp/timeout errors as is.
    """
    headers = (
        {"x-api-key": key, "anthropic-version": "2023-06-01"}
        if provider == "anthropic"
        else {"Authorization": f"Bearer {key}"}
    )
    # Outbound assistant traffic must not inherit trace propagation or capture headers.
    ctx = otel_context.set_value(otel_context._SUPPRESS_INSTRUMENTATION_KEY, True)
    token = otel_context.attach(otel_context.set_value(otel_context._SUPPRESS_HTTP_INSTRUMENTATION_KEY, True, ctx))
    try:
        async with aiohttp.ClientSession(
            trust_env=False, timeout=aiohttp.ClientTimeout(total=35), cookie_jar=aiohttp.DummyCookieJar()
        ) as client:
            async with client.post(
                PROFILES[provider].url, json=body, headers=headers, allow_redirects=False
            ) as response:
                if response.status != 200:
                    raise ValidationError(
                        f"Provider returned HTTP {response.status}. Check credentials, model and quota."
                    )
                raw = bytearray()
                async for chunk in response.content.iter_chunked(8192):
                    raw.extend(chunk)
                    if len(raw) > MAX_REPLY_BYTES:
                        raise ValueError("Oversized response")
    finally:
        otel_context.detach(token)
    envelope = json.loads(raw)
    if not isinstance(envelope, dict):
        raise ValueError("Invalid envelope")
    # Compare decoded text so JSON escapes cannot smuggle the credential back.
    if key in json.dumps(envelope, ensure_ascii=False):
        raise ValueError("Invalid content")
    return envelope


def _refuse_echo(key: str, decoded: object) -> None:
    """Nested JSON (an answer, tool arguments) can spell the key with escapes
    that the envelope check cannot see, so check it again once decoded."""
    if key in json.dumps(decoded, ensure_ascii=False):
        raise ValueError("Invalid content")


async def _guarded(call: Awaitable[T], incomplete: str) -> T:
    try:
        return await call
    except ValidationError:
        raise
    except TimeoutError:
        raise ValidationError("The provider request timed out.") from None
    except aiohttp.ClientError:
        raise ValidationError("The provider request or response transfer failed.") from None
    except (ValueError, TypeError, KeyError, IndexError, RecursionError):
        raise ValidationError(incomplete) from None


async def complete(provider: Provider, instruction: str, data: dict[str, Any]) -> dict[str, Any]:
    model, effort = profile(provider)
    context = json.dumps(data, ensure_ascii=False, allow_nan=False)
    if len(context.encode()) > 16000:
        raise ValidationError("Assistant context exceeds the 16 KB limit.")
    key = await _credential(provider)
    if key in context:
        raise ValidationError("Remove the configured credential from the request.")
    try:
        _reserve(1, 1)
    except BudgetExhausted:
        raise ValidationError("Assistant hourly turn budget reached.") from None
    codec = CODECS[provider]
    body = codec.build(model, effort, instruction, [{"role": "user", "content": context}], None, MAX_OUTPUT)

    async def call() -> dict[str, Any]:
        result = codec.parse(await _transport(provider, body, key))
        if result.text is None or result.tool_calls:
            raise ValueError("Incomplete completion")
        decoded = json.loads(result.text)
        if not isinstance(decoded, dict):
            raise ValueError("Invalid completion")
        _refuse_echo(key, decoded)
        return decoded

    return await _guarded(call(), "The provider returned an incomplete structured answer.")


async def step(
    provider: Provider, system: str, messages: list[Message], tools: list[Tool], reservation: Reservation
) -> Step:
    """Run one provider call of an agent turn, charged to ``reservation``."""
    model, effort = profile(provider)
    if tools and not supports_tools(provider, model):
        raise ProviderNoTools()
    codec = CODECS[provider]
    body = codec.build(model, effort, system, messages, tools, MAX_STEP_OUTPUT)
    encoded = json.dumps(body, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > MAX_CALL_BYTES:
        raise ValidationError("Assistant context exceeds the 48 KB call limit.")
    key = await _credential(provider)
    if key in encoded:
        raise ValidationError("Remove the configured credential from the request.")
    reservation.take()

    async def call() -> Step:
        parsed = codec.parse(await _transport(provider, body, key))
        for tool_call in parsed.tool_calls:
            _refuse_echo(key, tool_call.arguments)
        return parsed

    result = await _guarded(call(), "The provider returned an incomplete answer.")
    reservation.record(result.usage)
    return result
