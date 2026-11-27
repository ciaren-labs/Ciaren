---
title: Convert Excel to Parquet
description: Convert one sheet of an Excel (.xlsx) workbook to a Parquet file in Ciaren with File Input and File Output, choose the sheet at upload, and check the column types. Includes the pandas and Polars export.
search: recipe convert excel xlsx to parquet columnar file format sheet workbook types
---

# Convert Excel to Parquet

You have an Excel workbook and want a Parquet file that other tools can read
with its column types. Excel stores a type per cell; Parquet stores one type
per column, so each column gets a single type on the way. It takes two nodes.

**You'll use:** [File Input](/transformations/file-input) →
[File Output](/transformations/file-output).

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"orders.xlsx · Excel"},
  {"type":"output","label":"File Output","detail":"orders · Parquet"}
]' />

## Sample data

Download <a href="/samples/recipes/orders.xlsx" download>orders.xlsx</a>. It has two sheets. The
first, `Summary`, holds one note. The second, `Orders`, holds the data. `zip` is
stored as a number with the cell format `00000`, so Excel shows `02134`:

| order_id | order_date | amount | zip |
| --- | --- | --- | --- |
| ORD-1 | 2024-01-05 | 250.00 | 02134 |
| ORD-2 | 2024-01-06 | 99.99 | 10001 |
| ORD-3 | 2024-01-09 | 100.00 | 94105 |

## Steps

1. On **Datasets**, open **Import options** and set **Excel sheet (name or
   0-based index)** to `Orders`. Then upload `orders.xlsx`. Ciaren imports one
   sheet per upload: without this setting it takes the first sheet, `Summary`.
2. In a new flow, add **File Input**. Set **File type** to Excel and **Dataset**
   to `orders.xlsx`. The Dataset list only shows uploads of the selected file
   type.
3. Add **File Output**. Set **File type** to Parquet (.parquet) and **Dataset
   name** to `orders`. Connect the two nodes and click **Run**.
4. Open the run from **Runs** to download `orders`.

![A workbook with a Summary sheet and an Orders sheet: only the named sheet becomes the dataset, and the Parquet file stores one type per column, with the zip that Excel shows as 02134 stored as the number 2134](/illustrations/recipes/excel-one-sheet.svg)

## Result

`orders.parquet` has 3 rows and these column types:

| Column | Type in Parquet | First value |
| --- | --- | --- |
| `order_id` | text | ORD-1 |
| `order_date` | datetime | 2024-01-05 00:00:00 |
| `amount` | decimal (float) | 250.0 |
| `zip` | integer | 2134 |

## Check the result

Save the flow, click **Preview** and click **Run preview** on the File Input
node. You should see 3 rows and the columns `order_id`, `order_date`, `amount`
and `zip`. A single `note` column means the `Summary` sheet was imported:
upload the file again with the sheet set.

## Pitfalls

- **Re-uploading adds a version.** Uploading `orders.xlsx` again creates
  version 2 of the dataset, and the File Input stays pinned to version 1. Pick
  the new version in its **Version** field.
- **Cell formats are not imported.** The `00000` format only changes how
  Excel displays the zip, so Ciaren reads the number `2134`, in runs and in both
  exports. To keep the leading zero, store the code as text in Excel (type
  `'02134`). Text cells stay text in runs and in both exports, and a column
  that mixes text and number cells becomes a text column.
- **Dates gain a time.** An Excel date becomes a datetime at midnight.
- **One sheet per dataset.** Every upload of `orders.xlsx` becomes a version
  of the same dataset. To convert a second sheet as well, upload a copy of the
  workbook under another file name with that sheet set.

## Exported Python

Click **Export** in the editor toolbar. The **pandas** and **polars** tabs show
this code for the flow. It reads the original `orders.xlsx`, including the
sheet you chose at upload, and writes `orders.parquet`. The pandas version
needs `openpyxl` and `pyarrow`; the Polars version needs `openpyxl`.

::: code-group

```python [pandas]
import pandas as pd

df_orders = pd.read_excel('orders.xlsx', dtype=object, sheet_name='Orders')
# Columns with any text cell stay text (zip codes, IDs keep leading zeros).
df_orders = df_orders.apply(lambda col: col.where(col.isna(), col.astype(str)) if col.apply(isinstance, args=(str,)).any() else col.infer_objects())
df_orders.to_parquet('orders.parquet', index=False)
```

```python [Polars]
import polars as pl

df_orders = pl.read_excel('orders.xlsx', engine="openpyxl", sheet_name='Orders')
df_orders.write_parquet('orders.parquet')
```

:::

To go the other way, use a File Input with **File type** Parquet and a File
Output with **File type** Excel (.xlsx) or CSV (.csv).

## See also

- [File Input](/transformations/file-input)
- [File Output](/transformations/file-output)
- [Recipes](/recipes/overview)
