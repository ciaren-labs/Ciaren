---
title: Limit rows
search: limit rows head top n offset slice first
description: Keep a slice of rows, optionally skipping some first
---

# Limit rows — `limitRows`

Keep a slice of rows.

## Use cases

- Take the top N after a [Sort](./sort-rows.md) (e.g. top 100 customers).
- Page through data with `offset` + `n`.
- Trim a preview to a manageable size.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `n` | int | Yes | Number of rows to keep (≥ 1) |
| `offset` | int | No | Skip this many rows first (default 0) |

## Generated Python code

```python
df_2 = df_1.head(100)
```

## Tips & common mistakes

- **Limit is positional**, not random — sort first for a meaningful "top N". For
  a random subset use [Sample rows](./sample-rows.md).
- `offset` skips from the current row order, so combine it with a deterministic
  [Sort](./sort-rows.md) for stable paging.

## See also

- [Sort rows](./sort-rows.md) · [Sample rows](./sample-rows.md)
