---
title: Split a Column by a Delimiter
description: Split a delimited text field such as EU|Paris into separate region and city columns in Ciaren with Split Column, and see what happens to missing and extra pieces. Includes the pandas and Polars export.
search: recipe split column delimiter csv text separate columns region city pipe pandas polars
---

# Split a Column by a Delimiter

A store list has a `location` field such as `EU|Paris`, and you want separate
`region` and `city` columns. **Split Column** cuts the text at a delimiter and
writes the pieces, in order, into the columns you name.

**You'll use:** [File Input](/transformations/file-input) →
[Split Column](/transformations/split-column) →
[File Output](/transformations/file-output).

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"stores.csv"},
  {"type":"transform","label":"Split Column","detail":"location · | → region, city"},
  {"type":"output","label":"File Output","detail":"stores_split"}
]' />

## Sample data

Save this as `stores.csv`. Store `S3` has no city, `S4` has no location, and
`S5` has a third piece.

```csv
store_id,location
S1,EU|Paris
S2,US|Boston
S3,EU
S4,
S5,US|Austin|TX
```

## Steps

1. On **Datasets**, upload `stores.csv`.
2. In a new flow, add **File Input**. Set **File type** to CSV and **Dataset**
   to `stores.csv`.
3. Add **Split Column** and set:
   - **Column**: `location`.
   - **Split by**: Delimiter.
   - **Delimiter**: click **Pipe**, or type `|`.
   - **New columns**: `region, city`. The first piece goes into the first
     name, the second piece into the second.
   - Leave **Keep the original column** checked, so you can compare each
     result with its source.
4. Add **File Output**. Set **File type** to CSV (.csv) and **Dataset name** to
   `stores_split`. Connect the nodes in order and click **Run**.

## Result

| store_id | location | region | city |
| --- | --- | --- | --- |
| S1 | `EU\|Paris` | EU | Paris |
| S2 | `US\|Boston` | US | Boston |
| S3 | `EU` | EU | null |
| S4 | null | null | null |
| S5 | `US\|Austin\|TX` | US | Austin |

![Split Column fills region and city with the pieces in order: EU has no second piece, so city is null; US|Austin|TX has a third piece with no column, so TX is dropped](/illustrations/recipes/split-column-parts.svg)

## Check the result

Save the flow, click **Preview**, select the Split Column node and click **Run
preview**. `S1` should show `EU` and `Paris`. If `region` holds the whole
`EU|Paris`, the delimiter does not match the data, for example a comma instead
of a pipe.

## Pitfalls

- **Extra pieces are dropped.** `TX` in `US|Austin|TX` has no column, so it is
  not in the output. Add a third name to **New columns** to keep it, and keep
  the original column to spot such rows.
- **Missing pieces become null.** `S3` gets a null `city` rather than an error,
  so check for nulls before you rely on the new column.
- **Spaces stay.** `EU | Paris` gives `"EU "` and `" Paris"`. Add a
  [String Transform](/transformations/string-transform) with **Strip spaces**
  on each new column.
- **Choose a delimiter that only separates.** Splitting people's names on a
  space breaks names with several words.
- **For one row per piece** instead of one column per piece, use
  [Split to Rows](/recipes/one-row-per-tag).

## Exported Python

Click **Export** in the editor toolbar. The **pandas** and **polars** tabs show
this code for the flow. It reads `stores.csv` from the script's folder and
writes `stores_split.csv`.

::: code-group

```python [pandas]
import pandas as pd

df_stores = pd.read_csv('stores.csv')
_parts = df_stores['location'].astype('string').str.split('|', expand=True)
df_stores = df_stores.assign(region=(_parts[0] if 0 in _parts.columns else pd.NA), city=(_parts[1] if 1 in _parts.columns else pd.NA))
df_stores.to_csv('stores_split.csv', index=False)
```

```python [Polars]
import polars as pl

df_stores = pl.read_csv('stores.csv')
df_stores = df_stores.with_columns([pl.col('location').cast(pl.Utf8).str.split('|').list.get(0, null_on_oob=True).alias('region'), pl.col('location').cast(pl.Utf8).str.split('|').list.get(1, null_on_oob=True).alias('city')])
df_stores.write_csv('stores_split.csv')
```

:::

## See also

- [Split Column](/transformations/split-column)
- [One Row per Tag](/recipes/one-row-per-tag)
- [Clean Messy Text](/recipes/clean-messy-text)
- [Recipes](/recipes/overview)
