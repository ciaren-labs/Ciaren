---
title: Bin column
search: bin column bucket cut quantile equalwidth bands labels histogram
description: Bucket a numeric column into labeled bins as a new column
---

# Bin column — `binColumn`

Bucket a numeric column into labeled bins (a new column).

## Use cases

- Turn ages or amounts into bands (`0–18`, `19–35`, …).
- Create quantile buckets (quartiles, deciles) for segmentation.

## What it does

Reads a numeric column and writes a new text column whose values are the bin labels.
`equalwidth` makes bins of equal numeric span; `quantile` makes bins with roughly
equal row counts.

<DataTransform
  transform="Bin column (column=total_spent, bins=3, method=quantile, labels=[Bronze,Silver,Gold])"
  :before='{
    "columns":["name","total_spent"],
    "rows":[
      ["Grace",500],["Margaret",250],["Ada",100],["Linus",15]
    ]
  }'
  :after='{
    "columns":["name","total_spent","tier"],
    "rows":[
      ["Grace",500,"Gold"],["Margaret",250,"Silver"],
      ["Ada",100,"Bronze"],["Linus",15,"Bronze"]
    ]
  }'
  :highlight='["tier"]'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `column` | string | Yes | Numeric column to bin |
| `new_column` | string | Yes | Name of the new bin column |
| `bins` | int | No | Number of bins (≥ 2, default 4) |
| `method` | string | No | `equalwidth` (default) or `quantile` |
| `labels` | string[] | No | Custom labels (one per bin) |

## Generated Python code

```python
df_2 = df_1.assign(amount_band=pd.cut(df_1['amount'], bins=4).astype('string'))
```

## Tips & common mistakes

- **`equalwidth` vs `quantile`:** equal-width splits the value range into equal
  spans (uneven counts); quantile splits into equal-sized groups (uneven spans).
- **Custom `labels` must match the bin count** (one label per bin).
- The result is a text/category column — feed it into
  [Group by + aggregate](./group-by-aggregate.md) to count per band.

## See also

- [Round numbers](./round-numbers.md) · [Conditional column](./conditional-column.md)
