"""Local license tokens for premium plugins — signed, cached, offline-tolerant.

This is reusable infrastructure, **not** wired into the open-source core: a
premium plugin registers its own :class:`TokenLicenseProvider` so the core never
references premium licensing. A token is a small signed JSON blob the marketplace
issues after purchase; it is cached locally and keeps working offline until
``offline_grace_until``. This deters casual unlicensed use without pretending to
be unbreakable DRM (architecture plan §14).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.plugin_api import LicenseStatus
from app.plugin_api.providers import LicenseProvider
from app.plugin_api.signing import SigningUnavailableError, verify


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
    """A directory of cached license tokens, one JSON file per plugin id."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or (Path.home() / ".flowframe" / "licenses")

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
        verified = verify_token(token, self._public_key)
        return evaluate_token(token, verified=verified)
