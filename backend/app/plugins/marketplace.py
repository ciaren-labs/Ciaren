"""The marketplace index format — how a catalog of installable plugins is
described, searched, and pointed at downloadable artifacts.

This is just a data contract (no hosting, no billing): an index is a JSON document
listing plugins with the metadata a client needs to show, verify, and fetch them.
FlowFrame can read a local index file today; a hosted index is a future drop-in
that returns the same shape.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.plugin_api import Permission


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
    #: Where to download the ``.ffplugin`` artifact.
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

    def find(self, plugin_id: str) -> MarketplaceEntry | None:
        return next((p for p in self.plugins if p.id == plugin_id), None)

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


def load_index(path: str | os.PathLike[str]) -> MarketplaceIndex:
    """Load a marketplace index from a local JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return MarketplaceIndex.model_validate(data)


def parse_index(data: dict[str, Any] | str) -> MarketplaceIndex:
    """Parse an index from an already-loaded mapping or JSON string (e.g. an HTTP
    response body, when a hosted index is added later)."""
    if isinstance(data, str):
        data = json.loads(data)
    return MarketplaceIndex.model_validate(data)
