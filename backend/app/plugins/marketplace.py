# SPDX-License-Identifier: AGPL-3.0-only
"""The marketplace index format — how a catalog of installable plugins is
described, searched, and pointed at downloadable artifacts.

This is just a data contract (no hosting, no billing): an index is a JSON document
listing plugins with the metadata a client needs to show, verify, and fetch them.
Ciaren can read a local index file today; a hosted index is a future drop-in
that returns the same shape.
"""

from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.plugin_api import Permission
from app.plugin_api.specs import DEFAULT_PLUGIN_NODE_CATEGORY

#: The index schema major version this client understands. Minor additions
#: (new optional fields) parse fine; a new *major* means a shape change this
#: client cannot safely interpret, so it is refused rather than misread.
SUPPORTED_SCHEMA_MAJOR = 1


class MarketplaceIndexError(ValueError):
    """An index this client cannot use (malformed or incompatible schema version)."""


class MarketplaceEntry(BaseModel):
    """One plugin as advertised in a marketplace index."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    version: str = "0.0.0"
    publisher: str = "community"
    description: str = ""
    license: str = "community"
    trust: str = "community"
    capabilities: list[str] = Field(default_factory=list)
    permissions: list[Permission] = Field(default_factory=list)
    #: PEP 440 specifier of compatible Ciaren versions, from the manifest. Older
    #: indexes predate this field and default to "" (unknown).
    ciaren_spec: str = Field(default="", alias="ciarenSpec")
    #: pip requirements the plugin declares it needs (advisory, from the manifest).
    dependencies: list[str] = Field(default_factory=list)
    #: Node type ids the plugin declares for the editor palette, e.g. ``hello.greeting``.
    nodes: list[str] = Field(default_factory=list)
    #: Best-known palette category for each declared node id. Manifest-only packages
    #: do not import code, so unknown categories default to ``plugins`` until loaded.
    node_categories: dict[str, str] = Field(default_factory=dict, alias="nodeCategories")
    #: Where to download the ``.ciarenplugin`` artifact.
    download_url: str = Field(default="", alias="downloadUrl")
    #: Expected package digest (clients re-verify after download).
    digest: str = ""
    #: Which trusted key signed it (lookup into trusted keys).
    key_id: str = Field(default="", alias="keyId")
    license_required: bool = Field(default=False, alias="licenseRequired")


class MarketplaceIndex(BaseModel):
    """A versioned list of marketplace plugins."""

    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(default="1.0.0", alias="schemaVersion")
    plugins: list[MarketplaceEntry] = Field(default_factory=list)
    #: Plugin ids the catalog has withdrawn (e.g. malicious or broken releases).
    #: Independent of ``plugins``: an id stays revocable after it is delisted, so
    #: users who already installed it can still be warned. Clients refuse to
    #: install a revoked id and flag it where it is already installed.
    revoked: list[str] = Field(default_factory=list)

    def find(self, plugin_id: str) -> MarketplaceEntry | None:
        return next((p for p in self.plugins if p.id == plugin_id), None)

    def is_revoked(self, plugin_id: str) -> bool:
        return plugin_id in self.revoked

    def search(self, query: str) -> list[MarketplaceEntry]:
        """Case-insensitive match over id, name, description, and capabilities."""
        q = query.strip().lower()
        if not q:
            return list(self.plugins)
        return [
            p
            for p in self.plugins
            if q in p.id.lower()
            or q in p.name.lower()
            or q in p.description.lower()
            or any(q in c.lower() for c in p.capabilities)
        ]


def _check_schema(index: MarketplaceIndex) -> MarketplaceIndex:
    """Refuse an index whose schema major this client does not understand —
    misreading a future shape is worse than a clear error."""
    major = index.schema_version.split(".", 1)[0]
    if not major.isdigit() or int(major) != SUPPORTED_SCHEMA_MAJOR:
        raise MarketplaceIndexError(
            f"unsupported marketplace index schemaVersion {index.schema_version!r} "
            f"(this Ciaren understands major {SUPPORTED_SCHEMA_MAJOR})"
        )
    return index


def load_index(path: str | os.PathLike[str]) -> MarketplaceIndex:
    """Load a marketplace index from a local JSON file. Raises
    :class:`MarketplaceIndexError` on an incompatible schema version."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return _check_schema(MarketplaceIndex.model_validate(data))


def parse_index(data: dict[str, Any] | str) -> MarketplaceIndex:
    """Parse an index from an already-loaded mapping or JSON string (e.g. an HTTP
    response body, when a hosted index is added later). Raises
    :class:`MarketplaceIndexError` on an incompatible schema version."""
    if isinstance(data, str):
        data = json.loads(data)
    return _check_schema(MarketplaceIndex.model_validate(data))


# -- configured catalog source ------------------------------------------------


def configured_index_path() -> Path | None:
    """The local index file the "Explore" catalog reads, from
    ``settings.MARKETPLACE_INDEX``. When unset, Ciaren falls back to the
    bundled community catalog so first-time users can try the plugin install
    flow. Set the value to ``none``, ``off``, or ``disabled`` to disable Explore.

    A hosted index is a future drop-in: the same setting will accept an ``https://``
    URL once network fetch lands, parsed through :func:`parse_index` — the API
    contract and the frontend do not change.
    """
    from app.core.config import get_settings

    raw = get_settings().MARKETPLACE_INDEX.strip()
    if raw.lower() in {"none", "off", "disabled"}:
        return None
    if raw:
        return Path(raw).expanduser()
    bundled = resources.files("app.bundled_plugins").joinpath("marketplace.json")
    return Path(str(bundled))


def load_configured_index() -> MarketplaceIndex | None:
    """Read the configured catalog index, or ``None`` if unset/missing."""
    path = configured_index_path()
    if path is None or not path.is_file():
        return None
    return load_index(path)


def resolve_artifact_path(entry: MarketplaceEntry, index_path: Path) -> Path | None:
    """Local filesystem path to an entry's ``.ciarenplugin`` when ``download_url`` names
    a local file — absolute, ``file://``, or relative to the index file. Returns
    ``None`` for an ``http(s)`` URL (remote download is a future drop-in, not done
    here so the catalog stays fully local)."""
    url = entry.download_url.strip()
    if not url or url.startswith(("http://", "https://")):
        return None
    if url.startswith("file://"):
        url = url[len("file://") :]
    p = Path(url).expanduser()
    return p if p.is_absolute() else index_path.parent / p


# -- index authoring (`ciaren plugin index add`) ---------------------------


def build_entry(package_path: str | os.PathLike[str], *, download_url: str = "") -> MarketplaceEntry:
    """Build a marketplace entry from a ``.ciarenplugin``: its manifest metadata plus
    the package digest and signing key id, so a client can re-verify after fetch."""
    from app.plugins.package import compute_package_digest, read_manifest, read_signature

    manifest = read_manifest(package_path)
    sig = read_signature(package_path)
    return MarketplaceEntry(
        id=manifest.id,
        name=manifest.name,
        version=manifest.version,
        publisher=manifest.publisher,
        description=manifest.description,
        license=manifest.license,
        trust=manifest.trust,
        capabilities=list(manifest.capabilities),
        permissions=list(manifest.permissions),
        ciaren_spec=manifest.ciaren,
        dependencies=list(manifest.dependencies),
        nodes=list(manifest.ui.nodes),
        node_categories={
            node: manifest.ui.node_categories.get(node, DEFAULT_PLUGIN_NODE_CATEGORY) for node in manifest.ui.nodes
        },
        download_url=download_url,
        digest=compute_package_digest(package_path),
        key_id=(sig.key_id if sig else ""),
        license_required=manifest.license_required,
    )


def upsert_entry(index: MarketplaceIndex, entry: MarketplaceEntry) -> MarketplaceIndex:
    """Return a copy of ``index`` with ``entry`` added or replacing the same id."""
    kept = [e for e in index.plugins if e.id != entry.id]
    return MarketplaceIndex(schema_version=index.schema_version, plugins=[*kept, entry], revoked=index.revoked)


def add_to_index_file(
    index_path: str | os.PathLike[str],
    package_path: str | os.PathLike[str],
    *,
    download_url: str | None = None,
) -> MarketplaceEntry:
    """Add/replace ``package_path``'s entry in the index JSON at ``index_path``
    (created if absent), and return the entry. ``download_url`` defaults to the
    artifact's path **relative to the index file** so the catalog stays portable
    and local; pass an explicit URL to point at a hosted artifact instead."""
    idx_path = Path(index_path)
    index = load_index(idx_path) if idx_path.is_file() else MarketplaceIndex()
    if download_url is None:
        pkg = Path(package_path).resolve()
        try:
            download_url = pkg.relative_to(idx_path.resolve().parent).as_posix()
        except ValueError:
            download_url = str(pkg)  # artifact lives outside the index dir
    entry = build_entry(package_path, download_url=download_url)
    new_index = upsert_entry(index, entry)
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(new_index.model_dump_json(by_alias=True, indent=2), encoding="utf-8")
    return entry
