---
title: Change types
search: cast types change types dtype convert integer float boolean string datetime coerce
description: Convert columns to numbers, booleans, text or dates in Ciaren. Choose strict or invalid-to-null casts; view pandas and Polars exports.
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

These exports convert `amount` to float and `ordered_at` to datetime with the default `errors: raise`. To turn invalid values into nulls, choose `errors: coerce`, as in the illustration above.

### pandas

```python
df_2 = df_1.assign(amount=lambda _d: _d['amount'].astype('float64'), ordered_at=lambda _d: pd.to_datetime(_d['ordered_at']))
```

### Polars

```python
_sch = df_1.collect_schema()
df_2 = df_1.with_columns(pl.col('amount').cast(pl.Float64), (pl.col('ordered_at').str.to_datetime(strict=True) if _sch['ordered_at'] == pl.Utf8 else pl.col('ordered_at').cast(pl.Datetime, strict=True)))
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
