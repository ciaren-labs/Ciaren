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

## What it does

Only the listed columns change; all others pass through untouched.

<DataTransform
  transform="Rename columns (amt→amount, Cust ID→customer_id, ord_dt→ordered_at)"
  :before='{
    "columns":["amt","Cust ID","ord_dt"],
    "rows":[[120.5,1001,"2024-01-01"],[89.0,1002,"2024-01-02"]]
  }'
  :after='{
    "columns":["amount","customer_id","ordered_at"],
    "rows":[[120.5,1001,"2024-01-01"],[89.0,1002,"2024-01-02"]]
  }'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
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
