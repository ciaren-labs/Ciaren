---
title: Join
search: join merge left right inner outer semi anti on left_on right_on suffixes key
description: Combine or filter two inputs with inner/left/right/outer/semi/anti join semantics
---

# Join — `join`

Combine two inputs (`left`, `right`) on a key. Join is one of two multi-input
nodes — connect one upstream node to its **left** handle and another to its
**right** handle.

## Use cases

- Enrich transactions with customer attributes.
- Look up reference data (region names, prices) by key.
- Keep rows whose key exists in another table with a semi join.
- Find rows whose key is missing from another table with an anti join.

## What it does

Join combines the **left** and **right** inputs on a shared key. The `how` parameter
controls which rows survive — `inner` keeps only matches, `left` keeps all rows from
the left input (filling nulls for unmatched right-side columns), `semi` keeps left
rows with a match, and `anti` keeps left rows without a match. Semi and anti joins
return only the left input's columns.

<ForkJoin
  :left='[{"type":"transform","label":"Left input","detail":"orders aggregated by customer_id"}]'
  :right='[{"type":"input","label":"Right input","detail":"customers.csv"}]'
  :join='{"label":"Join","detail":"on: customer_id · how: left"}'
  :after='[{"type":"transform","label":"Enriched result","detail":"transactions + customer name/country"}]'
/>

<DataTransform
  transform="Join (on=customer_id, how=left)"
  :before='{
    "columns":["customer_id","total_spent"],
    "rows":[[1,100],[2,500],[3,15]]
  }'
  :after='{
    "columns":["customer_id","total_spent","name","country"],
    "rows":[
      [1,100,"Ada","UK"],
      [2,500,"Grace","US"],
      [3,15,"Linus","FI"]
    ]
  }'
  :highlight='["name","country"]'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `on` | string \| string[] | Conditional | Key(s) present in both frames |
| `left_on` / `right_on` | string \| string[] | Conditional | Use when key names differ (supply both) |
| `how` | string | No | `inner` (default), `left`, `right`, `outer`, `semi`, `anti` |
| `suffixes` | [string, string] | No | Suffixes for overlapping columns (default `_x`, `_y`) |

Provide either `on` (same key name on both sides) **or** both `left_on` and
`right_on` (different names).

## Generated Python code

```python
df_3 = df_1.merge(df_2, on='customer_id', how='left')
```

## Tips & common mistakes

- **`how` controls which rows survive:** `inner` keeps matches only; `left`/`right`
  keep all rows from one side; `outer` keeps everything (unmatched cells become
  null); `semi` keeps matching left rows; and `anti` keeps non-matching left rows.
- **Semi and anti joins return exactly the left columns.** Duplicate keys on the
  right do not duplicate left rows.
- **Null keys match null keys** in semi and anti joins. Ciaren enables this
  explicitly in Polars so pandas and Polars produce the same rows.
- **Overlapping non-key columns get `suffixes`.** Rename or drop them upstream to
  avoid `_x`/`_y` columns.
- A shared-key (`on=`) outer join produces a **single** key column (the keys are
  coalesced), matching pandas — verified across both engines.
- Join takes two inputs at a time; chain join nodes to combine three or more.

## See also

- [Union / Concat](./union-concat.md) · [Rename columns](./rename-columns.md)
