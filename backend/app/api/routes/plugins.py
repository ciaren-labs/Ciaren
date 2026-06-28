"""Installed-plugin introspection: what loaded and what failed.

Read-only in Phase 1d — install/enable/disable land in later phases. The
diagnostics endpoint surfaces isolated load errors so a broken plugin is visible
without crashing the app.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.plugin_api import Permission
from app.plugins import get_load_result
from app.plugins.loader import LoadedPlugin

router = APIRouter()


class PluginInfo(BaseModel):
    id: str
    name: str
    version: str
    publisher: str
    description: str
    source: str
    capabilities: list[str]
    permissions: list[Permission]


class PluginErrorInfo(BaseModel):
    source: str
    error: str


class PluginDiagnostics(BaseModel):
    loaded: list[PluginInfo]
    errors: list[PluginErrorInfo]


def _plugin_info(loaded: LoadedPlugin) -> PluginInfo:
    meta = loaded.metadata
    return PluginInfo(
        id=meta.id,
        name=meta.name,
        version=meta.version,
        publisher=meta.publisher,
        description=meta.description,
        source=loaded.source,
        capabilities=list(meta.capabilities),
        permissions=list(meta.permissions),
    )


@router.get("", response_model=list[PluginInfo])
async def list_plugins() -> list[PluginInfo]:
    """Plugins that loaded successfully (the open-source core is not listed —
    it is always present)."""
    return [_plugin_info(p) for p in get_load_result().loaded]


@router.get("/diagnostics", response_model=PluginDiagnostics)
async def plugin_diagnostics() -> PluginDiagnostics:
    """Loaded plugins plus any isolated load/validation errors."""
    result = get_load_result()
    return PluginDiagnostics(
        loaded=[_plugin_info(p) for p in result.loaded],
        errors=[PluginErrorInfo(source=e.source, error=e.error) for e in result.errors],
    )
