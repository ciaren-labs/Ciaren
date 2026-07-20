# SPDX-License-Identifier: AGPL-3.0-only
"""Install and uninstall plugins from ``.ciarenplugin`` packages (or source dirs).

Installation extracts a verified package into the user plugin directory
(``~/.ciaren/plugins`` by default, a directory the loader already scans), so
the plugin is picked up on the next registry build. Verification runs *before*
extraction: a tampered/invalid package is always refused, and ``require_trusted``
refuses anything not signed by a trusted key.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

from app.plugin_api import PLUGIN_API_VERSION, PluginManifest, validate_manifest
from app.plugins.package import (
    MANIFEST_FILENAME,
    PackageError,
    VerifyResult,
    compute_directory_digest,
    compute_manifest_digest,
    read_manifest,
    verify_package,
)
from app.version import ciaren_version

INSTALL_DIR_ENV = "CIAREN_PLUGIN_INSTALL_DIR"

#: Anti zip-bomb / runaway-package limits applied during extraction.
MAX_ENTRY_BYTES = 256 * 1024 * 1024  # 256 MiB per file
MAX_TOTAL_BYTES = 1024 * 1024 * 1024  # 1 GiB across the whole package
MAX_ENTRIES = 10_000

#: Unix file-type bits in a zip entry's external attributes. A symlink entry
#: (``S_IFLNK``) is refused so a package can't drop a symlink that later redirects
#: writes/reads outside the tree.
_S_IFMT = 0o170000
_S_IFLNK = 0o120000


class InstallError(RuntimeError):
    """Raised when a plugin cannot be installed (bad package, untrusted, exists)."""


@dataclass
class InstallResult:
    plugin_id: str
    location: Path
    verification: VerifyResult


def user_plugins_dir() -> Path:
    """Directory new plugins are installed into. ``CIAREN_PLUGIN_INSTALL_DIR``
    overrides the default ``~/.ciaren/plugins`` (which the loader scans)."""
    override = os.environ.get(INSTALL_DIR_ENV)
    return Path(override).expanduser() if override else Path.home() / ".ciaren" / "plugins"


def _safe_target_name(plugin_id: str) -> str:
    """A filesystem-safe directory name for a plugin id (ids may contain dots).

    The mapping must be **injective** — silently rewriting ``a/b`` and ``a_b`` to
    the same name would let one plugin id clobber another's install dir — so we
    reject any id with characters outside ``[A-Za-z0-9._-]`` rather than rewrite.
    """
    if not plugin_id or plugin_id in (".", "..") or not all(c.isalnum() or c in "._-" for c in plugin_id):
        raise InstallError(f"invalid plugin id for installation: {plugin_id!r}")
    return plugin_id


def _reject_case_collision(base: Path, name: str) -> None:
    """Refuse an install whose target directory name differs from an existing
    sibling's only by case. Plugin ids — and their state/TOFU entries — are
    case-sensitive, but the install target is a real directory and common
    filesystems (Windows, macOS) are case-insensitive: there, installing ``foo``
    would ``rmtree`` ``Foo``'s files (the marketplace path always forces) while
    both keep distinct state entries. Rejected on every platform so a package set
    that installs on Linux never breaks elsewhere. Same-cased reinstalls are
    unaffected."""
    if not base.is_dir():
        return
    try:
        siblings = [p.name for p in base.iterdir()]
    except OSError:
        return
    for existing in siblings:
        if existing != name and existing.casefold() == name.casefold():
            raise InstallError(
                f"cannot install {name!r}: {existing!r} is already installed and the two ids "
                f"differ only by letter case, so they would share one install directory on a "
                f"case-insensitive filesystem; uninstall {existing!r} first"
            )


def _is_unsafe_name(name: str) -> bool:
    """Reject an archive entry name lexically (before touching the filesystem):
    absolute paths, drive-qualified paths, backslashes, or any ``..`` component."""
    if name.startswith("/") or "\\" in name or ":" in name:
        return True
    return any(part == ".." for part in name.split("/"))


def _extract_safely(zf: ZipFile, target: Path) -> None:
    """Extract every entry under ``target``, rejecting path traversal (zip-slip),
    symlink entries, and oversized/too-many entries (zip-bomb)."""
    target = target.resolve()
    infos = [i for i in zf.infolist() if not i.filename.endswith("/")]
    if len(infos) > MAX_ENTRIES:
        raise InstallError(f"package has too many entries ({len(infos)} > {MAX_ENTRIES})")
    total = 0
    for info in infos:
        name = info.filename
        # 1. Lexical check on the *archive* name, before any path resolution.
        if _is_unsafe_name(name):
            raise InstallError(f"unsafe path in package: {name!r}")
        # 2. Refuse symlink entries — extracting them could redirect outside target.
        if (info.external_attr >> 16) & _S_IFMT == _S_IFLNK:
            raise InstallError(f"package contains a symlink entry: {name!r}")
        # 3. Size guards (uncompressed) to bound a decompression bomb.
        if info.file_size > MAX_ENTRY_BYTES:
            raise InstallError(f"entry {name!r} is too large ({info.file_size} bytes)")
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise InstallError("package exceeds the maximum uncompressed size")
        # 4. Resolved-path check as defense in depth against any residual escape.
        dest = (target / name).resolve()
        if not str(dest).startswith(str(target) + os.sep) and dest != target:
            raise InstallError(f"unsafe path in package: {name!r}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(zf.read(name))


def _ensure_compatible(manifest: PluginManifest) -> None:
    """Refuse a plugin the running host cannot load — *before* touching the install
    directory. This mirrors the loader's compatibility gate (app ``ciaren`` spec +
    plugin-contract ``api_version``), but the loader only guards runtime import: it
    can't stop a force-install/marketplace-update from ``shutil.rmtree``-ing a
    working plugin and dropping an incompatible one that then fails to load. Checking
    here keeps a bad update from replacing the existing install at all."""
    if not manifest.is_compatible_with(ciaren_version()):
        raise InstallError(
            f"refusing to install {manifest.id!r}: requires Ciaren {manifest.ciaren!r}, running {ciaren_version()}"
        )
    if not manifest.is_api_compatible_with(PLUGIN_API_VERSION):
        raise InstallError(
            f"refusing to install {manifest.id!r}: targets plugin-API {manifest.api_version}, "
            f"backend provides {PLUGIN_API_VERSION}"
        )


def _record_install_state(
    plugin_id: str, verification: VerifyResult, manifest_digest: str = "", code_digest: str = ""
) -> None:
    """Persist how the package verified (trust badge) and enforce TOFU signer
    pinning: a plugin id is claimable, so approval the user gave to one publisher's
    code must not silently carry over to a replacement.

    Approval survives a reinstall **only** when the new package is provably the
    same signer — a non-empty signing key id identical to the one pinned at the
    previous install. Everything else is treated as a possible publisher swap and
    withdraws approval: a different key, an unsigned replacement (no identity to
    pin to, so re-approval is required even for unsigned-over-unsigned), or a
    downgrade away from a trusted signature. In those cases the plugin drops back
    to pending and its new code stays un-imported until the user re-approves it."""
    from app.plugins.state import PluginStateStore

    state = PluginStateStore()
    prev = state.entry(plugin_id)
    if prev is not None and prev.approved:
        same_signer = bool(verification.key_id) and verification.key_id == prev.key_id
        if not same_signer:
            state.set_approved(plugin_id, False)
    state.set_signature(plugin_id, verification.outcome, key_id=verification.key_id)
    # Pin the installed manifest so the loader can detect a post-install manifest
    # edit (the license/permission-gate bypass), and the installed code tree so it
    # can detect a post-install code edit (the signature is only verified at
    # install; without this pin a .py swapped on disk later would still run with
    # the recorded trust badge). A source-directory install passes "" for both,
    # which the loader reads as "nothing to verify" and skips — dev installs are
    # deliberately editable.
    state.set_manifest_digest(plugin_id, manifest_digest)
    state.set_code_digest(plugin_id, code_digest)
    state.save()


def install_ciarenplugin(
    package_path: str | os.PathLike[str],
    *,
    install_dir: Path | None = None,
    require_trusted: bool = False,
    trusted_keys: dict[str, str] | None = None,
    force: bool = False,
) -> InstallResult:
    """Verify and install a ``.ciarenplugin``. Returns where it landed + the
    verification result. Raises :class:`InstallError` on a bad/untrusted package
    or an existing install (unless ``force``)."""
    manifest = read_manifest(package_path)  # raises PackageError if malformed
    result = verify_package(package_path, trusted_keys)
    if not result.ok:
        raise InstallError(f"refusing to install {manifest.id!r}: {result.reason}")
    if require_trusted and result.outcome != "trusted":
        raise InstallError(f"refusing to install {manifest.id!r}: not signed by a trusted key ({result.reason})")
    _ensure_compatible(manifest)  # before we replace any existing install

    base = install_dir or user_plugins_dir()
    target = base / _safe_target_name(manifest.id)
    _reject_case_collision(base, target.name)  # before exists(): case-blind on Windows/macOS
    if target.exists():
        if not force:
            raise InstallError(f"{manifest.id!r} is already installed at {target}; pass force to overwrite")
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    with ZipFile(package_path) as zf:
        _extract_safely(zf, target)
    if not (target / MANIFEST_FILENAME).is_file():  # defensive: should always be present
        shutil.rmtree(target, ignore_errors=True)
        raise InstallError(f"installed package for {manifest.id!r} is missing {MANIFEST_FILENAME}")
    _record_install_state(
        manifest.id,
        result,
        compute_manifest_digest(target / MANIFEST_FILENAME),
        compute_directory_digest(target),
    )
    return InstallResult(plugin_id=manifest.id, location=target, verification=result)


def install_directory(
    src_dir: str | os.PathLike[str],
    *,
    install_dir: Path | None = None,
    force: bool = False,
) -> InstallResult:
    """Install a plugin from an unpacked source directory (dev convenience)."""
    src = Path(src_dir)
    if not (src / MANIFEST_FILENAME).is_file():
        raise PackageError(f"{src} has no {MANIFEST_FILENAME}")
    manifest = read_manifest_from_dir(src)
    _ensure_compatible(manifest)  # before we replace any existing install
    base = install_dir or user_plugins_dir()
    target = base / _safe_target_name(manifest.id)
    _reject_case_collision(base, target.name)  # before exists(): case-blind on Windows/macOS
    if target.exists():
        if not force:
            raise InstallError(f"{manifest.id!r} is already installed at {target}; pass force to overwrite")
        shutil.rmtree(target)
    shutil.copytree(src, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    verification = VerifyResult("unsigned", "", signed=False, reason="installed from source directory")
    _record_install_state(manifest.id, verification)
    return InstallResult(plugin_id=manifest.id, location=target, verification=verification)


def read_manifest_from_dir(src: Path) -> PluginManifest:
    return validate_manifest(json.loads((src / MANIFEST_FILENAME).read_text(encoding="utf-8")))


def installed_location(plugin_id: str, *, install_dir: Path | None = None) -> Path | None:
    """The managed install directory for ``plugin_id`` if it exists on disk — i.e.
    the plugin was installed through the install flow and can be uninstalled.
    Returns ``None`` for a dev-dir (``CIAREN_PLUGINS_DIR``) or entry-point plugin,
    which live outside the managed dir and must be removed by other means."""
    base = install_dir or user_plugins_dir()
    try:
        target = base / _safe_target_name(plugin_id)
    except InstallError:
        return None
    return target if target.is_dir() else None


def uninstall_plugin(plugin_id: str, *, install_dir: Path | None = None) -> bool:
    """Remove an installed plugin's directory. Returns True if something was
    removed. Also forgets its persisted state (enable/grants)."""
    base = install_dir or user_plugins_dir()
    target = base / _safe_target_name(plugin_id)
    removed = False
    if target.is_dir():
        shutil.rmtree(target)
        removed = True
    try:
        from app.plugins.state import PluginStateStore

        state = PluginStateStore()
        state.forget(plugin_id)
        state.save()
    except Exception:  # noqa: BLE001 — state cleanup is best-effort
        pass
    return removed
