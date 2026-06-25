---
title: Remove duplicates
search: remove duplicates dedupe drop_duplicates keep first last subset unique
description: Drop duplicate rows, optionally keying on a subset of columns
---

# Remove duplicates — `removeDuplicates`

Drop duplicate rows.

## Use cases

- Collapse exact duplicate records.
- Keep one row per key (e.g. one row per `customer_id`) by choosing a `subset`.

## What it does

With `subset: ["email"]`, any two rows sharing the same email are considered
duplicates and only the first is kept.

<DataTransform
  transform="Remove duplicates (subset=email, keep=first)"
  :before='{
    "columns":["email","name","score"],
    "rows":[
      ["grace@example.com","Grace H",92],
      ["ada@example.com","Ada L",88],
      ["grace@example.com","Grace Hop",95],
      ["linus@example.com","Linus T",74]
    ]
  }'
  :after='{
    "columns":["email","name","score"],
    "rows":[
      ["grace@example.com","Grace H",92],
      ["ada@example.com","Ada L",88],
      ["linus@example.com","Linus T",74]
    ]
  }'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `subset` | string[] | No | Only consider these columns when deciding duplicates |
| `keep` | string \| false | No | `first` (default), `last`, or `false` (drop all duplicates) |

## Generated Python code

```python
df_2 = df_1.drop_duplicates(keep='first')
```

## Tips & common mistakes

- **`subset` controls "duplicate by what".** Without it, two rows must match on
  *every* column to count as duplicates.
- **`keep: false` drops every copy** of a duplicated row — use it to find rows
  that are truly unique.
- Pair with [Sort rows](./sort-rows.md) first when `keep: first`/`last` should
  pick a specific record per key.

## See also

- [Sort rows](./sort-rows.md) · [Group by + aggregate](./group-by-aggregate.md)
