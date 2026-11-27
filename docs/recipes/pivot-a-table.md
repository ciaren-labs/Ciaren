---
title: Pivot a Table
description: "Pivot sales from long to wide in Ciaren with the Pivot Table node: one row per region, one column per month, repeated rows summed, and how the Polars and pandas engines fill empty cells."
search: recipe pivot table long to wide reshape crosstab summary month columns sum missing cells
---

# Pivot a Table

Your sales file has one row per sale, and you want a summary with one row per
region and one column per month. **Pivot Table** turns the values of one column
into new columns and fills each cell by aggregating a value column.

**You'll use:** [File Input](/transformations/file-input) →
[Pivot Table](/transformations/pivot) →
[File Output](/transformations/file-output).

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"sales_long.csv"},
  {"type":"transform","label":"Pivot Table","detail":"region × month · sum of amount"},
  {"type":"output","label":"File Output","detail":"sales_wide"}
]' />

## Sample data

Save this as `sales_long.csv`. North has two January sales, and South has no
February sale.

```csv
region,month,amount
North,Jan,100
North,Feb,120
South,Jan,80
North,Jan,30
```

## Steps

1. On **Datasets**, upload `sales_long.csv`.
2. In a new flow, add **File Input**. Set **File type** to CSV and **Dataset**
   to `sales_long.csv`.
3. Add **Pivot Table** and set:
   - **Index columns**: `region`. Each region becomes one output row.
   - **Columns from**: `month`. Each distinct month becomes a column.
   - **Values from**: `amount`. These values fill the cells.
   - **Aggregation**: `sum`. Rows that land in the same cell are added up.
4. Add **File Output**. Set **File type** to CSV (.csv) and **Dataset name** to
   `sales_wide`. Connect the nodes in order and click **Run**.

![Pivot Table turns month values into columns: the two North January rows, 100 and 30, sum into one cell of 130.0 in the pandas output, and the South February cell, which has no rows, is null on pandas and 0 on Polars](/illustrations/recipes/pivot-cell-placement.svg)

## Result

A new flow runs on pandas, the engine shown in the editor toolbar, and Preview
always uses pandas. The run output is:

| region | Feb | Jan |
| --- | --- | --- |
| North | 120.0 | 130.0 |
| South | null | 80.0 |

pandas sorts the month columns, so `Feb` comes before `Jan`, and the null in
the South row makes both columns decimal.

If you switch the toolbar engine to **polars** before **Run**, the sums are the
same but two details change:

| Engine | Columns | South, Feb | Numbers on this sample |
| --- | --- | --- | --- |
| pandas | `region`, `Feb`, `Jan` (sorted) | null | decimal |
| polars | `region`, `Jan`, `Feb` (first appearance) | `0` | integer |

## Check the result

Save the flow, click **Preview**, select the Pivot Table node and click **Run
preview**. You should see 2 rows and the North `Jan` cell should read 130.0. A
different value means **Aggregation** is not `sum`: `mean` gives 65, `first`
gives 100.

## Pitfalls

- **An empty cell is not always null.** With **Aggregation** `sum` or `count`,
  pandas writes null where no rows exist and Polars writes 0. With `mean`,
  `min`, `max`, `median`, `first` or `last`, both write null. To get 0 on
  every engine, add [Fill Nulls](/transformations/fill-nulls) after the pivot
  with **Strategy** Zero.
- **Column names come from the data.** A month that appears in the next file
  adds a column, and a downstream node that names a missing month fails.
- **Pick the aggregation on purpose.** `sum` adds repeated rows; `mean`
  averages them, which turns North `Jan` into 65.
- **To go from wide back to long**, use [Unpivot](/transformations/unpivot).

## Exported Python

Click **Export** in the editor toolbar. The **pandas** and **polars** tabs show
this code for the flow. It reads `sales_long.csv` from the script's folder and
writes `sales_wide.csv`. Each script keeps its engine's column order and empty
cell value from the table above.

::: code-group

```python [pandas]
import pandas as pd

df_sales_long = pd.read_csv('sales_long.csv')
df_sales_long = df_sales_long.pivot_table(index='region', columns='month', values='amount', aggfunc='sum').reset_index()
df_sales_long.to_csv('sales_wide.csv', index=False)
```

```python [Polars]
import polars as pl

df_sales_long = pl.read_csv('sales_long.csv')
df_sales_long = df_sales_long.pivot(on='month', index='region', values='amount', aggregate_function='sum')
df_sales_long.write_csv('sales_wide.csv')
```

:::

## See also

- [Pivot](/transformations/pivot)
- [Unpivot](/transformations/unpivot)
- [Group by + Aggregate](/transformations/group-by-aggregate)
- [Recipes](/recipes/overview)
