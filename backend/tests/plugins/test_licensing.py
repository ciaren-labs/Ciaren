"""License tokens: signing, evaluation (incl. offline grace), cache, provider."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.plugin_api import signing
from app.plugins.licensing import (
    LicenseCache,
    LicenseToken,
    TokenLicenseProvider,
    evaluate_token,
    verify_token,
)

_HAS_CRYPTO = signing.signing_available()


def _token(*, expires_in_days: int, grace_extra_days: int) -> LicenseToken:
    now = datetime.now(UTC)
    return LicenseToken(
        userId="u1",
        pluginId="acme.databricks",
        licenseType="pro",
        expiresAt=(now + timedelta(days=expires_in_days)).isoformat(),
        offlineGraceUntil=(now + timedelta(days=expires_in_days + grace_extra_days)).isoformat(),
    )


def test_evaluate_valid_token():
    status = evaluate_token(_token(expires_in_days=30, grace_extra_days=14), verified=True)
    assert status.valid is True
    assert status.license_type == "pro"


def test_evaluate_offline_grace():
    # Expired 1 day ago but within the grace window → still valid.
    now = datetime.now(UTC)
    token = LicenseToken(
        userId="u1",
        pluginId="acme.x",
        expiresAt=(now - timedelta(days=1)).isoformat(),
        offlineGraceUntil=(now + timedelta(days=5)).isoformat(),
    )
    status = evaluate_token(token, verified=True)
    assert status.valid is True
    assert "grace" in status.reason


def test_evaluate_fully_expired():
    now = datetime.now(UTC)
    token = LicenseToken(
        userId="u1",
        pluginId="acme.x",
        expiresAt=(now - timedelta(days=10)).isoformat(),
        offlineGraceUntil=(now - timedelta(days=3)).isoformat(),
    )
    status = evaluate_token(token, verified=True)
    assert status.valid is False
    assert "expired" in status.reason


def test_unverified_token_is_invalid():
    status = evaluate_token(_token(expires_in_days=30, grace_extra_days=7), verified=False)
    assert status.valid is False
    assert "signature" in status.reason


def test_malformed_dates_invalid():
    token = LicenseToken(userId="u", pluginId="p", expiresAt="nope", offlineGraceUntil="nope")
    assert evaluate_token(token, verified=True).valid is False


def test_cache_roundtrip(tmp_path):
    cache = LicenseCache(tmp_path / "licenses")
    token = _token(expires_in_days=30, grace_extra_days=7)
    cache.save(token)
    loaded = cache.load("acme.databricks")
    assert loaded is not None
    assert loaded.user_id == "u1"
    assert cache.load("missing.plugin") is None


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_token_sign_and_verify():
    priv, pub = signing.generate_keypair()
    token = _token(expires_in_days=30, grace_extra_days=7)
    token.signature = signing.sign(priv, token.signing_payload())
    assert verify_token(token, pub) is True
    # Tampering with a field invalidates the signature.
    token.license_type = "enterprise"
    assert verify_token(token, pub) is False


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_token_license_provider_end_to_end(tmp_path):
    priv, pub = signing.generate_keypair()
    token = _token(expires_in_days=30, grace_extra_days=7)
    token.signature = signing.sign(priv, token.signing_payload())
    cache = LicenseCache(tmp_path / "licenses")
    cache.save(token)

    provider = TokenLicenseProvider(pub, cache)
    status = provider.validate_license("acme.databricks")
    assert status.valid is True
    # A plugin with no cached token is unlicensed.
    assert provider.validate_license("acme.unknown").valid is False


def test_provider_invalid_signature(tmp_path):
    # Unsigned token in cache → provider reports invalid (no valid signature).
    cache = LicenseCache(tmp_path / "licenses")
    cache.save(_token(expires_in_days=30, grace_extra_days=7))
    provider = TokenLicenseProvider("00" * 32, cache)
    assert provider.validate_license("acme.databricks").valid is False
