# SPDX-License-Identifier: AGPL-3.0-only
from typing import Literal

from pydantic import BaseModel, StrictInt, StrictStr

# Strict so JSON booleans/floats don't silently coerce (True -> 1) before the
# registry-level validation even sees them.
SettingValue = StrictInt | StrictStr
SettingSource = Literal["default", "env", "override"]


class AppSettingRead(BaseModel):
    """One editable setting: metadata, constraints, and its effective value."""

    key: str
    label: str
    description: str
    # The CIAREN_* environment variable this setting maps to. While an
    # override exists, that variable is ignored (until the override is reset).
    env_var: str
    category: str
    value_type: Literal["integer", "select", "url"]
    choices: list[str] | None = None
    min_value: int | None = None
    max_value: int | None = None
    # The value is consumed at startup/pool creation; a change needs a restart.
    restart_required: bool = False
    # Effective value and where it comes from.
    value: SettingValue
    source: SettingSource
    # Built-in default, and the environment/default value an override would
    # fall back to when reset (so the UI can say what "Reset" restores).
    default_value: SettingValue
    env_value: SettingValue


class AppSettingUpdate(BaseModel):
    value: SettingValue
