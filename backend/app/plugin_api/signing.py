"""Detached Ed25519 signatures for plugin artifacts — the verification half of
the marketplace trust model.

A publisher signs an artifact's SHA-256 digest with their private key; FlowFrame
verifies the signature against a *trusted* public key before trusting the
artifact. This protects against tampered packages and unofficial builds presented
as official (see the architecture plan §13). It does **not** sandbox plugin code —
that's the permission model's job.

Signing/verifying needs the optional ``cryptography`` dependency
(``pip install flowframe[signing]``); hashing is stdlib-only and always works.
This module is part of the stable contract package, so an external signing tool
can reuse it. It imports only the stdlib and (lazily) ``cryptography``.
"""

from __future__ import annotations

import hashlib
from typing import Any


class SigningUnavailableError(RuntimeError):
    """Raised when a sign/verify is attempted without ``cryptography`` installed."""


def sha256_hex(data: bytes) -> str:
    """Hex SHA-256 digest of ``data`` (stdlib; no optional dependency)."""
    return hashlib.sha256(data).hexdigest()


def signing_available() -> bool:
    """Whether the optional ``cryptography`` backend is importable."""
    try:
        import cryptography.hazmat.primitives.asymmetric.ed25519  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def _ed25519() -> Any:
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519

        return ed25519
    except Exception as exc:  # noqa: BLE001
        raise SigningUnavailableError(
            "plugin signing/verification needs the 'cryptography' package — install flowframe[signing]"
        ) from exc


def generate_keypair() -> tuple[str, str]:
    """Generate an Ed25519 keypair, returned as ``(private_hex, public_hex)``
    (raw 32-byte keys, hex-encoded). For signing tooling and tests."""
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )

    ed = _ed25519()
    private = ed.Ed25519PrivateKey.generate()
    private_hex = str(private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex())
    public_hex = str(private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex())
    return private_hex, public_hex


def sign(private_key_hex: str, message: bytes) -> str:
    """Sign ``message`` with a hex-encoded raw Ed25519 private key → hex signature."""
    ed = _ed25519()
    private = ed.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    return str(private.sign(message).hex())


def verify(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
    """Whether ``signature_hex`` is a valid Ed25519 signature of ``message`` under
    the hex-encoded raw public key. Returns False on any malformed input or
    mismatch (never raises for a bad signature)."""
    ed = _ed25519()
    try:
        public = ed.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        public.verify(bytes.fromhex(signature_hex), message)
        return True
    except SigningUnavailableError:
        raise
    except Exception:  # noqa: BLE001 — invalid signature / key / encoding
        return False
