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
    def fill_nulls(
        self, df: AnyFrame, columns: list[str] | None, strategy: str, value: Any
    ) -> AnyFrame: ...
    def drop_nulls(
        self, df: AnyFrame, columns: list[str] | None, how: str = "any"
    ) -> AnyFrame: ...
    def drop_duplicates(
        self, df: AnyFrame, subset: list[str] | None, keep: str | bool
    ) -> AnyFrame: ...
    def cast_column(
        self, df: AnyFrame, column: str, dtype: str, fmt: str | None = None, errors: str = "raise"
    ) -> AnyFrame: ...
    def sort_rows(
        self, df: AnyFrame, columns: list[str], ascending: list[bool], na_position: str = "last"
    ) -> AnyFrame: ...
    def select_columns(self, df: AnyFrame, columns: list[str]) -> AnyFrame: ...
    def add_column(self, df: AnyFrame, name: str, expression: str) -> AnyFrame: ...
    def groupby_agg(
        self, df: AnyFrame, by: list[str], aggregations: dict[str, str]
    ) -> AnyFrame: ...
    def join(
        self,
        left: AnyFrame,
        right: AnyFrame,
        on: list[str] | None,
        how: str,
        left_on: list[str] | None = None,
        right_on: list[str] | None = None,
        suffixes: tuple[str, str] = ("_x", "_y"),
    ) -> AnyFrame: ...
    def concat(self, frames: list[AnyFrame]) -> AnyFrame: ...
    def limit_rows(self, df: AnyFrame, n: int, offset: int = 0) -> AnyFrame: ...
    def replace_values(
        self, df: AnyFrame, column: str, to_replace: Any, value: Any, regex: bool = False
    ) -> AnyFrame: ...
    def string_transform(
        self,
        df: AnyFrame,
        column: str,
        operation: str,
        find: str | None = None,
        replace_with: str | None = None,
        width: int | None = None,
        fill_char: str = " ",
        side: str = "left",
    ) -> AnyFrame: ...
    # -- New nodes (Phase 3) -------------------------------------------
    def sample_rows(
        self, df: AnyFrame, n: int | None, frac: float | None, seed: int | None
    ) -> AnyFrame: ...
    def remove_outliers(
        self,
        df: AnyFrame,
        columns: list[str],
        method: str,
        action: str,
        factor: float,
        threshold: float,
        lower: float,
        upper: float,
    ) -> AnyFrame: ...
    def round_columns(self, df: AnyFrame, columns: list[str], decimals: int) -> AnyFrame: ...
    def bin_column(
        self,
        df: AnyFrame,
        column: str,
        new_column: str,
        method: str,
        bins: int,
        labels: list[str] | None,
    ) -> AnyFrame: ...
    def extract_date_parts(
        self, df: AnyFrame, column: str, parts: list[str]
    ) -> AnyFrame: ...
    def unpivot(
        self,
        df: AnyFrame,
        id_vars: list[str],
        value_vars: list[str] | None,
        var_name: str,
        value_name: str,
    ) -> AnyFrame: ...
    def pivot(
        self,
        df: AnyFrame,
        index: list[str],
        columns: str,
        values: str,
        aggfunc: str,
    ) -> AnyFrame: ...

    # -- New nodes (text/date/value mapping) ---------------------------
    def split_column(
        self,
        df: AnyFrame,
        column: str,
        into: list[str],
        mode: str,
        delimiter: str,
        pattern: str,
        keep_original: bool,
    ) -> AnyFrame: ...
    def parse_dates(
        self, df: AnyFrame, columns: list[str], fmt: str | None, errors: str
    ) -> AnyFrame: ...
    def map_values(
        self,
        df: AnyFrame,
        column: str,
        new_column: str | None,
        mapping: dict[Any, Any],
        default: Any,
        use_default: bool,
    ) -> AnyFrame: ...
    def window_function(
        self,
        df: AnyFrame,
        function: str,
        partition_by: list[str],
        order_by: list[str],
        target: str | None,
        offset: int,
        descending: bool,
        new_column: str,
    ) -> AnyFrame: ...
    def conditional_column(
        self,
        df: AnyFrame,
        rules: list[dict[str, Any]],
        default: Any,
        new_column: str,
    ) -> AnyFrame: ...


def rule_conditions(rule: dict[str, Any]) -> list[dict[str, Any]]:
    """The conditions of a conditionalColumn rule, as a uniform list.

    New rules carry a ``conditions`` list combined by ``match`` (all/any). Legacy
    rules store a single flat condition on the rule itself; normalize those to a
    one-item list so the engines and codegen only ever handle one shape.
    """
    conditions = rule.get("conditions")
    if isinstance(conditions, list) and conditions:
        return conditions
    condition = {"column": rule.get("column"), "operator": rule.get("operator", "==")}
    if "value" in rule:
        condition["value"] = rule["value"]
    return [condition]


def rule_combine_all(rule: dict[str, Any]) -> bool:
    """True when a rule's conditions must ALL hold (AND); False for ANY (OR)."""
    return bool(rule.get("match", "all") != "any")


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
