---
title: Filter Rows with Boolean Expressions
search: filter expression query boolean multi condition and or keep rows
description: Filter Ciaren rows with boolean expressions combining columns, comparisons and arithmetic. Compare exact pandas and eager Polars exports.
---

# Filter by expression — `filterExpression`

Keep rows where a boolean expression evaluates to true. Unlike
[Filter rows](./filter-rows.md) (one column, one operator), this handles several
conditions combined with `and` / `or` in a single expression.

## Use cases

- Multi-column filters: `amount > 100 and status == 'paid'`.
- Ranges and combinations: `score >= 0.8 or manual_review == True`.
- Arithmetic conditions: `revenue - cost > 0`.

## What it does

The expression is evaluated per row with pandas `eval` semantics — the same
syntax as [Calculated column](./calculated-column.md) — and only rows where it is
true are kept. The result behaves identically on the pandas and polars engines.
Column count is unchanged; the row index is reset.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `expression` | string | Yes | A boolean expression over the columns |

Reference columns by name; use `and` / `or` / `not`, comparisons (`==`, `!=`,
`>`, `>=`, `<`, `<=`), and arithmetic (`+ - * /`).

### Build condition helper

Above the `expression` textarea, the config panel also has an optional
**Build condition** mini-form: pick a column, an operator, and a value, then
click **AND** or **OR** to append the resulting condition onto whatever is
already in the expression. It's purely a convenience for constructing the
expression string one piece at a time — it doesn't add any config of its own,
and you can ignore it and type the expression by hand instead.

## Generated Python code

These exports keep only rows with `amount > 100` and `status == "paid"`. The Polars export uses eager frames and evaluates the mask through pandas, so it also requires pandas and PyArrow.

### pandas

```python
df_2 = df_1.query("amount > 100 and status == 'paid'").reset_index(drop=True)
```

### Polars

```python
# the filter expression uses pandas eval semantics (needs pandas + pyarrow installed)
df_2 = df_1.filter(pl.Series(df_1.to_pandas().eval("amount > 100 and status == 'paid'")).cast(pl.Boolean))
```

## Tips & common mistakes

- **Use `==` for equality** (not `=`), and quote text values: `status == 'paid'`.
- For a single simple condition, [Filter rows](./filter-rows.md) is quicker.
- To produce a *label* from conditions instead of filtering, use
  [Conditional column](./conditional-column.md).

## See also

- [Filter rows](./filter-rows.md) · [Calculated column](./calculated-column.md) · [Conditional column](./conditional-column.md)
