# SPDX-License-Identifier: AGPL-3.0-only
"""Author-side helper: generate a plugin manifest from the plugin's own code.

A ``.ciarenplugin`` must ship a ``ciaren-plugin.json`` manifest that the loader
validates **before** importing any plugin code — that is the security property
that lets Ciaren check compatibility, permissions, and gating without running an
untrusted entry point. But nothing says an author must *hand-write* that file:
the same facts (id, name, version, permissions, contributed nodes, …) already
live in the plugin's :class:`~app.plugin_api.providers.Plugin` implementation.

Hand-maintaining both copies is boilerplate and drifts silently. This module
derives the manifest from the plugin object, so authoring has a single source of
truth in Python while the shipped manifest — and therefore the pre-import
validation — stays exactly as before. It is authoring/CLI tooling (it imports and
runs the plugin's ``register``), never used on the untrusted install path.
"""

from __future__ import annotations

from app.plugin_api import Permission, Plugin, PluginManifest, ServiceRegistry
from app.plugin_api.manifest import PluginUI


def manifest_from_plugin(
    plugin: Plugin,
    *,
    entrypoint: str,
    ciaren: str = ">=0.1",
    license: str = "community",
    trust: str = "community",
    dependencies: list[str] | None = None,
) -> PluginManifest:
    """Build a :class:`PluginManifest` from a plugin's declared metadata and the
    specs it registers, so the manifest never has to be written by hand.

    Identity/description come from :meth:`Plugin.metadata`; contributed nodes and
    their palette categories, plus the union of every permission and capability
    the plugin's specs declare, come from registering the plugin into a throwaway
    registry and reading it back. ``entrypoint`` and the compatibility/license
    fields (which aren't part of the runtime metadata) are supplied by the caller.
    """
    meta = plugin.metadata()

    # Register into a throwaway registry so we can enumerate exactly what this
    # plugin contributes — nothing else is registered, so every spec is its own.
    registry = ServiceRegistry()
    registry.register_plugin(plugin)

    node_specs = registry.node_specs()

    # Surface the union of what the plugin's metadata *and* its specs declare, so
    # the manifest (and the gating UI that reads it) sees every permission and
    # capability the plugin can exercise — not just the plugin-level metadata.
    permissions: set[Permission] = set(meta.permissions)
    capabilities: set[str] = set(meta.capabilities)
    for node in node_specs:
        permissions.update(node.permissions)
        capabilities.update(node.capabilities)
    for connector in registry.connector_specs():
        permissions.update(connector.permissions)
        capabilities.update(connector.capabilities)
    for storage in registry.storage_specs():
        permissions.update(storage.permissions)
        capabilities.update(storage.capabilities)
    for execution in registry.execution_specs():
        capabilities.update(execution.capabilities)
    for exporter in registry.exporter_specs():
        capabilities.update(exporter.capabilities)
    for validator in registry.validator_specs():
        capabilities.update(validator.capabilities)
    for ai in registry.ai_capabilities():
        capabilities.update(ai.capabilities)
    for model_type in registry.model_type_specs():
        permissions.update(model_type.permissions)
        capabilities.add(f"model.{model_type.id}")

    return PluginManifest(
        id=meta.id,
        name=meta.name,
        version=meta.version,
        publisher=meta.publisher,
        description=meta.description,
        license=license,  # validated by PluginManifest
        ciaren=ciaren,
        entrypoint=entrypoint,
        permissions=sorted(permissions, key=lambda p: p.value),
        capabilities=sorted(capabilities),
        # PluginUI aliases node_categories -> "nodeCategories" and is not
        # populate_by_name, so build it from the aliased mapping.
        ui=PluginUI.model_validate(
            {
                "nodes": [spec.id for spec in node_specs],
                "nodeCategories": {spec.id: spec.category for spec in node_specs},
            }
        ),
        dependencies=list(dependencies or []),
        license_required=False,
        trust=trust,  # validated by PluginManifest
    )


def manifest_json_from_plugin(
    plugin: Plugin,
    *,
    entrypoint: str,
    ciaren: str = ">=0.1",
    license: str = "community",
    trust: str = "community",
    dependencies: list[str] | None = None,
) -> str:
    """The generated manifest as pretty JSON, ready to write to
    ``ciaren-plugin.json`` (camelCase aliases, e.g. ``nodeCategories``)."""
    manifest = manifest_from_plugin(
        plugin,
        entrypoint=entrypoint,
        ciaren=ciaren,
        license=license,
        trust=trust,
        dependencies=dependencies,
    )
    return manifest.model_dump_json(by_alias=True, indent=2, exclude_defaults=False)
