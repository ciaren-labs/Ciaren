import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Connection(Base):
    """A reusable database connection (one per database, shared across many SQL
    nodes). Security: the password is **never** stored — only ``password_env``,
    the name of an environment variable resolved at connect time."""

    __tablename__ = "connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Database name, or a file path for SQLite — Text since paths can be long.
    database: Mapped[str | None] = mapped_column(Text, nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # The NAME of an env var holding the password — never the password itself.
    password_env: Mapped[str | None] = mapped_column(String(255), nullable=True)
    options_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    # When the connection was last tested (any test, pass or fail). Null = never.
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
