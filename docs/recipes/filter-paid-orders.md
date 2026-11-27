---
title: Filter Paid Orders with Two Conditions
description: Keep only paid orders of 100 or more in Ciaren by combining two conditions in one Filter by Expression node, including the boundary value. Includes the pandas and Polars export.
search: recipe filter paid orders two conditions and amount status expression boundary pandas polars
---

# Filter Paid Orders with Two Conditions

You want the orders that are paid **and** worth at least 100. A
[Filter Rows](/transformations/filter-rows) node tests one condition;
**Filter by Expression** tests both in one expression and keeps a row only when
the whole expression is true.

**You'll use:** [File Input](/transformations/file-input) →
[Filter by Expression](/transformations/filter-expression) →
[File Output](/transformations/file-output).

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"orders.csv"},
  {"type":"clean","label":"Filter by Expression","detail":"amount ≥ 100 and status paid"},
  {"type":"output","label":"File Output","detail":"paid_orders"}
]' />

## Sample data

Save this as `orders.csv`. It has one unpaid order and paid orders below, at
and above 100.

```csv
order_id,amount,status
ORD-1001,250.00,pending
ORD-1002,99.99,paid
ORD-1003,100.00,paid
ORD-1004,180.50,paid
```

## Steps

1. On **Datasets**, upload `orders.csv`.
2. In a new flow, add **File Input**. Set **File type** to CSV and **Dataset**
   to `orders.csv`.
3. Add **Filter by Expression** and type this into **Expression**:

   ```text
   amount >= 100 and status == 'paid'
   ```

   You can also build it with **Build condition**: pick `amount`,
   **≥ greater or equal** and `100`, click **Use condition**, then pick
   `status`, **= equals** and `paid`, and click **AND**.
4. Add **File Output**. Set **File type** to CSV (.csv) and **Dataset name** to
   `paid_orders`. Connect the nodes in order and click **Run**.

## Result

| order_id | amount | status |
| --- | --- | --- |
| ORD-1003 | 100.00 | paid |
| ORD-1004 | 180.50 | paid |

![Each order is checked against amount >= 100 and status == 'paid'; ORD-1001 fails the status test, ORD-1002 fails the amount test, and ORD-1003 and ORD-1004 pass both](/illustrations/recipes/filter-two-conditions.svg)

`ORD-1003` stays because `>=` includes 100. `ORD-1001` is worth 250 but is not
paid, so `and` drops it.

## Check the result

Save the flow, click **Preview**, select the Filter by Expression node and
click **Run preview**. You should see exactly `ORD-1003` and `ORD-1004`. If
`ORD-1001` appears, the expression uses `or` instead of `and`. If `ORD-1003` is
missing, it uses `>` instead of `>=`.

## Pitfalls

- **Use `==` and quote text.** `status == 'paid'` compares with a text value;
  with a single `=` the node fails.
- **Text must match exactly.** `Paid` or `paid` with a trailing space does not
  equal `'paid'`, so those orders are dropped. Clean the column first, see
  [Clean Messy Text](/recipes/clean-messy-text).
- **Missing values fail the test.** An order with an empty `amount` or `status`
  is dropped, because a comparison with null is false.
- **Use `amount > 100`** if an order of exactly 100 should not count.

## Exported Python

Click **Export** in the editor toolbar. The **pandas** and **polars** tabs show
this code for the flow. It reads `orders.csv` from the script's folder and
writes `paid_orders.csv`.

::: code-group

```python [pandas]
import pandas as pd

df_orders = pd.read_csv('orders.csv')
df_orders = df_orders.query("amount >= 100 and status == 'paid'").reset_index(drop=True)
df_orders.to_csv('paid_orders.csv', index=False)
```

```python [Polars]
import polars as pl

df_orders = pl.read_csv('orders.csv')
# the filter expression uses pandas eval semantics (needs pandas + pyarrow installed)
df_orders = df_orders.filter(pl.Series(df_orders.to_pandas().eval("amount >= 100 and status == 'paid'")).cast(pl.Boolean))
df_orders.write_csv('paid_orders.csv')
```

:::

The expression uses pandas syntax on both engines. The Polars script therefore
converts the frame with `to_pandas()` to evaluate it, which needs pandas and
PyArrow installed next to Polars.

## See also

- [Filter by Expression](/transformations/filter-expression)
- [Filter Rows](/transformations/filter-rows)
- [Recipes](/recipes/overview)
