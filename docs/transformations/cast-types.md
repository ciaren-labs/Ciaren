---
title: Change types
search: cast types change types dtype convert integer float boolean string datetime coerce
description: Convert column data types, with optional coercion and datetime format
---

# Change types — `castDtypes`

Convert column data types.

## Use cases

- Turn numbers read as text (`"42"`) into real integers/floats for math.
- Parse a date column into a real `datetime` so sorting and
  [Extract date parts](./extract-date-parts.md) work.
- Coerce a dirty column, sending unparseable values to null instead of failing.

## What it does

Rewrites the column values to the target type. With `errors: coerce`, rows with
unparseable values become null rather than crashing the run.

<DataTransform
  transform="Change types (amount→float errors=coerce, ordered_at→datetime)"
  :before='{
    "columns":["order_id","amount","ordered_at"],
    "rows":[
      [1001,"120.5","2024-01-03"],[1002,"bad","2024-01-04"],[1003,"89.0","2024-01-05"]
    ]
  }'
  :after='{
    "columns":["order_id","amount","ordered_at"],
    "rows":[
      [1001,120.5,"2024-01-03"],[1002,null,"2024-01-04"],[1003,89.0,"2024-01-05"]
    ]
  }'
/>

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
