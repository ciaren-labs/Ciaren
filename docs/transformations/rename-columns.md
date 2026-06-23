---
title: Rename columns
search: rename columns mapping old new header
description: Rename columns via an old to new mapping
---

# Rename columns — `renameColumns`

Rename columns via an old → new mapping.

## Use cases

- Normalize messy headers (`amt` → `amount`, `Cust ID` → `customer_id`).
- Align column names across two datasets before a [Join](./join.md) or
  [Union/Concat](./union-concat.md).

## Configuration

| Config key | Type | Required | Description |
|---|---|---|---|
| `mapping` | object | Yes | `{ "old_name": "new_name" }` |

## Generated Python code

```python
df_2 = df_1.rename(columns={'amt': 'amount'})
```

## Tips & common mistakes

- Only listed columns change; everything else passes through untouched.
- Renaming to a name that already exists will collide — rename or drop the
  conflicting column first.

## See also

- [Select columns](./select-columns.md) · [Drop columns](./drop-columns.md)
