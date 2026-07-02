# SPDX-License-Identifier: AGPL-3.0-only
"""Single source for the running Ciaren version.

Resolved from the installed package metadata, falling back to the in-repo version
when running from a source checkout that was never installed.
"""

from __future__ import annotations

from importlib.metadata import version

_FALLBACK = "0.1.0-alpha.1"


def ciaren_version() -> str:
    # Catch broadly, not just PackageNotFoundError: third-party meta-path
    # finders (e.g. the importlib_metadata backport) raise their own exception
    # types, and a version lookup must never break plugin loading or startup.
    try:
        return version("ciaren")
    except Exception:  # noqa: BLE001
        return _FALLBACK
