"""Single source for the running FlowFrame version.

Resolved from the installed package metadata, falling back to the in-repo version
when running from a source checkout that was never installed.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

_FALLBACK = "0.1.0"


def flowframe_version() -> str:
    try:
        return version("flowframe")
    except PackageNotFoundError:
        return _FALLBACK
