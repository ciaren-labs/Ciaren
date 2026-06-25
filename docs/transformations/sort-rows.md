---
title: Sort rows
search: sort rows order ascending descending na_position multi-column
description: Sort by one or more columns, with per-column direction and null placement
---

# Sort rows — `sortRows`

Sort by one or more columns.

## Use cases

- Order results by amount, date, or rank for presentation or export.
- Set up row order before [Limit rows](./limit-rows.md) (top-N) or a
  [Window function](./window-function.md).

## What it does

Reorders rows by the chosen keys. Multiple keys resolve ties: the first column
is primary, subsequent ones are tie-breakers.

<DataTransform
  transform="Sort rows (columns=[amount], ascending=false)"
  :before='{
    "columns":["region","amount"],
    "rows":[["North",80],["South",150],["East",30],["West",120]]
  }'
  :after='{
    "columns":["region","amount"],
    "rows":[["South",150],["West",120],["North",80],["East",30]]
  }'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `columns` | string[] | Yes | Sort keys (in priority order) |
| `ascending` | bool \| bool[] | No | Default `true`; pass a list for per-column direction |
| `na_position` | string | No | `last` (default) or `first` |

## Generated Python code

```python
df_2 = df_1.sort_values(by=['amount'], ascending=False)
```

## Tips & common mistakes

- **Per-column direction:** pass an `ascending` list the same length as
  `columns` (e.g. sort by region ascending, amount descending).
- Window functions order *within* their own `order_by`, so you don't need a
  separate sort just to feed one.

## See also

- [Limit rows](./limit-rows.md) · [Window function](./window-function.md)
