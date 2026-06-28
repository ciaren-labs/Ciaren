"""Unit tests for the Ed25519 signing primitives."""

from __future__ import annotations

import pytest

from app.plugin_api import signing

pytestmark = pytest.mark.skipif(not signing.signing_available(), reason="cryptography not installed")


def test_sha256_hex_is_stable():
    assert signing.sha256_hex(b"hello") == signing.sha256_hex(b"hello")
    assert signing.sha256_hex(b"a") != signing.sha256_hex(b"b")


def test_sign_verify_roundtrip():
    priv, pub = signing.generate_keypair()
    sig = signing.sign(priv, b"payload")
    assert signing.verify(pub, b"payload", sig) is True


def test_verify_rejects_tampered_message():
    priv, pub = signing.generate_keypair()
    sig = signing.sign(priv, b"payload")
    assert signing.verify(pub, b"payload-tampered", sig) is False


def test_verify_rejects_wrong_key():
    priv, _ = signing.generate_keypair()
    _, other_pub = signing.generate_keypair()
    sig = signing.sign(priv, b"payload")
    assert signing.verify(other_pub, b"payload", sig) is False


def test_verify_rejects_garbage_signature():
    _, pub = signing.generate_keypair()
    assert signing.verify(pub, b"payload", "not-hex") is False
    assert signing.verify(pub, b"payload", "deadbeef") is False


def test_keypair_is_random():
    assert signing.generate_keypair()[0] != signing.generate_keypair()[0]
