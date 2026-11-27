# SPDX-License-Identifier: AGPL-3.0-only
"""Closed provider/model contracts. Destinations and capabilities are operator-independent."""

from dataclasses import dataclass
from typing import Literal

Provider = Literal["openai", "anthropic", "deepseek", "opencode"]


@dataclass(frozen=True)
class Profile:
    label: str
    url: str
    models: tuple[str, ...]
    efforts: tuple[str, ...]


PROFILES: dict[str, Profile] = {
    "openai": Profile(
        "OpenAI", "https://api.openai.com/v1/responses", ("gpt-5-mini", "gpt-5"), ("low", "medium", "high")
    ),
    "anthropic": Profile(
        "Anthropic", "https://api.anthropic.com/v1/messages", ("claude-sonnet-4-6",), ("low", "medium", "high")
    ),
    "deepseek": Profile(
        "DeepSeek",
        "https://api.deepseek.com/chat/completions",
        ("deepseek-flash", "deepseek-v4-pro"),
        ("low", "high", "max", "none"),
    ),
    "opencode": Profile(
        "OpenCode Console",
        "https://opencode.ai/inference/openai/v1/chat/completions",
        ("minimax-m2.7", "kimi-k2.6"),
        (),
    ),
}
