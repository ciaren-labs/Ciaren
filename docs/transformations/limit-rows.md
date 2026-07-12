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

## What it does

Returns the first `n` rows from the current row order. Combine with
[Sort rows](./sort-rows.md) before limiting to get a meaningful "top N".

<DataTransform
  transform="Limit rows (n=3)"
  :before='{
    "columns":["region","amount"],
    "rows":[["South",150],["West",120],["North",80],["East",30],["Central",10]]
  }'
  :after='{
    "columns":["region","amount"],
    "rows":[["South",150],["West",120],["North",80]]
  }'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `n` | int | Yes | Number of rows to keep (≥ 0; `0` keeps no rows) |
| `offset` | int | No | Skip this many rows first (default 0) |

## Generated Python code

```python
df_2 = df_1.head(3)
```

## Tips & common mistakes

- **Limit is positional**, not random — sort first for a meaningful "top N". For
  a random subset use [Sample rows](./sample-rows.md).
- `offset` skips from the current row order, so combine it with a deterministic
  [Sort](./sort-rows.md) for stable paging.

## See also

- [Sort rows](./sort-rows.md) · [Sample rows](./sample-rows.md)
