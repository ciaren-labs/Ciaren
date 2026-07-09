# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime application settings (the Settings page).

Only keys in ``app.core.runtime_settings.REGISTRY`` are readable/writable — an
explicit allowlist of non-secret, non-security-guard settings. Overrides are
persisted in ``app_settings`` (so they survive restarts) and applied to the live
process immediately. Any other key raises ``NotFoundError``, so this service can
neither read nor touch secrets or environment-only configuration.

Holding the DB access here (rather than in the route) keeps the route a thin HTTP
adapter, matching every other resource — see app/README.md.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import runtime_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.app_setting import AppSetting
from app.schemas.app_setting import AppSettingRead


class AppSettingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def list_all(self) -> list[dict[str, Any]]:
        return runtime_settings.describe_settings()

    def describe_one(self, key: str) -> AppSettingRead:
        for item in runtime_settings.describe_settings():
            if item["key"] == key:
                return AppSettingRead(**item)
        raise NotFoundError("Setting", key)

    async def update(self, key: str, value: Any) -> AppSettingRead:
        spec = runtime_settings.REGISTRY.get(key)
        if spec is None:
            raise NotFoundError("Setting", key)
        try:
            normalized = spec.coerce(value)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        # Persist first: if the write fails, the running process keeps its old
        # value and the API reports the error — never applied-but-not-saved.
        await self._upsert(key, normalized)
        runtime_settings.set_override(key, normalized)
        return self.describe_one(key)

    async def reset(self, key: str) -> AppSettingRead:
        """Remove ``key``'s override, falling back to the environment/default.

        Idempotent: resetting a setting that has no override succeeds and simply
        reports the current (environment/default) state.
        """
        if key not in runtime_settings.REGISTRY:
            raise NotFoundError("Setting", key)
        row = await self.db.get(AppSetting, key)
        if row is not None:
            await self.db.delete(row)
            await self.db.commit()
        runtime_settings.clear_override(key)
        return self.describe_one(key)

    async def _upsert(self, key: str, normalized: Any) -> None:
        row = await self.db.get(AppSetting, key)
        if row is None:
            self.db.add(AppSetting(key=key, value_json=normalized))
        else:
            row.value_json = normalized
            row.updated_at = datetime.now(UTC).replace(tzinfo=None)
        try:
            await self.db.commit()
        except IntegrityError:
            # Two concurrent PUTs for a key with no row yet: the loser's INSERT
            # hits the PK. Retry as an update — last write wins, like any PUT.
            await self.db.rollback()
            row = await self.db.get(AppSetting, key)
            if row is None:  # row vanished again (concurrent DELETE); re-insert
                self.db.add(AppSetting(key=key, value_json=normalized))
            else:
                row.value_json = normalized
                row.updated_at = datetime.now(UTC).replace(tzinfo=None)
            await self.db.commit()
