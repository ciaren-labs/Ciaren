---
title: Round numbers
search: round numbers decimals precision numeric
description: Round numeric columns to a number of decimal places
---

# Round numbers — `roundNumbers`

Round numeric columns to a number of decimals.

## Use cases

- Tidy currency to 2 decimals before export.
- Reduce noisy precision for display.

## Configuration

| Config key | Type | Required | Description |
|---|---|---|---|
| `columns` | string[] | Yes | Numeric columns to round |
| `decimals` | int | No | Decimal places (default 0) |

## Generated Python code

```python
df_2 = df_1.assign(**{c: df_1[c].round(2) for c in ['amount']})
```

## Tips & common mistakes

- **`decimals: 0` returns floats**, not integers (e.g. `3.0`). Use
  [Cast types](./cast-types.md) → `integer` if you need whole numbers.
- Listing a non-numeric column will error — round only numeric columns.

## See also

- [Cast types](./cast-types.md) · [Bin column](./bin-column.md)
