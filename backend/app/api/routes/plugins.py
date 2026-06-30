# SPDX-License-Identifier: AGPL-3.0-only
"""Installed-plugin introspection and management.

Lists what loaded, what was gated (disabled or pending permission approval), and
what failed. The management endpoints let the user enable/disable a plugin and
grant/revoke the permissions it requested — the *trust/UX boundary* from the
architecture plan. Changes take effect live: the registry is rebuilt so a granted
plugin's nodes appear in the catalog without a restart.
"""

import os
import tempfile
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.plugin_api import Hook, LicenseStatus, Permission
from app.plugins import (
    get_load_result,
    get_plugin_state,
    get_registry,
    reload_plugins,
)
from app.plugins.loader import GatedPlugin, LoadedPlugin, LoadResult
from app.plugins.state import PluginStateStore

router = APIRouter()

PluginStatus = Literal["loaded", "disabled", "needs_permissions"]


class PluginInfo(BaseModel):
    id: str
    name: str
    version: str = ""
    publisher: str = ""
    description: str = ""
    source: str
    status: PluginStatus
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
    #: Node type ids this plugin contributes to the editor palette.
    nodes: list[str] = Field(default_factory=list)
    #: Palette category/subgroup for each contributed node.
    node_categories: dict[str, str] = Field(default_factory=dict)


def _node_categories_for_loaded(loaded: LoadedPlugin) -> dict[str, str]:
    provider = loaded.metadata.id
    return {spec.id: spec.category for spec in get_registry().node_specs() if spec.provider == provider}


class PluginErrorInfo(BaseModel):
    source: str
    error: str


class PluginDiagnostics(BaseModel):
    loaded: list[PluginInfo]
    gated: list[PluginInfo]
    errors: list[PluginErrorInfo]


class PluginInstallResult(BaseModel):
    """Outcome of installing a ``.ffplugin``: the verification result plus the
    plugin's resulting status (it usually lands ``needs_permissions`` until the
    user approves it)."""

    plugin: PluginInfo
    #: Signature trust outcome: ``trusted`` | ``untrusted`` | ``unsigned`` | ``invalid``.
    outcome: str
    reason: str


class GrantRequest(BaseModel):
    #: Permissions to grant. Omit/empty to grant every permission the plugin requests.
    permissions: list[Permission] = Field(default_factory=list)


class RevokeRequest(BaseModel):
    permissions: list[Permission] = Field(default_factory=list)


def _loaded_info(loaded: LoadedPlugin, state: PluginStateStore) -> PluginInfo:
    meta = loaded.metadata
    return PluginInfo(
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
        nodes=list(loaded.manifest.ui.nodes) if loaded.manifest else [],
        node_categories=_node_categories_for_loaded(loaded),
    )


def _gated_info(gated: GatedPlugin, state: PluginStateStore) -> PluginInfo:
    status: PluginStatus = "disabled" if gated.reason == "disabled" else "needs_permissions"
    return PluginInfo(
        id=gated.plugin_id,
        name=gated.name,
        source=gated.source,
        status=status,
        permissions=list(gated.requested_permissions),
        granted_permissions=sorted(state.granted(gated.plugin_id), key=lambda p: p.value),
        missing_permissions=list(gated.missing_permissions),
        signature=state.signature(gated.plugin_id),
        nodes=list(gated.nodes),
        node_categories={node: gated.node_categories.get(node, "plugins") for node in gated.nodes},
    )


def _all_infos(result: LoadResult, state: PluginStateStore) -> list[PluginInfo]:
    return [_loaded_info(p, state) for p in result.loaded] + [_gated_info(g, state) for g in result.gated]


@router.get("", response_model=list[PluginInfo])
async def list_plugins() -> list[PluginInfo]:
    """Every discovered plugin (loaded + gated) with its status. The open-source
    core is not listed — it is always present."""
    return _all_infos(get_load_result(), get_plugin_state())


@router.get("/diagnostics", response_model=PluginDiagnostics)
async def plugin_diagnostics() -> PluginDiagnostics:
    """Loaded plugins, gated plugins, and any isolated load/validation errors."""
    result = get_load_result()
    state = get_plugin_state()
    return PluginDiagnostics(
        loaded=[_loaded_info(p, state) for p in result.loaded],
        gated=[_gated_info(g, state) for g in result.gated],
        errors=[PluginErrorInfo(source=e.source, error=e.error) for e in result.errors],
    )


def install_package_and_report(package_path: str, *, require_trusted: bool) -> PluginInstallResult:
    """Verify + install a local ``.ffplugin``, rebuild the registry live, and
    report the result. Shared by the upload endpoint and the marketplace install
    endpoint. Installation never imports plugin code — a freshly installed plugin
    stays gated (``needs_permissions``) until the user explicitly approves it, even
    when it declares no permissions, since approving means letting its code run."""
    from app.plugins.install import InstallError, install_ffplugin
    from app.plugins.package import PackageError

    try:
        result = install_ffplugin(package_path, require_trusted=require_trusted, force=True)
    except (InstallError, PackageError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Remember how it verified so the UI can show a trust badge for the installed
    # plugin (the package itself is gone after extraction).
    state = get_plugin_state()
    state.set_signature(result.plugin_id, result.verification.outcome)
    state.save()
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
    """Install an uploaded ``.ffplugin``. Refuses tampered/invalid packages always;
    refuses unsigned/untrusted ones when ``require_trusted`` (defaults to the
    ``REQUIRE_TRUSTED_PLUGINS`` setting)."""
    from app.core.config import get_settings

    settings = get_settings()
    must_trust = settings.REQUIRE_TRUSTED_PLUGINS if require_trusted is None else require_trusted
    limit = settings.max_upload_bytes

    # Stream the upload to disk in bounded chunks, aborting as soon as the size
    # limit is crossed — so an oversized package can't be buffered whole in memory
    # before it is rejected (a cheap DoS otherwise).
    tmp = tempfile.NamedTemporaryFile(suffix=".ffplugin", delete=False)
    try:
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > limit:
                raise HTTPException(status_code=413, detail="package exceeds the maximum upload size")
            tmp.write(chunk)
        tmp.close()
        return install_package_and_report(tmp.name, require_trusted=must_trust)
    finally:
        tmp.close()
        os.unlink(tmp.name)


@router.get("/{plugin_id}/license", response_model=LicenseStatus)
async def plugin_license(plugin_id: str) -> LicenseStatus:
    """The license status for a plugin, resolved through any registered license
    provider. A premium plugin registers a ``TokenLicenseProvider`` (backed by a
    locally-cached signed token); with no provider, a plugin reports licensed (the
    open-source default)."""
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
