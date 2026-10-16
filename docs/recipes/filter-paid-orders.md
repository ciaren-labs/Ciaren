---
title: Filter Paid Orders with Two Conditions
description: Keep only paid orders of 100 or more in Ciaren by combining two conditions in Filter by expression, and export runnable pandas or Polars.
search: recipe filter paid orders two conditions and amount status expression boundary pandas polars
---

# Filter Paid Orders with Two Conditions

Keep only the orders that are paid **and** worth at least 100. A
[Filter rows](/transformations/filter-rows) node checks one column at a time;
[Filter by expression](/transformations/filter-expression) combines both
conditions in a single expression.

**You'll use:** [File Input](/transformations/file-input) →
[Filter by expression](/transformations/filter-expression) →
[File Output](/transformations/file-output).

## Steps

1. Upload your orders CSV on **Datasets** and select it in **File Input**.
2. Add **Filter by expression** and set
   `expression: amount >= 100 and status == 'paid'`.
3. Preview the node. An order of exactly 100 stays because `>=` includes the
   boundary; an unpaid order stays out even when its amount is high.
4. Connect **File Output**, choose CSV or Parquet, and run the flow.

## Before / after

The input has four orders: one unpaid, and paid orders below, exactly at and
above 100. Only the two orders that meet both conditions remain.

### Before

| order_id | amount | status | Kept? |
| --- | --- | --- | --- |
| `ORD-1001` | 250.00 | `pending` | No: not paid |
| `ORD-1002` | 99.99 | `paid` | No: below 100 |
| `ORD-1003` | 100.00 | `paid` | Yes: `>=` includes 100 |
| `ORD-1004` | 180.50 | `paid` | Yes |

The **Kept?** column explains each row; it is not part of the data.

### After

| order_id | amount | status |
| --- | --- | --- |
| `ORD-1003` | 100.00 | `paid` |
| `ORD-1004` | 180.50 | `paid` |

## Exported Python

These runnable examples use the same configuration. The transformation lines
come from Ciaren's code generators, and both examples keep only `ORD-1003` and
`ORD-1004`.

### pandas

```python
import pandas as pd

df_1 = pd.DataFrame({
    'order_id': ['ORD-1001', 'ORD-1002', 'ORD-1003', 'ORD-1004'],
    'amount': [250.0, 99.99, 100.0, 180.5],
    'status': ['pending', 'paid', 'paid', 'paid'],
})
df_2 = df_1.query("amount >= 100 and status == 'paid'").reset_index(drop=True)
print(df_2)
```

### Polars

```python
import polars as pl

df_1 = pl.DataFrame({
    'order_id': ['ORD-1001', 'ORD-1002', 'ORD-1003', 'ORD-1004'],
    'amount': [250.0, 99.99, 100.0, 180.5],
    'status': ['pending', 'paid', 'paid', 'paid'],
})
# the filter expression uses pandas eval semantics (needs pandas + pyarrow installed)
df_2 = df_1.filter(pl.Series(df_1.to_pandas().eval("amount >= 100 and status == 'paid'")).cast(pl.Boolean))
print(df_2)
```

The Polars export uses eager frames and evaluates the expression with pandas
`eval`, so it keeps the same rows as the pandas export. `to_pandas()` needs
pandas and PyArrow installed alongside Polars, even though the script does not
import pandas itself.

## Tips

- Use `==` for equality and quote text values: `status == 'paid'`.
- Use `amount > 100` instead to exclude an order of exactly 100.
- Text matches exactly: `Paid`, or `paid` followed by a trailing space, does
  not match `'paid'`. Normalize the column first, for example with
  [Clean Messy Text](/recipes/clean-messy-text).
- A row with a missing `amount` or `status` does not meet both conditions, so
  it is removed.
- For a single condition, [Filter rows](/transformations/filter-rows) is
  quicker.

## See also

- [Filter by expression](/transformations/filter-expression)
- [Filter rows](/transformations/filter-rows)
- [Recipes](/recipes/overview)
