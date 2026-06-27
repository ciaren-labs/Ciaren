"""Data-quality assertion nodes.

Each node is a pass-through: the output frame is always identical to the
input frame. The node checks a contract and either raises
``AssertionViolationError`` (mode='error', the default) or records the
result as a warning in the run's NodeMetadata (mode='warn') so execution
continues.

All checks convert to pandas internally so the logic stays engine-agnostic
without adding new methods to EngineBackend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation, EmitsNodeMetadata, NodeMetadata

_SAMPLE_ROWS = 5
_VALID_MODES = {"error", "warn"}


class AssertionViolationError(Exception):
    """Raised by assertion nodes in 'error' mode when the contract is broken."""


@dataclass
class _CheckResult:
    passed: bool
    violation_count: int
    message: str
    violating_sample: list[dict[str, Any]] = field(default_factory=list)


def _sample(pdf: pd.DataFrame) -> list[dict[str, Any]]:
    return pdf.head(_SAMPLE_ROWS).to_dict("records")  # type: ignore[return-value]


class _BaseAssertion(BaseTransformation, EmitsNodeMetadata):
    """Shared skeleton for all assertion nodes."""

    emits_metadata: bool = True

    def execute(
        self,
        engine: EngineBackend,
        inputs: dict[str, AnyFrame],
        config: dict[str, Any],
    ) -> dict[str, AnyFrame]:
        frames, _ = self.execute_with_metadata(engine, inputs, config)
        return frames

    def execute_with_metadata(
        self,
        engine: EngineBackend,
        inputs: dict[str, AnyFrame],
        config: dict[str, Any],
    ) -> tuple[dict[str, AnyFrame], NodeMetadata | None]:
        df = inputs["in"]
        result = self._check(engine.to_pandas(df), config)
        if not result.passed and config.get("mode", "error") == "error":
            raise AssertionViolationError(result.message)
        meta = NodeMetadata(
            assertion_passed=result.passed,
            assertion_violation_count=result.violation_count,
            assertion_violating_sample=result.violating_sample,
        )
        return {"out": df}, meta

    def _check(self, pdf: pd.DataFrame, config: dict[str, Any]) -> _CheckResult:
        raise NotImplementedError

    # -- codegen helpers ---------------------------------------------------

    def _violation_action(self, mode: str, msg_expr: str) -> str:
        """One-liner that raises or warns, for inline codegen."""
        if mode == "warn":
            return f"import warnings; warnings.warn({msg_expr})"
        return f"raise ValueError({msg_expr})"


# ---------------------------------------------------------------------------
# assertNotNull
# ---------------------------------------------------------------------------


class AssertNotNullTransformation(_BaseAssertion):
    """Fail/warn when any of the specified columns contain null values."""

    type = "assertNotNull"

    def validate_config(self, config: dict[str, Any]) -> None:
        mode = config.get("mode", "error")
        if mode not in _VALID_MODES:
            raise ValueError(f"assertNotNull 'mode' must be one of {_VALID_MODES}")

    def _check(self, pdf: pd.DataFrame, config: dict[str, Any]) -> _CheckResult:
        cols = config.get("columns") or list(pdf.columns)
        missing = [c for c in cols if c not in pdf.columns]
        if missing:
            raise ValueError(f"assertNotNull: columns not found: {missing}")
        mask = pdf[cols].isnull().any(axis=1)
        violating = pdf[mask]
        count = int(mask.sum())
        passed = count == 0
        return _CheckResult(
            passed=passed,
            violation_count=count,
            message=f"assertNotNull: {count} row(s) contain nulls in {cols}",
            violating_sample=_sample(violating) if not passed else [],
        )

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        cols = config.get("columns") or None
        mode = config.get("mode", "error")
        cols_expr = f"{cols!r}" if cols else f"list({src}.columns)"
        msg = f'f"assertNotNull: {{_null_mask.sum()}} row(s) contain nulls in {cols_expr}"'
        action = self._violation_action(mode, msg)
        return (
            f"{dst} = {src}\n_null_mask = {dst}[{cols_expr}].isnull().any(axis=1)\nif _null_mask.any():\n    {action}"
        )

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        cols = config.get("columns") or None
        mode = config.get("mode", "error")
        cols_expr = f"{cols!r}" if cols else f"{src}.columns"
        msg = f'f"assertNotNull: {{_null_count}} row(s) contain nulls in {cols_expr}"'
        action = self._violation_action(mode, msg)
        return (
            f"{dst} = {src}\n"
            f"_null_count = {dst}.select(pl.any_horizontal(pl.col({cols_expr}).is_null())).to_series().sum()\n"
            f"if _null_count > 0:\n"
            f"    {action}"
        )


# ---------------------------------------------------------------------------
# assertUnique
# ---------------------------------------------------------------------------


class AssertUniqueTransformation(_BaseAssertion):
    """Fail/warn when duplicate rows exist across the specified columns."""

    type = "assertUnique"

    def validate_config(self, config: dict[str, Any]) -> None:
        mode = config.get("mode", "error")
        if mode not in _VALID_MODES:
            raise ValueError(f"assertUnique 'mode' must be one of {_VALID_MODES}")

    def _check(self, pdf: pd.DataFrame, config: dict[str, Any]) -> _CheckResult:
        cols = config.get("columns") or None
        subset = cols if cols else None
        mask = pdf.duplicated(subset=subset, keep=False)
        violating = pdf[mask]
        count = int(mask.sum())
        passed = count == 0
        label = cols if cols else "all columns"
        return _CheckResult(
            passed=passed,
            violation_count=count,
            message=f"assertUnique: {count} duplicate row(s) on {label}",
            violating_sample=_sample(violating) if not passed else [],
        )

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        cols = config.get("columns") or None
        mode = config.get("mode", "error")
        subset_expr = f"subset={cols!r}, " if cols else ""
        msg = 'f"assertUnique: {_dup_mask.sum()} duplicate row(s)"'
        action = self._violation_action(mode, msg)
        return (
            f"{dst} = {src}\n_dup_mask = {dst}.duplicated({subset_expr}keep=False)\nif _dup_mask.any():\n    {action}"
        )

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        cols = config.get("columns") or None
        mode = config.get("mode", "error")
        subset_expr = f"subset={cols!r}, " if cols else ""
        msg = 'f"assertUnique: {_dup_count} duplicate row(s)"'
        action = self._violation_action(mode, msg)
        return (
            f"{dst} = {src}\n"
            f"_dup_count = len({dst}) - len({dst}.unique({subset_expr}maintain_order=True))\n"
            f"if _dup_count > 0:\n"
            f"    {action}"
        )


# ---------------------------------------------------------------------------
# assertValueRange
# ---------------------------------------------------------------------------


class AssertValueRangeTransformation(_BaseAssertion):
    """Fail/warn when column values fall outside [min, max]."""

    type = "assertValueRange"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("column"):
            raise ValueError("assertValueRange requires a 'column'")
        if config.get("min") is None and config.get("max") is None:
            raise ValueError("assertValueRange requires at least one of 'min' or 'max'")
        mode = config.get("mode", "error")
        if mode not in _VALID_MODES:
            raise ValueError(f"assertValueRange 'mode' must be one of {_VALID_MODES}")

    def _check(self, pdf: pd.DataFrame, config: dict[str, Any]) -> _CheckResult:
        col = config["column"]
        if col not in pdf.columns:
            raise ValueError(f"assertValueRange: column {col!r} not found")
        lo, hi = config.get("min"), config.get("max")
        inclusive = config.get("inclusive", True)
        series = pd.to_numeric(pdf[col], errors="coerce")
        mask = pd.Series([True] * len(pdf), index=pdf.index)
        if lo is not None:
            mask &= (series >= lo) if inclusive else (series > lo)
        if hi is not None:
            mask &= (series <= hi) if inclusive else (series < hi)
        violating = pdf[~mask]
        count = int((~mask).sum())
        passed = count == 0
        bounds = f"[{lo}, {hi}]" if inclusive else f"({lo}, {hi})"
        return _CheckResult(
            passed=passed,
            violation_count=count,
            message=f"assertValueRange: {count} row(s) in {col!r} outside {bounds}",
            violating_sample=_sample(violating) if not passed else [],
        )

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col = config["column"]
        lo, hi = config.get("min"), config.get("max")
        inclusive = config.get("inclusive", True)
        mode = config.get("mode", "error")
        ge, le = (">=", "<=") if inclusive else (">", "<")
        parts = []
        if lo is not None:
            parts.append(f"(pd.to_numeric({dst}[{col!r}], errors='coerce') {ge} {lo!r})")
        if hi is not None:
            parts.append(f"(pd.to_numeric({dst}[{col!r}], errors='coerce') {le} {hi!r})")
        valid_expr = " & ".join(parts)
        msg = f'f"assertValueRange: {{(~_range_mask).sum()}} row(s) in {col!r} outside range"'
        action = self._violation_action(mode, msg)
        return f"{dst} = {src}\n_range_mask = {valid_expr}\nif not _range_mask.all():\n    {action}"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col = config["column"]
        lo, hi = config.get("min"), config.get("max")
        inclusive = config.get("inclusive", True)
        mode = config.get("mode", "error")
        closed = "both" if inclusive else "none"
        msg = f'f"assertValueRange: {{_range_violations}} row(s) in {col!r} outside range"'
        action = self._violation_action(mode, msg)
        return (
            f"{dst} = {src}\n"
            f"_range_violations = {dst}.filter(\n"
            f"    ~pl.col({col!r}).cast(pl.Float64, strict=False)"
            f".is_between({lo!r}, {hi!r}, closed={closed!r}).fill_null(False)\n"
            f").height\n"
            f"if _range_violations > 0:\n"
            f"    {action}"
        )


# ---------------------------------------------------------------------------
# assertExpression
# ---------------------------------------------------------------------------


class AssertExpressionTransformation(_BaseAssertion):
    """Fail/warn when a boolean pandas-eval expression is false for any row.

    The expression is evaluated with ``df.eval()``, so it supports column
    references and standard arithmetic/comparison operators:
    e.g. ``"amount > 0"``, ``"price >= cost"``, ``"age >= 18 & age <= 65"``.
    """

    type = "assertExpression"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("expression", "").strip():
            raise ValueError("assertExpression requires a non-empty 'expression'")
        mode = config.get("mode", "error")
        if mode not in _VALID_MODES:
            raise ValueError(f"assertExpression 'mode' must be one of {_VALID_MODES}")

    def _check(self, pdf: pd.DataFrame, config: dict[str, Any]) -> _CheckResult:
        expr = config["expression"]
        try:
            raw = pdf.eval(expr)
        except Exception as exc:
            raise ValueError(f"assertExpression: invalid expression {expr!r}: {exc}") from exc
        result_series: pd.Series = pd.Series(raw).astype(bool)
        mask = ~result_series
        violating = pdf[mask.to_numpy()]
        count = int(mask.sum())
        passed = count == 0
        return _CheckResult(
            passed=passed,
            violation_count=count,
            message=f"assertExpression: {count} row(s) violate '{expr}'",
            violating_sample=_sample(violating) if not passed else [],
        )

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        expr = config["expression"]
        mode = config.get("mode", "error")
        msg = f'f"assertExpression: {{_expr_mask.sum()}} row(s) violate {expr!r}"'
        action = self._violation_action(mode, msg)
        return f"{dst} = {src}\n_expr_mask = ~{dst}.eval({expr!r}).astype(bool)\nif _expr_mask.any():\n    {action}"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        expr = config["expression"]
        mode = config.get("mode", "error")
        msg = f'f"assertExpression: {{_expr_violations}} row(s) violate {expr!r}"'
        action = self._violation_action(mode, msg)
        return (
            f"{dst} = {src}\n"
            f"_expr_violations = {dst}.to_pandas().eval({expr!r}).pipe(lambda s: (~s.astype(bool)).sum())\n"
            f"if _expr_violations > 0:\n"
            f"    {action}"
        )


# ---------------------------------------------------------------------------
# assertRowCount
# ---------------------------------------------------------------------------


class AssertRowCountTransformation(_BaseAssertion):
    """Fail/warn when the row count falls outside the declared bounds."""

    type = "assertRowCount"

    def validate_config(self, config: dict[str, Any]) -> None:
        lo, hi = config.get("min_rows"), config.get("max_rows")
        if lo is None and hi is None:
            raise ValueError("assertRowCount requires at least one of 'min_rows' or 'max_rows'")
        if lo is not None and (not isinstance(lo, int) or lo < 0):
            raise ValueError("assertRowCount 'min_rows' must be a non-negative integer")
        if hi is not None and (not isinstance(hi, int) or hi < 0):
            raise ValueError("assertRowCount 'max_rows' must be a non-negative integer")
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("assertRowCount 'min_rows' must be <= 'max_rows'")
        mode = config.get("mode", "error")
        if mode not in _VALID_MODES:
            raise ValueError(f"assertRowCount 'mode' must be one of {_VALID_MODES}")

    def _check(self, pdf: pd.DataFrame, config: dict[str, Any]) -> _CheckResult:
        lo, hi = config.get("min_rows"), config.get("max_rows")
        actual = len(pdf)
        passed = True
        if lo is not None and actual < lo:
            passed = False
        if hi is not None and actual > hi:
            passed = False
        bounds = f"[{lo}, {hi}]".replace("None", "∞")
        return _CheckResult(
            passed=passed,
            violation_count=0 if passed else actual,
            message=f"assertRowCount: got {actual} row(s), expected {bounds}",
            violating_sample=[],
        )

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        lo, hi = config.get("min_rows"), config.get("max_rows")
        mode = config.get("mode", "error")
        conditions = []
        if lo is not None:
            conditions.append(f"len({dst}) < {lo!r}")
        if hi is not None:
            conditions.append(f"len({dst}) > {hi!r}")
        cond = " or ".join(conditions)
        msg = f'f"assertRowCount: got {{len({dst})}} row(s), expected [{lo}, {hi}]"'
        action = self._violation_action(mode, msg)
        return f"{dst} = {src}\nif {cond}:\n    {action}"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        lo, hi = config.get("min_rows"), config.get("max_rows")
        mode = config.get("mode", "error")
        conditions = []
        if lo is not None:
            conditions.append(f"{dst}.height < {lo!r}")
        if hi is not None:
            conditions.append(f"{dst}.height > {hi!r}")
        cond = " or ".join(conditions)
        msg = f'f"assertRowCount: got {{{dst}.height}} row(s), expected [{lo}, {hi}]"'
        action = self._violation_action(mode, msg)
        return f"{dst} = {src}\nif {cond}:\n    {action}"
