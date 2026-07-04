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

_REPO_BLOB = "https://github.com/ciaren-labs/Ciaren/blob/main"
_REPO_RAW = "https://raw.githubusercontent.com/ciaren-labs/Ciaren/main"


class ReadmeMetadataHook(MetadataHookInterface):
    PLUGIN_NAME = "custom"

    def update(self, metadata: dict) -> None:
        readme = next(
            (
                candidate
                for candidate in (Path(self.root).parent / "README.md", Path(self.root) / "README.md")
                if candidate.is_file()
            ),
            None,
        )
        if readme is None:
            metadata["readme"] = {
                "content-type": "text/markdown",
                "text": "Ciaren is a local-first visual platform for building data and ML workflows.",
            }
            return
        text = readme.read_text(encoding="utf-8")
        metadata["readme"] = {
            "content-type": "text/markdown",
            "text": _rewrite_repo_relative_links(text),
        }


def _rewrite_repo_relative_links(text: str) -> str:
    """Make the repo README render correctly as PyPI long_description."""
    replacements = {
        'src="brand-assets/': f'src="{_REPO_RAW}/brand-assets/',
        "(docs/public/": f"({_REPO_RAW}/docs/public/",
        "(backend/app/plugin_api/)": f"({_REPO_BLOB}/backend/app/plugin_api/)",
        "(SECURITY.md)": f"({_REPO_BLOB}/SECURITY.md)",
        "(CONTRIBUTING.md)": f"({_REPO_BLOB}/CONTRIBUTING.md)",
        "(LICENSE)": f"({_REPO_BLOB}/LICENSE)",
        "(NOTICE)": f"({_REPO_BLOB}/NOTICE)",
        "(LICENSES/)": f"({_REPO_BLOB}/LICENSES/)",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text
