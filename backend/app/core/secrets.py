# SPDX-License-Identifier: AGPL-3.0-only
"""Resolve connection secrets from pluggable local sources.

Security model: Ciaren **never persists a secret**. A ``Connection`` stores only
a *reference* (the ``password_env`` column); the value is fetched at connect
time and is never written to the database, returned in an API response, or
emitted into exported code. Like Airflow's secrets backends, the reference
carries a scheme picking the source — all local, no external service required:

- ``PG_PASSWORD`` or ``env:PG_PASSWORD`` — an environment variable (the
  historical default; bare names stay valid).
- ``keyring:NAME`` — the OS keychain (Windows Credential Manager, macOS
  Keychain, Secret Service on Linux) under the ``ciaren`` service, stored with
  ``ciaren secret set NAME``. Encrypted at rest and not inherited by child
  processes — the recommended source on desktop installs.
- ``file:/path`` — the file's contents (Docker/Kubernetes secrets). Confined to
  the allowed secret folders (``SECRET_FILE_DIRS``; by default
  ``<DATA_DIR>/secrets`` and ``/run/secrets``) so a connection can't read
  arbitrary server files.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from app.core.exceptions import ValidationError

#: Service name namespacing Ciaren's entries in the OS keychain. References can
#: only read secrets deliberately stored for Ciaren, never other apps' entries.
KEYRING_SERVICE = "ciaren"

_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_KEYRING_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SCHEMES = ("env", "file", "keyring")


def parse_secret_ref(ref: str) -> tuple[str, str]:
    """Split a secret reference into ``(scheme, value)``, validating its syntax.

    A bare env var name (the pre-scheme format every existing row uses) parses
    as the ``env`` scheme. Syntax only — policy (env allowlist, file
    confinement) is enforced by :func:`ensure_permitted_secret_ref`.
    """
    scheme, sep, rest = ref.partition(":")
    if sep and scheme in _SCHEMES:
        value = rest.strip()
        if scheme == "env" and not _ENV_NAME_RE.match(value):
            raise ValidationError(
                f"env: reference needs a valid environment variable name "
                f"(letters, digits, underscores; must not start with a digit). Got: {value!r}"
            )
        if scheme == "keyring" and not _KEYRING_NAME_RE.match(value):
            raise ValidationError(
                f"keyring: reference needs a name made of letters, digits, dots, dashes, or underscores. Got: {value!r}"
            )
        if scheme == "file" and not value:
            raise ValidationError("file: reference needs a path to a secret file.")
        return scheme, value
    if _ENV_NAME_RE.match(ref):
        return "env", ref
    raise ValidationError(
        f"{ref!r} is not a valid secret reference. Use an environment variable name "
        "(PG_PASSWORD or env:PG_PASSWORD), keyring:NAME (OS keychain — store it with "
        "`ciaren secret set NAME`), or file:/path/to/secret (inside an allowed secrets folder)."
    )


@lru_cache
def _app_config_env_names() -> frozenset[str]:
    """Env var names of Ciaren's own settings (CIAREN_API_TOKEN, …), uppercased.

    A connection must never name one of these as its secret: whatever value they
    hold is sent to a user-chosen host as a password/API key, which would turn
    the connections API into an exfiltration channel for the app's own secrets
    (API token, webhook secrets, database URL, …).
    """
    from app.core.config import Settings

    prefix = str(Settings.model_config.get("env_prefix") or "")
    return frozenset((prefix + name).upper() for name in Settings.model_fields)


def _ensure_permitted_env(env_var: str) -> None:
    """Env-scheme policy: Ciaren's own config vars are always off-limits
    (compared case-insensitively — Windows env vars are case-insensitive, so a
    lowercase alias would still read them), and when ``SECRET_ENV_ALLOWLIST`` is
    configured (shared deployments) the name must match one of its entries
    (exact, or prefix when the entry ends with ``*``). Empty list = any name,
    the historical local-first default."""
    if env_var.upper() in _app_config_env_names():
        raise ValidationError(
            f"Environment variable '{env_var}' is Ciaren's own configuration and cannot be used as a connection secret."
        )
    from app.core.config import get_settings

    allowlist = get_settings().SECRET_ENV_ALLOWLIST
    if not allowlist:
        return
    for entry in allowlist:
        entry = entry.strip()
        if not entry:
            continue
        if entry.endswith("*"):
            if env_var.startswith(entry[:-1]):
                return
        elif env_var == entry:
            return
    raise ValidationError(
        f"Environment variable '{env_var}' is not in this server's secret allowlist "
        "(CIAREN_SECRET_ENV_ALLOWLIST). Ask the operator to allow it."
    )


def _secret_file_dirs() -> list[Path]:
    """Folders a ``file:`` reference may read from, resolved absolute. Defaults
    to ``<DATA_DIR>/secrets`` plus ``/run/secrets`` (Docker/Kubernetes secrets)."""
    from app.core.config import get_settings

    settings = get_settings()
    raw = settings.SECRET_FILE_DIRS or [str(Path(settings.DATA_DIR) / "secrets"), "/run/secrets"]
    return [Path(r.strip()).expanduser().resolve() for r in raw if r.strip()]


def _ensure_permitted_file(path_text: str) -> Path:
    """File-scheme policy: the resolved path (symlinks included) must live inside
    an allowed secrets folder — otherwise a connection could exfiltrate any file
    the server can read (~/.aws/credentials, Ciaren's own database, …)."""
    resolved = Path(path_text).expanduser().resolve()
    dirs = _secret_file_dirs()
    for base in dirs:
        if resolved == base:
            break
        try:
            resolved.relative_to(base)
            break
        except ValueError:
            continue
    else:
        raise ValidationError(
            f"Secret file {resolved} is outside the allowed secrets folders "
            f"({', '.join(str(d) for d in dirs)}). Move it there or adjust CIAREN_SECRET_FILE_DIRS."
        )
    return resolved


def ensure_permitted_secret_ref(ref: str | None) -> None:
    """Refuse secret references policy forbids. Enforced at resolve time (the
    single choke point, covering rows saved before a rule existed) and at
    connection save time (early feedback). A falsy ref means "no secret"."""
    if not ref:
        return
    scheme, value = parse_secret_ref(ref)
    if scheme == "env":
        _ensure_permitted_env(value)
    elif scheme == "file":
        _ensure_permitted_file(value)
    # keyring: syntax-only — entries are namespaced under the ciaren service,
    # so a reference can only read secrets deliberately stored for Ciaren.


def resolve_secret(ref: str | None) -> str | None:
    """Fetch the secret a reference points at.

    A falsy ``ref`` means "no password" (e.g. SQLite, or trust auth). A
    reference whose source has no value is a configuration error surfaced to
    the user — without ever echoing any secret value.
    """
    if not ref:
        return None
    scheme, value = parse_secret_ref(ref)
    if scheme == "env":
        _ensure_permitted_env(value)
        env_value = os.environ.get(value)
        if env_value is None:
            raise ValidationError(
                f"Environment variable '{value}' is not set. Define it before "
                "connecting — Ciaren never stores the password itself."
            )
        return env_value
    if scheme == "file":
        path = _ensure_permitted_file(value)
        try:
            return path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            raise ValidationError(f"Secret file {path} does not exist.") from None
        except OSError as exc:
            raise ValidationError(f"Secret file {path} could not be read: {exc.strerror or exc}.") from None
    return _resolve_keyring(value)


def _resolve_keyring(name: str) -> str:
    try:
        import keyring
    except ImportError:  # pragma: no cover — keyring is a core dependency; broken installs only
        raise ValidationError("The 'keyring' package is missing — reinstall Ciaren (pip install ciaren).") from None
    try:
        secret: str | None = keyring.get_password(KEYRING_SERVICE, name)
    except Exception as exc:  # noqa: BLE001 — backend errors (locked/no daemon) must be a clear 400
        raise ValidationError(f"The OS keychain could not be read: {exc}") from None
    if secret is None:
        raise ValidationError(f"No secret named '{name}' in the OS keychain. Store it with `ciaren secret set {name}`.")
    return secret


def scrub(text: str, *secrets: str | None) -> str:
    """Redact any secret values that may have leaked into a driver error string."""
    cleaned = text
    for secret in secrets:
        if secret:
            cleaned = cleaned.replace(secret, "***")
    return cleaned
