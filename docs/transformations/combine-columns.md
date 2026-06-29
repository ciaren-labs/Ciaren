---
title: Combine columns
search: combine concatenate columns join merge text separator full name
description: Join several columns into one text column with a separator
---

# Combine columns — `combineColumns`

Join several columns into one text column, separated by a separator. The inverse
of [Split column](./split-column.md).

## Use cases

- Build a full name from `first` + `last`.
- Make a composite key like `region-year`.
- Assemble an address from street / city / zip.

## What it does

Each selected column is cast to text and joined left-to-right with the separator.
Null cells become empty strings, so the separator's position is preserved
(`"a" + null + "c"` → `"a||c"` with separator `|`).

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `columns` | string[] | Yes | Columns to combine (≥ 2), in order |
| `new_column` | string | Yes | Name of the combined column |
| `separator` | string | No | Text between values (default a single space) |
| `keep_original` | boolean | No | Keep the source columns (default true) |

## Generated Python code

```python
df_2 = df_1.assign(**{"full_name": df_1[["first", "last"]].astype("string").fillna("").apply(" ".join, axis=1).astype("string")})
```

## Tips & common mistakes

- **Order matters** — columns are joined in the order you pick them.
- Turn off **keep original** to drop the source columns once combined.

## See also

- [Split column](./split-column.md) · [Coalesce columns](./coalesce-columns.md)
