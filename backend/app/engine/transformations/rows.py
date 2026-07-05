# SPDX-License-Identifier: AGPL-3.0-only
from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation, one_or_list

_SIMPLE_OPS = {"==", "!=", ">", ">=", "<", "<="}


class FilterRowsTransformation(BaseTransformation):
    type = "filterRows"

    def validate_config(self, config: dict[str, Any]) -> None:
        required = {"column", "operator"}
        if not required.issubset(config):
            raise ValueError(f"filterRows requires keys: {required}")
        op = config["operator"]
        # value is not required for unary operators (isnull/notnull)
        if op not in {"isnull", "notnull"} and "value" not in config:
            raise ValueError("filterRows requires a 'value' for this operator")
        if op == "between" and "value2" not in config:
            raise ValueError("filterRows 'between' requires a 'value2' (upper bound)")

    def _values(self, config: dict[str, Any]) -> Any:
        """Normalize the config value(s) into what the engine expects per operator."""
        op = config["operator"]
        val = config.get("value")
        if op == "between":
            return [val, config.get("value2")]
        if op == "in":
            if isinstance(val, list):
                return val
            return [v.strip() for v in str(val).split(",") if v.strip()]
        return val

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        col = config["column"]
        op = config["operator"]
        return {"out": engine.filter_rows(inputs["in"], col, op, self._values(config))}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        # `.loc[lambda _d: …]` instead of `src[src[col] …]`: the callable form is
        # the idiomatic chainable filter — the mask reads the *running* frame, so
        # exported linear flows fuse into one fluent expression (the subscript
        # form references src twice and breaks the chain; see fuse_method_chains).
        # `_d` because `_` names are reserved away from flow parameters.
        src, dst = input_vars["in"], output_vars["out"]
        col, op = config["column"], config["operator"]
        val = config.get("value")
        if op in _SIMPLE_OPS:
            return f"{dst} = {src}.loc[lambda _d: _d[{col!r}] {op} {val!r}]"
        if op == "isnull":
            return f"{dst} = {src}.loc[lambda _d: _d[{col!r}].isna()]"
        if op == "notnull":
            return f"{dst} = {src}.loc[lambda _d: _d[{col!r}].notna()]"
        if op == "between":
            low, high = self._values(config)
            return f"{dst} = {src}.loc[lambda _d: _d[{col!r}].between({low!r}, {high!r})]"
        if op == "in":
            return f"{dst} = {src}.loc[lambda _d: _d[{col!r}].isin({self._values(config)!r})]"
        if op in {"contains", "startswith", "endswith"}:
            # str() like the engine: a numeric search value must not emit .str.contains(5).
            return f"{dst} = {src}.loc[lambda _d: _d[{col!r}].astype(str).str.{op}({str(val)!r})]"
        raise ValueError(f"Unknown filter operator: {op!r}")

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col, op = config["column"], config["operator"]
        val = config.get("value")
        if op in _SIMPLE_OPS:
            return f"{dst} = {src}.filter(pl.col({col!r}) {op} {val!r})"
        if op == "isnull":
            return f"{dst} = {src}.filter(pl.col({col!r}).is_null())"
        if op == "notnull":
            return f"{dst} = {src}.filter(pl.col({col!r}).is_not_null())"
        if op == "between":
            return f"{dst} = {src}.filter(pl.col({col!r}).is_between({val!r}, {config.get('value2')!r}))"
        if op == "in":
            return f"{dst} = {src}.filter(pl.col({col!r}).is_in({self._values(config)!r}))"
        if op in {"contains", "startswith", "endswith"}:
            method = {
                "contains": "contains",
                "startswith": "starts_with",
                "endswith": "ends_with",
            }[op]
            # literal=True mirrors PolarsEngine.filter_rows — polars' contains is
            # regex by default, which would misread values like "a.b". str() like
            # the engine so numeric search values stay valid code.
            extra = ", literal=True" if op == "contains" else ""
            return f"{dst} = {src}.filter(pl.col({col!r}).cast(pl.Utf8).str.{method}({str(val)!r}{extra}))"
        raise ValueError(f"Unknown filter operator: {op!r}")


class FilterExpressionTransformation(BaseTransformation):
    """Keep rows where a boolean expression is true. The expression uses pandas
    ``eval`` semantics (e.g. ``amount > 100 and status == 'paid'``) on both engines,
    so the same expression behaves identically on pandas and polars."""

    type = "filterExpression"
    # The polars path evaluates the mask via pandas, so it can't run on a LazyFrame.
    polars_lazy_safe = False

    def validate_config(self, config: dict[str, Any]) -> None:
        if not str(config.get("expression", "")).strip():
            raise ValueError("filterExpression requires a non-empty 'expression'")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {"out": engine.filter_expr(inputs["in"], config["expression"])}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        expr = config["expression"]
        # .query() is the idiomatic form of "filter by an eval expression" and
        # chains cleanly. Known divergence from PandasEngine.filter_expr (which
        # coerces the mask with astype(bool)): an expression that doesn't
        # evaluate to booleans raises here instead of keeping truthy rows —
        # acceptable, since a non-boolean filter expression is almost certainly
        # a mistake the script should surface.
        return f"{dst} = {src}.query({expr!r}).reset_index(drop=True)"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        expr = config["expression"]
        # Mirror execute(): evaluate the mask with pandas, filter the polars frame.
        # The emitted comment warns script users about the hidden runtime deps.
        return (
            "# the filter expression uses pandas eval semantics (needs pandas + pyarrow installed)\n"
            f"{dst} = {src}.filter(pl.Series({src}.to_pandas().eval({expr!r})).cast(pl.Boolean))"
        )


class SortRowsTransformation(BaseTransformation):
    type = "sortRows"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("columns"):
            raise ValueError("sortRows requires a non-empty 'columns' list")
        if config.get("na_position", "last") not in ("first", "last"):
            raise ValueError("sortRows 'na_position' must be 'first' or 'last'")

    def _ascending(self, config: dict[str, Any]) -> list[bool]:
        columns = config["columns"]
        ascending = config.get("ascending", True)
        if isinstance(ascending, bool):
            return [ascending] * len(columns)
        return list(ascending)

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {
            "out": engine.sort_rows(
                inputs["in"],
                config["columns"],
                self._ascending(config),
                config.get("na_position", "last"),
            )
        }

    @staticmethod
    def _collapse(flags: Any) -> Any:
        """A per-column direction list where every entry agrees is just a bool."""
        if isinstance(flags, list) and len(set(flags)) == 1:
            return flags[0]
        return flags

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        ascending = self._collapse(config.get("ascending", True))
        na_position = config.get("na_position", "last")
        args = f"{one_or_list(config['columns'])!r}"
        if ascending is not True:
            args += f", ascending={ascending!r}"
        if na_position != "last":
            args += f", na_position={na_position!r}"
        return f"{dst} = {src}.sort_values({args})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        ascending = config.get("ascending", True)
        descending = [not a for a in ascending] if isinstance(ascending, list) else not ascending
        descending = self._collapse(descending)
        args = f"{one_or_list(config['columns'])!r}"
        if descending is not False:
            args += f", descending={descending!r}"
        if config.get("na_position", "last") == "last":
            # Non-default in polars (its default puts nulls first) but the
            # node's default — mirrors PolarsEngine.sort_rows / pandas.
            args += ", nulls_last=True"
        return f"{dst} = {src}.sort({args})"


class LimitRowsTransformation(BaseTransformation):
    type = "limitRows"

    def validate_config(self, config: dict[str, Any]) -> None:
        n = config.get("n")
        if not isinstance(n, int) or n < 0:
            raise ValueError("limitRows requires a non-negative integer 'n'")
        offset = config.get("offset", 0)
        if not isinstance(offset, int) or offset < 0:
            raise ValueError("limitRows 'offset' must be a non-negative integer")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {"out": engine.limit_rows(inputs["in"], config["n"], config.get("offset", 0))}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        n, offset = config["n"], config.get("offset", 0)
        if offset:
            return f"{dst} = {src}.iloc[{offset!r}:{offset + n!r}]"
        return f"{dst} = {src}.head({n!r})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        n, offset = config["n"], config.get("offset", 0)
        if offset:
            return f"{dst} = {src}.slice({offset!r}, {n!r})"
        return f"{dst} = {src}.head({n!r})"


class SampleRowsTransformation(BaseTransformation):
    type = "sampleRows"
    polars_lazy_safe = False  # LazyFrame has no .sample()

    def validate_config(self, config: dict[str, Any]) -> None:
        seed = config.get("seed")
        # bool is an int subclass — reject True/False masquerading as a seed.
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError(
                "sampleRows requires an integer 'seed' for reproducibility (random samples are not allowed)."
            )
        n, frac = config.get("n"), config.get("frac")
        if frac is not None:
            if not isinstance(frac, (int, float)) or not (0 < frac <= 1):
                raise ValueError("sampleRows 'frac' must be a number in (0, 1]")
        elif not isinstance(n, int) or n < 0:
            raise ValueError("sampleRows requires a non-negative integer 'n' or a 'frac'")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        frac = config.get("frac")
        n = None if frac is not None else config.get("n")
        return {"out": engine.sample_rows(inputs["in"], n, frac, config.get("seed"))}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        seed = config.get("seed")
        size = f"frac={config['frac']!r}" if config.get("frac") is not None else f"n={config['n']!r}"
        return f"{dst} = {src}.sample({size}, random_state={seed!r})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        seed = config.get("seed")
        size = f"fraction={config['frac']!r}" if config.get("frac") is not None else f"n={config['n']!r}"
        return f"{dst} = {src}.sample({size}, seed={seed!r})"


class RemoveDuplicatesTransformation(BaseTransformation):
    type = "removeDuplicates"

    _POLARS_KEEP = {"first": "first", "last": "last", False: "none"}

    def validate_config(self, config: dict[str, Any]) -> None:
        keep = config.get("keep", "first")
        if keep not in ("first", "last", False):
            raise ValueError("removeDuplicates 'keep' must be 'first', 'last', or false")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        subset = config.get("subset") or None
        keep = config.get("keep", "first")
        return {"out": engine.drop_duplicates(inputs["in"], subset, keep)}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        subset = config.get("subset")
        keep = config.get("keep", "first")
        args = []
        if subset:
            args.append(f"subset={one_or_list(subset)!r}")
        if keep != "first":  # pandas' own default
            args.append(f"keep={keep!r}")
        return f"{dst} = {src}.drop_duplicates({', '.join(args)})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        keep = self._POLARS_KEEP.get(config.get("keep", "first"), "first")
        subset = config.get("subset")
        args = []
        if subset:
            args.append(f"subset={one_or_list(subset)!r}")
        # keep and maintain_order are always spelled out: polars' defaults
        # ('any', unordered) differ from the node's pandas-like semantics.
        args.append(f"keep={keep!r}")
        args.append("maintain_order=True")
        return f"{dst} = {src}.unique({', '.join(args)})"
