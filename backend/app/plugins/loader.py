# SPDX-License-Identifier: AGPL-3.0-only
"""Discover, validate, and register external plugins.

Discovery sources (Phase 1d):

- Python entry points in the ``ciaren.plugins`` group (installed packages).
- Local plugin directories: each immediate subdirectory containing a
  ``ciaren-plugin.json`` manifest.

The loader validates a manifest and checks version compatibility *before*
importing the plugin's entry point, and isolates every plugin behind a try/except
so one broken or incompatible plugin is recorded as an error rather than crashing
the app. Registration is atomic per plugin (the registry rolls back partial
contributions on failure).
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint, entry_points
from pathlib import Path
from typing import Any

from app.plugin_api import (
    PLUGIN_API_VERSION,
    Permission,
    Plugin,
    PluginManifest,
    ServiceRegistry,
    validate_manifest,
)
from app.plugin_api.specs import PluginMetadata
from app.plugins.state import PluginStateStore
from app.version import ciaren_version

logger = logging.getLogger("app.plugins.loader")

ENTRY_POINT_GROUP = "ciaren.plugins"
MANIFEST_FILENAME = "ciaren-plugin.json"


class IncompatiblePluginError(RuntimeError):
    """Raised when a plugin is incompatible with the running host — either its
    ``ciaren`` app-version specifier or its ``api_version`` plugin-contract version
    doesn't match what this backend provides."""


@dataclass
class LoadedPlugin:
    source: str
    metadata: PluginMetadata
    manifest: PluginManifest | None = None


@dataclass
class PluginError:
    source: str
    error: str


@dataclass
class GatedPlugin:
    """A discovered plugin that was deliberately *not* loaded: the user disabled
    it, it declares permissions that have not been granted yet, or it requires a
    license that doesn't validate — in every case its code is never imported.
    Surfaced to the UI so the user can enable/approve/license it."""

    source: str
    plugin_id: str
    name: str
    reason: str  # "disabled" | "needs_permissions" | "needs_license"
    requested_permissions: list[Permission] = field(default_factory=list)
    missing_permissions: list[Permission] = field(default_factory=list)
    nodes: list[str] = field(default_factory=list)
    node_categories: dict[str, str] = field(default_factory=dict)
    #: Human-readable context for the gate (e.g. why the license is not valid).
    detail: str = ""
    #: The validated manifest (gated plugins always have one — gating only applies
    #: to manifest-bearing candidates). Lets the UI show version/publisher/
    #: description without ever importing the plugin's code.
    manifest: PluginManifest | None = None


@dataclass
class LoadResult:
    loaded: list[LoadedPlugin] = field(default_factory=list)
    errors: list[PluginError] = field(default_factory=list)
    gated: list[GatedPlugin] = field(default_factory=list)


class TamperError(RuntimeError):
    """Raised when an installed plugin's manifest or code no longer matches the
    digests recorded at install — someone edited it on disk after installation
    (e.g. to strip ``license_required``, widen ``permissions``, or swap in
    different code behind an intact trust badge). Its code is not imported.
    Best-effort against a casual edit, not tamper-proof: the recorded baseline
    lives in the same user-writable state file, so this is defense in depth, not a
    substitute for server-side license enforcement."""


@dataclass
class PluginCandidate:
    """A potential plugin: where it came from, how to load it, and (if known) its
    validated manifest. ``load`` is deferred so a malformed manifest or an import
    error is caught uniformly during processing. ``path`` is the plugin's install
    directory for filesystem candidates (used for tamper detection); ``None`` for
    entry-point / injected candidates, which have no directory to re-verify."""

    source: str
    load: Callable[[], Plugin]
    manifest: PluginManifest | None = None
    path: Path | None = None


# -- entry point resolution ---------------------------------------------------


def _instantiate(obj: Any) -> Plugin:
    """Coerce an entry-point target into a Plugin instance: it may be a Plugin
    instance, a Plugin subclass, or a zero-arg factory returning one."""
    if isinstance(obj, Plugin):
        return obj
    if isinstance(obj, type) and issubclass(obj, Plugin):
        return obj()
    if callable(obj):
        result = obj()
        if isinstance(result, Plugin):
            return result
    raise TypeError(f"{obj!r} is not a Plugin, Plugin subclass, or Plugin factory")


def load_entrypoint(spec: str) -> Plugin:
    """Import ``module.path:Attribute`` and instantiate it as a Plugin."""
    module_path, _, attr = spec.partition(":")
    if not module_path or not attr:
        raise ValueError(f"entrypoint must be 'module.path:Attribute', got {spec!r}")
    module = importlib.import_module(module_path)
    return _instantiate(getattr(module, attr))


# -- candidate discovery ------------------------------------------------------


def _entry_point_loader(ep: EntryPoint) -> Callable[[], Plugin]:
    def load() -> Plugin:
        return _instantiate(ep.load())

    return load


def _entry_point_candidates() -> list[PluginCandidate]:
    return [
        PluginCandidate(source=f"entry_point:{ep.name}", load=_entry_point_loader(ep))
        for ep in entry_points(group=ENTRY_POINT_GROUP)
    ]


def _raiser(exc: Exception) -> Callable[[], Plugin]:
    def _raise() -> Plugin:
        raise exc

    return _raise


def _local_candidate(plugin_dir: Path, manifest_path: Path) -> PluginCandidate:
    source = f"dir:{plugin_dir.name}"
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = validate_manifest(data)
    except Exception as exc:  # noqa: BLE001 — surfaced as a load error in diagnostics
        return PluginCandidate(source=source, load=_raiser(exc), manifest=None)

    def load(plugin_dir: Path = plugin_dir, manifest: PluginManifest = manifest) -> Plugin:
        # The plugin's package lives directly inside its own directory, so put
        # that directory on sys.path to make the entry-point module importable.
        # *Append* (never insert at 0): a plugin dir must not take import priority
        # over the stdlib or the Ciaren app, or a plugin shipping e.g. its own
        # ``json.py``/``os.py`` would shadow those modules process-wide — for the
        # core and every other plugin, not just itself.
        if str(plugin_dir) not in sys.path:
            sys.path.append(str(plugin_dir))
        if not manifest.entrypoint:
            raise ValueError(f"plugin {manifest.id!r} manifest has no entrypoint")
        return load_entrypoint(manifest.entrypoint)

    return PluginCandidate(source=source, load=load, manifest=manifest, path=plugin_dir)


def _local_dir_candidates(dirs: Iterable[str | os.PathLike[str]]) -> list[PluginCandidate]:
    candidates: list[PluginCandidate] = []
    for raw in dirs:
        base = Path(raw).expanduser()
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            manifest_path = child / MANIFEST_FILENAME
            if child.is_dir() and manifest_path.is_file():
                candidates.append(_local_candidate(child, manifest_path))
    return candidates


# -- loading ------------------------------------------------------------------


def _gate(candidate: PluginCandidate, state: PluginStateStore) -> GatedPlugin | None:
    """Decide whether to skip a manifest-bearing candidate (disabled, or pending
    permission approval). Returns the gating record, or None to proceed.

    Only plugins that ship a manifest are gated — that's the drop-in / marketplace
    case where code should not run before the user opts in. Entry-point packages
    are pip-installed deliberately and load without this gate.
    """
    manifest = candidate.manifest
    if manifest is None:
        return None
    state.note_seen(manifest.id)
    if not state.is_enabled(manifest.id):
        return GatedPlugin(
            source=candidate.source,
            plugin_id=manifest.id,
            name=manifest.name,
            reason="disabled",
            requested_permissions=list(manifest.permissions),
            nodes=list(manifest.ui.nodes),
            node_categories=dict(manifest.ui.node_categories),
            manifest=manifest,
        )
    # A plugin runs only after the user explicitly approves it (enabling or granting
    # permissions). A freshly discovered plugin is unapproved, so its code stays
    # un-imported even when it declares no permissions — approval means "let this
    # code run", not merely "grant these capabilities".
    missing = state.missing_permissions(manifest.id, manifest.permissions)
    if missing or not state.is_approved(manifest.id):
        return GatedPlugin(
            source=candidate.source,
            plugin_id=manifest.id,
            name=manifest.name,
            reason="needs_permissions",
            requested_permissions=list(manifest.permissions),
            missing_permissions=missing,
            nodes=list(manifest.ui.nodes),
            node_categories=dict(manifest.ui.node_categories),
            manifest=manifest,
        )
    return None


def _license_gate(registry: ServiceRegistry, candidate: PluginCandidate) -> GatedPlugin | None:
    """Gate a ``license_required`` plugin whose license does not validate — a
    user-actionable state (activate a license token), not a load error. Runs
    *after* the disable/permission gate so an unapproved premium plugin asks for
    approval first, and its code stays un-imported throughout."""
    manifest = candidate.manifest
    if manifest is None or not manifest.license_required:
        return None
    if not registry.has_license_provider():
        detail = (
            "requires a license, but no license provider is registered — configure a "
            "marketplace license issuer key (CIAREN_MARKETPLACE_LICENSE_ISSUER_KEYS)"
        )
    else:
        status = registry.validate_license(manifest.id)
        if status.valid:
            return None
        detail = f"requires a valid license: {status.reason}" if status.reason else "requires a valid license"
    return GatedPlugin(
        source=candidate.source,
        plugin_id=manifest.id,
        name=manifest.name,
        reason="needs_license",
        requested_permissions=list(manifest.permissions),
        nodes=list(manifest.ui.nodes),
        node_categories=dict(manifest.ui.node_categories),
        manifest=manifest,
        detail=detail,
    )


def _find_bytecode_cache(root: Path) -> Path | None:
    """First surviving ``__pycache__`` under ``root`` (real dir, undeletable dir,
    or **symlink**), else ``None`` — used to confirm the cache clear succeeded.

    Detection is via each parent's ``dirnames`` from ``os.walk``, NOT by waiting
    for the walk to descend into the entry. ``os.walk(followlinks=False)`` never
    yields a symlinked ``__pycache__`` as its own ``dirpath``, so a scan that
    matched on ``dirpath`` would miss a symlinked cache entirely — the exact
    bypass. A parent always lists ``__pycache__`` in ``dirnames`` whether it is a
    real directory, a locked/read-only one, or a symlink, closing that gap.

    Scoped deliberately to ``__pycache__``: the injection vector is a planted
    ``__pycache__/<mod>.<tag>.pyc`` that Python's timestamp invalidation runs in
    place of the digested source. A *bare* ``mod.pyc`` elsewhere in the tree (what
    ``pack_directory(compile_python=True)`` ships for source-protected plugins, the
    module living at ``pkg/mod.pyc`` with no ``.py``) is NOT a survivor: it is the
    module itself and is already covered by the code digest, and Python never
    imports a bare ``.pyc`` that sits next to a ``.py`` (source wins). Flagging it
    here would wrongly refuse every untampered ``compile_python`` install."""
    for dirpath, dirnames, _ in os.walk(root, followlinks=False):
        if "__pycache__" in dirnames:
            return Path(dirpath) / "__pycache__"
    return None


def _clear_pycache(root: Path) -> list[Path]:
    """Delete every ``__pycache__`` under ``root`` — real dir OR symlink — and
    return the caches that are *tamper evidence* (empty when the tree came out
    clean).

    Called before importing a *pinned* plugin so Python must recompile from the
    digested source. Without this, ``__pycache__`` is a hole in the code digest:
    an attacker who can write into the plugin dir can plant a
    ``__pycache__/<mod>.<tag>.pyc`` whose header (magic + flags=0 + source mtime +
    source size) matches the unchanged, digested ``.py``; timestamp-based pyc
    invalidation then executes the planted bytecode while the source — and so the
    digest — stays byte-identical.

    Two things count as tamper evidence and land in the returned list:

    - a ``__pycache__`` that could not be removed (an open handle / read-only dir
      on Windows, which chmod/retry can't beat) — it survives and Python would run
      the plant;
    - a **symlinked** ``__pycache__`` — Python only ever creates a real cache
      directory, so a symlink is never legitimate. The link is unlinked (breaking
      the redirect for any retry), but its mere presence is treated as tampering.

    A removal error is swallowed (logged, not raised): the *caller* decides. For
    pinned installs :func:`_ensure_not_tampered` refuses the load when this list is
    non-empty (fail-closed), rather than importing bytecode it could not vouch for."""
    import shutil

    problems: list[Path] = []
    for dirpath, dirnames, _ in os.walk(root, followlinks=False):
        if "__pycache__" in dirnames:
            dirnames.remove("__pycache__")  # don't descend into what we're deleting
            target = Path(dirpath) / "__pycache__"
            try:
                if target.is_symlink():
                    target.unlink()  # rmtree refuses a symlink; drop the link itself
                    problems.append(target)  # a symlinked cache is never legitimate
                else:
                    shutil.rmtree(target)
            except OSError as exc:
                logger.warning("Could not clear bytecode cache %s before import: %s", target, exc)
                problems.append(target)
    return problems


def _ensure_not_tampered(candidate: PluginCandidate, state: PluginStateStore) -> None:
    """Refuse to import a managed install whose on-disk manifest or code no longer
    matches the digests pinned at install time. Only applies when there *is* a
    pinned digest (packaged install) and a directory — source/dev-dir and
    entry-point plugins have no baseline and are skipped, so deliberately-editable
    local installs are never falsely rejected. Two baselines are checked:

    - the manifest digest (what the license/permission gates read — checked first
      so a manifest edit gets its precise error);
    - the install-tree code digest (``.py``/bare ``.pyc``/native modules; the
      package signature is only verified at install, so without this a code file
      swapped on disk afterwards would run with the recorded trust badge intact).

    The code digest covers only code files (not ``__pycache__``, not runtime
    data/cache files), so a plugin writing data into its own directory is never
    mistaken for tampered. Because ``__pycache__`` is excluded from the digest, a
    pinned plugin's ``__pycache__`` trees are *deleted* here before import so a
    planted ``.pyc`` can't run in place of the digested source (see
    :func:`app.plugins.package.compute_directory_digest`), and the deletion is then
    *verified* — if any cache survives (undeletable via a lock/read-only), the load
    is refused rather than importing a plant Python would trust over the source.

    Fail-closed for pinned installs: if either digest cannot be recomputed (IO
    error, unreadable/looping path — all forceable by an attacker as a way to skip
    the check and then swap a digested file), or the bytecode cache cannot be
    cleared, the plugin is *refused*, not loaded. Only manifest-less / non-pinned /
    dev installs stay fail-open, since they have no security baseline to protect and
    must not brick startup on IO.
    """
    manifest = candidate.manifest
    if manifest is None or candidate.path is None:
        return
    from app.plugins.package import compute_directory_digest, compute_manifest_digest

    recorded = state.recorded_manifest_digest(manifest.id)
    if recorded:
        try:
            actual = compute_manifest_digest(candidate.path / MANIFEST_FILENAME)
        except OSError as exc:
            raise TamperError(
                f"plugin {manifest.id!r} manifest could not be verified against its pinned digest "
                f"({exc}) — refusing to load; reinstall it from a trusted source"
            ) from exc
        if actual != recorded:
            raise TamperError(
                f"plugin {manifest.id!r} manifest changed on disk since it was installed "
                "(digest mismatch) — reinstall it from a trusted source to load it again"
            )
    recorded_code = state.recorded_code_digest(manifest.id)
    if recorded_code:
        try:
            actual_code = compute_directory_digest(candidate.path)
        except OSError as exc:
            raise TamperError(
                f"plugin {manifest.id!r} code could not be verified against its pinned digest "
                f"({exc}) — refusing to load; reinstall it from a trusted source"
            ) from exc
        if actual_code != recorded_code:
            raise TamperError(
                f"plugin {manifest.id!r} code changed on disk since it was installed "
                "(install-tree digest mismatch) — reinstall it from a trusted source to load it again"
            )
        # Source verified — drop any bytecode caches so import can't run a planted
        # .pyc in place of the digested source (the __pycache__ injection vector),
        # then confirm the clear succeeded. Fail-closed: if any cache is tamper
        # evidence — undeletable (a lock / read-only dir) or a symlink (never a
        # legitimate cache) — or any __pycache__ still survives afterwards, refuse
        # rather than import, since Python would trust a matching-header plant over
        # the verified source.
        problems = _clear_pycache(candidate.path)
        survivor = _find_bytecode_cache(candidate.path)
        if survivor is not None:
            problems.append(survivor)
        if problems:
            raise TamperError(
                f"plugin {manifest.id!r} has an unsafe bytecode cache ({problems[0]}) that could "
                "not be cleared or is a symlink — refusing to load; a planted .pyc could run in "
                "place of the verified source. Remove the cache (check for locks/read-only/symlink) "
                "and retry."
            )


def _process(
    registry: ServiceRegistry,
    candidate: PluginCandidate,
    version: str,
    api_version: str,
    result: LoadResult,
    state: PluginStateStore | None,
) -> None:
    try:
        manifest = candidate.manifest
        # Detect post-install tampering before anything else — a hand-edited
        # manifest must not even reach the compat/gate checks that read it.
        if state is not None:
            _ensure_not_tampered(candidate, state)
        if manifest is not None and not manifest.is_compatible_with(version):
            raise IncompatiblePluginError(
                f"plugin {manifest.id!r} requires Ciaren {manifest.ciaren!r}, running {version}"
            )
        if manifest is not None and not manifest.is_api_compatible_with(api_version):
            raise IncompatiblePluginError(
                f"plugin {manifest.id!r} targets plugin-API {manifest.api_version}, backend provides {api_version}"
            )
        gated = _gate(candidate, state) if state is not None else None
        if gated is None:
            gated = _license_gate(registry, candidate)
        if gated is not None:
            result.gated.append(gated)
            logger.info("Plugin %s from %s gated (%s)", gated.plugin_id, candidate.source, gated.reason)
            return
        plugin = candidate.load()
        meta = registry.register_plugin(plugin)
        result.loaded.append(LoadedPlugin(source=candidate.source, metadata=meta, manifest=manifest))
        logger.info("Loaded plugin %s from %s", meta.id, candidate.source)
    except Exception as exc:  # noqa: BLE001 — one plugin must not break the rest
        result.errors.append(PluginError(source=candidate.source, error=str(exc)))
        logger.warning("Failed to load plugin from %s: %s", candidate.source, exc, exc_info=True)


def load_plugins(
    registry: ServiceRegistry,
    *,
    plugin_dirs: Iterable[str | os.PathLike[str]] | None = None,
    include_entry_points: bool = True,
    extra: Iterable[PluginCandidate] | None = None,
    ciaren_version_str: str | None = None,
    api_version_str: str | None = None,
    state: PluginStateStore | None = None,
) -> LoadResult:
    """Discover and register plugins into ``registry``. Returns a result with the
    plugins that loaded, the errors that were isolated, and the manifest-bearing
    plugins that were gated (disabled or pending permission approval).

    ``extra`` lets callers inject pre-built candidates (used by the example plugin
    and tests) without going through entry points or the filesystem. ``state``,
    when given, enables enable/disable + permission gating for manifest plugins.
    ``ciaren_version_str`` / ``api_version_str`` override the app and plugin-contract
    versions a plugin's manifest is checked against (default: the running values);
    tests use them to simulate an older/newer host.
    """
    version = ciaren_version_str or ciaren_version()
    api_version = api_version_str or PLUGIN_API_VERSION
    candidates: list[PluginCandidate] = []
    if include_entry_points:
        candidates += _entry_point_candidates()
    if plugin_dirs is not None:
        candidates += _local_dir_candidates(plugin_dirs)
    if extra is not None:
        candidates += list(extra)

    result = LoadResult()
    for candidate in candidates:
        _process(registry, candidate, version, api_version, result, state)
    if state is not None:
        state.save()
    return result


def default_plugin_dirs() -> list[str]:
    """Plugin directories scanned by default: ``CIAREN_PLUGINS_DIR`` (an
    ``os.pathsep``-separated list) plus ``~/.ciaren/plugins``."""
    dirs: list[str] = []
    env = os.environ.get("CIAREN_PLUGINS_DIR")
    if env:
        dirs += [d for d in env.split(os.pathsep) if d]
    dirs.append(str(Path.home() / ".ciaren" / "plugins"))
    return dirs
