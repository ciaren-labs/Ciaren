from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import pandas as pd

# Runtime type for DataFrames — Any because polars.DataFrame is an optional import.
AnyFrame = Any


@runtime_checkable
class EngineBackend(Protocol):
    """Structural protocol every DataFrame backend must satisfy.

    Each method receives and returns AnyFrame (pd.DataFrame or pl.DataFrame).
    Concrete implementations must not import each other's libraries.
    """

    name: str

    # -- I/O ------------------------------------------------------------

    def read(self, path: str, source_type: str) -> AnyFrame: ...
    def write(self, df: AnyFrame, path: str, source_type: str) -> None: ...
    def to_pandas(self, df: AnyFrame) -> pd.DataFrame: ...
    def to_records(self, df: AnyFrame, n: int | None = None) -> list[dict[str, Any]]: ...
    def row_count(self, df: AnyFrame) -> int: ...

    # -- Core operations ------------------------------------------------

    def rename_columns(self, df: AnyFrame, mapping: dict[str, str]) -> AnyFrame: ...
    def drop_columns(self, df: AnyFrame, columns: list[str]) -> AnyFrame: ...
    def filter_rows(self, df: AnyFrame, column: str, operator: str, value: Any) -> AnyFrame: ...
    def fill_nulls(self, df: AnyFrame, columns: list[str] | None, value: Any) -> AnyFrame: ...
    def drop_nulls(self, df: AnyFrame, columns: list[str] | None) -> AnyFrame: ...
    def drop_duplicates(
        self, df: AnyFrame, subset: list[str] | None, keep: str | bool
    ) -> AnyFrame: ...
    def cast_column(self, df: AnyFrame, column: str, dtype: str) -> AnyFrame: ...
    def sort_rows(
        self, df: AnyFrame, columns: list[str], ascending: list[bool]
    ) -> AnyFrame: ...
    def select_columns(self, df: AnyFrame, columns: list[str]) -> AnyFrame: ...
    def add_column(self, df: AnyFrame, name: str, expression: str) -> AnyFrame: ...
    def groupby_agg(
        self, df: AnyFrame, by: list[str], aggregations: dict[str, str]
    ) -> AnyFrame: ...
    def join(
        self, left: AnyFrame, right: AnyFrame, on: list[str], how: str
    ) -> AnyFrame: ...
    def concat(self, frames: list[AnyFrame]) -> AnyFrame: ...
    def limit_rows(self, df: AnyFrame, n: int) -> AnyFrame: ...
    def replace_values(
        self, df: AnyFrame, column: str, to_replace: Any, value: Any
    ) -> AnyFrame: ...
    def string_transform(self, df: AnyFrame, column: str, operation: str) -> AnyFrame: ...


_REGISTRY: dict[str, type[EngineBackend]] = {}


def register_engine(cls: type[EngineBackend]) -> type[EngineBackend]:
    _REGISTRY[cls.name] = cls
    return cls


def get_engine(name: str) -> EngineBackend:
    if name not in _REGISTRY:
        available = list(_REGISTRY)
        raise ValueError(f"Unknown engine {name!r}. Available: {available}")
    return _REGISTRY[name]()


def available_engines() -> list[str]:
    return list(_REGISTRY)
