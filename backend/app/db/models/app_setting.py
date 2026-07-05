# SPDX-License-Identifier: AGPL-3.0-only
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AppSetting(Base):
    """A runtime override for one editable ``Settings`` field.

    Only keys in :data:`app.core.runtime_settings.REGISTRY` are ever written
    here — the registry is the allowlist of what the Settings page may edit,
    and secrets are deliberately not part of it, so this table never holds a
    secret. A row's presence *is* the override: deleting it falls back to the
    environment variable / built-in default.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_json: Mapped[Any] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
