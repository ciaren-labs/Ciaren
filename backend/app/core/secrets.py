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


#: Cap on a keychain secret's length. Secrets are small; this only guards
#: against a runaway payload (some OS backends have their own smaller limits,
#: surfaced as a clear error when they reject the write).
MAX_KEYRING_SECRET_BYTES = 4096


#: Shown wherever the optional keyring package is needed but missing.
KEYRING_INSTALL_HINT = "Install the OS keychain support with: pip install ciaren[keyring]"


def _import_keyring() -> object:
    try:
        import keyring
    except ImportError:
        raise ValidationError(f"The OS keychain needs the 'keyring' package. {KEYRING_INSTALL_HINT}") from None
    return keyring


def keyring_availability() -> tuple[bool, str | None, str | None]:
    """``(available, backend_name, detail)`` for the current host's OS keychain.

    Two "unavailable" cases the UI distinguishes via ``detail``: the optional
    ``keyring`` package isn't installed (offer the install command), or it's
    installed but the host has no usable backend — a headless server selects
    keyring's "fail" backend whose reads/writes raise. Never touches any value.
    """
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring
    except ImportError:
        return False, None, KEYRING_INSTALL_HINT
    try:
        backend = keyring.get_keyring()
    except Exception as exc:  # noqa: BLE001 — a broken backend must not 500 the probe
        return False, None, str(exc)
    name = type(backend).__module__ + "." + type(backend).__qualname__
    if isinstance(backend, FailKeyring):
        return False, name, "No usable OS keychain on this host (typical on headless servers)."
    return True, name, None


#: Upper bound on a keychain entry name, shared by every entry point (API,
#: CLI, path params) — well under any platform keychain's own limit.
MAX_KEYRING_NAME_LEN = 255


def validate_keyring_name(name: str) -> str:
    """Validate a keychain entry name against the ``keyring:`` grammar, returning
    it unchanged. Raises :class:`ValidationError` on a bad or over-long name."""
    if len(name) > MAX_KEYRING_NAME_LEN:
        raise ValidationError(f"keyring: name must be at most {MAX_KEYRING_NAME_LEN} characters.")
    scheme, value = parse_secret_ref(f"keyring:{name}")
    return value


def _resolve_keyring(name: str) -> str:
    keyring = _import_keyring()
    try:
        secret: str | None = keyring.get_password(KEYRING_SERVICE, name)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 — backend errors (locked/no daemon) must be a clear 400
        raise ValidationError(f"The OS keychain could not be read: {exc}") from None
    if secret is None:
        raise ValidationError(f"No secret named '{name}' in the OS keychain. Store it with `ciaren secret set {name}`.")
    return secret


def keyring_secret_exists(name: str) -> bool:
    """Whether a Ciaren-namespaced keychain entry ``name`` exists. Never returns
    or logs the value."""
    validate_keyring_name(name)
    keyring = _import_keyring()
    try:
        return keyring.get_password(KEYRING_SERVICE, name) is not None  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(f"The OS keychain could not be read: {exc}") from None


def set_keyring_secret(name: str, value: str) -> None:
    """Store ``value`` in the OS keychain under the Ciaren service and ``name``.

    The value is written straight to the platform keychain — never to Ciaren's
    database, an API response, or a log. Validates the name and bounds the size;
    a backend error (locked keychain, no daemon, size limit) surfaces as a clear
    :class:`ValidationError`.
    """
    validate_keyring_name(name)
    if not value:
        raise ValidationError("The secret value is empty.")
    if len(value.encode("utf-8")) > MAX_KEYRING_SECRET_BYTES:
        raise ValidationError(f"The secret exceeds the {MAX_KEYRING_SECRET_BYTES}-byte limit.")
    keyring = _import_keyring()
    try:
        keyring.set_password(KEYRING_SERVICE, name, value)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 — surface a backend failure, never the value
        raise ValidationError(f"The OS keychain could not be written: {exc}") from None


def delete_keyring_secret(name: str) -> None:
    """Remove a Ciaren-namespaced keychain entry. Raises if it does not exist."""
    validate_keyring_name(name)
    keyring = _import_keyring()
    from keyring.errors import PasswordDeleteError

    try:
        keyring.delete_password(KEYRING_SERVICE, name)  # type: ignore[attr-defined]
    except PasswordDeleteError:
        raise ValidationError(f"No secret named '{name}' in the OS keychain.") from None
    except Exception as exc:  # noqa: BLE001 — locked keychain / no daemon
        raise ValidationError(f"The OS keychain could not be updated: {exc}") from None


# -- credential-in-options guard ------------------------------------------------
#
# A REST-style connection must take its secret from its secret *reference*
# (auth_style api_key / bearer / basic / query_param), never from a static custom
# header or a stored query parameter. Those persist in plain text in the database,
# echo back in every API response, and (query params) leak into request URLs that
# land in error messages and logs. Best-effort defense in depth — unconventional
# names still slip through; the real control is the never-stored secret-reference
# model. Applied to the core REST connector and, equally, to plugin-contributed
# connectors whose options can carry the same shapes.

_SECRET_HEADER_NAMES = frozenset({"authorization", "proxy-authorization", "cookie", "x-api-key"})
_SECRET_QUERY_PARAM_NAMES = frozenset(
    {
        "api_key",
        "api-key",
        "apikey",
        "api_token",
        "apitoken",
        "access_token",
        "auth",
        "auth_token",
        "authorization",
        "bearer",
        "client_secret",
        "key",
        "password",
        "private_token",
        "secret",
        "sig",
        "signature",
        "token",
    }
)


def _mapping_option(options: dict[str, object] | None, key: str) -> dict[str, object]:
    import json

    raw = (options or {}).get(key) or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else {}
        except ValueError:
            return {}  # malformed JSON gets the connector's own, clearer error
    return raw if isinstance(raw, dict) else {}


def _reject_secret_headers(options: dict[str, object] | None) -> None:
    for header in _mapping_option(options, "headers"):
        if str(header).strip().lower() in _SECRET_HEADER_NAMES:
            raise ValidationError(
                f"Custom header '{header}' would store a credential in plain text. "
                "Use the connection's authentication settings instead — the secret "
                "then comes from an environment variable and is never stored."
            )


def _reject_secret_query_params(options: dict[str, object] | None) -> None:
    import urllib.parse

    def _refuse(param: str, where: str) -> None:
        raise ValidationError(
            f"Query parameter '{param}' in {where} would store a credential in plain "
            "text (and leak it into request URLs and error messages). Use auth_style "
            "'query_param' with api_key_param instead — the secret then comes "
            "from the connection's secret reference and is never stored."
        )

    for param in _mapping_option(options, "query_params"):
        if str(param).strip().lower() in _SECRET_QUERY_PARAM_NAMES:
            _refuse(str(param), "query_params")
    # Endpoints may carry their own query strings ("users?api_key=..."), which are
    # persisted and echoed exactly like query_params — check them too.
    raw_endpoints = (options or {}).get("endpoints") or []
    if isinstance(raw_endpoints, str):
        raw_endpoints = raw_endpoints.split(",")
    if isinstance(raw_endpoints, list):
        for endpoint in raw_endpoints:
            query = urllib.parse.urlsplit(str(endpoint).strip()).query
            for key, _ in urllib.parse.parse_qsl(query, keep_blank_values=True):
                if key.strip().lower() in _SECRET_QUERY_PARAM_NAMES:
                    _refuse(key, f"endpoint '{str(endpoint).strip()[:80]}'")


def ensure_no_plaintext_credentials(options: dict[str, object] | None) -> None:
    """Refuse connection options that would persist a credential in plain text: a
    secret-bearing custom header, or a secret-bearing query parameter (in
    ``query_params`` or embedded in an endpoint's own query string). Shared by the
    core REST connector and plugin connectors so both enforce the same rule."""
    _reject_secret_headers(options)
    _reject_secret_query_params(options)


def scrub(text: str, *secrets: str | None) -> str:
    """Redact any secret values that may have leaked into a driver error string.

    Also redacts the URL-encoded forms of each secret: connector errors embed
    request URLs (and DSNs) where the secret appears percent-encoded, so a
    literal replace of the raw value alone would leave a trivially decodable
    copy behind whenever the secret contains ``+ / = &`` or spaces (typical of
    base64/HMAC keys).
    """
    import urllib.parse

    cleaned = text
    for secret in secrets:
        if not secret:
            continue
        for variant in {secret, urllib.parse.quote(secret, safe=""), urllib.parse.quote_plus(secret)}:
            cleaned = cleaned.replace(variant, "***")
    return cleaned
