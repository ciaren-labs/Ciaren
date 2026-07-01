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

from app.plugin_api import PluginManifest, validate_manifest
from app.plugins.package import (
    MANIFEST_FILENAME,
    PackageError,
    VerifyResult,
    read_manifest,
    verify_package,
)

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

    base = install_dir or user_plugins_dir()
    target = base / _safe_target_name(manifest.id)
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
    base = install_dir or user_plugins_dir()
    target = base / _safe_target_name(manifest.id)
    if target.exists():
        if not force:
            raise InstallError(f"{manifest.id!r} is already installed at {target}; pass force to overwrite")
        shutil.rmtree(target)
    shutil.copytree(src, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return InstallResult(
        plugin_id=manifest.id,
        location=target,
        verification=VerifyResult("unsigned", "", signed=False, reason="installed from source directory"),
    )


def read_manifest_from_dir(src: Path) -> PluginManifest:
    return validate_manifest(json.loads((src / MANIFEST_FILENAME).read_text(encoding="utf-8")))


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
