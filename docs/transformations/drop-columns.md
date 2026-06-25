---
title: Drop columns
search: drop columns remove delete column field
description: Remove one or more columns from the frame
---

# Drop columns — `dropColumns`

Remove one or more columns.

## Use cases

- Strip internal IDs, scratch columns, or PII before sharing or saving.
- Slim a wide frame down before a join or export.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `columns` | string[] | Yes | Columns to remove |

## Generated Python code

```python
df_2 = df_1.drop(columns=['internal_id', 'temp_notes'])
```

## Tips & common mistakes

- **To keep a few columns, invert the operation** with [Select columns](./select-columns.md)
  instead of listing everything you don't want.
- Dropping a column other nodes downstream reference will surface as a validation
  error when you run the flow.

## See also

- [Select columns](./select-columns.md) · [Rename columns](./rename-columns.md)
