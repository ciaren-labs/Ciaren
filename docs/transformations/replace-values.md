---
title: Replace values
search: replace values substitute regex find to_replace value
description: Substitute values in a column, literally or by regex
---

# Replace values — `replaceValues`

Substitute values in a column.

## Use cases

- Standardize codes (`N` → `North`, `Y`/`N` → `Yes`/`No`).
- Clean stray characters with a regex pattern.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `column` | string | Yes | Column to edit |
| `to_replace` | any | Yes | Value (or regex pattern) to find |
| `value` | any | Yes | Replacement value |
| `regex` | bool | No | Treat `to_replace` as a regex (default `false`) |

## Generated Python code

```python
df_2 = df_1.assign(**{'region': df_1['region'].replace('N', 'North')})
```

## Tips & common mistakes

- **Literal vs regex:** with `regex: false` the whole value must match; with
  `regex: true`, `to_replace` is a pattern and `value` is the substitution.
- To map *many* values to new ones with an optional default, prefer
  [Map values](./map-values.md).

## See also

- [Map values](./map-values.md) · [String transform](./string-transform.md)
