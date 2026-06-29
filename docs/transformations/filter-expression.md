---
title: Filter by expression
search: filter expression query boolean multi condition and or keep rows
description: Keep rows where a boolean expression is true
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

## Generated Python code

```python
df_2 = df_1[df_1.eval("amount > 100 and status == 'paid'").astype(bool)].reset_index(drop=True)
```

## Tips & common mistakes

- **Use `==` for equality** (not `=`), and quote text values: `status == 'paid'`.
- For a single simple condition, [Filter rows](./filter-rows.md) is quicker.
- To produce a *label* from conditions instead of filtering, use
  [Conditional column](./conditional-column.md).

## See also

- [Filter rows](./filter-rows.md) · [Calculated column](./calculated-column.md) · [Conditional column](./conditional-column.md)
