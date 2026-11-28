---
title: Sales Data Analysis
description: "Ciaren example: clean a messy sales CSV and summarize revenue by region with Drop Nulls, Filter Rows, Replace Values and Group By Aggregate, then export Python."
search: example sales analysis group by aggregate clean revenue region refunds
---

# Sales Data Analysis

You have an order export with a few problems in it and you want one number per
region: total revenue and order count. This walkthrough cleans the six-row
sample, collapses it to three rows with **Group By Aggregate**, and exports the
flow as a pandas or polars script.

**You'll use:** File Input → Drop Columns → Change Types → Drop Nulls →
Filter Rows → Replace Values (twice) → Fill Nulls → Group By Aggregate →
Rename Columns → Sort Rows → File Output.

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"sales.csv"},
  {"type":"clean","label":"Drop Columns","detail":"internal_note"},
  {"type":"clean","label":"Change Types","detail":"amount → float · ordered_at → datetime"},
  {"type":"clean","label":"Drop Nulls","detail":"subset: amount"},
  {"type":"clean","label":"Filter Rows","detail":"amount > 0 (drops refunds)"},
  {"type":"clean","label":"Replace Values","detail":"region: north → North, south → South"},
  {"type":"clean","label":"Fill Nulls","detail":"region → Unknown"},
  {"type":"transform","label":"Group By Aggregate","detail":"region · sum(amount) · count(order_id)"},
  {"type":"clean","label":"Rename Columns","detail":"amount → total_sales · order_id → num_orders"},
  {"type":"clean","label":"Sort Rows","detail":"total_sales, descending"},
  {"type":"output","label":"File Output","detail":"sales_summary.csv"}
]' :vertical="true" />

## Sample data

Save this as `sales.csv`, or [download sales.csv](/samples/sales-analysis/sales.csv),
and upload it on the **Datasets** page:

```csv
order_id,region,amount,ordered_at,internal_note
1001,North,120.50,2024-01-03,batch-a
1002,south,89.00,2024-01-03,batch-a
1003,North,,2024-01-04,batch-b
1004,South,-5.00,2024-01-04,refund
1005,,42.25,2024-01-05,batch-b
1006,north,210.00,2024-01-06,batch-c
```

Five things need fixing before the numbers are trustworthy:

- `internal_note` is an internal column that should not reach the summary.
- Order 1003 has no amount.
- Order 1004 is a refund (`-5.00`), not revenue.
- Order 1005 has no region.
- `north` and `south` are lowercase, so they would form their own groups.

## Build the flow

1. **File Input**: set **File type** to CSV and pick the `sales.csv` dataset.
2. **Drop Columns**: **Columns to drop** = `internal_note`.
3. **Change Types**: under **Casts**, set `amount` → `float` and
   `ordered_at` → `datetime`. Leave **On bad values** at *Raise an error* so a
   malformed amount stops the run instead of silently turning into null.
4. **Drop Nulls**: **Subset** = `amount`. This removes order 1003. Limit the
   subset to `amount`, or the row with no region would be dropped too.
5. **Filter Rows**: **Column** `amount`, **Operator** *> greater than*,
   **Value** `0`. The node keeps the rows where the condition is true, so the
   refund, order 1004, is dropped.
6. **Replace Values**: **Column** `region`, **Replace** `north`,
   **With** `North`. Add a second **Replace Values** node for `south` → `South`.
   Replace Values matches the whole cell exactly, so each spelling needs its own
   node.
7. **Fill Nulls**: **Strategy** *Constant value*, **Fill value** `Unknown`,
   **Columns** `region`. Order 1005 keeps its revenue under an explicit
   `Unknown` group.
8. **Group By Aggregate**: **Group by columns** = `region`. Under
   **Aggregations**, set `amount` → `sum` and `order_id` → `count`.
9. **Rename Columns**: `amount` → `total_sales`, `order_id` → `num_orders`.
   After the group-by, those columns hold a sum and a count, so the old names
   would mislead.
10. **Sort Rows**: **Sort by columns** `total_sales`, **Order** *Descending*.
11. **File Output**: **File type** CSV, **Dataset name** `sales_summary`.

Select a node to see the live preview of its output, then click **Run**.

:::tip Prefer to describe it?
With a provider key set up, upload the sample data, open a blank flow in the same project and ask the [Flow assistant](/guide/flow-assistant), for example: "clean this sales file, drop refunds and total revenue and orders per region." Review the proposed nodes and settings, then choose **Apply and save**. The manual steps above build the same flow. The assistant never runs a flow, so click **Run** yourself.
:::

## What Group By Aggregate does

Group By Aggregate turns many rows into one row per distinct value of the group
column. Every other column you want to keep needs an aggregation; the result has
only the group columns and the aggregated columns.

![Four cleaned order rows collapse into three region rows: North sums 120.50 and 210.00 into 330.50 with two orders](/illustrations/examples/sales-group-by.svg)

This is also why step 6 matters. Without the two Replace Values nodes, `North`
and `north` are different keys and the summary has four rows.

![Without Replace Values, North and north form separate groups of 120.50 and 210.00 instead of one North group of 330.50](/illustrations/examples/sales-case-split.svg)

## Result

<DataTransform
  transform="Full flow"
  :before='{
    "columns":["order_id","region","amount","ordered_at","internal_note"],
    "rows":[
      [1001,"North",120.50,"2024-01-03","batch-a"],
      [1002,"south",89.00,"2024-01-03","batch-a"],
      [1003,"North",null,"2024-01-04","batch-b"],
      [1004,"South",-5.00,"2024-01-04","refund"],
      [1005,null,42.25,"2024-01-05","batch-b"],
      [1006,"north",210.00,"2024-01-06","batch-c"]
    ]
  }'
  :after='{
    "columns":["region","total_sales","num_orders"],
    "rows":[
      ["North",330.50,2],
      ["South",89.00,1],
      ["Unknown",42.25,1]
    ]
  }'
  :highlight='["total_sales","num_orders"]'
/>

### Check the result

- The output has exactly three rows: `North`, `South`, `Unknown`.
- `total_sales` adds up to 461.75. That is the sum of the four positive amounts
  (120.50 + 89.00 + 42.25 + 210.00); the refund and the missing amount are not
  in it.
- `num_orders` adds up to 4, one per surviving order.

If you see a `north` row, a Replace Values node is missing or misspelled. If the
total is 456.75, the refund got through: check the Filter Rows node.

## Exported Python

Click **Export** in the editor toolbar. The **pandas** tab shows a standalone
script. The input frame is named after the dataset, and consecutive steps fuse
into method chains. The `_filter_value` helper at the top compares the Filter
Rows value, saved as the text `'0'`, as a number because `amount` is numeric.
Fill Nulls is a short loop that fills only the listed columns the value fits:

```python
import pandas as pd

def _filter_value(df, column, value):
    """Type a comparison value like its column: text becomes a number on a numeric column."""
    if isinstance(value, list):
        items = [_filter_value(df, column, v) for v in value]
        # One float makes every item a float: polars types a list by its first item.
        return [float(v) for v in items] if any(isinstance(v, float) for v in items) else items
    numeric = pd.api.types.is_numeric_dtype(df[column]) and not pd.api.types.is_bool_dtype(df[column])
    if not isinstance(value, str) or not numeric:
        return value
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Value {value!r} is not a number, but column {column!r} is numeric.") from None

df_sales = pd.read_csv('sales.csv')

df_sales = (
    df_sales.drop(columns=['internal_note'])
    .assign(amount=lambda _d: _d['amount'].astype('float64'), ordered_at=lambda _d: pd.to_datetime(_d['ordered_at']))
    .dropna(subset='amount')
    .loc[lambda _d: _d['amount'] > _filter_value(_d, 'amount', '0')]
    .assign(region=lambda _d: _d['region'].replace('north', 'North'))
    .assign(region=lambda _d: _d['region'].replace('south', 'South'))
)

df_sales = df_sales.copy()
for _col in ['region']:
    try:
        _fill = pd.array(['Unknown'], dtype=df_sales[_col].dtype)[0]
    except (ValueError, TypeError):
        continue  # the value does not fit this column's type
    df_sales[_col] = df_sales[_col].fillna(_fill)

df_sales = (
    df_sales.groupby('region')
    .agg({'amount': 'sum', 'order_id': 'count'})
    .reset_index()
    .rename(columns={'amount': 'total_sales', 'order_id': 'num_orders'})
    .sort_values('total_sales', ascending=False)
)

df_sales.to_csv('sales_summary.csv', index=False)
```

Run it next to `sales.csv` and `sales_summary.csv` contains the three rows from
the result table. The **polars** tab writes the same file.

## Pitfalls

- **Group By Aggregate drops columns that have no aggregation.** `ordered_at`
  is not in the output because it is neither a group column nor aggregated. Add
  it to **Aggregations** (for example `max`) if you need the latest order date.
- **Drop Nulls with an empty subset checks every column.** Here that would also
  remove order 1005 and its 42.25 of revenue.
- **Count counts non-null values.** `order_id` is never null, so its count is
  the number of orders. Counting a column with gaps gives a smaller number.

## Variations

- **Revenue per region and month:** add **Extract Date Parts** on `ordered_at`
  with the `year` and `month` parts, then add `ordered_at_year` and
  `ordered_at_month` to the group columns. [Time Series Analysis](/examples/time-series)
  walks through this pattern.
- **A daily summary:** attach a [schedule](/guide/scheduling) to run the flow
  every morning.

## Next steps

- [Customer Segmentation](/examples/customer-segmentation)
- [Group By Aggregate reference](/transformations/group-by-aggregate)
- [Transformations Reference](/transformations/overview)
