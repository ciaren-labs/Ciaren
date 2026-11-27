---
title: Bin column
search: bin column bucket cut quantile equalwidth bands labels histogram
description: Bucket a numeric column into equal-width or quantile bins in Ciaren. Configure labels and compare the generated pandas and Polars code.
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

This example bins `amount` into four equal-width bands named `amount_band`, using the default method and labels.

### pandas

```python
df_2 = df_1.assign(amount_band=pd.cut(df_1['amount'], bins=4).astype('string'))
```

### Polars

```python
_lo, _hi = df_1['amount'].min(), df_1['amount'].max()
_breaks = [_lo + (_hi - _lo) / 4 * i for i in range(1, 4)]
df_2 = df_1.with_columns(pl.col('amount').cut(_breaks).cast(pl.Utf8).alias('amount_band'))
```

## Tips & common mistakes

- **`equalwidth` vs `quantile`:** equal-width splits the value range into equal
  spans (uneven counts); quantile splits into equal-sized groups (uneven spans).
- **How quantile edges work:** the edges are the 1/`bins`, 2/`bins`, …
  quantiles of the non-null values, and the lowest and highest bins are open
  ended. A value equal to an edge goes into the lower bin. When ties make two
  edges equal, the bin between them stays empty and the other bins keep their
  labels, so a label can go unused. A column whose values are all equal lands
  in the first bin. Nulls stay null. Both engines and both exports put every
  row in the same bin.
- **Custom `labels` must match the bin count** (one label per bin); the node
  rejects any other count before it runs.
- **Default labels show the bin edges** and each engine formats them its own
  way, for example `(-inf, 100.0]` on pandas and `(-inf, 100]` on Polars. Set
  `labels` when a later step depends on the text.
- The result is a text/category column — feed it into
  [Group by + aggregate](./group-by-aggregate.md) to count per band.

## See also

- [Round numbers](./round-numbers.md) · [Conditional column](./conditional-column.md)
