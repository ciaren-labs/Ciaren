# SPDX-License-Identifier: AGPL-3.0-only
"""One bounded, stateless completion. No redirects, ambient proxies, tools or automatic retry."""

import asyncio
import json
from collections import deque
from time import monotonic
from typing import Any

import aiohttp
from opentelemetry import context as otel_context

from app.core.assistant_keys import read_key
from app.core.assistant_profiles import PROFILES, Provider
from app.core.config import get_settings
from app.core.exceptions import ValidationError

MAX_OUTPUT = 2048
MAX_REPLY_BYTES = 128 * 1024
_turns: deque[float] = deque()


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


def payload(provider: Provider, model: str, effort: str, instruction: str, context: str) -> dict[str, Any]:
    message = {"role": "user", "content": context}
    if provider == "openai":
        body: dict[str, Any] = dict(
            model=model, instructions=instruction, input=[message], max_output_tokens=MAX_OUTPUT, store=False
        )
        if effort != "default":
            body["reasoning"] = {"effort": effort}
        return body
    body = {"model": model, "messages": [message], "max_tokens": MAX_OUTPUT}
    if provider == "anthropic":
        body["system"] = instruction
        if effort != "default":
            body.update(thinking={"type": "adaptive"}, output_config={"effort": effort})
    else:
        body["messages"].insert(0, {"role": "system", "content": instruction})
        if provider == "deepseek" and effort != "default":
            if effort == "none":
                body["thinking"] = {"type": "disabled"}
            else:
                body["reasoning_effort"] = effort
    return body


def extract(provider: Provider, reply: dict[str, Any]) -> str:
    if provider == "openai" and reply.get("status") == "completed":
        return "".join(
            p["text"]
            for item in reply["output"]
            if item["type"] == "message"
            for p in item["content"]
            if p["type"] == "output_text"
        )
    if provider == "anthropic" and reply.get("stop_reason") == "end_turn":
        return "".join(p["text"] for p in reply["content"] if p["type"] == "text")
    if provider in {"deepseek", "opencode"}:
        choice = reply["choices"][0]
        message = choice["message"]
        value = message.get("content") if isinstance(message, dict) else None
        if choice["finish_reason"] == "stop" and isinstance(value, str):
            return value
    raise ValueError("Incomplete completion")


async def complete(provider: Provider, instruction: str, data: dict[str, Any]) -> dict[str, Any]:
    model, effort = profile(provider)
    context = json.dumps(data, ensure_ascii=False, allow_nan=False)
    if len(context.encode()) > 16000:
        raise ValidationError("Assistant context exceeds the 16 KB limit.")
    secret = await asyncio.to_thread(read_key, provider)
    if not secret:
        raise ValidationError("Configure an API key for this provider in Settings.")
    key = secret.get_secret_value()
    if key in context:
        raise ValidationError("Remove the configured credential from the request.")
    now = monotonic()
    while _turns and _turns[0] <= now - 3600:
        _turns.popleft()
    if len(_turns) >= get_settings().ASSISTANT_TURNS_PER_HOUR:
        raise ValidationError("Assistant hourly turn budget reached.")
    _turns.append(now)
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
                PROFILES[provider].url,
                json=payload(provider, model, effort, instruction, context),
                headers=headers,
                allow_redirects=False,
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
        envelope = json.loads(raw)
        if not isinstance(envelope, dict):
            raise ValueError("Invalid envelope")
        answer = extract(provider, envelope)
        if not isinstance(answer, str) or key in answer:
            raise ValueError("Invalid content")
        decoded = json.loads(answer)
        if not isinstance(decoded, dict) or key in json.dumps(decoded, ensure_ascii=False):
            raise ValueError("Invalid completion")
        return decoded
    except ValidationError:
        raise
    except (aiohttp.ClientError, TimeoutError, ValueError, TypeError, KeyError, IndexError, RecursionError):
        raise ValidationError("Provider request failed or returned an incomplete structured answer.") from None
    finally:
        otel_context.detach(token)
