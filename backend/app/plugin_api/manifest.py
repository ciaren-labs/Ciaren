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
    #: ``PLUGIN_API_VERSION`` at build time. Independent of both the plugin's own
    #: ``version`` and the app's ``ciaren`` compatibility. Compared against the
    #: running backend's contract version at load (see ``is_api_compatible_with``):
    #: pre-1.0 the ``major.minor`` must match *exactly* (the alpha contract makes no
    #: compatibility promise); from 1.0 on the major must match and the plugin's
    #: minor be ``<=`` the backend's (additive minors). Defaults to the first
    #: (alpha) contract so a manifest that predates this field still loads.
    api_version: str = "0.1.0-alpha.1"
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
        can run this plugin. SemVer on the contract, with the standard pre-1.0
        caveat:

        - **Pre-1.0 (major 0)** — the alpha contract promises nothing across
          versions, so the ``major.minor`` must match *exactly*. A ``0.1`` plugin
          runs only on a ``0.1`` backend; a ``0.2`` backend rejects it (and it must
          be rebuilt against ``0.2``).
        - **1.0 and later** — the major must match (a new major is breaking) and the
          plugin's minor be ``<=`` the backend's, since minors only add features. So
          a ``1.2`` backend runs plugins built for ``1.0``/``1.1``/``1.2`` but
          rejects one needing ``1.3``.

        The patch/pre-release components never affect the decision (``0.1.0-alpha.1``
        compares as ``0.1``); any cross-major pair is always rejected.
        """
        try:
            want = Version(self.api_version)
            have = Version(provider_api_version)
        except InvalidVersion:
            return False
        if want.major != have.major:
            return False
        if want.major == 0:  # pre-1.0 alpha: no compatibility promise across minors
            return want.minor == have.minor
        return want.minor <= have.minor


def validate_manifest(data: dict[str, Any]) -> PluginManifest:
    """Validate a raw manifest mapping. Raises ``pydantic.ValidationError`` on
    malformed input."""
    return PluginManifest.model_validate(data)
