# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime application settings (the Settings page).

Only keys in ``app.core.runtime_settings.REGISTRY`` are readable/writable —
an explicit allowlist of non-secret, non-security-guard settings. Overrides
are persisted in ``app_settings`` (so they survive restarts) and applied to
the live process immediately. Requests for any other key 404, so this API
can neither read nor touch secrets or environment-only configuration.

State-changing verbs are covered by the app-level API-token and browser-origin
(CSRF) guards, like every other /api route.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import runtime_settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.app_setting import AppSetting
from app.schemas.app_setting import AppSettingRead, AppSettingUpdate

router = APIRouter()


def _describe_one(key: str) -> AppSettingRead:
    for item in runtime_settings.describe_settings():
        if item["key"] == key:
            return AppSettingRead(**item)
    raise NotFoundError("Setting", key)


@router.get("", response_model=list[AppSettingRead])
async def list_settings() -> list[dict[str, Any]]:
    return runtime_settings.describe_settings()


@router.put("/{key}", response_model=AppSettingRead)
async def update_setting(key: str, body: AppSettingUpdate, db: AsyncSession = Depends(get_db)) -> AppSettingRead:
    spec = runtime_settings.REGISTRY.get(key)
    if spec is None:
        raise NotFoundError("Setting", key)
    try:
        normalized = spec.coerce(body.value)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    # Persist first: if the write fails, the running process keeps its old
    # value and the API reports the error — never applied-but-not-saved.
    row = await db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value_json=normalized))
    else:
        row.value_json = normalized
        row.updated_at = datetime.utcnow()
    try:
        await db.commit()
    except IntegrityError:
        # Two concurrent PUTs for a key with no row yet: the loser's INSERT
        # hits the PK. Retry as an update — last write wins, like any PUT.
        await db.rollback()
        row = await db.get(AppSetting, key)
        if row is None:  # row vanished again (concurrent DELETE); re-insert
            db.add(AppSetting(key=key, value_json=normalized))
        else:
            row.value_json = normalized
            row.updated_at = datetime.utcnow()
        await db.commit()

    runtime_settings.set_override(key, normalized)
    return _describe_one(key)


@router.delete("/{key}", response_model=AppSettingRead)
async def reset_setting(key: str, db: AsyncSession = Depends(get_db)) -> AppSettingRead:
    """Remove ``key``'s override, falling back to the environment/default.

    Idempotent: resetting a setting that has no override succeeds and simply
    reports the current (environment/default) state.
    """
    if key not in runtime_settings.REGISTRY:
        raise NotFoundError("Setting", key)
    row = await db.get(AppSetting, key)
    if row is not None:
        await db.delete(row)
        await db.commit()
    runtime_settings.clear_override(key)
    return _describe_one(key)
