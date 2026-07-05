---
title: Assert not null
description: Fail or warn when a column contains null values
search: assert not null data quality validation missing values contract check
---

# Assert not null — `assertNotNull`

Verify that one or more columns contain no null (missing) values.

The node is **pass-through**: the dataframe leaves unchanged regardless of the
outcome. The violation is recorded in the run's per-node result and either fails
the run (`error` mode) or logs a warning and continues (`warn` mode).

## Use cases

- Enforce that a primary-key column is never null before a join.
- Validate that required fields (`email`, `user_id`) are populated after an
  ingestion step.
- Add a contract at the boundary between two teams' pipelines without changing
  the data shape.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `columns` | list of strings | No | Columns that must be non-null. Empty (or omitted) checks **every** column. |
| `mode` | `"error"` \| `"warn"` | No | `"error"` (default) stops the run; `"warn"` continues and logs |

## Behavior

| Outcome | What happens |
| --- | --- |
| All specified columns are non-null | Run continues; `assertion_passed: true` |
| Any null found, `mode: "error"` | Run fails; error message names the column and null count |
| Any null found, `mode: "warn"` | Run continues; warning recorded with column and null count |

The per-node result in the run detail always includes `assertion_passed`,
`assertion_violation_count`, and a sample of up to 5 violating rows.

## Generated Python code

```python
_null_mask = df_1[['user_id', 'email']].isnull().any(axis=1)
if _null_mask.any():
    raise ValueError(f"assertNotNull: {_null_mask.sum()} row(s) contain nulls in ['user_id', 'email']")
```

In `warn` mode the `raise` is replaced by a `warnings.warn(...)` call and
execution continues.

## Tips & common mistakes

- **The dataframe is unchanged.** Place this node anywhere in the graph where
  you want a contract check, then continue with other nodes after it.
- **Use `warn` during development.** Switch to `error` when the pipeline goes
  into production to catch real data issues early.
- Use [Drop nulls](./drop-nulls.md) if you want to *remove* null rows instead
  of asserting they don't exist.

## See also

- [Assert unique](./assert-unique.md) · [Assert value range](./assert-value-range.md)
- [Drop nulls](./drop-nulls.md) · [Filter rows](./filter-rows.md)
