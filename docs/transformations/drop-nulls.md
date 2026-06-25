---
title: Drop nulls
search: drop nulls missing na dropna how any all subset
description: Remove rows with missing values, optionally only in chosen columns
---

# Drop nulls — `dropNulls`

Remove rows with missing values.

## Use cases

- Discard records that are missing a required field (e.g. no `amount`).
- Drop fully-empty rows while keeping partially-populated ones.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `how` | string | No | `any` (default) drops a row with any null; `all` only if every value is null |
| `subset` | string[] | No | Only consider these columns |

## Generated Python code

```python
df_2 = df_1.dropna(subset=['amount'])
```

## Tips & common mistakes

- **`how: all` needs a `subset`** to be meaningful row-wise — pair it with the
  columns that define an "empty" row.
- To *keep* rows and fill the gaps instead, use [Fill nulls](./fill-nulls.md).

## See also

- [Fill nulls](./fill-nulls.md) · [Filter rows](./filter-rows.md)
