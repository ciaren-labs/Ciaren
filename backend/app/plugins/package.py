"""The ``.ffplugin`` package format and its signature verification.

A ``.ffplugin`` is a plain zip archive containing:

- ``flowframe-plugin.json`` — the manifest (required).
- the plugin's Python package (the module the manifest ``entrypoint`` points at).
- ``flowframe-signature.json`` — optional detached Ed25519 signature.

The package **digest** is a deterministic SHA-256 over every entry except the
signature file (sorted by name, length-delimited), so two byte-identical payloads
always hash the same regardless of zip ordering. A publisher signs that digest;
FlowFrame verifies it against a trusted public key before installing.

Signed but with an untrusted key, or unsigned, is *allowed by default* for
community plugins — the installer can require a trusted signature via policy.
Tampered (digest mismatch) or a bad signature is always rejected.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from pydantic import BaseModel

from app.plugin_api import PluginManifest, validate_manifest
from app.plugin_api.signing import SigningUnavailableError, sign, verify

MANIFEST_FILENAME = "flowframe-plugin.json"
SIGNATURE_FILENAME = "flowframe-signature.json"
TRUSTED_KEYS_ENV = "FLOWFRAME_TRUSTED_PLUGIN_KEYS"

#: How much we trust a package after verification.
TrustOutcome = Literal["trusted", "untrusted", "unsigned", "invalid"]


class PackageSignature(BaseModel):
    """The detached signature stored in ``flowframe-signature.json``."""

    algorithm: Literal["ed25519"] = "ed25519"
    publisher: str = ""
    #: Identifies which public key signed it (lookup key for trusted keys).
    key_id: str = ""
    #: The package digest that was signed (must equal the recomputed digest).
    digest: str
    signature: str


class PackageError(ValueError):
    """A malformed ``.ffplugin`` (not a zip, missing/invalid manifest)."""


@dataclass
class VerifyResult:
    """Outcome of verifying a ``.ffplugin``."""

    outcome: TrustOutcome
    digest: str
    signed: bool
    reason: str
    publisher: str | None = None

    @property
    def ok(self) -> bool:
        """Whether the package's integrity is acceptable (not tampered/invalid).
        Unsigned and signed-untrusted are acceptable by default; the installer
        decides whether to *require* ``trusted``."""
        return self.outcome != "invalid"


def compute_digest_from_zip(zf: ZipFile) -> str:
    """Deterministic SHA-256 over all entries except the signature file."""
    h = hashlib.sha256()
    names = sorted(n for n in zf.namelist() if n != SIGNATURE_FILENAME and not n.endswith("/"))
    for name in names:
        data = zf.read(name)
        h.update(name.encode("utf-8"))
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return h.hexdigest()


def compute_package_digest(path: str | os.PathLike[str]) -> str:
    with _open_zip(path) as zf:
        return compute_digest_from_zip(zf)


def _open_zip(path: str | os.PathLike[str]) -> ZipFile:
    try:
        return ZipFile(path)
    except (BadZipFile, OSError) as exc:
        raise PackageError(f"{path} is not a valid .ffplugin (zip) archive: {exc}") from exc


def read_manifest(path: str | os.PathLike[str]) -> PluginManifest:
    with _open_zip(path) as zf:
        if MANIFEST_FILENAME not in zf.namelist():
            raise PackageError(f"{path} has no {MANIFEST_FILENAME}")
        try:
            data = json.loads(zf.read(MANIFEST_FILENAME))
        except json.JSONDecodeError as exc:
            raise PackageError(f"{MANIFEST_FILENAME} in {path} is not valid JSON: {exc}") from exc
    return validate_manifest(data)


def read_signature(path: str | os.PathLike[str]) -> PackageSignature | None:
    with _open_zip(path) as zf:
        if SIGNATURE_FILENAME not in zf.namelist():
            return None
        data = json.loads(zf.read(SIGNATURE_FILENAME))
    return PackageSignature.model_validate(data)


def load_trusted_keys() -> dict[str, str]:
    """Trusted publisher public keys, ``key_id -> public_hex``.

    Read from ``FLOWFRAME_TRUSTED_PLUGIN_KEYS`` (a JSON object) and, if present,
    ``~/.flowframe/trusted_keys.json``. Env entries win on conflict.
    """
    keys: dict[str, str] = {}
    file_path = Path.home() / ".flowframe" / "trusted_keys.json"
    if file_path.is_file():
        try:
            keys.update(json.loads(file_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    raw = os.environ.get(TRUSTED_KEYS_ENV)
    if raw:
        try:
            keys.update(json.loads(raw))
        except json.JSONDecodeError:
            pass
    return keys


def verify_package(path: str | os.PathLike[str], trusted_keys: dict[str, str] | None = None) -> VerifyResult:
    """Verify a ``.ffplugin``'s integrity and signature trust.

    Outcomes: ``unsigned`` (no signature), ``invalid`` (digest mismatch or bad
    signature — reject), ``untrusted`` (valid signature but key not in
    ``trusted_keys``), ``trusted`` (valid signature from a trusted key).
    """
    trusted = load_trusted_keys() if trusted_keys is None else trusted_keys
    digest = compute_package_digest(path)
    sig = read_signature(path)

    if sig is None:
        return VerifyResult("unsigned", digest, signed=False, reason="package is not signed")
    if sig.digest != digest:
        return VerifyResult(
            "invalid", digest, signed=True, reason="digest mismatch — package was modified after signing"
        )
    public_hex = trusted.get(sig.key_id) or (trusted.get(sig.publisher) if sig.publisher else None)
    if public_hex is None:
        return VerifyResult(
            "untrusted", digest, signed=True, reason=f"signed by untrusted key {sig.key_id!r}", publisher=sig.publisher
        )
    try:
        valid = verify(public_hex, digest.encode("utf-8"), sig.signature)
    except SigningUnavailableError as exc:
        return VerifyResult("untrusted", digest, signed=True, reason=str(exc), publisher=sig.publisher)
    if not valid:
        return VerifyResult("invalid", digest, signed=True, reason="signature does not match", publisher=sig.publisher)
    return VerifyResult(
        "trusted", digest, signed=True, reason="valid signature from a trusted key", publisher=sig.publisher
    )


# -- packaging / signing tooling ----------------------------------------------


def pack_directory(src_dir: str | os.PathLike[str], out_path: str | os.PathLike[str]) -> Path:
    """Zip a plugin source directory into an (unsigned) ``.ffplugin``.

    The directory must contain a valid ``flowframe-plugin.json`` at its root.
    Returns the written path.
    """
    src = Path(src_dir)
    manifest_path = src / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise PackageError(f"{src} has no {MANIFEST_FILENAME}")
    validate_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))  # fail early on a bad manifest

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(out, "w", ZIP_DEFLATED) as zf:
        for file in sorted(p for p in src.rglob("*") if p.is_file()):
            arcname = file.relative_to(src).as_posix()
            if arcname == SIGNATURE_FILENAME:
                continue  # never carry a stale signature from the source tree
            if "__pycache__" in file.parts:
                continue
            zf.write(file, arcname)
    return out


def sign_package(
    path: str | os.PathLike[str],
    private_key_hex: str,
    *,
    key_id: str,
    publisher: str = "",
) -> PackageSignature:
    """Sign a ``.ffplugin`` in place: compute its digest, sign it, and embed
    ``flowframe-signature.json``. Rewrites the archive (zips can't update entries).
    """
    src = Path(path)
    with _open_zip(src) as zf:
        entries = [(n, zf.read(n)) for n in zf.namelist() if n != SIGNATURE_FILENAME and not n.endswith("/")]
        digest = compute_digest_from_zip(zf)

    signature = PackageSignature(
        publisher=publisher,
        key_id=key_id,
        digest=digest,
        signature=sign(private_key_hex, digest.encode("utf-8")),
    )
    with ZipFile(src, "w", ZIP_DEFLATED) as zf:
        for name, data in entries:
            zf.writestr(name, data)
        zf.writestr(SIGNATURE_FILENAME, signature.model_dump_json(indent=2))
    return signature
