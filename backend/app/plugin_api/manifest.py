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
#: A manifest's declared tier is advisory and never surfaced as a badge; what the
#: UI shows is *derived*: ``trusted`` only when the artifact's signature verifies
#: against a trusted publisher key. ``verified`` is reserved for
#: marketplace-verified publisher identity — assigned by the hosted marketplace
#: when it launches, never derivable locally. Everything else is ``community``.
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
    #: PEP 440 specifier set describing compatible Ciaren *app* versions.
    ciaren: str = ">=0.1"
    #: The plugin *contract* version this plugin was built against — the value of
    #: ``PLUGIN_API_VERSION`` at build time, as ``MAJOR.MINOR``. Independent of both
    #: the plugin's own ``version`` and the app's ``ciaren`` compatibility. Compared
    #: against the running backend's contract version at load: the major must match
    #: (a new major is a breaking contract change) and the plugin's minor must be
    #: ``<=`` the backend's (minors are additive, so a newer backend still runs an
    #: older plugin, but a backend must reject a plugin needing a minor it lacks).
    #: Defaults to ``"1.0"`` so manifests written before this field existed are
    #: treated as targeting the first stable contract.
    api_version: str = "1.0"
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

    @field_validator("api_version")
    @classmethod
    def _valid_api_version(cls, v: str) -> str:
        try:
            Version(v)
        except InvalidVersion as exc:
            raise ValueError(f"invalid plugin api_version {v!r}: {exc}") from exc
        return v

    @field_validator("entrypoint")
    @classmethod
    def _valid_entrypoint(cls, v: str | None) -> str | None:
        if v is not None and v.count(":") != 1:
            raise ValueError(f"entrypoint must be 'module.path:Attribute', got {v!r}")
        return v

    def is_compatible_with(self, ciaren_version: str) -> bool:
        """Whether this plugin declares compatibility with ``ciaren_version``.
        Pre-releases are allowed so a plugin can target a dev build.

        Compares against the release's ``base_version`` (dropping any pre/dev/post
        suffix): under PEP 440 ordering a pre-release sorts *before* its own final
        release, so e.g. ``0.1.0a1`` would otherwise fail a ``>=0.1`` spec even
        though it's conceptually a 0.1.0 build.
        """
        try:
            release_version = Version(Version(ciaren_version).base_version)
            return release_version in SpecifierSet(self.ciaren, prereleases=True)
        except (InvalidVersion, InvalidSpecifier):
            return False

    def is_api_compatible_with(self, provider_api_version: str) -> bool:
        """Whether the backend's plugin-contract version (``PLUGIN_API_VERSION``)
        can run this plugin. SemVer on the contract: the major must match — a new
        major is a breaking change — and the plugin's requested minor must be no
        newer than the backend's, since minors only add features. So a 1.2 backend
        runs a plugin built for 1.0/1.1/1.2, but a 1.1 backend rejects a plugin
        that needs 1.2, and any cross-major pair is rejected."""
        try:
            want = Version(self.api_version)
            have = Version(provider_api_version)
        except InvalidVersion:
            return False
        return want.major == have.major and want.minor <= have.minor


def validate_manifest(data: dict[str, Any]) -> PluginManifest:
    """Validate a raw manifest mapping. Raises ``pydantic.ValidationError`` on
    malformed input."""
    return PluginManifest.model_validate(data)
