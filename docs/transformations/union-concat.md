---
title: Stack Rows with Concat and Schema Alignment
search: union concat stack append rows combine multiple inputs variadic concat rows
description: Stack Ciaren inputs in connection order with Concat Rows. Align different schemas, preserve duplicate rows, and compare pandas and Polars exports.
---

# Concat Rows (Union / Concat) — `concatRows`

Stack multiple inputs row-wise (no config). This is the variadic node — connect
**two or more** upstream nodes to its input handle and they're concatenated in
order.

## Use cases

- Combine monthly files into one dataset.
- Append a new batch to an existing one before further cleaning.

## What it does

Stacks all connected inputs row-wise in connection order. Column alignment happens
by name: inputs with different schemas produce null for missing columns.

<DataTransform
  transform="Union / Concat (Input A + Input B stacked)"
  :before='{
    "columns":["region","amount"],
    "rows":[["North",100],["South",80]]
  }'
  :after='{
    "columns":["region","amount"],
    "rows":[["North",100],["South",80],["East",150],["West",90]]
  }'
/>

:::tip
The **Before** pane above shows Input A; the **After** pane shows the stacked result
after appending Input B (`East/150`, `West/90`). Connect as many inputs as you need.
:::

## Configuration

This node has **no configuration** — it stacks whatever inputs are connected.

## Generated Python code

These exports stack `df_1` then `df_2` with no configuration. Columns align by name;
missing fields become null and numeric types can be relaxed. Both duplicate rows and
source connection order are retained. The upstream inputs and the engine alias must
already be defined.

### pandas

```python
df_3 = pd.concat([df_1, df_2], ignore_index=True)
```

### Polars

```python
df_3 = pl.concat([df_1, df_2], how='diagonal_relaxed')
```

## Tips & common mistakes

- **Align columns first.** Inputs with different column names produce sparse rows
  (missing columns become null) — use [Rename columns](./rename-columns.md) /
  [Select columns](./select-columns.md) to match schemas.
- Concat stacks **rows**; to combine *columns* on a key use [Join](./join.md).
- Use [Remove duplicates](./remove-duplicates.md) afterward if sources overlap.

## See also

- [Join](./join.md) · [Remove duplicates](./remove-duplicates.md)
