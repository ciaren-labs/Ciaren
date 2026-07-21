# SPDX-License-Identifier: AGPL-3.0-only
"""The "Explore" plugin catalog — a read-only view over the configured marketplace
index, plus one-click install of an entry whose ``.ciarenplugin`` is available locally.

The catalog source is a local JSON file today (``settings.MARKETPLACE_INDEX``); a
hosted index is a drop-in later (same shape, with a network fetch added) and needs
no change to this contract or the frontend. Installing an entry reuses the exact
verified, permission-gated path as a hand-uploaded package.
"""

import asyncio
from pathlib import Path

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
    #: Derived by *verifying* the artifact against the trusted keys — never echoed
    #: from the index/manifest, which are publisher-controlled and could otherwise
    #: claim a "trusted" badge for anything. ``official`` when the valid signature
    #: comes from a publisher key pinned into the app (first-party); ``trusted``
    #: for any other trusted key; everything else (unsigned, untrusted key, or
    #: remote/unverifiable) is ``community``.
    trust: str = "community"
    capabilities: list[str] = Field(default_factory=list)
    permissions: list[Permission] = Field(default_factory=list)
    #: PEP 440 specifier of compatible Ciaren versions ("" for pre-existing indexes).
    ciaren_spec: str = ""
    #: pip requirements the plugin declares it needs (advisory).
    dependencies: list[str] = Field(default_factory=list)
    nodes: list[str] = Field(default_factory=list)
    node_categories: dict[str, str] = Field(default_factory=dict)
    license_required: bool = False
    #: A plugin with this id is already installed (loaded or gated).
    installed: bool = False
    #: The installed plugin's version ("" when not installed or unknown).
    installed_version: str = ""
    #: The catalog offers a strictly newer version than the one installed.
    update_available: bool = False
    #: The catalog has withdrawn this plugin (installing it is refused).
    revoked: bool = False
    #: The entry's artifact is available locally for one-click install (vs. a
    #: remote-only entry that must be downloaded/installed manually for now).
    installable: bool = False


class MarketplaceCatalog(BaseModel):
    #: False when no index is configured — the UI shows how to enable the catalog.
    configured: bool
    plugins: list[MarketplaceEntryInfo] = Field(default_factory=list)
    #: Installed plugin ids the catalog has revoked — surfaced prominently so the
    #: user can uninstall them (a revoked id may already be delisted from
    #: ``plugins``, so this cannot be derived from the entries alone).
    revoked_installed: list[str] = Field(default_factory=list)


def _installed_versions() -> dict[str, str]:
    """Installed plugin ids (loaded or gated) mapped to their version ("" when
    unknown, e.g. a gated plugin without a manifest)."""
    result = get_load_result()
    versions = {p.metadata.id: p.metadata.version for p in result.loaded}
    for g in result.gated:
        versions[g.plugin_id] = g.manifest.version if g.manifest else ""
    return versions


def _update_available(catalog_version: str, installed_version: str) -> bool:
    """Whether the catalog's version is strictly newer, by PEP 440 ordering.
    Unknown/malformed versions never signal an update."""
    from packaging.version import InvalidVersion, Version

    if not catalog_version or not installed_version:
        return False
    try:
        return Version(catalog_version) > Version(installed_version)
    except InvalidVersion:
        return False


def _derived_trust(entry: marketplace.MarketplaceEntry, index_path: Path, *, trusted_index: bool) -> str:
    """The trust tier we can actually stand behind for a catalog entry: verify the
    local artifact's signature against the trusted keys and report ``official``
    (first-party, signed by a key pinned into the app) or ``trusted`` only on a
    positive result. An entry we cannot verify (remote-only, missing file,
    unreadable) is ``community`` no matter what the index claims."""
    from app.plugins.package import PackageError, verify_package

    artifact = marketplace.resolve_artifact_path(entry, index_path, trusted=trusted_index)
    if artifact is None or not artifact.is_file():
        return "community"
    try:
        result = verify_package(artifact)
    except (PackageError, OSError):
        return "community"
    if result.official:
        return "official"
    return "trusted" if result.outcome == "trusted" else "community"


def _load_configured_index_or_400() -> marketplace.MarketplaceIndex | None:
    """The configured index, ``None`` when unconfigured/missing, or a clean 400
    when the file exists but cannot be used (bad JSON, incompatible schema) —
    a misconfigured catalog should read as such, not as a server crash."""
    try:
        return marketplace.load_configured_index()
    except (marketplace.MarketplaceIndexError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"the configured marketplace index is unusable: {exc}") from exc


@router.get("", response_model=MarketplaceCatalog)
async def list_marketplace() -> MarketplaceCatalog:
    """The catalog entries from the configured index, each annotated with whether
    it is already installed, whether an update is available, and whether its
    artifact can be installed locally."""
    index = _load_configured_index_or_400()
    index_path = marketplace.configured_index_path()
    if index is None or index_path is None:
        return MarketplaceCatalog(configured=False)
    installed = _installed_versions()
    # Whether the index source itself is trusted with local artifact paths (a
    # local file today; a future hosted index gets strict confined resolution).
    trusted_index = marketplace.configured_index_is_trusted()

    # _derived_trust signature-verifies each entry's artifact zip — file IO +
    # crypto per plugin — so the catalog build runs in a worker thread instead
    # of stalling the event loop. It only reads files and local dicts.
    def _build_entries() -> list[MarketplaceEntryInfo]:
        return [
            MarketplaceEntryInfo(
                id=e.id,
                name=e.name,
                version=e.version,
                publisher=e.publisher,
                description=e.description,
                license=e.license,
                trust=_derived_trust(e, index_path, trusted_index=trusted_index),
                capabilities=list(e.capabilities),
                permissions=list(e.permissions),
                ciaren_spec=e.ciaren_spec,
                dependencies=list(e.dependencies),
                nodes=list(e.nodes),
                node_categories=dict(e.node_categories),
                license_required=e.license_required,
                installed=e.id in installed,
                installed_version=installed.get(e.id, ""),
                update_available=_update_available(e.version, installed.get(e.id, "")),
                revoked=index.is_revoked(e.id),
                installable=bool(
                    (p := marketplace.resolve_artifact_path(e, index_path, trusted=trusted_index)) and p.is_file()
                ),
            )
            for e in index.plugins
        ]

    entries = await asyncio.to_thread(_build_entries)
    return MarketplaceCatalog(
        configured=True,
        plugins=entries,
        revoked_installed=sorted(set(index.revoked) & set(installed)),
    )


@router.post("/{plugin_id}/install", response_model=PluginInstallResult)
async def install_from_marketplace(plugin_id: str) -> PluginInstallResult:
    """Install a catalog entry from its locally-available artifact. Re-verifies the
    advertised digest before install; remote-only entries are refused for now
    (network download is a future drop-in).

    Also serves **updates**: installing over an existing version force-replaces it,
    and the TOFU signer pin withdraws approval if the publisher's key changed."""
    from app.core.config import get_settings
    from app.plugins.package import compute_package_digest

    index = _load_configured_index_or_400()
    index_path = marketplace.configured_index_path()
    if index is None or index_path is None:
        raise HTTPException(status_code=404, detail="no marketplace index is configured")
    if index.is_revoked(plugin_id):
        raise HTTPException(
            status_code=400,
            detail=f"{plugin_id!r} has been revoked by the catalog and cannot be installed",
        )
    entry = index.find(plugin_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"{plugin_id!r} is not in the catalog")
    artifact = marketplace.resolve_artifact_path(entry, index_path, trusted=marketplace.configured_index_is_trusted())
    if artifact is None:
        raise HTTPException(
            status_code=400,
            detail="this entry's artifact is not available as a safe local file "
            "(remote download is not supported yet, and an untrusted index may "
            "only reference artifacts inside its own directory)",
        )
    if not artifact.is_file():
        raise HTTPException(status_code=404, detail=f"artifact for {plugin_id!r} not found at {artifact}")
    # The digest is what binds the catalog entry to the artifact bytes — without
    # it a swapped artifact would install silently, so its absence is an error in
    # the index, not a reason to skip verification. (`ciaren plugin index add`
    # always records one.)
    if not entry.digest:
        raise HTTPException(
            status_code=400,
            detail=f"catalog entry for {plugin_id!r} has no digest; refusing to install an unverifiable artifact",
        )
    if await asyncio.to_thread(compute_package_digest, artifact) != entry.digest:
        raise HTTPException(status_code=400, detail="artifact digest does not match the catalog entry")
    return install_package_and_report(str(artifact), require_trusted=get_settings().REQUIRE_TRUSTED_PLUGINS)
