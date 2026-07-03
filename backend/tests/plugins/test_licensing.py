"""License tokens: signing, evaluation (incl. offline grace), cache, provider,
and the core bootstrap that turns configured issuer keys into providers."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.plugin_api import signing
from app.plugins.licensing import (
    LicenseCache,
    LicenseToken,
    TokenLicenseProvider,
    check_token_against_issuers,
    core_license_providers,
    evaluate_token,
    issuer_public_keys,
    verify_token,
)

_HAS_CRYPTO = signing.signing_available()


@pytest.fixture(autouse=True)
def _fresh_settings():
    """The issuer-key tests mutate CIAREN_* env vars; clear the settings cache
    after each test so the mutated values never leak into other tests."""
    yield
    from app.core.config import get_settings

    get_settings.cache_clear()


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


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_provider_rejects_cached_token_for_other_plugin(tmp_path):
    """Sanitized cache filenames collide across plugin ids ("acme/databricks" and
    "acme_databricks" share a file) — a validly signed token must only ever
    license the plugin id its signed payload names."""
    priv, pub = signing.generate_keypair()
    now = datetime.now(UTC)
    token = LicenseToken(
        userId="u1",
        pluginId="acme/databricks",
        expiresAt=(now + timedelta(days=30)).isoformat(),
        offlineGraceUntil=(now + timedelta(days=44)).isoformat(),
    )
    token.signature = signing.sign(priv, token.signing_payload())
    cache = LicenseCache(tmp_path / "licenses")
    cache.save(token)

    provider = TokenLicenseProvider(pub, cache)
    status = provider.validate_license("acme_databricks")
    assert status.valid is False
    assert "different plugin" in status.reason
    # The id the payload actually names still validates.
    assert provider.validate_license("acme/databricks").valid is True


def test_cache_delete(tmp_path):
    cache = LicenseCache(tmp_path / "licenses")
    cache.save(_token(expires_in_days=30, grace_extra_days=7))
    assert cache.delete("acme.databricks") is True
    assert cache.load("acme.databricks") is None
    assert cache.delete("acme.databricks") is False


def test_cache_default_dir_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("CIAREN_LICENSE_DIR", str(tmp_path / "custom"))
    assert LicenseCache().directory == tmp_path / "custom"


# -- core bootstrap (issuer keys from settings → providers) ---------------------


def _set_issuer_keys(monkeypatch, keys: list[str]) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("CIAREN_MARKETPLACE_LICENSE_ISSUER_KEYS", json.dumps(keys))
    get_settings.cache_clear()


def test_no_issuer_keys_no_core_providers(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.delenv("CIAREN_MARKETPLACE_LICENSE_ISSUER_KEYS", raising=False)
    get_settings.cache_clear()
    assert issuer_public_keys() == []
    assert core_license_providers() == []


def test_issuer_keys_from_settings(monkeypatch):
    _set_issuer_keys(monkeypatch, ["aa" * 32, "aa" * 32, "  ", "bb" * 32])
    # Deduplicated, blank entries dropped, order preserved.
    assert issuer_public_keys() == ["aa" * 32, "bb" * 32]
    assert len(core_license_providers()) == 2


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_core_provider_validates_issuer_signed_token(tmp_path, monkeypatch):
    priv, pub = signing.generate_keypair()
    _set_issuer_keys(monkeypatch, [pub])
    token = _token(expires_in_days=30, grace_extra_days=7)
    token.signature = signing.sign(priv, token.signing_payload())
    cache = LicenseCache(tmp_path / "licenses")
    cache.save(token)

    providers = core_license_providers(cache)
    assert len(providers) == 1
    assert providers[0].validate_license("acme.databricks").valid is True


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_check_token_against_issuers(monkeypatch):
    priv, pub = signing.generate_keypair()
    other_priv, _ = signing.generate_keypair()
    _set_issuer_keys(monkeypatch, [pub])

    token = _token(expires_in_days=30, grace_extra_days=7)
    token.signature = signing.sign(priv, token.signing_payload())
    status = check_token_against_issuers(token)
    assert status is not None and status.valid is True

    forged = _token(expires_in_days=30, grace_extra_days=7)
    forged.signature = signing.sign(other_priv, forged.signing_payload())
    status = check_token_against_issuers(forged)
    assert status is not None and status.valid is False

    _set_issuer_keys(monkeypatch, [])
    # No issuer keys → the core cannot judge the token at all.
    assert check_token_against_issuers(token) is None
