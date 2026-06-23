---
title: Split column
search: split column delimiter regex into capture groups expand
description: Split one text column into several, by delimiter or regex capture groups
---

# Split column — `splitColumn`

Split one text column into several columns, by a literal delimiter or by regex
capture groups.

## Use cases

- Split a full name into `first` / `last`.
- Break a code like `A-100` into its parts with a regex.

## Configuration

| Config key | Type | Required | Description |
|---|---|---|---|
| `column` | string | Yes | Text column to split |
| `mode` | string | No | `delimiter` (default) or `regex` |
| `delimiter` | string | Conditional | Delimiter to split on (required for `delimiter` mode) |
| `pattern` | string | Conditional | Regex; capture group 1 → first column, etc. (required for `regex` mode) |
| `into` | string[] | Yes | Names for the resulting columns, in order |
| `keep_original` | bool | No | Keep the source column (default `true`) |

## Generated Python code

```python
_parts = df_1['name'].astype('string').str.split(' ', expand=True, regex=False)
df_2 = df_1.assign(**{'first': _parts[0], 'last': _parts[1]})
```

## Tips & common mistakes

- **`into` names the outputs in order.** In regex mode, capture group 1 fills the
  first name, group 2 the second, and so on.
- **Uneven splits** leave trailing columns null when a row has fewer parts.
- Set `keep_original: false` to drop the source column after splitting.

## See also

- [String transform](./string-transform.md) · [Extract date parts](./extract-date-parts.md)
