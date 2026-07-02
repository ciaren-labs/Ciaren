# SPDX-License-Identifier: AGPL-3.0-only
"""Local license tokens for premium plugins — signed, cached, offline-tolerant.

A token is a small signed JSON blob the marketplace issues after purchase; it is
cached locally and keeps working offline until ``offline_grace_until``. This
deters casual unlicensed use without pretending to be unbreakable DRM
(architecture plan §14).

The core carries **no billing logic**, only generic token verification: it
registers a :class:`TokenLicenseProvider` per trusted issuer public key —
pinned :data:`OFFICIAL_LICENSE_ISSUER_KEYS` plus the
``MARKETPLACE_LICENSE_ISSUER_KEYS`` setting (see :func:`core_license_providers`).
A premium plugin can still register its own provider for bespoke schemes.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.plugin_api import LicenseStatus
from app.plugin_api.providers import LicenseProvider
from app.plugin_api.signing import SigningUnavailableError, verify

#: Overrides where license tokens are cached (default ``~/.ciaren/licenses``).
LICENSE_DIR_ENV = "CIAREN_LICENSE_DIR"

#: License-issuer public keys pinned into the application — the trust root for
#: the official marketplace's purchase tokens, mirroring
#: ``OFFICIAL_PUBLISHER_KEYS`` for package signing. Populated when the official
#: marketplace launches (the public key is not a secret). Multiple entries so an
#: old and a new key can overlap during rotation.
OFFICIAL_LICENSE_ISSUER_KEYS: tuple[str, ...] = ()


class LicenseToken(BaseModel):
    """A license grant for one plugin and user. Field names mirror the marketplace
    wire format (camelCase) per the architecture plan."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    plugin_id: str = Field(alias="pluginId")
    license_type: str = Field(default="pro", alias="licenseType")
    expires_at: str = Field(alias="expiresAt")
    offline_grace_until: str = Field(alias="offlineGraceUntil")
    signature: str = ""

    def signing_payload(self) -> bytes:
        """The canonical bytes that get signed — every field except the signature,
        ordered, so signing and verification agree regardless of JSON key order."""
        payload = {
            "userId": self.user_id,
            "pluginId": self.plugin_id,
            "licenseType": self.license_type,
            "expiresAt": self.expires_at,
            "offlineGraceUntil": self.offline_grace_until,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _parse(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def evaluate_token(token: LicenseToken, *, verified: bool, now: datetime | None = None) -> LicenseStatus:
    """Turn a (already signature-checked) token into a :class:`LicenseStatus`.

    Valid while before ``expires_at``; still valid in the offline grace window up
    to ``offline_grace_until``; otherwise expired. A failed signature is invalid.
    """
    now = now or datetime.now(UTC)
    base = dict(plugin_id=token.plugin_id, license_type=token.license_type, expires_at=token.expires_at)
    if not verified:
        return LicenseStatus(valid=False, reason="invalid signature", **base)
    expires = _parse(token.expires_at)
    grace = _parse(token.offline_grace_until)
    if expires is None or grace is None:
        return LicenseStatus(valid=False, reason="malformed license dates", **base)
    if now <= expires:
        return LicenseStatus(valid=True, reason="licensed", **base)
    if now <= grace:
        return LicenseStatus(valid=True, reason="licensed (offline grace period)", **base)
    return LicenseStatus(valid=False, reason="license expired", **base)


def verify_token(token: LicenseToken, public_key_hex: str) -> bool:
    """Whether the token's signature is valid under the issuer's public key."""
    if not token.signature:
        return False
    try:
        return verify(public_key_hex, token.signing_payload(), token.signature)
    except SigningUnavailableError:
        return False


class LicenseCache:
    """A directory of cached license tokens, one JSON file per plugin id.
    ``CIAREN_LICENSE_DIR`` overrides the default ``~/.ciaren/licenses``."""

    def __init__(self, directory: Path | None = None) -> None:
        override = os.environ.get(LICENSE_DIR_ENV)
        default = Path(override).expanduser() if override else Path.home() / ".ciaren" / "licenses"
        self.directory = directory or default

    def _path(self, plugin_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in plugin_id)
        return self.directory / f"{safe}.json"

    def save(self, token: LicenseToken) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self._path(token.plugin_id).write_text(token.model_dump_json(by_alias=True, indent=2), encoding="utf-8")

    def load(self, plugin_id: str) -> LicenseToken | None:
        path = self._path(plugin_id)
        if not path.is_file():
            return None
        try:
            return LicenseToken.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — a corrupt cache entry is treated as absent
            return None

    def delete(self, plugin_id: str) -> bool:
        """Remove the cached token for ``plugin_id``. Returns True if one existed."""
        path = self._path(plugin_id)
        if not path.is_file():
            return False
        path.unlink()
        return True


class TokenLicenseProvider(LicenseProvider):
    """A :class:`LicenseProvider` backed by signed tokens in a local cache.

    A premium plugin constructs this with the cache and the issuer's public key
    and registers it; the core's :meth:`ServiceRegistry.validate_license` then
    consults it. Plugins not covered by a cached token report invalid.
    """

    def __init__(self, public_key_hex: str, cache: LicenseCache | None = None) -> None:
        self._public_key = public_key_hex
        self._cache = cache or LicenseCache()

    def validate_license(self, plugin_id: str) -> LicenseStatus:
        token = self._cache.load(plugin_id)
        if token is None:
            return LicenseStatus(plugin_id=plugin_id, valid=False, reason="no license token found")
        if token.plugin_id != plugin_id:
            # Cache filenames are sanitized, so distinct plugin ids can collide on
            # the same file (``a/b`` vs ``a_b``) — a validly-signed token must
            # never license a plugin its signed payload doesn't name.
            return LicenseStatus(plugin_id=plugin_id, valid=False, reason="cached token is for a different plugin")
        verified = verify_token(token, self._public_key)
        return evaluate_token(token, verified=verified)


# -- core bootstrap -------------------------------------------------------------
#
# The loader refuses a ``license_required`` plugin unless a license provider is
# registered — but a premium plugin can't register its own provider, because it
# never loads without one. The core breaks that cycle: it registers a
# TokenLicenseProvider per trusted issuer key at registry build, before any
# plugin is processed, so load order can never matter.


def issuer_public_keys() -> list[str]:
    """The license-issuer public keys the core trusts: the pinned
    :data:`OFFICIAL_LICENSE_ISSUER_KEYS` plus the
    ``MARKETPLACE_LICENSE_ISSUER_KEYS`` setting, deduplicated in order."""
    from app.core.config import get_settings

    seen: dict[str, None] = {}
    for key in (*OFFICIAL_LICENSE_ISSUER_KEYS, *get_settings().MARKETPLACE_LICENSE_ISSUER_KEYS):
        if key.strip():
            seen.setdefault(key.strip())
    return list(seen)


def core_license_providers(cache: LicenseCache | None = None) -> list[TokenLicenseProvider]:
    """One :class:`TokenLicenseProvider` per trusted issuer key (the registry asks
    each in turn; the first valid answer wins). Empty when no issuer is configured
    — then only plugin-registered providers, if any, can validate licenses."""
    shared = cache or LicenseCache()
    return [TokenLicenseProvider(key, shared) for key in issuer_public_keys()]


def check_token_against_issuers(token: LicenseToken, keys: list[str] | None = None) -> LicenseStatus | None:
    """Evaluate ``token`` directly against the trusted issuer keys (no cache
    involved) — used to vet a token *before* saving it, so a bad paste can't
    clobber a working cached token. Returns ``None`` when no issuer keys are
    configured (the core then can't judge the token itself)."""
    keys = issuer_public_keys() if keys is None else keys
    if not keys:
        return None
    status: LicenseStatus | None = None
    for key in keys:
        status = evaluate_token(token, verified=verify_token(token, key))
        if status.valid:
            return status
    return status
