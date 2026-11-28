# SPDX-License-Identifier: AGPL-3.0-only
"""API keys for the assistant, managed from the Connections page.

Each secret is stored in the OS keychain of the machine that runs Ciaren; the
database row keeps only the name, provider, model and state. At most one
enabled key is active, and that key is mirrored into ``assistant_keys`` so
provider calls need no database access.
"""

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import assistant_keys
from app.core.assistant_profiles import PROFILES, Provider, valid_model
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.models.assistant_key import AssistantKey
from app.schemas.assistant import AssistantKeyCreate, AssistantKeyRead, AssistantKeyUpdate, ProviderModels


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _read(row: AssistantKey) -> AssistantKeyRead:
    return AssistantKeyRead(
        id=row.id,
        name=row.name,
        provider=cast(Provider, row.provider),
        model=row.model,
        effort=row.effort,
        is_enabled=row.is_enabled,
        is_active=bool(row.active),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _check(provider: str, model: str, effort: str) -> None:
    if not valid_model(provider, model):
        raise ValidationError("Enter a model name of letters, digits and . _ : / - characters.")
    if effort not in ("default", *PROFILES[provider].efforts):
        raise ValidationError("This provider does not offer that reasoning effort.")


def providers() -> list[ProviderModels]:
    return [
        ProviderModels(id=cast(Provider, name), label=p.label, models=list(p.models), efforts=list(p.efforts))
        for name, p in PROFILES.items()
    ]


async def load_active(db: AsyncSession) -> None:
    """Mirror the active key into the process, or clear it when none is active."""
    row = (await db.execute(select(AssistantKey).where(AssistantKey.active.is_(True)))).scalar_one_or_none()
    if row is None or not row.is_enabled or row.provider not in PROFILES:
        assistant_keys.use_local(None)
        return
    assistant_keys.use_local(
        assistant_keys.Selection(
            provider=cast(Provider, row.provider),
            model=row.model,
            effort=row.effort,
            source="local",
            key_id=row.id,
            name=row.name,
        )
    )


class AssistantKeyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_keys(self) -> list[AssistantKeyRead]:
        rows = (await self.db.execute(select(AssistantKey).order_by(AssistantKey.created_at))).scalars()
        return [_read(r) for r in rows]

    async def _get(self, key_id: str) -> AssistantKey:
        row = await self.db.get(AssistantKey, key_id)
        if row is None:
            raise NotFoundError("Assistant key", key_id)
        return row

    async def _commit(self) -> None:
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise ConflictError("Another API key already has this name.") from None

    async def create(self, body: AssistantKeyCreate) -> AssistantKeyRead:
        _check(body.provider, body.model, body.effort)
        if await self.db.scalar(select(AssistantKey.id).where(AssistantKey.name == body.name)):
            raise ConflictError("Another API key already has this name.")
        active = await self.db.scalar(select(AssistantKey.id).where(AssistantKey.active.is_(True)))
        now = _now()
        row = AssistantKey(
            id=str(uuid4()),
            name=body.name,
            provider=body.provider,
            model=body.model,
            effort=body.effort,
            is_enabled=True,
            # The first key is the one the assistant uses until the user picks another.
            active=None if active else True,
            created_at=now,
            updated_at=now,
        )
        await asyncio.to_thread(assistant_keys.store_key, row.id, body.key)
        self.db.add(row)
        try:
            await self._commit()
        except BaseException:
            await asyncio.to_thread(assistant_keys.store_key, row.id, None)
            raise
        await load_active(self.db)
        return _read(row)

    async def update(self, key_id: str, body: AssistantKeyUpdate) -> AssistantKeyRead:
        row = await self._get(key_id)
        model = body.model if body.model is not None else row.model
        effort = body.effort if body.effort is not None else row.effort
        _check(row.provider, model, effort)
        if body.key is not None:
            if not body.acknowledged:
                raise ValidationError("Confirm the storage notice to save a new API key.")
            await asyncio.to_thread(assistant_keys.store_key, row.id, body.key)
        if body.name is not None:
            row.name = body.name
        row.model, row.effort = model, effort
        if body.is_enabled is not None:
            row.is_enabled = body.is_enabled
            if not body.is_enabled:
                row.active = None
        row.updated_at = _now()
        await self._commit()
        await load_active(self.db)
        return _read(row)

    async def activate(self, key_id: str) -> AssistantKeyRead:
        row = await self._get(key_id)
        if not row.is_enabled:
            raise ValidationError("Enable this API key before using it for the assistant.")
        await self.db.execute(update(AssistantKey).where(AssistantKey.id != key_id).values(active=None))
        row.active = True
        row.updated_at = _now()
        await self._commit()
        await load_active(self.db)
        return _read(row)

    async def delete(self, key_id: str) -> None:
        row = await self._get(key_id)
        # Remove the secret first: a failure keeps the row, so the user can retry.
        await asyncio.to_thread(assistant_keys.store_key, row.id, None)
        await self.db.delete(row)
        await self.db.commit()
        await load_active(self.db)
