# SPDX-License-Identifier: AGPL-3.0-only
"""The "Explore" plugin catalog — a read-only view over the configured marketplace
index, plus one-click install of an entry whose ``.ffplugin`` is available locally.

The catalog source is a local JSON file today (``settings.MARKETPLACE_INDEX``); a
hosted index is a drop-in later (same shape, with a network fetch added) and needs
no change to this contract or the frontend. Installing an entry reuses the exact
verified, permission-gated path as a hand-uploaded package.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.routes.plugins import PluginInstallResult, install_package_and_report
from app.plugin_api import Permission
from app.plugins import get_load_result, marketplace

router = APIRouter()


class MarketplaceEntryInfo(BaseModel):
    id: str
    name: str
    version: str = ""
    publisher: str = ""
    description: str = ""
    license: str = "community"
    trust: str = "community"
    capabilities: list[str] = Field(default_factory=list)
    permissions: list[Permission] = Field(default_factory=list)
    nodes: list[str] = Field(default_factory=list)
    node_categories: dict[str, str] = Field(default_factory=dict)
    license_required: bool = False
    #: A plugin with this id is already installed (loaded or gated).
    installed: bool = False
    #: The entry's artifact is available locally for one-click install (vs. a
    #: remote-only entry that must be downloaded/installed manually for now).
    installable: bool = False


class MarketplaceCatalog(BaseModel):
    #: False when no index is configured — the UI shows how to enable the catalog.
    configured: bool
    plugins: list[MarketplaceEntryInfo] = Field(default_factory=list)


def _installed_ids() -> set[str]:
    result = get_load_result()
    return {p.metadata.id for p in result.loaded} | {g.plugin_id for g in result.gated}


@router.get("", response_model=MarketplaceCatalog)
async def list_marketplace() -> MarketplaceCatalog:
    """The catalog entries from the configured index, each annotated with whether
    it is already installed and whether its artifact can be installed locally."""
    index = marketplace.load_configured_index()
    index_path = marketplace.configured_index_path()
    if index is None or index_path is None:
        return MarketplaceCatalog(configured=False)
    installed = _installed_ids()
    entries = [
        MarketplaceEntryInfo(
            id=e.id,
            name=e.name,
            version=e.version,
            publisher=e.publisher,
            description=e.description,
            license=e.license,
            trust=e.trust,
            capabilities=list(e.capabilities),
            permissions=list(e.permissions),
            nodes=list(e.nodes),
            node_categories=dict(e.node_categories),
            license_required=e.license_required,
            installed=e.id in installed,
            installable=bool((p := marketplace.resolve_artifact_path(e, index_path)) and p.is_file()),
        )
        for e in index.plugins
    ]
    return MarketplaceCatalog(configured=True, plugins=entries)


@router.post("/{plugin_id}/install", response_model=PluginInstallResult)
async def install_from_marketplace(plugin_id: str) -> PluginInstallResult:
    """Install a catalog entry from its locally-available artifact. Re-verifies the
    advertised digest before install; remote-only entries are refused for now
    (network download is a future drop-in)."""
    from app.core.config import get_settings
    from app.plugins.package import compute_package_digest

    index = marketplace.load_configured_index()
    index_path = marketplace.configured_index_path()
    if index is None or index_path is None:
        raise HTTPException(status_code=404, detail="no marketplace index is configured")
    entry = index.find(plugin_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"{plugin_id!r} is not in the catalog")
    artifact = marketplace.resolve_artifact_path(entry, index_path)
    if artifact is None:
        raise HTTPException(
            status_code=400,
            detail="this entry must be downloaded and installed manually (remote download not supported yet)",
        )
    if not artifact.is_file():
        raise HTTPException(status_code=404, detail=f"artifact for {plugin_id!r} not found at {artifact}")
    if entry.digest and compute_package_digest(artifact) != entry.digest:
        raise HTTPException(status_code=400, detail="artifact digest does not match the catalog entry")
    return install_package_and_report(str(artifact), require_trusted=get_settings().REQUIRE_TRUSTED_PLUGINS)
