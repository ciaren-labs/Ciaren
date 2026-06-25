---
title: Sales Data Analysis
description: Clean raw sales data and summarize revenue by region
search: example sales analysis group by aggregate clean
---

# Sales Data Analysis

A common first task: take a messy export of orders and turn it into a clean
revenue summary by region. This walkthrough cleans the data, then groups and
aggregates it.

**You'll use:** CSV Input → Drop Columns → Cast Types → Drop Nulls → Filter Rows →
Fill Nulls → Group by + Aggregate → Rename → Sort → CSV Output.

## Sample data

Save this as `sales.csv` and upload it on the **Datasets** page:

```csv
order_id,region,amount,ordered_at,internal_note
1001,North,120.50,2024-01-03,batch-a
1002,south,89.00,2024-01-03,batch-a
1003,North,,2024-01-04,batch-b
1004,South,-5.00,2024-01-04,refund
1005,,42.25,2024-01-05,batch-b
1006,north,210.00,2024-01-06,batch-c
```

Notice the problems: an internal column we don't want, mixed-case regions, a
missing amount, a negative (refund) amount, and a missing region.

## Build the flow

1. **CSV Input** — select the `sales.csv` dataset.
2. **Drop Columns** — `columns: ["internal_note"]`.
3. **Cast Types** — `casts: { "amount": "float", "ordered_at": "datetime" }`.
4. **Drop Nulls** — `subset: ["amount"]` (drop rows with no amount).
5. **Filter Rows** — `column: "amount"`, `operator: ">"`, `value: 0` (drop refunds).
6. **Replace Values** — tidy region casing, e.g. `column: "region"`,
   `to_replace: "north"`, `value: "North"` (add a second node for `"south" → "South"`).
7. **Fill Nulls** — `strategy: "constant"`, `value: "Unknown"`, `columns: ["region"]`.
8. **Group by + Aggregate** — `group_by: ["region"]`,
   `aggregations: { "amount": "sum", "order_id": "count" }`.
9. **Rename Columns** — `mapping: { "amount": "total_sales", "order_id": "num_orders" }`.
10. **Sort Rows** — `columns: ["total_sales"]`, `ascending: false`.
11. **CSV Output** — `path: "sales_summary.csv"`.

Use the **live preview** after each node to watch the data take shape, then
**Run** the flow.

## Exported Python

Click **Export → Python**. The generated pandas script is standalone:

```python
import pandas as pd

df_1 = pd.read_csv("sales.csv")
df_2 = df_1.drop(columns=['internal_note'])
df_3 = df_2.assign(**{'amount': df_2['amount'].astype('float64')})
df_3 = df_3.assign(**{'ordered_at': pd.to_datetime(df_3['ordered_at'])})
df_4 = df_3.dropna(subset=['amount'])
df_5 = df_4[df_4['amount'] > 0]
df_6 = df_5.assign(**{'region': df_5['region'].replace('north', 'North')})
df_7 = df_6.assign(**{'region': df_6['region'].replace('south', 'South')})
df_8 = df_7.assign(**{c: df_7[c].fillna('Unknown') for c in ['region']})
df_9 = df_8.groupby(['region']).agg({'amount': 'sum', 'order_id': 'count'}).reset_index()
df_10 = df_9.rename(columns={'amount': 'total_sales', 'order_id': 'num_orders'})
df_11 = df_10.sort_values(by=['total_sales'], ascending=False)
df_11.to_csv("sales_summary.csv", index=False)
```

FlowFrame also generates the **polars** equivalent — pick whichever you prefer.

## Result

| region | total_sales | num_orders |
| -------- | ------------- | ------------ |
| North | 330.50 | 2 |
| South | 89.00 | 1 |

(The refund and the missing-amount rows were filtered out; the row with no region
became `Unknown`.)

## Variations

- Want revenue **per day**? Add **Extract Date Parts** on `ordered_at` and group
  by the new `ordered_at_day` column.
- Want a recurring summary? Attach a [schedule](/guide/scheduling) to run this
  flow every morning.

## Next steps

- [Customer Segmentation](/examples/customer-segmentation)
- [Transformations Reference](/transformations/overview)
