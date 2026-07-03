---
title: Sales Data Analysis
description: Clean raw sales data and summarize revenue by region
search: example sales analysis group by aggregate clean
---

# Sales Data Analysis

A common first task: take a messy export of orders and turn it into a clean
revenue summary by region. This walkthrough cleans the data, then groups and
aggregates it.

**You'll use:** CSV Input → Drop Columns → Change Types → Drop Nulls → Filter Rows →
Fill Nulls → Group by + Aggregate → Rename → Sort → File Output.

<FlowPipeline :nodes='[
  {"type":"input","label":"CSV Input","detail":"sales.csv"},
  {"type":"clean","label":"Drop Columns","detail":"remove internal_note"},
  {"type":"clean","label":"Change Types","detail":"amount→float · ordered_at→datetime"},
  {"type":"clean","label":"Drop Nulls","detail":"subset: amount"},
  {"type":"clean","label":"Filter Rows","detail":"amount > 0 (remove refunds)"},
  {"type":"clean","label":"Replace Values","detail":"normalise region casing"},
  {"type":"clean","label":"Fill Nulls","detail":"region → \"Unknown\""},
  {"type":"transform","label":"Group By + Aggregate","detail":"region · sum(amount) · count(order_id)"},
  {"type":"clean","label":"Rename Columns","detail":"amount→total_sales · order_id→num_orders"},
  {"type":"clean","label":"Sort Rows","detail":"total_sales desc"},
  {"type":"output","label":"File Output","detail":"sales_summary.csv"}
]' :vertical="true" />

## Sample data

Save this as `sales.csv` and upload it on the **Datasets** page
(📥 [download sales.csv](/samples/sales-analysis/sales.csv)):

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
3. **Change Types** — `casts: { "amount": "float", "ordered_at": "datetime" }`.
4. **Drop Nulls** — `subset: ["amount"]` (drop rows with no amount).
5. **Filter Rows** — `column: "amount"`, `operator: ">"`, `value: 0` (drop refunds).
6. **Replace Values** — tidy region casing, e.g. `column: "region"`,
   `to_replace: "north"`, `value: "North"` (add a second node for `"south" → "South"`).
7. **Fill Nulls** — `strategy: "constant"`, `value: "Unknown"`, `columns: ["region"]`.
8. **Group by + Aggregate** — `group_by: ["region"]`,
   `aggregations: { "amount": "sum", "order_id": "count" }`.
9. **Rename Columns** — `mapping: { "amount": "total_sales", "order_id": "num_orders" }`.
10. **Sort Rows** — `columns: ["total_sales"]`, `ascending: false`.
11. **File Output** — `format: csv` (name `sales_summary`).

Use the **live preview** after each node to watch the data take shape, then
**Run** the flow.

## Exported Python

Click **Export → Python**. The generated pandas script is standalone — on a
straight chain like this one, every step reuses a single variable:

```python
import pandas as pd

df_1 = pd.read_csv("sales.csv")
df_1 = df_1.drop(columns=['internal_note'])
df_1 = df_1.assign(**{'amount': df_1['amount'].astype('float64')})
df_1 = df_1.assign(**{'ordered_at': pd.to_datetime(df_1['ordered_at'])})
df_1 = df_1.dropna(subset=['amount'])
df_1 = df_1[df_1['amount'] > 0]
df_1 = df_1.assign(**{'region': df_1['region'].replace('north', 'North')})
df_1 = df_1.assign(**{'region': df_1['region'].replace('south', 'South')})
df_1 = df_1.assign(**{c: df_1[c].fillna('Unknown') for c in ['region']})
df_1 = df_1.groupby(['region']).agg({'amount': 'sum', 'order_id': 'count'}).reset_index()
df_1 = df_1.rename(columns={'amount': 'total_sales', 'order_id': 'num_orders'})
df_1 = df_1.sort_values(by=['total_sales'], ascending=[False])
df_1.to_csv("sales_summary.csv", index=False)
```

Ciaren also generates the **polars** equivalent — pick whichever you prefer.

## Result

The pipeline transforms the raw messy CSV into a clean revenue summary.

<DataTransform
  transform="Full pipeline"
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

The refund row (`amount = -5`) and the missing-amount row were filtered out; the
row with no region became `Unknown`.

## Variations

- Want revenue **per day**? Add **Extract Date Parts** on `ordered_at` and group
  by the new `ordered_at_day` column.
- Want a recurring summary? Attach a [schedule](/guide/scheduling) to run this
  flow every morning.

## Next steps

- [Customer Segmentation](/examples/customer-segmentation)
- [Transformations Reference](/transformations/overview)
