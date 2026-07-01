# SPDX-License-Identifier: AGPL-3.0-only
"""Resolve database credentials from environment variables.

Security model: Ciaren **never persists a database password**. A ``Connection``
stores only the *name* of an environment variable (``password_env``); the secret
is read from the process environment at connect time and is never written to the
database, returned in an API response, or emitted into exported code.
"""

from __future__ import annotations

import os

from app.core.exceptions import ValidationError


def resolve_secret(env_var: str | None) -> str | None:
    """Return the value of the named environment variable.

    A falsy ``env_var`` means "no password" (e.g. SQLite, or trust auth). A named
    but unset variable is a configuration error surfaced to the user — without
    ever echoing the variable's value.
    """
    if not env_var:
        return None
    value = os.environ.get(env_var)
    if value is None:
        raise ValidationError(
            f"Environment variable '{env_var}' is not set. Define it before "
            "connecting — Ciaren never stores the password itself."
        )
    return value


def scrub(text: str, *secrets: str | None) -> str:
    """Redact any secret values that may have leaked into a driver error string."""
    cleaned = text
    for secret in secrets:
        if secret:
            cleaned = cleaned.replace(secret, "***")
    return cleaned
