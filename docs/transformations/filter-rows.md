---
title: Filter rows
search: filter rows where condition operator between in contains isnull keep
description: Filter Ciaren dataframe rows with comparisons, text or null checks. Configure a condition and compare pandas and Polars exports.
---

# Filter rows — `filterRows`

Keep rows matching a condition.

## Use cases

- Keep only positive amounts, a date range, or a set of categories.
- Drop rows where a key column is null (`isnull`/`notnull`).
- Text matching: `contains`, `startswith`, `endswith`.

## What it does

Rows that **match** the condition are kept; everything else is dropped. The number
of columns does not change.

<DataTransform
  transform="Filter rows (amount > 0)"
  :before='{
    "columns":["order_id","region","amount"],
    "rows":[
      [1001,"North",120.5],[1002,"South",-5.0],[1003,"North",89.0],[1004,"South",0.0]
    ]
  }'
  :after='{
    "columns":["order_id","region","amount"],
    "rows":[
      [1001,"North",120.5],[1003,"North",89.0]
    ]
  }'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `column` | string | Yes | Column to test |
| `operator` | string | Yes | See operators below |
| `value` | any | Conditional | Required except for `isnull` / `notnull` |
| `value2` | any | Conditional | Upper bound, required for `between` |

**Operators:** `==`, `!=`, `>`, `>=`, `<`, `<=`, `isnull`, `notnull`,
`between` (needs `value2`), `in` (comma-separated or a list), `contains`,
`startswith`, `endswith`.

The editor saves the value as text. When the flow runs, the value is compared in
the column's type: on a numeric column `100` and `99.5` are compared as numbers,
and on a text column `02134` stays the text `02134`. On a numeric column, a
value that is not a number, such as `abc`, stops the run with an error that
names the value and the column. The `between` bounds and each `in` item follow
the same rule. The text operators (`contains`, `startswith`, `endswith`) always
compare text.

## Generated Python code

This example keeps rows where `amount > 0` (`column: amount`, `operator: >`, `value: 0`). Zero, negative and missing amounts are excluded.

The value typed in the editor is the text `'0'`, and the exported script does
not know the column types in advance. A value that looks like a number goes
through a small `_filter_value` helper, defined once at the top of the script,
that applies the rule above when the script runs.

### pandas

```python
df_2 = df_1.loc[lambda _d: _d['amount'] > _filter_value(_d, 'amount', '0')]
```

### Polars

```python
df_2 = df_1.filter(pl.col('amount') > _filter_value(df_1, 'amount', '0'))
```

Other text needs no helper: `status == paid` exports as
`_d['status'] == 'paid'` and `pl.col('status') == 'paid'`. A value stored as a
number in the flow file (`"value": 0`) exports as `_d['amount'] > 0` and
`pl.col('amount') > 0`.

## Tips & common mistakes

- **`between` needs an upper bound** (`value2`); the form blocks saving without
  it. It's inclusive on both ends.
- **`in` takes a comma-separated list** (`x, z`) or an actual list.
- For multi-condition AND/OR logic that produces a *label* (not just a filter),
  use [Conditional column](./conditional-column.md).

## See also

- [Conditional column](./conditional-column.md) · [Drop nulls](./drop-nulls.md)
