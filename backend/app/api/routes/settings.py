# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime application settings (the Settings page).

Only keys in ``app.core.runtime_settings.REGISTRY`` are readable/writable —
an explicit allowlist of non-secret, non-security-guard settings. Overrides
are persisted in ``app_settings`` (so they survive restarts) and applied to
the live process immediately. Requests for any other key 404, so this API
can neither read nor touch secrets or environment-only configuration.

State-changing verbs are covered by the app-level API-token and browser-origin
(CSRF) guards, like every other /api route. The persistence + override logic
lives in :class:`app.services.app_setting_service.AppSettingService`; this router
is a thin HTTP adapter (no direct DB access), matching every other resource.
"""

from typing import Any

from fastapi import APIRouter

from app.api.deps import AppSettingServiceDep
from app.schemas.app_setting import AppSettingRead, AppSettingUpdate

router = APIRouter()


@router.get("", response_model=list[AppSettingRead])
async def list_settings(service: AppSettingServiceDep) -> list[dict[str, Any]]:
    return service.list_all()


@router.put("/{key}", response_model=AppSettingRead)
async def update_setting(key: str, body: AppSettingUpdate, service: AppSettingServiceDep) -> AppSettingRead:
    return await service.update(key, body.value)


@router.delete("/{key}", response_model=AppSettingRead)
async def reset_setting(key: str, service: AppSettingServiceDep) -> AppSettingRead:
    """Remove ``key``'s override, falling back to the environment/default."""
    return await service.reset(key)
