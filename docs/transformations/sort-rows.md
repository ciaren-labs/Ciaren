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

## Configuration

| Config key | Type | Required | Description |
|---|---|---|---|
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
