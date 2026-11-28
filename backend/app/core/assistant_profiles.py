# SPDX-License-Identifier: AGPL-3.0-only
"""Closed provider/model contracts. Destinations and capabilities are operator-independent."""

import re
from dataclasses import dataclass
from typing import Literal

Provider = Literal["openai", "anthropic", "deepseek", "opencode"]


@dataclass(frozen=True)
class Profile:
    label: str
    url: str
    models: tuple[str, ...]
    efforts: tuple[str, ...]
    # Models whose tool calling is covered by a recorded-envelope codec test.
    tools: tuple[str, ...] = ()


PROFILES: dict[str, Profile] = {
    "openai": Profile(
        "OpenAI",
        "https://api.openai.com/v1/responses",
        ("gpt-5-mini", "gpt-5"),
        ("low", "medium", "high"),
        ("gpt-5-mini", "gpt-5"),
    ),
    "anthropic": Profile(
        "Anthropic",
        "https://api.anthropic.com/v1/messages",
        ("claude-sonnet-4-6",),
        ("low", "medium", "high"),
        ("claude-sonnet-4-6",),
    ),
    "deepseek": Profile(
        "DeepSeek",
        "https://api.deepseek.com/chat/completions",
        ("deepseek-flash", "deepseek-v4-pro"),
        ("low", "high", "max", "none"),
        ("deepseek-flash", "deepseek-v4-pro"),
    ),
    "opencode": Profile(
        "OpenCode Console",
        "https://opencode.ai/inference/openai/v1/chat/completions",
        ("minimax-m2.7", "kimi-k2.6"),
        (),
    ),
}


# A model name typed by the user: it only selects a model at the provider's fixed URL.
CUSTOM_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}")


def valid_model(provider: str, model: str) -> bool:
    return model in PROFILES[provider].models or CUSTOM_MODEL.fullmatch(model) is not None


def supports_tools(provider: str, model: str) -> bool:
    """Known models use tool calling only when a codec test covers it; a model
    the user typed is newer than this list, so tool calling is attempted."""
    spec = PROFILES[provider]
    return model in spec.tools or model not in spec.models
