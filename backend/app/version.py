# SPDX-License-Identifier: AGPL-3.0-only
"""Single source for the running Ciaren version.

Resolved from the installed package metadata, falling back to the in-repo version
when running from a source checkout that was never installed.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

_FALLBACK = "0.1.0"


def ciaren_version() -> str:
    try:
        return version("ciaren")
    except PackageNotFoundError:
        return _FALLBACK
