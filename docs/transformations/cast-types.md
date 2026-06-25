---
title: Cast types
search: cast types dtype convert integer float boolean string datetime coerce
description: Convert column data types, with optional coercion and datetime format
---

# Cast types — `castDtypes`

Convert column data types.

## Use cases

- Turn numbers read as text (`"42"`) into real integers/floats for math.
- Parse a date column into a real `datetime` so sorting and
  [Extract date parts](./extract-date-parts.md) work.
- Coerce a dirty column, sending unparseable values to null instead of failing.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `casts` | object | Yes | `{ "col": "dtype" }` — dtype is `integer`, `float`, `boolean`, `string`, or `datetime` |
| `format` | string | No | datetime parse format (e.g. `%Y-%m-%d`) |
| `errors` | string | No | `raise` (default) or `coerce` (invalid → null) |

## Generated Python code

```python
df_2 = df_1.assign(**{'amount': df_1['amount'].astype('float64')})
df_2 = df_2.assign(**{'ordered_at': pd.to_datetime(df_2['ordered_at'])})
```

## Tips & common mistakes

- **Use `coerce` for dirty data.** With `errors: raise` (the default), a single
  unparseable value fails the whole run; `coerce` turns bad values into null.
- **Give datetimes a `format`** when the layout is unambiguous (e.g. `%m-%Y`) —
  it's faster and avoids mis-parsing day/month order.
- For text-to-date parsing across several columns at once, see
  [Parse dates](./parse-dates.md).

## See also

- [Parse dates](./parse-dates.md) · [Fill nulls](./fill-nulls.md)
