---
title: Assert values in set
search: assert values in set allowed domain categorical contract validation
description: Fail or warn when a column has values outside an allowed set
---

# Assert values in set — `assertValuesInSet`

Fail or warn when a column contains values outside an allowed set — a domain
check for categorical columns. Like the other [data-quality](./overview.md)
nodes, the output frame is the input passed through unchanged.

## Use cases

- Guarantee `status` is only `paid`, `pending`, or `failed`.
- Catch typos or unexpected categories before they reach a report.
- Enforce a controlled vocabulary as a data contract.

## What it does

Each value in the column is checked against the allowed set. Violations either
**fail the run** (`mode: error`, the default) or are **recorded as a warning**
(`mode: warn`) so the run continues. Nulls are tolerated by default.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `column` | string | Yes | The column to check |
| `allowed` | string[] | Yes | The permitted values (≥ 1) |
| `allow_null` | boolean | No | Treat null as allowed (default true) |
| `mode` | string | No | `error` (default) or `warn` |

## Generated Python code

```python
df_2 = df_1
_set_mask = df_2["status"].isin(["paid", "pending", "failed"]) | df_2["status"].isna()
if not _set_mask.all():
    raise ValueError(f"assertValuesInSet: {(~_set_mask).sum()} row(s) in 'status' outside the allowed set")
```

## Tips & common mistakes

- Turn off **allow null** to also flag missing values as violations.
- For numeric bounds use [Assert value range](./assert-value-range.md); for an
  arbitrary rule use [Assert expression](./assert-expression.md).

## See also

- [Assert value range](./assert-value-range.md) · [Assert expression](./assert-expression.md)
