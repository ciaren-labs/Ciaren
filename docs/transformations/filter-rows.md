---
title: Filter rows
search: filter rows where condition operator between in contains isnull keep
description: Keep only the rows that match a condition
---

# Filter rows — `filterRows`

Keep rows matching a condition.

## Use cases

- Keep only positive amounts, a date range, or a set of categories.
- Drop rows where a key column is null (`isnull`/`notnull`).
- Text matching: `contains`, `startswith`, `endswith`.

## Configuration

| Config key | Type | Required | Description |
|---|---|---|---|
| `column` | string | Yes | Column to test |
| `operator` | string | Yes | See operators below |
| `value` | any | Conditional | Required except for `isnull` / `notnull` |
| `value2` | any | Conditional | Upper bound, required for `between` |

**Operators:** `==`, `!=`, `>`, `>=`, `<`, `<=`, `isnull`, `notnull`,
`between` (needs `value2`), `in` (comma-separated or a list), `contains`,
`startswith`, `endswith`.

Numeric columns accept numeric values; text columns accept strings — the editor
keeps the value type aligned to the column.

## Generated Python code

```python
df_2 = df_1[df_1['amount'] > 0]
```

## Tips & common mistakes

- **`between` needs an upper bound** (`value2`); the form blocks saving without
  it. It's inclusive on both ends.
- **`in` takes a comma-separated list** (`x, z`) or an actual list.
- For multi-condition AND/OR logic that produces a *label* (not just a filter),
  use [Conditional column](./conditional-column.md).

## See also

- [Conditional column](./conditional-column.md) · [Drop nulls](./drop-nulls.md)
