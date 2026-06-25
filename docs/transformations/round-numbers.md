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

## What it does

Rounds each value in the target columns to `decimals` decimal places in place.

<DataTransform
  transform="Round numbers (columns=[price, tax], decimals=2)"
  :before='{
    "columns":["item","price","tax"],
    "rows":[["Widget",12.34567,1.23456],["Gadget",7.89012,0.78901]]
  }'
  :after='{
    "columns":["item","price","tax"],
    "rows":[["Widget",12.35,1.23],["Gadget",7.89,0.79]]
  }'
  :highlight='["price","tax"]'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
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
