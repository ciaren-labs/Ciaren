# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime-editable application settings.

A small, explicitly allowlisted subset of :class:`~app.core.config.Settings`
fields can be edited at runtime (the Settings page / ``/api/settings``) and is
persisted in the ``app_settings`` table. Precedence, highest first:

1. Database override — set from the UI/API, survives restarts.
2. Environment variable / ``.env`` file (``CIAREN_<KEY>``).
3. Built-in default.

Overrides are applied by assigning onto the ``get_settings()`` singleton, so
every existing consumer picks them up with no call-site changes. The active
override map is stored on that same instance, which ties its lifetime to the
settings cache: tests that call ``get_settings.cache_clear()`` automatically
start from a clean slate, and "reset" restores whatever the environment says
*now*, not a stale snapshot.

Everything NOT in :data:`REGISTRY` stays environment-only, deliberately:

- **Bootstrap values** read before or while the app comes up: ``DATABASE_URL``,
  ``DATA_DIR``, ``LOG_FORMAT``, ``FRONTEND_DIST``, ``ENVIRONMENT``, ``DEBUG``,
  ``SEED_*``, and the ``SCHEDULER_ENABLED`` / ``ML_ENABLED`` switches that gate
  what is wired up during startup.
- **Secrets**: ``API_TOKEN``, ``WEBHOOK_SECRET``, ``NOTIFY_WEBHOOK_SECRET``.
  Never stored in the database, never echoed by the API.
- **Outbound targets paired with an env-only secret**: ``NOTIFY_WEBHOOK_URL``.
  ``notifications.py`` sends ``NOTIFY_WEBHOOK_SECRET`` to whatever URL is
  configured and deliberately skips the SSRF guard *because* the URL comes from
  the environment; a UI-editable URL would let any UI user redirect the
  operator's secret to a host they control (and the URL itself — a Slack/
  Discord webhook — is often a capability-bearing secret the API must not echo).
- **Security guards**: ``CORS_ORIGINS``, ``TRUSTED_HOSTS``,
  ``SECRET_ENV_ALLOWLIST``, ``SECRET_FILE_DIRS``, ``STORAGE_ALLOWED_ROOTS``,
  ``CONNECTOR_BLOCK_PRIVATE_HOSTS``, ``PYTHON_TRANSFORM_STRICT``,
  ``REQUIRE_TRUSTED_PLUGINS``, ``PLUGIN_PERMISSION_ENFORCEMENT``,
  ``MARKETPLACE_INDEX``, ``MARKETPLACE_LICENSE_ISSUER_KEYS``, and the ML
  paths/URIs (``ML_ARTIFACT_DIR``, ``MLFLOW_*``). The settings API is reachable
  by exactly the audience those guards constrain (the UI is unauthenticated in
  the local-first posture), so making them editable would let that audience
  weaken its own guardrails. Changing them requires access to the server's
  process environment.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlsplit

from app.core.config import Settings, get_settings
from app.core.enums import Engine, ExecutionMode

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("app.core.runtime_settings")

# Attribute on the Settings instance holding {key: normalized value} for the
# overrides currently applied. Set via object.__setattr__ (pydantic refuses
# assignment of non-field names); dies with the instance on cache_clear().
_OVERRIDES_ATTR = "_runtime_overrides"

ValueType = Literal["integer", "select", "url"]


@dataclass(frozen=True)
class SettingSpec:
    """One editable setting: its UI metadata and validation rules."""

    key: str
    label: str
    description: str
    category: str
    value_type: ValueType
    choices: tuple[str, ...] | None = None
    min_value: int | None = None
    max_value: int | None = None
    # True when the value is consumed once at startup (or at pool creation), so
    # an override only fully takes effect after a server restart.
    restart_required: bool = False

    def coerce(self, value: Any) -> Any:
        """Validate and normalize a caller-supplied value, or raise ValueError."""
        if self.value_type == "integer":
            # bool is a subclass of int — reject it explicitly.
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{self.key} must be an integer.")
            if self.min_value is not None and value < self.min_value:
                raise ValueError(f"{self.key} must be at least {self.min_value}.")
            if self.max_value is not None and value > self.max_value:
                raise ValueError(f"{self.key} must be at most {self.max_value}.")
            return value
        if self.value_type == "select":
            if not isinstance(value, str) or (self.choices and value not in self.choices):
                allowed = ", ".join(self.choices or ())
                raise ValueError(f"{self.key} must be one of: {allowed}.")
            return value
        # "url": empty string disables; otherwise require a well-formed
        # http(s) URL so a stored value can never smuggle another scheme.
        if not isinstance(value, str):
            raise ValueError(f"{self.key} must be a string.")
        value = value.strip()
        if value == "":
            return value
        if len(value) > 2000:
            raise ValueError(f"{self.key} is too long (max 2000 characters).")
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError(f"{self.key} must be an http:// or https:// URL (or empty to disable).")
        return value


_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        key="DEFAULT_ENGINE",
        label="Default engine",
        description="Dataframe engine used for runs that don't request one explicitly.",
        category="Execution",
        value_type="select",
        choices=(str(Engine.PANDAS), str(Engine.POLARS)),
    ),
    SettingSpec(
        key="EXECUTION_MODE",
        label="Execution mode",
        description=(
            "How flow compute is offloaded. 'thread' (recommended) is simplest and "
            "fully featured — precise run cancel, plugin node hooks; a single polars "
            "run is already multi-core. 'process' adds crash isolation and multi-core "
            "across concurrent runs for shared servers running scheduled jobs, at the "
            "cost of coarser cancel and a slower first run. Applies from the next run."
        ),
        category="Execution",
        value_type="select",
        choices=(str(ExecutionMode.THREAD), str(ExecutionMode.PROCESS)),
    ),
    SettingSpec(
        key="RUN_TIMEOUT_SECONDS",
        label="Run timeout (seconds)",
        description="Abandon a run after this many seconds. 0 means no limit.",
        category="Execution",
        value_type="integer",
        min_value=0,
        max_value=604_800,
    ),
    SettingSpec(
        key="MAX_UPLOAD_SIZE_MB",
        label="Max upload size (MB)",
        description="Largest dataset file the upload endpoint accepts.",
        category="Datasets",
        value_type="integer",
        min_value=1,
        max_value=10_240,
    ),
    SettingSpec(
        key="DATASET_RETENTION_DAYS",
        label="Deleted dataset retention (days)",
        description=(
            "Days a soft-deleted dataset's files are kept (and restorable) before "
            "'purge-expired' removes them. 0 purges immediately."
        ),
        category="Datasets",
        value_type="integer",
        min_value=0,
        max_value=3_650,
    ),
    SettingSpec(
        key="SCHEDULER_POLL_INTERVAL_SECONDS",
        label="Scheduler poll interval (seconds)",
        description="How often the scheduler checks for due runs. Lower is more responsive but wakes more often.",
        category="Scheduler",
        value_type="integer",
        min_value=1,
        max_value=3_600,
    ),
    SettingSpec(
        key="SCHEDULER_MAX_CONCURRENT_RUNS",
        label="Max concurrent scheduled runs",
        description="Cap on simultaneous scheduled runs (also sizes the process pool in process mode).",
        category="Scheduler",
        value_type="integer",
        min_value=1,
        max_value=64,
        restart_required=True,
    ),
    SettingSpec(
        key="SCHEDULER_MAX_CONSECUTIVE_FAILURES",
        label="Auto-disable after failures",
        description="Consecutive failed runs before a schedule is disabled automatically. 0 never disables.",
        category="Scheduler",
        value_type="integer",
        min_value=0,
        max_value=1_000,
    ),
    SettingSpec(
        key="ML_MAX_MODEL_SIZE_MB",
        label="Max model size (MB)",
        description="Largest model artifact ML nodes will save or load.",
        category="Machine learning",
        value_type="integer",
        min_value=1,
        max_value=100_000,
    ),
    SettingSpec(
        key="ML_MAX_TRAINING_ROWS",
        label="Max training rows",
        description="Largest row count a single training job accepts.",
        category="Machine learning",
        value_type="integer",
        min_value=1,
        max_value=1_000_000_000,
    ),
    SettingSpec(
        key="ML_MAX_FEATURE_COLUMNS",
        label="Max feature columns",
        description="Largest feature-column count a single training job accepts.",
        category="Machine learning",
        value_type="integer",
        min_value=1,
        max_value=100_000,
    ),
)

REGISTRY: dict[str, SettingSpec] = {spec.key: spec for spec in _SPECS}


def get_active_overrides() -> dict[str, Any]:
    """The overrides currently applied to the settings singleton (a copy)."""
    return dict(getattr(get_settings(), _OVERRIDES_ATTR, {}))


def _baseline() -> Settings:
    """A fresh Settings built from environment/defaults only — what every
    registry key falls back to when its override is cleared.

    If the environment has become invalid *since startup* (e.g. someone edited
    ``.env`` to a value pydantic rejects), fall back to the live singleton so
    the Settings page and resets keep working instead of turning into 500s;
    the bad variable will fail properly on the next real restart.
    """
    try:
        return Settings()
    except Exception:  # noqa: BLE001 - degraded mode beats a broken settings API
        logger.warning("Could not rebuild Settings from the environment; using live values.", exc_info=True)
        return get_settings()


def _record(settings: Settings, key: str, value: Any | None, *, remove: bool = False) -> None:
    active = getattr(settings, _OVERRIDES_ATTR, None)
    if active is None:
        active = {}
        object.__setattr__(settings, _OVERRIDES_ATTR, active)
    if remove:
        active.pop(key, None)
    else:
        active[key] = value


def set_override(key: str, value: Any) -> Any:
    """Validate ``value`` for ``key`` and apply it to the live settings.

    Returns the normalized value (what the caller should persist). Raises
    ``KeyError`` for a key outside the registry and ``ValueError`` for an
    invalid value.
    """
    spec = REGISTRY[key]
    normalized = spec.coerce(value)
    settings = get_settings()
    previous = getattr(settings, key)
    setattr(settings, key, normalized)
    _record(settings, key, normalized)
    if previous != normalized:
        logger.info("App setting %s changed: %r -> %r", key, previous, normalized)
    return normalized


def clear_override(key: str) -> Any:
    """Drop ``key``'s override, restoring the environment/default value.

    Returns the restored value. Raises ``KeyError`` for unknown keys.
    Idempotent: clearing a key that has no override is a no-op.
    """
    if key not in REGISTRY:
        raise KeyError(key)
    settings = get_settings()
    restored = getattr(_baseline(), key)
    setattr(settings, key, restored)
    _record(settings, key, None, remove=True)
    return restored


def apply_overrides(overrides: Mapping[str, Any], *, reset_missing: bool = False) -> None:
    """Apply a persisted override map onto the live settings singleton.

    Invalid entries (unknown key, out-of-range value — e.g. rows written by a
    different version) are skipped with a warning rather than failing startup.
    With ``reset_missing`` every registry key absent from ``overrides`` is reset
    to its environment/default value — used by process-pool workers to mirror
    the parent's effective state exactly, even on a reused worker.
    """
    settings = get_settings()
    baseline = _baseline() if reset_missing else None
    for key, raw in overrides.items():
        spec = REGISTRY.get(key)
        if spec is None:
            logger.warning("Ignoring unknown app setting override %r.", key)
            continue
        try:
            value = spec.coerce(raw)
        except ValueError as exc:
            logger.warning("Ignoring invalid app setting override %s=%r: %s", key, raw, exc)
            continue
        setattr(settings, key, value)
        _record(settings, key, value)
    if baseline is not None:
        for key in REGISTRY:
            if key not in overrides:
                setattr(settings, key, getattr(baseline, key))
                _record(settings, key, None, remove=True)


async def load_and_apply_overrides(session: "AsyncSession") -> dict[str, Any]:
    """Read all persisted overrides and apply them. Returns the raw rows."""
    from sqlalchemy import select

    from app.db.models.app_setting import AppSetting

    result = await session.execute(select(AppSetting))
    rows = {row.key: row.value_json for row in result.scalars()}
    apply_overrides(rows)
    return rows


def describe_settings() -> list[dict[str, Any]]:
    """UI-facing description of every editable setting.

    ``value`` is the effective value; ``source`` says where it comes from
    (``override`` / ``env`` / ``default``); ``env_value`` is what the setting
    falls back to when the override is cleared (shown so "Reset" is predictable).
    """
    settings = get_settings()
    active = getattr(settings, _OVERRIDES_ATTR, {})
    baseline = _baseline()
    env_prefix = str(Settings.model_config.get("env_prefix") or "")
    out: list[dict[str, Any]] = []
    for spec in _SPECS:
        base_value = getattr(baseline, spec.key)
        # Enum-typed defaults (e.g. Engine.POLARS) compare equal to their str
        # value but serialize differently; normalize to plain str for the API.
        if not isinstance(base_value, (int, str)) or isinstance(base_value, bool):
            base_value = str(base_value)
        default_value = Settings.model_fields[spec.key].default
        if not isinstance(default_value, (int, str)) or isinstance(default_value, bool):
            default_value = str(default_value)
        if spec.key in active:
            source, value = "override", active[spec.key]
        elif base_value != default_value:
            source, value = "env", base_value
        else:
            source, value = "default", base_value
        out.append(
            {
                "key": spec.key,
                "label": spec.label,
                "description": spec.description,
                # The env var this setting maps to, so the UI can say exactly
                # which variable an override shadows (edits to it are ignored
                # until the override is reset).
                "env_var": f"{env_prefix}{spec.key}",
                "category": spec.category,
                "value_type": spec.value_type,
                "choices": list(spec.choices) if spec.choices else None,
                "min_value": spec.min_value,
                "max_value": spec.max_value,
                "restart_required": spec.restart_required,
                "value": value,
                "source": source,
                "default_value": default_value,
                "env_value": base_value,
            }
        )
    return out
