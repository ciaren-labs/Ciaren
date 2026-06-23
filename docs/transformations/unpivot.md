---
title: Unpivot
search: unpivot melt wide long reshape id_vars value_vars var_name value_name
description: Reshape wide to long with pandas melt
---

# Unpivot — `unpivot`

Reshape wide → long (pandas `melt`).

## Use cases

- Turn `Jan`/`Feb`/… columns back into `month` + `value` rows.
- Normalize a wide spreadsheet into a tidy, tall format for grouping.

## Configuration

| Config key | Type | Required | Description |
|---|---|---|---|
| `id_vars` | string[] | Yes | Columns to keep as identifiers |
| `value_vars` | string[] | No | Columns to unpivot (defaults to the rest) |
| `var_name` | string | No | Name for the variable column (default `variable`) |
| `value_name` | string | No | Name for the value column (default `value`) |

## Generated Python code

```python
df_2 = df_1.melt(id_vars=['region'], value_vars=None, var_name='variable', value_name='value')
```

## Tips & common mistakes

- **Leave `value_vars` empty** to unpivot every column that isn't an `id_var`.
- Name `var_name`/`value_name` meaningfully (e.g. `month`/`amount`) for a tidy
  result.
- To go the other way (long → wide), use [Pivot](./pivot.md).

## See also

- [Pivot](./pivot.md) · [Group by + aggregate](./group-by-aggregate.md)
