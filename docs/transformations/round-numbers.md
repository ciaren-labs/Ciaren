---
title: Round numbers
search: round numbers decimals precision numeric
description: Round selected numeric columns in Ciaren to a chosen decimal precision. Preserve other fields and view pandas and Polars exports.
---

# Round numbers — `roundNumbers`

Round numeric columns to a number of decimals.

## Use cases

- Tidy currency to 2 decimals before export.
- Reduce noisy precision for display.

## What it does

Rounds each value in the target columns to `decimals` decimal places in the output.

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

These exports round only `amount` to two decimal places (`columns: ["amount"]`, `decimals: 2`). Other columns remain unchanged; the illustration above rounds `price` and `tax`.

### pandas

```python
df_2 = df_1.round({'amount': 2})
```

### Polars

```python
df_2 = df_1.with_columns(pl.col('amount').round(2))
```

## Tips & common mistakes

- **Rounding a floating-point column keeps it floating point** (e.g. `3.0`
  with `decimals: 0`). Use
  [Change types](./cast-types.md) → `integer` if you need whole numbers.
- Listing a non-numeric column will error — round only numeric columns.

## See also

- [Change types](./cast-types.md) · [Bin column](./bin-column.md)
