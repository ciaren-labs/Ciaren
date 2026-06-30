# SPDX-License-Identifier: AGPL-3.0-only
"""A tiny, dependency-free flag for "we are computing a preview, not a real run".

Preview computes the whole graph in memory to show one node's output. For ETL
nodes that is cheap and side-effect-free, but ML training/scoring nodes would
otherwise fit models and log MLflow runs on every preview. They consult
:func:`in_preview` to short-circuit to a cheap passthrough instead. The flag is a
``ContextVar`` so it is safe under concurrent async previews.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_preview: ContextVar[bool] = ContextVar("flowframe_preview", default=False)


def in_preview() -> bool:
    return _preview.get()


@contextmanager
def preview_mode() -> Iterator[None]:
    token = _preview.set(True)
    try:
        yield
    finally:
        _preview.reset(token)
