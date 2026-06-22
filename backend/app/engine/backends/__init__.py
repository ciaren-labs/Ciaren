"""DataFrame engine backends.

Importing this package registers every available engine. ``pandas`` is always
available; ``polars`` registers only if the optional dependency is installed.
"""

from app.engine.backends.base import (
    AnyFrame,
    EngineBackend,
    available_engines,
    get_engine,
    register_engine,
)
from app.engine.backends.pandas_engine import PandasEngine

try:  # polars is an optional dependency
    from app.engine.backends.polars_engine import PolarsEngine
except ImportError:  # pragma: no cover - exercised only when polars is absent
    PolarsEngine = None  # type: ignore[assignment, misc]

__all__ = [
    "AnyFrame",
    "EngineBackend",
    "PandasEngine",
    "PolarsEngine",
    "available_engines",
    "get_engine",
    "register_engine",
]
