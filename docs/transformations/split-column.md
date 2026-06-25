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

## What it does

Splits the source column on the delimiter (or regex capture groups) and writes
one new column per name in `into`. Rows with fewer parts leave trailing columns null.

<DataTransform
  transform="Split column (column=full_name, delimiter=space, into=[first, last])"
  :before='{
    "columns":["id","full_name"],
    "rows":[[1,"Ada Lovelace"],[2,"Grace Hopper"],[3,"Linus Torvalds"]]
  }'
  :after='{
    "columns":["id","full_name","first","last"],
    "rows":[
      [1,"Ada Lovelace","Ada","Lovelace"],
      [2,"Grace Hopper","Grace","Hopper"],
      [3,"Linus Torvalds","Linus","Torvalds"]
    ]
  }'
  :highlight='["first","last"]'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
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
