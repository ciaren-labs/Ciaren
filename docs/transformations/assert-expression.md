---
title: Assert expression
description: Fail or warn when a boolean column expression is not true for every row
search: assert expression boolean eval data quality custom condition contract check
---

# Assert expression — `assertExpression`

Verify that a boolean expression evaluates to `true` for every row.

The node is **pass-through**: the dataframe leaves unchanged regardless of the
outcome. The violation is recorded in the run's per-node result and either fails
the run (`error` mode) or logs a warning and continues (`warn` mode).

## Use cases

- Assert a business invariant: `revenue >= cost` on every row.
- Validate a cross-column relationship: `end_date >= start_date`.
- Catch unexpected nulls in a derived column: `score.notnull()`.
- Any condition expressible as a pandas column expression.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `expression` | string | Yes | A pandas `eval`-compatible expression that must be `True` for every row |
| `mode` | `"error"` \| `"warn"` | No | `"error"` (default) stops the run; `"warn"` continues and logs |

The expression is evaluated via `df.eval(expression)` which supports
arithmetic operators (`+`, `-`, `*`, `/`), comparisons (`==`, `!=`, `>`, `<`,
`>=`, `<=`), boolean operators (`and`, `or`, `not`), and column name references.

## Behavior

| Outcome | What happens |
| --- | --- |
| Expression is `True` for all rows | Run continues; `assertion_passed: true` |
| Any row is `False`, `mode: "error"` | Run fails; error names the expression and violation count |
| Any row is `False`, `mode: "warn"` | Run continues; warning recorded with violation count |

The per-node result in the run detail always includes `assertion_passed`,
`assertion_violation_count`, and a sample of up to 5 violating rows.

## Generated Python code

```python
_expr_mask = ~df_1.eval('revenue >= cost').astype(bool)
if _expr_mask.any():
    raise ValueError(f"assertExpression: {_expr_mask.sum()} row(s) violate 'revenue >= cost'")
```

In `warn` mode the `raise` is replaced by `warnings.warn(...)` and execution
continues.

## Tips & common mistakes

- **Use pandas `eval` syntax.** Column names with spaces need backtick quoting:
  `` `my column` > 0 ``.
- **Expressions must return a boolean series.** An expression like `price * 2`
  does not evaluate to booleans and will error; use `price * 2 > 0` instead.
- **`NaN` comparisons return `False`**, so a null in any compared column will
  appear as a violation. Precede this node with [Fill nulls](./fill-nulls.md)
  or [Drop nulls](./drop-nulls.md) if needed.
- For a simpler range check on a single column, use
  [Assert value range](./assert-value-range.md) — it has a dedicated UI and
  clearer error messages.

## See also

- [Assert value range](./assert-value-range.md) · [Assert not null](./assert-not-null.md)
- [Calculated column](./calculated-column.md) · [Filter rows](./filter-rows.md)
