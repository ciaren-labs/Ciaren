---
title: Calculated column
search: calculated column expression eval compute derived arithmetic formula
description: Add a column computed from an arithmetic expression over existing columns
---

# Calculated column — `calculatedColumn`

Add a column computed from an expression over existing columns.

## Use cases

- Derive `total = price * quantity` or `margin = revenue - cost`.
- Build a ratio or percentage from two columns.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `column_name` | string | Yes | New column name |
| `expression` | string | Yes | Arithmetic expression, e.g. `price * quantity` |

The editor offers formula templates that fill the expression from your upstream
column names.

## Generated Python code

```python
df_2 = df_1.assign(**{'total': df_1.eval('price * quantity')})
```

## Tips & common mistakes

- **Arithmetic expressions only** (column names, numbers, `+ - * /`,
  parentheses). For if/else logic use [Conditional column](./conditional-column.md);
  for ranks/running totals use [Window function](./window-function.md).
- Reference columns by their exact name; quote names with spaces per pandas
  `eval` rules.

## See also

- [Conditional column](./conditional-column.md) · [Window function](./window-function.md)
