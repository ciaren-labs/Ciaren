---
title: Assert row count
description: Fail or warn when the number of rows falls outside declared bounds
search: assert row count min max rows data quality contract check size
---

# Assert row count — `assertRowCount`

Verify that the number of rows in the dataframe falls within declared bounds.

The node is **pass-through**: the dataframe leaves unchanged regardless of the
outcome. The violation is recorded in the run's per-node result and either fails
the run (`error` mode) or logs a warning and continues (`warn` mode).

## Use cases

- Catch a completely empty dataset before it silently propagates through a
  pipeline.
- Ensure a daily feed has at least a reasonable number of rows (warn when
  a day is suspiciously sparse).
- Assert that a join didn't fan-out unexpectedly by capping the maximum.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `min_rows` | integer | Conditional | Minimum number of rows (at least one of `min_rows`/`max_rows` required) |
| `max_rows` | integer | Conditional | Maximum number of rows (at least one of `min_rows`/`max_rows` required) |
| `mode` | `"error"` \| `"warn"` | No | `"error"` (default) stops the run; `"warn"` continues and logs |

You can set only `min_rows` (no upper limit), only `max_rows` (no lower limit),
or both. The check is inclusive on both bounds.

## Behavior

| Outcome | What happens |
| --- | --- |
| Row count within `[min_rows, max_rows]` | Run continues; `assertion_passed: true` |
| Row count outside bounds, `mode: "error"` | Run fails; error reports actual vs. expected count |
| Row count outside bounds, `mode: "warn"` | Run continues; warning recorded with actual count |

## Generated Python code

```python
if len(df_1) < 1:
    raise ValueError(f"assertRowCount: got {len(df_1)} row(s), expected [1, None]")
```

In `warn` mode the `raise` is replaced by `warnings.warn(...)` and execution
continues.

## Tips & common mistakes

- **Place it early.** An empty-dataset check right after the input node catches
  fetch failures before they silently produce empty outputs.
- **`min_rows=1` is usually the most important check.** An empty dataframe passes
  through all transformation nodes without error, so downstream joins,
  aggregates, and outputs all succeed on zero rows — which is almost never the
  desired behavior.
- **Combine with `warn` for alerts on sparse days.** Set `min_rows` to your
  expected minimum with `mode: "warn"` so the pipeline still produces output
  while the warning appears in the run log.

## See also

- [Assert not null](./assert-not-null.md) · [Assert expression](./assert-expression.md)
- [Filter rows](./filter-rows.md) · [Limit rows](./limit-rows.md)
