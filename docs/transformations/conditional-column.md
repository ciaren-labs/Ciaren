---
title: Conditional column
search: conditional column case when if elif else rules match all any and or default
description: Build a column from ordered if/elif/else rules, with AND/OR conditions
---

# Conditional column — `conditionalColumn`

Build a column from ordered if/elif/else rules (CASE-WHEN). The **first** matching
rule wins; rows matching none take the default. Each rule can combine several
conditions with **match ALL** (AND) or **match ANY** (OR).

## Use cases

- Grade buckets (`score >= 90 → A`, `>= 70 → B`, else `F`).
- Segment customers on multiple criteria (`age >= 18 AND country == US → us_adult`).
- Flag rows that satisfy *any* of several conditions.

## What it does

Rules are evaluated top to bottom; the **first** match assigns the result. Rows
matching no rule receive the `default` value (or null if none is set).

<DataTransform
  transform="Conditional column: age ≥ 18 AND country = US → us_adult; else → other"
  :before='{
    "columns":["name","age","country"],
    "rows":[
      ["Alice",25,"US"],["Bob",16,"US"],["Carol",30,"UK"]
    ]
  }'
  :after='{
    "columns":["name","age","country","segment"],
    "rows":[
      ["Alice",25,"US","us_adult"],
      ["Bob",16,"US","other"],
      ["Carol",30,"UK","other"]
    ]
  }'
  :highlight='["segment"]'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `new_column` | string | Yes | Name of the column to add |
| `rules` | object[] | Yes | Ordered rules: `{ match, conditions, result }` |
| `default` | any | No | Value when no rule matches |

Each rule's `conditions` is a list of `{ column, operator, value }`, and `match`
is `all` (AND, the default) or `any` (OR). A single-condition rule may also be
written flat as `{ column, operator, value, result }`.

**Condition operators:** `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`,
`startswith`, `endswith`, `isnull`, `notnull`.

## Generated Python code

```python
# rule: age >= 18 AND country == "US" → "us_adult"; default "other"
df_2 = df_1.copy()
df_2['segment'] = 'other'
df_2.loc[(df_2['age'] >= 18) & (df_2['country'] == 'US'), 'segment'] = 'us_adult'
```

## Tips & common mistakes

- **Order matters** — rules are evaluated top to bottom and the first match wins,
  so put the most specific rules first.
- **Numeric vs text values:** compare a numeric column with a number
  (`amount >= 5000`) and a text column with a string — the editor accepts both.
- **`isnull`/`notnull` take no value.**
- For a simple value lookup (no comparisons) use [Map values](./map-values.md);
  to merely *keep* matching rows use [Filter rows](./filter-rows.md).

## See also

- [Map values](./map-values.md) · [Filter rows](./filter-rows.md) · [Calculated column](./calculated-column.md)
