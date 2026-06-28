---
title: Assert value range
description: Fail or warn when a numeric column has values outside a declared range
search: assert value range min max bounds data quality numeric validation contract
---

# Assert value range — `assertValueRange`

Verify that every value in a numeric column falls within a declared range.

The node is **pass-through**: the dataframe leaves unchanged regardless of the
outcome. The violation is recorded in the run's per-node result and either fails
the run (`error` mode) or logs a warning and continues (`warn` mode).

## Use cases

- Ensure prices are never negative.
- Assert that a percentage column stays in `[0, 100]`.
- Validate sensor readings are within expected physical bounds before analytics.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `column` | string | Yes | Column to check |
| `min` | number | Conditional | Lower bound (at least one of `min`/`max` required) |
| `max` | number | Conditional | Upper bound (at least one of `min`/`max` required) |
| `inclusive` | `"both"` \| `"left"` \| `"right"` \| `"neither"` | No | Which bounds are inclusive (default `"both"`) |
| `mode` | `"error"` \| `"warn"` | No | `"error"` (default) stops the run; `"warn"` continues and logs |

You can set only `min` (no upper bound), only `max` (no lower bound), or both.

## Behavior

| Outcome | What happens |
| --- | --- |
| All values within range | Run continues; `assertion_passed: true` |
| Out-of-range values found, `mode: "error"` | Run fails; error names the column and violation count |
| Out-of-range values found, `mode: "warn"` | Run continues; warning recorded with violation count |

The per-node result in the run detail always includes `assertion_passed`,
`assertion_violation_count`, and a sample of up to 5 violating rows.

## Generated Python code

```python
# assertValueRange: column='price', min=0, max=None, inclusive='both' — mode: error
_mask = ~(df_1['price'] >= 0)
_violations = df_1[_mask]
if not _violations.empty:
    _msg = f"assertValueRange: {len(_violations)} value(s) in 'price' out of range [0, ∞)"
    raise AssertionError(_msg)
df_2 = df_1
```

In `warn` mode the `raise` is replaced by `warnings.warn(...)` and execution
continues.

## Tips & common mistakes

- **NaN values are treated as violations.** A null in a numeric column is neither
  in nor out of range by pandas convention; the node counts it as a violation.
  Precede this node with [Drop nulls](./drop-nulls.md) or [Fill nulls](./fill-nulls.md)
  if that isn't what you want.
- **`inclusive="neither"` means strict inequalities.** `min=0, max=100,
  inclusive="neither"` passes values in `(0, 100)`, rejecting 0 and 100
  themselves.
- Use [Filter rows](./filter-rows.md) if you want to *remove* out-of-range rows
  rather than assert they don't exist.

## See also

- [Assert not null](./assert-not-null.md) · [Assert expression](./assert-expression.md)
- [Filter rows](./filter-rows.md) · [Remove outliers](./remove-outliers.md)
