---
title: Select columns
search: select columns keep reorder subset project
description: Keep only the listed columns and reorder them
---

# Select columns — `selectColumns`

Keep only the listed columns (and reorder them).

## Use cases

- Produce a tidy output with just the columns that matter, in a chosen order.
- Reduce a wide frame to the few columns a downstream step needs.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `columns` | string[] | Yes | Columns to keep, in order |

## Generated Python code

```python
df_2 = df_1[['region', 'amount']]
```

## Tips & common mistakes

- **Order matters** — the output columns follow the order you list them in.
- To drop just a couple of columns from a wide frame, use
  [Drop columns](./drop-columns.md) instead.

## See also

- [Drop columns](./drop-columns.md) · [Rename columns](./rename-columns.md)
