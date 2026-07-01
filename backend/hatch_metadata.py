"""Hatchling metadata hook: inline the repo-root README as the package's long description.

The README lives at the repo root (documenting the whole monorepo), not inside
``backend/``, which is the packaging root. Referencing it as a static
``project.readme = "../README.md"`` path fails: hatchling embeds a literal
``../README.md`` member path in the sdist (a path escaping the archive root,
which tar/zip readers reject or strip), and pip's isolated wheel-from-sdist
build can't see outside the sdist's own tree either way. Reading the content
here and inlining it as text sidesteps both: the description text ends up
directly in the package metadata, with no on-disk reference at install time.
"""

from __future__ import annotations

from pathlib import Path

from hatchling.metadata.plugin.interface import MetadataHookInterface


class ReadmeMetadataHook(MetadataHookInterface):
    PLUGIN_NAME = "custom"

    def update(self, metadata: dict) -> None:
        readme = Path(self.root).parent / "README.md"
        metadata["readme"] = {
            "content-type": "text/markdown",
            "text": readme.read_text(encoding="utf-8"),
        }
