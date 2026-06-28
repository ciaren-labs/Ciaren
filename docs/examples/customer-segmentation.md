---
title: Customer Segmentation
description: Join customers with orders and group them into spending tiers
search: example customer segmentation join group by bin tiers
---

# Customer Segmentation

Group customers into spending tiers by combining two files: a customer list and
an order history. This shows off **Join**, **Group by + Aggregate**, and
**Bin Column**.

**You'll use:** two CSV Inputs → Group by + Aggregate → Rename → Join → Bin Column
→ Sort → File Output.

The key pattern here is a **fork-join**: two separate CSV inputs feed into a single
Join node. The left branch aggregates orders first; the right branch is the raw
customer list.

<ForkJoin
  :left='[
    {"type":"input","label":"CSV Input","detail":"orders.csv"},
    {"type":"transform","label":"Group By + Aggregate","detail":"sum amount, count orders per customer"},
    {"type":"clean","label":"Rename Columns","detail":"amount→total_spent · order_id→num_orders"}
  ]'
  :right='[
    {"type":"input","label":"CSV Input","detail":"customers.csv"}
  ]'
  :join='{"label":"Join","detail":"on: customer_id · how: left"}'
  :after='[
    {"type":"transform","label":"Bin Column","detail":"total_spent → tier (Bronze/Silver/Gold)"},
    {"type":"clean","label":"Sort Rows","detail":"total_spent desc"},
    {"type":"output","label":"File Output","detail":"segments.csv"}
  ]'
/>

## Sample data

`customers.csv`:

```csv
customer_id,name,country
1,Ada,UK
2,Grace,US
3,Linus,FI
4,Margaret,US
```

`orders.csv`:

```csv
order_id,customer_id,amount
5001,1,40.00
5002,1,60.00
5003,2,500.00
5004,3,15.00
5005,4,220.00
5006,4,30.00
```

Upload both on the **Datasets** page.

## Build the flow

1. **CSV Input** (orders) — select `orders.csv`.
2. **Group by + Aggregate** — `group_by: ["customer_id"]`,
   `aggregations: { "amount": "sum", "order_id": "count" }`. One row per customer
   with their total spend and order count.
3. **Rename Columns** — `mapping: { "amount": "total_spent", "order_id": "num_orders" }`.
4. **CSV Input** (customers) — select `customers.csv`.
5. **Join** — connect the renamed aggregate to the **left** handle and the
   customers input to the **right** handle. Config: `on: "customer_id"`,
   `how: "left"`.
6. **Bin Column** — `column: "total_spent"`, `new_column: "tier"`, `bins: 3`,
   `method: "quantile"`, `labels: ["Bronze", "Silver", "Gold"]`.
7. **Sort Rows** — `columns: ["total_spent"]`, `ascending: false`.
8. **File Output** — `format: csv` (name `segments`).

## Exported Python

```python
import pandas as pd

df_1 = pd.read_csv("orders.csv")
df_2 = df_1.groupby(['customer_id']).agg({'amount': 'sum', 'order_id': 'count'}).reset_index()
df_3 = df_2.rename(columns={'amount': 'total_spent', 'order_id': 'num_orders'})
df_4 = pd.read_csv("customers.csv")
df_5 = pd.merge(df_3, df_4, on=['customer_id'], how='left', suffixes=('_x', '_y'))
df_6 = df_5.assign(**{'tier': pd.qcut(df_5['total_spent'], q=3, labels=['Bronze', 'Silver', 'Gold'], duplicates='drop').astype('string')})
df_7 = df_6.sort_values(by=['total_spent'], ascending=False)
df_7.to_csv("segments.csv", index=False)
```

## Result

Each customer now has their total spend, order count, and assigned tier.

<DataTransform
  transform="Full pipeline"
  :before='{
    "columns":["order_id","customer_id","amount"],
    "rows":[
      [5001,1,40.00],[5002,1,60.00],[5003,2,500.00],
      [5004,3,15.00],[5005,4,220.00],[5006,4,30.00]
    ]
  }'
  :after='{
    "columns":["customer_id","name","country","total_spent","num_orders","tier"],
    "rows":[
      [2,"Grace","US",500.00,1,"Gold"],
      [4,"Margaret","US",250.00,2,"Silver"],
      [1,"Ada","UK",100.00,2,"Bronze"],
      [3,"Linus","FI",15.00,1,"Bronze"]
    ]
  }'
  :highlight='["total_spent","num_orders","tier"]'
/>

## Tips

- **Quantile vs. equal-width bins.** `quantile` puts roughly equal *counts* of
  customers in each tier; `equalwidth` splits the *value range* evenly. Choose
  based on whether you care about ranking or absolute thresholds.
- **Key names differ?** If the join columns aren't both named `customer_id`, use
  `left_on` and `right_on` on the Join node instead of `on`.

## Next steps

- [Time Series](/examples/time-series)
- [Transformations Reference](/transformations/overview)
