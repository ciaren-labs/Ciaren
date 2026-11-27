---
title: Customer Segmentation
description: "Ciaren example: total each customer's orders, join the totals to the customer list and bucket customers into spending tiers with Group By Aggregate, Join / Merge and Bin Column."
search: example customer segmentation join merge group by bin tiers equal width quantile
---

# Customer Segmentation

You have a customer list and a separate order history, and you want each
customer labelled Bronze, Silver or Gold by how much they spent. The order file
has one row per order, so you total it per customer first, then join the totals
to the customer list and bin them into three tiers.

**You'll use:** two File Inputs → Group By Aggregate → Rename Columns →
Join / Merge → Bin Column → Sort Rows → File Output.

The flow has two branches. The left branch reads and totals the orders; the
right branch is the customer list. They meet at the Join / Merge node.

<ForkJoin
  :left='[
    {"type":"input","label":"File Input","detail":"orders.csv"},
    {"type":"transform","label":"Group By Aggregate","detail":"customer_id · sum(amount) · count(order_id)"},
    {"type":"clean","label":"Rename Columns","detail":"amount → total_spent · order_id → num_orders"}
  ]'
  :right='[
    {"type":"input","label":"File Input","detail":"customers.csv"}
  ]'
  :join='{"label":"Join / Merge","detail":"on: customer_id · how: left"}'
  :after='[
    {"type":"transform","label":"Bin Column","detail":"total_spent → tier, 3 equal-width bins"},
    {"type":"clean","label":"Sort Rows","detail":"total_spent, descending"},
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

Download [customers.csv](/samples/customer-segmentation/customers.csv) and
[orders.csv](/samples/customer-segmentation/orders.csv), then upload both on the
**Datasets** page.

## Build the flow

1. **File Input** (orders): **File type** CSV, dataset `orders.csv`.
2. **Group By Aggregate**: **Group by columns** = `customer_id`. Under
   **Aggregations**, set `amount` → `sum` and `order_id` → `count`. The six
   orders become four rows, one per customer.
3. **Rename Columns**: `amount` → `total_spent`, `order_id` → `num_orders`.
4. **File Input** (customers): **File type** CSV, dataset `customers.csv`.
5. **Join / Merge**: connect the Rename Columns output to the **left** handle
   and the customers input to the **right** handle. Set **Join type** to
   *Left* and **Join on** to `customer_id`. Each customer total now carries the
   customer's name and country.
6. **Bin Column**: **Column** `total_spent`, **New column** `tier`, **Method**
   *Equal width*, **Number of bins** `3`, **Custom labels**
   `Bronze, Silver, Gold`.
7. **Sort Rows**: **Sort by columns** `total_spent`, **Order** *Descending*.
8. **File Output**: **File type** CSV, **Dataset name** `segments`.

Aggregating before the join keeps the join one-to-one: four totals meet four
customers. If you joined the raw orders instead, Ada and Margaret would each
appear twice and you would still need a group-by afterwards.

## How the tiers are cut

With **Equal width**, Bin Column splits the range from the smallest total to the
largest into three bins of the same width. The totals run from 15 to 500, so
each bin is 161.67 wide and the edges sit at 176.67 and 338.33.

![Equal-width bins split the 15 to 500 range at 176.67 and 338.33, putting Linus and Ada in Bronze, Margaret in Silver and Grace in Gold](/illustrations/examples/segmentation-equal-width.svg)

One large customer stretches the range. Grace's 500 makes the Gold bin start at
338.33, so Margaret's 250, the second-highest total, lands in Silver.

## Result

<DataTransform
  transform="Full flow"
  :before='{
    "columns":["order_id","customer_id","amount"],
    "rows":[
      [5001,1,40.00],[5002,1,60.00],[5003,2,500.00],
      [5004,3,15.00],[5005,4,220.00],[5006,4,30.00]
    ]
  }'
  :after='{
    "columns":["customer_id","total_spent","num_orders","name","country","tier"],
    "rows":[
      [2,500.00,1,"Grace","US","Gold"],
      [4,250.00,2,"Margaret","US","Silver"],
      [1,100.00,2,"Ada","UK","Bronze"],
      [3,15.00,1,"Linus","FI","Bronze"]
    ]
  }'
  :highlight='["total_spent","num_orders","tier"]'
/>

The left input's columns come first, then the customer columns, then the new
`tier` column.

### Check the result

- Four rows, one per customer, and no empty `name`: every `customer_id` in the
  orders matched a customer.
- `num_orders` adds up to 6 and `total_spent` adds up to 865.00, the same as
  the order file.
- The tiers are Gold, Silver, Bronze, Bronze from top to bottom.

An empty `name` means an order references a customer that is not in
`customers.csv`. A *Left* join keeps that row so you can spot it; an *Inner*
join would drop it silently.

## Exported Python

Click **Export** in the editor toolbar and open the **pandas** tab:

```python
import pandas as pd

df_orders = pd.read_csv('orders.csv')
df_customers = pd.read_csv('customers.csv')

df_orders = (
    df_orders.groupby('customer_id')
    .agg({'amount': 'sum', 'order_id': 'count'})
    .reset_index()
    .rename(columns={'amount': 'total_spent', 'order_id': 'num_orders'})
)

df_1 = df_orders.merge(df_customers, on='customer_id', how='left')

df_1 = (
    df_1.assign(tier=pd.cut(df_1['total_spent'], bins=3, labels=['Bronze', 'Silver', 'Gold']).astype('string'))
    .sort_values('total_spent', ascending=False)
)

df_1.to_csv('segments.csv', index=False)
```

Each input frame is named after its dataset. The two branches keep their own
variables (`df_orders`, `df_customers`) because both must exist when `merge`
runs; the join output gets a numbered name, `df_1`. Run the script next to the
two CSV files and `segments.csv` matches the result table. The **polars** tab
computes the same bin edges explicitly and writes the same file.

## Pitfalls

- **Equal width or quantile.** *Equal width* splits the value range evenly, so
  one outlier can leave a bin almost empty. *Quantile* puts roughly the same
  number of customers in each bin instead. Its edges come from the data, and with
  four customers they fall exactly on Ada's and Margaret's totals, so look at the
  preview before you rely on a quantile tier for a sample this small.
- **Labels must match the bin count.** Three bins need exactly three labels,
  listed from the lowest bin to the highest. With two labels for three bins the
  node fails when it runs.
- **Keys with different names.** If the key is `customer_id` on one side and
  `id` on the other, tick **Keys have different names on each side** and set
  **Left key(s)** and **Right key(s)**.

## Next steps

- [Time Series Analysis](/examples/time-series)
- [Join / Merge reference](/transformations/join)
- [Bin Column reference](/transformations/bin-column)
