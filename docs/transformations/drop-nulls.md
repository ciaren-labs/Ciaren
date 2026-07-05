---
title: Drop nulls
search: drop nulls missing na dropna how any all subset
description: Remove rows with missing values, optionally only in chosen columns
---

# Drop nulls — `dropNulls`

Remove rows with missing values.

## Use cases

- Discard records that are missing a required field (e.g. no `amount`).
- Drop fully-empty rows while keeping partially-populated ones.

## What it does

Drops rows where the target column(s) are null. With `subset: ["amount"]` only
rows missing an `amount` are removed — rows with other nulls (like `region`) survive.

<DataTransform
  transform="Drop nulls (subset=amount)"
  :before='{
    "columns":["order_id","region","amount"],
    "rows":[
      [1001,"North",120.5],[1002,"South",null],[1003,null,89.0],[1004,"South",42.25]
    ]
  }'
  :after='{
    "columns":["order_id","region","amount"],
    "rows":[
      [1001,"North",120.5],[1003,null,89.0],[1004,"South",42.25]
    ]
  }'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `how` | string | No | `any` (default) drops a row with any null; `all` only if every value is null |
| `subset` | string[] | No | Only consider these columns |

## Generated Python code

```python
df_2 = df_1.dropna(subset='amount')
```

## Tips & common mistakes

- **`how: all` needs a `subset`** to be meaningful row-wise — pair it with the
  columns that define an "empty" row.
- To *keep* rows and fill the gaps instead, use [Fill nulls](./fill-nulls.md).

## See also

- [Fill nulls](./fill-nulls.md) · [Filter rows](./filter-rows.md)
