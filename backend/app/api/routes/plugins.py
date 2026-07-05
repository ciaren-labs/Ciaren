# SPDX-License-Identifier: AGPL-3.0-only
"""Installed-plugin introspection and management.

Lists what loaded, what was gated (disabled or pending permission approval), and
what failed. The management endpoints let the user enable/disable a plugin and
grant/revoke the permissions it requested — the *trust/UX boundary* from the
architecture plan. Changes take effect live: the registry is rebuilt so a granted
plugin's nodes appear in the catalog without a restart.
"""

import asyncio
import os
import tempfile
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.plugin_api import PLUGIN_API_VERSION, Hook, LicenseStatus, Permission, PluginManifest
from app.plugins import (
    get_load_result,
    get_plugin_state,
    get_registry,
    reload_plugins,
)
from app.plugins.licensing import LicenseToken
from app.plugins.loader import GatedPlugin, LoadedPlugin, LoadResult
from app.plugins.state import PluginStateStore

router = APIRouter()

PluginStatus = Literal["loaded", "disabled", "needs_permissions", "needs_license"]


class PluginInfo(BaseModel):
    id: str
    name: str
    version: str = ""
    publisher: str = ""
    description: str = ""
    source: str
    status: PluginStatus
    #: Human-readable context for a gated status (e.g. why the license is invalid).
    status_detail: str = ""
    capabilities: list[str] = Field(default_factory=list)
    #: Permissions the plugin requests in its manifest/metadata.
    permissions: list[Permission] = Field(default_factory=list)
    #: Permissions the user has granted it so far.
    granted_permissions: list[Permission] = Field(default_factory=list)
    #: Requested-but-not-yet-granted permissions (non-empty ⇒ needs approval).
    missing_permissions: list[Permission] = Field(default_factory=list)
    #: How the package verified at install time: ``trusted`` | ``untrusted`` |
    #: ``unsigned`` | ``invalid`` | "" (unknown, e.g. a hand-dropped directory).
    signature: str = ""
    #: First-party: verified as ``trusted`` under a publisher key pinned into the
    #: app itself (not merely a user-added trusted key). Derived, never declared.
    official: bool = False
    #: Node type ids this plugin contributes to the editor palette.
    nodes: list[str] = Field(default_factory=list)
    #: Palette category/subgroup for each contributed node.
    node_categories: dict[str, str] = Field(default_factory=dict)
    #: Connector ids this plugin contributes (empty for gated plugins — their
    #: code never ran, so only the manifest's advisory data is known).
    connectors: list[str] = Field(default_factory=list)
    #: Trainable model-type ids this plugin contributes to the ML catalog.
    model_types: list[str] = Field(default_factory=list)
    #: True when the plugin lives in the managed install dir and can be removed via
    #: DELETE. False for dev-dir (``CIAREN_PLUGINS_DIR``) or entry-point plugins,
    #: which the UI can only disable, not uninstall.
    uninstallable: bool = False
    #: Manifest license kind: ``community`` | ``commercial`` | "" (no manifest).
    license: str = ""
    #: Declared marketplace trust tier: ``trusted`` | ``verified`` | ``community``
    #: | "" (no manifest). Informational only — it grants nothing.
    trust: str = ""
    #: PEP 440 specifier of compatible Ciaren versions (e.g. ``>=0.1``).
    ciaren_spec: str = ""
    #: Plugin-contract version the plugin targets (e.g. ``1.1``), checked against
    #: the backend's ``plugin_api_version`` at load. "" when the plugin has no
    #: manifest (entry-point packages).
    api_version: str = ""
    #: pip requirements the plugin declares it needs.
    dependencies: list[str] = Field(default_factory=list)
    #: Dotted entry point (``module.path:ClassName``) from the manifest.
    entrypoint: str = ""
    #: Managed install directory on disk, "" when the plugin lives elsewhere
    #: (dev dir or entry-point package).
    install_path: str = ""


def _node_categories_for_loaded(loaded: LoadedPlugin) -> dict[str, str]:
    provider = loaded.metadata.id
    return {spec.id: spec.category for spec in get_registry().node_specs() if spec.provider == provider}


def _connectors_for_loaded(plugin_id: str) -> list[str]:
    return [spec.id for spec in get_registry().connector_specs() if spec.provider == plugin_id]


def _model_types_for_loaded(plugin_id: str) -> list[str]:
    return [spec.id for spec in get_registry().model_type_specs() if spec.provider == plugin_id]


def _install_path(plugin_id: str) -> str:
    """The managed install dir on disk, or "" for dev-dir / entry-point plugins."""
    from app.plugins.install import installed_location

    location = installed_location(plugin_id)
    return str(location) if location is not None else ""


def _is_official(plugin_id: str, state: PluginStateStore) -> bool:
    """First-party check from the install-time record: verified ``trusted`` and
    the pinned TOFU key id is one of the app's own publisher keys."""
    from app.plugins.package import is_official_key

    entry = state.entry(plugin_id)
    return entry is not None and entry.signature == "trusted" and is_official_key(entry.key_id)


def _apply_manifest(info: PluginInfo, manifest: PluginManifest | None) -> PluginInfo:
    """Copy advisory manifest fields onto ``info`` (left empty without one —
    entry-point packages may not ship a manifest)."""
    if manifest is not None:
        info.license = manifest.license
        info.trust = manifest.trust
        info.ciaren_spec = manifest.ciaren
        info.api_version = manifest.api_version
        info.dependencies = list(manifest.dependencies)
        info.entrypoint = manifest.entrypoint or ""
    return info


class PluginErrorInfo(BaseModel):
    source: str
    error: str


class PluginDiagnostics(BaseModel):
    loaded: list[PluginInfo]
    gated: list[PluginInfo]
    errors: list[PluginErrorInfo]
    #: The plugin-contract version this backend provides. A plugin whose manifest
    #: ``api_version`` is contract-incompatible with this is rejected at load and
    #: appears in ``errors`` — surfacing the backend's version here makes that
    #: mismatch actionable in the UI.
    plugin_api_version: str = PLUGIN_API_VERSION
    #: Runtime permission-enforcement mode for plugin code: ``off`` (advisory only),
    #: ``warn`` (log ungranted actions), or ``enforce`` (block them). Surfaced so the
    #: UI can show whether this opt-in hardening is active.
    permission_enforcement: str = "off"


class PluginInstallResult(BaseModel):
    """Outcome of installing a ``.ciarenplugin``: the verification result plus the
    plugin's resulting status (it usually lands ``needs_permissions`` until the
    user approves it)."""

    plugin: PluginInfo
    #: Signature trust outcome: ``trusted`` | ``untrusted`` | ``unsigned`` | ``invalid``.
    outcome: str
    reason: str


class PluginUninstallResult(BaseModel):
    plugin_id: str
    #: True if a managed install directory was actually deleted. False means the
    #: plugin was discovered from elsewhere (a dev dir or an entry-point package)
    #: and has no managed files to remove — its persisted state is still forgotten.
    removed: bool


class GrantRequest(BaseModel):
    #: Permissions to grant. Omit/empty to grant every permission the plugin requests.
    permissions: list[Permission] = Field(default_factory=list)


class RevokeRequest(BaseModel):
    permissions: list[Permission] = Field(default_factory=list)


def _loaded_info(loaded: LoadedPlugin, state: PluginStateStore) -> PluginInfo:
    meta = loaded.metadata
    install_path = _install_path(meta.id)
    info = PluginInfo(
        id=meta.id,
        name=meta.name,
        version=meta.version,
        publisher=meta.publisher,
        description=meta.description,
        source=loaded.source,
        status="loaded",
        capabilities=list(meta.capabilities),
        permissions=list(meta.permissions),
        granted_permissions=sorted(state.granted(meta.id), key=lambda p: p.value),
        signature=state.signature(meta.id),
        official=_is_official(meta.id, state),
        nodes=list(loaded.manifest.ui.nodes) if loaded.manifest else [],
        node_categories=_node_categories_for_loaded(loaded),
        connectors=_connectors_for_loaded(meta.id),
        model_types=_model_types_for_loaded(meta.id),
        uninstallable=bool(install_path),
        install_path=install_path,
    )
    return _apply_manifest(info, loaded.manifest)


def _gated_info(gated: GatedPlugin, state: PluginStateStore) -> PluginInfo:
    status: PluginStatus
    if gated.reason == "disabled":
        status = "disabled"
    elif gated.reason == "needs_license":
        status = "needs_license"
    else:
        status = "needs_permissions"
    # A gated plugin's code never ran, but its validated manifest is available —
    # surface identity from there so the approval decision has context.
    manifest = gated.manifest
    install_path = _install_path(gated.plugin_id)
    info = PluginInfo(
        id=gated.plugin_id,
        name=gated.name,
        version=manifest.version if manifest else "",
        publisher=manifest.publisher if manifest else "",
        description=manifest.description if manifest else "",
        source=gated.source,
        status=status,
        status_detail=gated.detail,
        capabilities=list(manifest.capabilities) if manifest else [],
        permissions=list(gated.requested_permissions),
        granted_permissions=sorted(state.granted(gated.plugin_id), key=lambda p: p.value),
        missing_permissions=list(gated.missing_permissions),
        signature=state.signature(gated.plugin_id),
        official=_is_official(gated.plugin_id, state),
        nodes=list(gated.nodes),
        node_categories={node: gated.node_categories.get(node, "plugins") for node in gated.nodes},
        uninstallable=bool(install_path),
        install_path=install_path,
    )
    return _apply_manifest(info, manifest)


def _all_infos(result: LoadResult, state: PluginStateStore) -> list[PluginInfo]:
    return [_loaded_info(p, state) for p in result.loaded] + [_gated_info(g, state) for g in result.gated]


@router.get("", response_model=list[PluginInfo])
async def list_plugins() -> list[PluginInfo]:
    """Every discovered plugin (loaded + gated) with its status. The open core
    core is not listed — it is always present."""
    return _all_infos(get_load_result(), get_plugin_state())


@router.get("/diagnostics", response_model=PluginDiagnostics)
async def plugin_diagnostics() -> PluginDiagnostics:
    """Loaded plugins, gated plugins, and any isolated load/validation errors."""
    from app.plugins.permission_audit import enforcement_mode

    result = get_load_result()
    state = get_plugin_state()
    return PluginDiagnostics(
        loaded=[_loaded_info(p, state) for p in result.loaded],
        gated=[_gated_info(g, state) for g in result.gated],
        errors=[PluginErrorInfo(source=e.source, error=e.error) for e in result.errors],
        permission_enforcement=enforcement_mode(),
    )


def install_package_and_report(package_path: str, *, require_trusted: bool) -> PluginInstallResult:
    """Verify + install a local ``.ciarenplugin``, rebuild the registry live, and
    report the result. Shared by the upload endpoint and the marketplace install
    endpoint. Installation never imports plugin code — a freshly installed plugin
    stays gated (``needs_permissions``) until the user explicitly approves it, even
    when it declares no permissions, since approving means letting its code run."""
    from app.plugins.install import InstallError, install_ciarenplugin
    from app.plugins.package import PackageError

    try:
        # install_ciarenplugin records the verification outcome + signing key in the
        # plugin state (trust badge, TOFU pin) and withdraws approval if the signer
        # changed or the trust level dropped since the previous install.
        result = install_ciarenplugin(package_path, require_trusted=require_trusted, force=True)
    except (InstallError, PackageError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    reload_plugins()
    return PluginInstallResult(
        plugin=_find_info(result.plugin_id),
        outcome=result.verification.outcome,
        reason=result.verification.reason,
    )


@router.post("/install", response_model=PluginInstallResult)
async def install_plugin(
    file: UploadFile = File(...),
    require_trusted: bool | None = Form(default=None),
) -> PluginInstallResult:
    """Install an uploaded ``.ciarenplugin``. Refuses tampered/invalid packages always;
    refuses unsigned/untrusted ones when ``require_trusted`` (defaults to the
    ``REQUIRE_TRUSTED_PLUGINS`` setting)."""
    from app.core.config import get_settings

    settings = get_settings()
    must_trust = settings.REQUIRE_TRUSTED_PLUGINS if require_trusted is None else require_trusted
    limit = settings.max_upload_bytes

    # Stream the upload to disk in bounded chunks, aborting as soon as the size
    # limit is crossed — so an oversized package can't be buffered whole in memory
    # before it is rejected (a cheap DoS otherwise).
    tmp = tempfile.NamedTemporaryFile(suffix=".ciarenplugin", delete=False)
    try:
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > limit:
                raise HTTPException(status_code=413, detail="package exceeds the maximum upload size")
            # Disk write off the loop; install/reload below deliberately stay ON
            # the loop so the plugin-registry swap remains atomic wrt requests.
            await asyncio.to_thread(tmp.write, chunk)
        tmp.close()
        return install_package_and_report(tmp.name, require_trusted=must_trust)
    finally:
        tmp.close()
        os.unlink(tmp.name)


@router.get("/{plugin_id}/license", response_model=LicenseStatus)
async def plugin_license(plugin_id: str) -> LicenseStatus:
    """The license status for a plugin, resolved through the registered license
    providers (the core registers one per configured issuer key; a premium plugin
    may register its own). With no provider, a plugin reports licensed (the
    open-core default)."""
    return get_registry().validate_license(plugin_id)


@router.post("/{plugin_id}/license", response_model=LicenseStatus)
async def activate_license(plugin_id: str, token: LicenseToken) -> LicenseStatus:
    """Activate a license: store the pasted/downloaded token in the local cache
    and reload plugins so a ``needs_license`` plugin loads immediately.

    A token is only ever saved once something can vouch for it: it is vetted
    against the configured issuer keys *before* saving, and when no issuer keys
    exist it is accepted only if a plugin-registered provider validates it
    (rolling the cache back otherwise) — so pasting a bad token can never
    clobber a working one, and activation never reports a false success. The
    plugin does not have to be installed yet — activating first and installing
    after is fine (the token waits in the cache)."""
    from app.plugins.licensing import LicenseCache, check_token_against_issuers

    if token.plugin_id != plugin_id:
        raise HTTPException(
            status_code=400,
            detail=f"token is for plugin {token.plugin_id!r}, not {plugin_id!r}",
        )
    vetted = check_token_against_issuers(token)
    if vetted is not None and not vetted.valid:
        raise HTTPException(status_code=400, detail=f"license token rejected: {vetted.reason}")
    cache = LicenseCache()
    if vetted is None:
        # No issuer keys configured, so the core can't judge the token itself.
        # Without any registered provider nothing else can either — refuse rather
        # than cache a token nobody can validate (a "success" here would be a lie:
        # a license_required plugin would still stay gated).
        if not get_registry().has_license_provider():
            raise HTTPException(
                status_code=400,
                detail=(
                    "no license provider can validate this token — configure a marketplace "
                    "license issuer key (CIAREN_MARKETPLACE_LICENSE_ISSUER_KEYS)"
                ),
            )
        # A vendor provider (registered by another loaded plugin) reads the cache,
        # so it can only judge the token once saved. Save, ask, and roll back the
        # previous cache state if the paste doesn't validate.
        previous = cache.load(plugin_id)
        cache.save(token)
        reload_plugins()
        status = get_registry().validate_license(plugin_id)
        if not status.valid:
            if previous is not None:
                cache.save(previous)
            else:
                cache.delete(plugin_id)
            reload_plugins()
            raise HTTPException(status_code=400, detail=f"license token rejected: {status.reason}")
        return status
    cache.save(token)
    reload_plugins()
    return get_registry().validate_license(plugin_id)


@router.delete("/{plugin_id}/license", response_model=LicenseStatus)
async def remove_license(plugin_id: str) -> LicenseStatus:
    """Remove the cached license token for a plugin (e.g. to move a seat to
    another machine). The plugin drops back to ``needs_license`` on reload."""
    from app.plugins.licensing import LicenseCache

    if not LicenseCache().delete(plugin_id):
        raise HTTPException(status_code=404, detail=f"no cached license token for {plugin_id!r}")
    reload_plugins()
    return get_registry().validate_license(plugin_id)


def _find_info(plugin_id: str) -> PluginInfo:
    info = next((i for i in _all_infos(get_load_result(), get_plugin_state()) if i.id == plugin_id), None)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Plugin {plugin_id!r} not found")
    return info


def _requested_permissions(plugin_id: str) -> list[Permission]:
    info = next((i for i in _all_infos(get_load_result(), get_plugin_state()) if i.id == plugin_id), None)
    return list(info.permissions) if info else []


def _emit_lifecycle(hook: Hook, plugin_id: str) -> None:
    try:
        get_registry().events.emit(hook, plugin_id=plugin_id)
    except Exception:  # noqa: BLE001 — lifecycle hooks must never break management
        pass


@router.post("/{plugin_id}/enable", response_model=PluginInfo)
async def enable_plugin(plugin_id: str) -> PluginInfo:
    """Enable a plugin and approve running its code. If it still requests ungranted
    permissions it moves to ``needs_permissions`` rather than ``loaded``.

    Enabling is an explicit opt-in: the plugin's Python runs with the user's full
    account access (it is not sandboxed), so this also marks it approved."""
    _find_info(plugin_id)  # 404 if unknown
    state = get_plugin_state()
    state.set_enabled(plugin_id, True)
    state.set_approved(plugin_id, True)
    state.save()
    reload_plugins()
    _emit_lifecycle(Hook.plugin_enabled, plugin_id)
    return _find_info(plugin_id)


@router.post("/{plugin_id}/disable", response_model=PluginInfo)
async def disable_plugin(plugin_id: str) -> PluginInfo:
    """Disable a plugin so its code is not loaded on subsequent startups."""
    _find_info(plugin_id)
    state = get_plugin_state()
    state.set_enabled(plugin_id, False)
    state.save()
    reload_plugins()
    _emit_lifecycle(Hook.plugin_disabled, plugin_id)
    return _find_info(plugin_id)


@router.post("/{plugin_id}/grant", response_model=PluginInfo)
async def grant_permissions(plugin_id: str, body: GrantRequest) -> PluginInfo:
    """Grant permissions to a plugin. With an empty list, grants everything the
    plugin requests (one-click "approve"). Loads the plugin if it was pending."""
    _find_info(plugin_id)
    perms = body.permissions or _requested_permissions(plugin_id)
    state = get_plugin_state()
    state.grant(plugin_id, perms)
    state.save()
    reload_plugins()
    return _find_info(plugin_id)


@router.post("/{plugin_id}/revoke", response_model=PluginInfo)
async def revoke_permissions(plugin_id: str, body: RevokeRequest) -> PluginInfo:
    """Revoke permissions from a plugin. If it then has ungranted required
    permissions it becomes pending (its code stops loading)."""
    _find_info(plugin_id)
    state = get_plugin_state()
    state.revoke(plugin_id, body.permissions)
    state.save()
    reload_plugins()
    return _find_info(plugin_id)


@router.delete("/{plugin_id}", response_model=PluginUninstallResult)
async def uninstall_plugin(plugin_id: str) -> PluginUninstallResult:
    """Uninstall a plugin: delete its managed install directory and forget its
    persisted state (enable/approval/grants). The registry is rebuilt so its nodes
    leave the catalog live.

    Only removes files for a plugin installed into the managed dir. A dev-dir
    (``CIAREN_PLUGINS_DIR``) or entry-point plugin has no managed files, so
    ``removed`` is False — disable it or remove the package instead."""
    from app.plugins.install import uninstall_plugin as _uninstall

    _find_info(plugin_id)  # 404 if unknown (must resolve before we delete it)
    removed = _uninstall(plugin_id)
    reload_plugins()
    return PluginUninstallResult(plugin_id=plugin_id, removed=removed)
