# SPDX-License-Identifier: Apache-2.0
"""The plugin manifest: a plugin's declared identity, compatibility, and the
permissions/capabilities it contributes.

Kept in the contract package (depends only on Pydantic + packaging) so tooling
and the loader validate manifests the same way. A manifest is advisory metadata —
the loader validates it before importing a plugin's entry point, so a malformed
or incompatible plugin is rejected without ever running its code.
"""

from __future__ import annotations

from typing import Any, Literal

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, Field, field_validator

from app.plugin_api.specs import BUILTIN_NODE_CATEGORIES, DEFAULT_PLUGIN_NODE_CATEGORY, Permission

#: Marketplace trust tiers (does not grant capabilities — purely informational).
TrustLevel = Literal["trusted", "verified", "community"]
LicenseKind = Literal["community", "commercial"]


class PluginUI(BaseModel):
    """UI contributions a plugin declares (advisory; the catalog is authoritative)."""

    nodes: list[str] = Field(default_factory=list)
    node_categories: dict[str, str] = Field(default_factory=dict, alias="nodeCategories")

    @field_validator("node_categories")
    @classmethod
    def _normalize_node_categories(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            node: category if category in BUILTIN_NODE_CATEGORIES else DEFAULT_PLUGIN_NODE_CATEGORY
            for node, category in value.items()
        }


class PluginManifest(BaseModel):
    """The validated contents of a plugin's manifest file."""

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    version: str = "0.0.0"
    publisher: str = "community"
    description: str = ""
    license: LicenseKind = "community"
    #: PEP 440 specifier set describing compatible Ciaren versions.
    ciaren: str = ">=0.1"
    #: Dotted entry point: ``module.path:ClassName``.
    entrypoint: str | None = None
    permissions: list[Permission] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    ui: PluginUI = Field(default_factory=PluginUI)
    dependencies: list[str] = Field(default_factory=list)
    license_required: bool = False
    trust: TrustLevel = "community"

    @field_validator("version")
    @classmethod
    def _valid_version(cls, v: str) -> str:
        try:
            Version(v)
        except InvalidVersion as exc:
            raise ValueError(f"invalid plugin version {v!r}: {exc}") from exc
        return v

    @field_validator("ciaren")
    @classmethod
    def _valid_specifier(cls, v: str) -> str:
        try:
            SpecifierSet(v)
        except InvalidSpecifier as exc:
            raise ValueError(f"invalid ciaren compatibility spec {v!r}: {exc}") from exc
        return v

    @field_validator("entrypoint")
    @classmethod
    def _valid_entrypoint(cls, v: str | None) -> str | None:
        if v is not None and v.count(":") != 1:
            raise ValueError(f"entrypoint must be 'module.path:Attribute', got {v!r}")
        return v

    def is_compatible_with(self, ciaren_version: str) -> bool:
        """Whether this plugin declares compatibility with ``ciaren_version``.
        Pre-releases are allowed so a plugin can target a dev build."""
        try:
            return Version(ciaren_version) in SpecifierSet(self.ciaren, prereleases=True)
        except (InvalidVersion, InvalidSpecifier):
            return False


def validate_manifest(data: dict[str, Any]) -> PluginManifest:
    """Validate a raw manifest mapping. Raises ``pydantic.ValidationError`` on
    malformed input."""
    return PluginManifest.model_validate(data)
