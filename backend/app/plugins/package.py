# SPDX-License-Identifier: AGPL-3.0-only
"""The ``.ciarenplugin`` package format and its signature verification.

A ``.ciarenplugin`` is a plain zip archive containing:

- ``ciaren-plugin.json`` — the manifest (required).
- the plugin's Python package (the module the manifest ``entrypoint`` points at).
- ``ciaren-signature.json`` — optional detached Ed25519 signature.

The package **digest** is a deterministic SHA-256 over every entry except the
signature file (sorted by name, length-delimited), so two byte-identical payloads
always hash the same regardless of zip ordering. A publisher signs that digest;
Ciaren verifies it against a trusted public key before installing.

Signed but with an untrusted key, or unsigned, is *allowed by default* for
community plugins — the installer can require a trusted signature via policy.
Tampered (digest mismatch) or a bad signature is always rejected.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from pydantic import BaseModel, ValidationError

from app.plugin_api import PluginManifest, validate_manifest
from app.plugin_api.signing import SigningUnavailableError, sign, verify

MANIFEST_FILENAME = "ciaren-plugin.json"
SIGNATURE_FILENAME = "ciaren-signature.json"
TRUSTED_KEYS_ENV = "CIAREN_TRUSTED_PLUGIN_KEYS"

logger = logging.getLogger("app.plugins.package")

#: How much we trust a package after verification.
TrustOutcome = Literal["trusted", "untrusted", "unsigned", "invalid"]


class PackageSignature(BaseModel):
    """The detached signature stored in ``ciaren-signature.json``."""

    algorithm: Literal["ed25519"] = "ed25519"
    publisher: str = ""
    #: Identifies which public key signed it (lookup key for trusted keys).
    key_id: str = ""
    #: The package digest that was signed (must equal the recomputed digest).
    digest: str
    signature: str

    def signed_message(self) -> bytes:
        """Canonical bytes a signature covers: the digest **plus** the signer
        metadata (``algorithm``/``key_id``/``publisher``). Binding the metadata
        into the signed payload stops anyone from taking a validly-signed
        ``(digest, signature)`` pair and relabelling who signed it — the signature
        only validates against the exact key/publisher it was issued for."""
        payload = {
            "algorithm": self.algorithm,
            "digest": self.digest,
            "keyId": self.key_id,
            "publisher": self.publisher,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


class PackageError(ValueError):
    """A malformed ``.ciarenplugin`` (not a zip, missing/invalid manifest)."""


@dataclass
class VerifyResult:
    """Outcome of verifying a ``.ciarenplugin``."""

    outcome: TrustOutcome
    digest: str
    signed: bool
    reason: str
    publisher: str | None = None
    #: The signing key's id ("" when unsigned) — recorded per install so a later
    #: reinstall under a *different* key can be detected and re-gated (TOFU).
    key_id: str = ""

    @property
    def ok(self) -> bool:
        """Whether the package's integrity is acceptable (not tampered/invalid).
        Unsigned and signed-untrusted are acceptable by default; the installer
        decides whether to *require* ``trusted``."""
        return self.outcome != "invalid"

    @property
    def official(self) -> bool:
        """Whether the package is first-party: a valid signature from one of the
        publisher keys pinned into the app (:data:`OFFICIAL_PUBLISHER_KEYS`).
        A refinement of ``trusted``, not a separate outcome — every official
        package is trusted, so ``require_trusted`` policies need no change."""
        return self.outcome == "trusted" and is_official_key(self.key_id)


def compute_digest_from_zip(zf: ZipFile) -> str:
    """Deterministic SHA-256 over all entries except the signature file.

    ``namelist()`` can contain the same name twice (a malformed build with
    duplicate entries); ``sorted(set(...))`` collapses those so the digest matches
    what extraction leaves on disk (last-writer-wins → one file per name)."""
    h = hashlib.sha256()
    names = sorted({n for n in zf.namelist() if n != SIGNATURE_FILENAME and not n.endswith("/")})
    for name in names:
        data = zf.read(name)
        h.update(name.encode("utf-8"))
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return h.hexdigest()


def compute_package_digest(path: str | os.PathLike[str]) -> str:
    with _open_zip(path) as zf:
        return compute_digest_from_zip(zf)


def compute_manifest_digest(manifest_path: str | os.PathLike[str]) -> str:
    """SHA-256 of the installed manifest's raw bytes.

    The manifest gets its own dedicated digest (in addition to being covered by
    :func:`compute_directory_digest`) because it is the file the loader's gates
    trust — ``license_required`` and the declared ``permissions`` are read from
    it — so a manifest edit deserves its own precise "manifest changed" error
    rather than a generic code-tamper message."""
    return hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest()


#: File suffixes covered by :func:`compute_directory_digest` — the files whose
#: modification means *different code runs on import*: ``.py`` source, bare
#: ``.pyc`` (how ``compile_python`` packages ship their code), and native
#: extension modules. Deliberately NOT every file in the tree: a plugin that
#: legitimately writes cache/data files inside its own install directory at
#: runtime must never be mistaken for tampered.
CODE_SUFFIXES = (".py", ".pyc", ".pyd", ".so")


def compute_directory_digest(plugin_dir: str | os.PathLike[str]) -> str:
    """Deterministic SHA-256 over an installed plugin's *code* files and manifest.

    The install-time baseline the loader re-checks at startup so a post-install
    edit to the plugin's code (not just its manifest) is refused before import —
    the package signature is only verified at install, so without this a ``.py``
    swapped on disk afterwards would still run with the recorded trust badge.

    Covered: every file with a :data:`CODE_SUFFIXES` suffix plus the manifest,
    keyed by relative path (so adding or removing a code file also changes the
    digest), hashed with the same length-delimited scheme as
    :func:`compute_digest_from_zip`. Excluded: anything under ``__pycache__`` and
    non-code files (runtime data/caches a plugin writes into its own directory).

    ``__pycache__`` is deliberately NOT digested — Python regenerates those caches
    on import, so hashing them would flag every plugin as tampered after its first
    run. That exclusion is only safe because the loader *deletes* every
    ``__pycache__`` tree before importing a pinned plugin (see
    :func:`app.plugins.loader._ensure_not_tampered`): otherwise an attacker with
    plugin-dir write access could plant a ``__pycache__/*.pyc`` whose header matches
    the (unchanged, digested) source ``.py`` and Python would execute the planted
    bytecode without changing this digest. Clearing the caches forces a recompile
    from the digested source and closes that vector.

    Residual gap (disclosed honestly): only *code* files are digested. A plugin
    that at runtime reads and ``exec``s / imports a **non-code** file it ships
    (e.g. a ``.json``/``.txt`` it treats as code) is not protected here — that
    class of tampering is the marketplace sandbox's job, not this local check.

    Best-effort like the manifest check: the recorded baseline lives in the same
    user-writable state file, so this is defense in depth, not DRM."""
    base = Path(plugin_dir)
    h = hashlib.sha256()
    entries: list[tuple[str, Path]] = []
    # os.walk(followlinks=False) never descends into a symlinked directory, so a
    # symlink loop planted in the install dir can neither spin us forever nor walk
    # us out of the tree.
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            path = Path(dirpath) / name
            rel = path.relative_to(base).as_posix()
            # Case-insensitive suffix match: on a case-insensitive filesystem
            # (Windows/macOS) "evil.PY" is just as importable as "evil.py" and must
            # not slip past the digest.
            if path.suffix.lower() in CODE_SUFFIXES or rel == MANIFEST_FILENAME:
                entries.append((rel, path))
    for rel, path in sorted(entries):
        data = path.read_bytes()
        h.update(rel.encode("utf-8"))
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return h.hexdigest()


def _open_zip(path: str | os.PathLike[str]) -> ZipFile:
    try:
        return ZipFile(path)
    except (BadZipFile, OSError) as exc:
        raise PackageError(f"{path} is not a valid .ciarenplugin (zip) archive: {exc}") from exc


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
        raw = zf.read(SIGNATURE_FILENAME)
    # A malformed signature file is a bad package, not a server error: surface it
    # as PackageError (like a malformed manifest) so callers reject it cleanly
    # instead of letting a raw JSON/validation error escape as a 500.
    try:
        return PackageSignature.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise PackageError(f"{SIGNATURE_FILENAME} in {path} is malformed: {exc}") from exc


#: Publisher keys pinned into the application itself — the trust root for the
#: official marketplace. Shipping the key in the app means officially-signed
#: plugins verify as ``trusted`` out of the box, instead of every user being
#: shown the "untrusted key" warning until they hand-edit a keys file (which
#: would train them to click through the one warning that matters). Populated
#: when the official marketplace launches; the public key is not a secret.
#: These entries can be *added to* but never overridden by user configuration —
#: a config-level swap of an official key id is exactly what a key-substitution
#: attack looks like.
OFFICIAL_PUBLISHER_KEYS: dict[str, str] = {
    # "ciaren-official-2026": "<ed25519 public key hex>",
}


def is_official_key(key_id: str) -> bool:
    """Whether ``key_id`` is one of the publisher keys pinned into the app —
    the basis for the "Official" badge (first-party plugins), distinct from a
    key the *user* chose to trust."""
    return bool(key_id) and key_id in OFFICIAL_PUBLISHER_KEYS


def _as_key_mapping(parsed: object) -> dict[str, str] | None:
    """``parsed`` if it is the shape trusted-keys config must have — a JSON object
    mapping string key ids to string public keys — else ``None``. Config parses as
    *valid* JSON of the wrong shape (an array, a string, an object with non-string
    values) more easily than one would hope; feeding that to ``dict.update`` raises
    and would turn a config typo into a broken install/catalog, so malformed shapes
    are ignored (with a log) exactly like malformed JSON."""
    if isinstance(parsed, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in parsed.items()):
        return parsed
    return None


def load_trusted_keys() -> dict[str, str]:
    """Trusted publisher public keys, ``key_id -> public_hex``.

    Starts from the pinned :data:`OFFICIAL_PUBLISHER_KEYS`, then adds
    ``~/.ciaren/trusted_keys.json`` (if present) and ``CIAREN_TRUSTED_PLUGIN_KEYS``
    (a JSON object). Env entries win over the file on conflict, but neither may
    override a pinned official key id — such an attempt is logged and ignored.
    """
    keys: dict[str, str] = {}
    file_path = Path.home() / ".ciaren" / "trusted_keys.json"
    if file_path.is_file():
        try:
            parsed = _as_key_mapping(json.loads(file_path.read_text(encoding="utf-8")))
            if parsed is None:
                logger.warning(
                    "Ignoring trusted-keys file %s: not a JSON object mapping key ids to public key strings.",
                    file_path,
                )
            else:
                keys.update(parsed)
        except (json.JSONDecodeError, OSError) as exc:
            # Don't silently fall back to "no trusted keys" — a config typo would
            # invisibly turn every signed package into an untrusted one.
            logger.warning("Ignoring unreadable trusted-keys file %s: %s", file_path, exc)
    raw = os.environ.get(TRUSTED_KEYS_ENV)
    if raw:
        try:
            env_parsed = _as_key_mapping(json.loads(raw))
        except json.JSONDecodeError:
            env_parsed = None
        if env_parsed is None:
            # Log neither the parse error (its message/doc can echo back fragments of
            # the env var's raw content, which holds trusted-key material) nor the env
            # var name via a variable (CodeQL's sensitive-data heuristic flags logging
            # any expression named like TRUSTED_KEYS_ENV, even just the env var name).
            logger.warning(
                "Ignoring malformed CIAREN_TRUSTED_PLUGIN_KEYS environment variable: "
                "not a JSON object mapping key ids to public key strings."
            )
        else:
            keys.update(env_parsed)
    for key_id, public_hex in OFFICIAL_PUBLISHER_KEYS.items():
        if keys.get(key_id) not in (None, public_hex):
            logger.warning(
                "Ignoring configured override of pinned official key %r — official keys cannot be replaced.",
                key_id,
            )
        keys[key_id] = public_hex
    return keys


def verify_package(path: str | os.PathLike[str], trusted_keys: dict[str, str] | None = None) -> VerifyResult:
    """Verify a ``.ciarenplugin``'s integrity and signature trust.

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
            "invalid",
            digest,
            signed=True,
            reason="digest mismatch — package was modified after signing",
            key_id=sig.key_id,
        )
    # Trust is keyed strictly by ``key_id``. The earlier ``publisher`` fallback let
    # a package-supplied (attacker-controlled) free-text name select which trusted
    # key to check against — a trust-anchor confusion we no longer allow.
    public_hex = trusted.get(sig.key_id)
    if public_hex is None:
        return VerifyResult(
            "untrusted",
            digest,
            signed=True,
            reason=f"signed by untrusted key {sig.key_id!r}",
            publisher=sig.publisher,
            key_id=sig.key_id,
        )
    try:
        valid = verify(public_hex, sig.signed_message(), sig.signature)
    except SigningUnavailableError as exc:
        return VerifyResult(
            "untrusted", digest, signed=True, reason=str(exc), publisher=sig.publisher, key_id=sig.key_id
        )
    if not valid:
        return VerifyResult(
            "invalid",
            digest,
            signed=True,
            reason="signature does not match",
            publisher=sig.publisher,
            key_id=sig.key_id,
        )
    return VerifyResult(
        "trusted",
        digest,
        signed=True,
        reason="valid signature from a trusted key",
        publisher=sig.publisher,
        key_id=sig.key_id,
    )


# -- packaging / signing tooling ----------------------------------------------


def _compile_to_pyc(source: Path) -> bytes:
    """Compile a ``.py`` file to optimized bytecode and return the ``.pyc`` bytes.
    ``optimize=2`` also strips docstrings and ``assert``s from the output."""
    import py_compile
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        cfile = Path(tmp) / "out.pyc"
        try:
            py_compile.compile(str(source), cfile=str(cfile), optimize=2, doraise=True)
        except py_compile.PyCompileError as exc:
            raise PackageError(f"could not compile {source}: {exc}") from exc
        return cfile.read_bytes()


def pack_directory(
    src_dir: str | os.PathLike[str],
    out_path: str | os.PathLike[str],
    *,
    compile_python: bool = False,
) -> Path:
    """Zip a plugin source directory into an (unsigned) ``.ciarenplugin``.

    The directory must contain a valid ``ciaren-plugin.json`` at its root.
    Returns the written path.

    When ``compile_python`` is set, every ``.py`` is compiled to optimized
    bytecode and only the resulting ``.pyc`` ships (placed at the same import path,
    e.g. ``pkg/mod.pyc``) — the source ``.py`` is **omitted**. The loader imports
    bare ``.pyc`` modules transparently, so the plugin still runs. This raises the
    bar against casual inspection/copying of a paid plugin's source; it is **not**
    strong protection — bytecode can still be decompiled, and a ``.pyc`` is locked
    to the building interpreter's Python version. For genuinely sensitive IP, keep
    the logic in a remote service (see the architecture plan §15).
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
            if compile_python and file.suffix == ".py":
                # Ship compiled bytecode at <module>.pyc instead of the source.
                zf.writestr(arcname[: -len(".py")] + ".pyc", _compile_to_pyc(file))
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
    """Sign a ``.ciarenplugin`` in place: compute its digest, sign it, and embed
    ``ciaren-signature.json``. Rewrites the archive (zips can't update entries).
    """
    src = Path(path)
    with _open_zip(src) as zf:
        entries = [(n, zf.read(n)) for n in zf.namelist() if n != SIGNATURE_FILENAME and not n.endswith("/")]
        digest = compute_digest_from_zip(zf)

    signature = PackageSignature(publisher=publisher, key_id=key_id, digest=digest, signature="")
    # Sign over the canonical payload (digest + signer metadata), not the bare
    # digest, so the signature binds *who* signed it, not just the file contents.
    signature.signature = sign(private_key_hex, signature.signed_message())
    with ZipFile(src, "w", ZIP_DEFLATED) as zf:
        for name, data in entries:
            zf.writestr(name, data)
        zf.writestr(SIGNATURE_FILENAME, signature.model_dump_json(indent=2))
    return signature
