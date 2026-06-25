---
title: Join
search: join merge left right inner outer on left_on right_on suffixes key
description: Combine two inputs on a key with inner/left/right/outer semantics
---

# Join — `join`

Combine two inputs (`left`, `right`) on a key. Join is one of two multi-input
nodes — connect one upstream node to its **left** handle and another to its
**right** handle.

## Use cases

- Enrich transactions with customer attributes.
- Look up reference data (region names, prices) by key.

## What it does

Join combines the **left** and **right** inputs on a shared key. The `how` parameter
controls which rows survive — `inner` keeps only matches, `left` keeps all rows from
the left input (filling nulls for unmatched right-side columns).

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
| `how` | string | No | `inner` (default), `left`, `right`, `outer` |
| `suffixes` | [string, string] | No | Suffixes for overlapping columns (default `_x`, `_y`) |

Provide either `on` (same key name on both sides) **or** both `left_on` and
`right_on` (different names).

## Generated Python code

```python
df_3 = pd.merge(df_1, df_2, on=['customer_id'], how='left', suffixes=('_x', '_y'))
```

## Tips & common mistakes

- **`how` controls which rows survive:** `inner` keeps matches only; `left`/`right`
  keep all rows from one side; `outer` keeps everything (unmatched cells become
  null).
- **Overlapping non-key columns get `suffixes`.** Rename or drop them upstream to
  avoid `_x`/`_y` columns.
- A shared-key (`on=`) outer join produces a **single** key column (the keys are
  coalesced), matching pandas — verified across both engines.
- Join takes two inputs at a time; chain join nodes to combine three or more.

## See also

- [Union / Concat](./union-concat.md) · [Rename columns](./rename-columns.md)
