# SPDX-License-Identifier: AGPL-3.0-only
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AssistantKey(Base):
    """A provider API key saved for the assistant. The secret itself lives in the
    OS keychain under this row's id; the row holds only non-secret settings."""

    __tablename__ = "assistant_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    effort: Mapped[str] = mapped_column(String(16), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # True on the one key the assistant uses, NULL on every other: a unique column
    # admits many NULLs on every supported database, so at most one row is active.
    active: Mapped[bool | None] = mapped_column(Boolean, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
