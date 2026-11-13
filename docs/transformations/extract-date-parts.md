---
title: Extract Date Parts with pandas and Polars
search: extract date parts year quarter month week day day_of_year weekday hour minute datetime components
description: Extract calendar and time-part columns from a date or datetime column in Ciaren. Compare runnable pandas and Polars exports, ISO weeks, null dates and weekday numbering.
---

# Extract date parts — `extractDateParts`

Add columns for parts of a date/datetime column.

## Use cases

- Add `year`/`month` columns to group sales by period.
- Pull `weekday` or `hour` for time-of-week analysis.

## What it does

Adds one new column per requested part, named `<column>_<part>`. All original
columns are preserved.

<DataTransform
  transform="Extract date parts (column=occurred_at, parts=[year, month])"
  :before='{
    "columns":["event_id","occurred_at","value"],
    "rows":[
      [1,"2024-01-05",10],[2,"2024-02-18",21],[3,"2024-03-01",17]
    ]
  }'
  :after='{
    "columns":["event_id","occurred_at","value","occurred_at_year","occurred_at_month"],
    "rows":[
      [1,"2024-01-05",10,2024,1],
      [2,"2024-02-18",21,2024,2],
      [3,"2024-03-01",17,2024,3]
    ]
  }'
  :highlight='["occurred_at_year","occurred_at_month"]'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `column` | string | Yes | Date/datetime column |
| `parts` | string[] | Yes | Any of `year`, `quarter`, `month`, `week`, `day`, `day_of_year`, `weekday`, `hour`, `minute` |

Each part becomes a new column named `<column>_<part>` (e.g. `ordered_at_year`).

## Generated Python code

Each complete File Input → Extract Date Parts → File Output flow reads `source.csv` and
writes `result.parquet`. The first example keeps the original configuration `column:
ordered_at`, `parts: [year, month]`; the illustration above instead uses `occurred_at`.
The second example requests all nine supported parts. The input dates in these examples
are ISO text; missing values produce missing date parts, and every original field and row
is retained. Pandas coerces invalid text to missing values. Polars can do the same when it
can infer a datetime format from the other rows; if every non-null string is invalid, parse
the column upstream with an explicit format. Put your original CSV beside the script; use
an environment with Ciaren and its file-format dependencies installed. Polars exports here
use eager frames.

### pandas

#### Year month

```python
import pandas as pd

df_source = pd.read_csv('source.csv')
_dt = pd.to_datetime(df_source['ordered_at'], errors='coerce')
df_source = df_source.assign(ordered_at_year=_dt.dt.year, ordered_at_month=_dt.dt.month)
df_source.to_parquet('result.parquet', index=False)
```

#### All parts

```python
import pandas as pd

df_source = pd.read_csv('source.csv')
_dt = pd.to_datetime(df_source['ordered_at'], errors='coerce')
df_source = df_source.assign(ordered_at_year=_dt.dt.year, ordered_at_quarter=_dt.dt.quarter, ordered_at_month=_dt.dt.month, ordered_at_week=_dt.dt.isocalendar().week, ordered_at_day=_dt.dt.day, ordered_at_day_of_year=_dt.dt.dayofyear, ordered_at_weekday=_dt.dt.weekday, ordered_at_hour=_dt.dt.hour, ordered_at_minute=_dt.dt.minute)
df_source.to_parquet('result.parquet', index=False)
```

### Polars

#### Year month

```python
import polars as pl

df_source = pl.read_csv('source.csv')
_sch = df_source.collect_schema()
_dt = (pl.col('ordered_at').str.to_datetime(strict=False) if _sch['ordered_at'] == pl.Utf8 else pl.col('ordered_at').cast(pl.Datetime, strict=False))
df_source = df_source.with_columns([_dt.dt.year().alias('ordered_at_year'), _dt.dt.month().alias('ordered_at_month')])
df_source.write_parquet('result.parquet')
```

#### All parts

```python
import polars as pl

df_source = pl.read_csv('source.csv')
_sch = df_source.collect_schema()
_dt = (pl.col('ordered_at').str.to_datetime(strict=False) if _sch['ordered_at'] == pl.Utf8 else pl.col('ordered_at').cast(pl.Datetime, strict=False))
df_source = df_source.with_columns([_dt.dt.year().alias('ordered_at_year'), _dt.dt.quarter().alias('ordered_at_quarter'), _dt.dt.month().alias('ordered_at_month'), _dt.dt.week().alias('ordered_at_week'), _dt.dt.day().alias('ordered_at_day'), _dt.dt.ordinal_day().alias('ordered_at_day_of_year'), (_dt.dt.weekday() - 1).alias('ordered_at_weekday'), _dt.dt.hour().alias('ordered_at_hour'), _dt.dt.minute().alias('ordered_at_minute')])
df_source.write_parquet('result.parquet')
```

## Tips & common mistakes

- **`weekday` is Monday=0 … Sunday=6** (consistent across pandas and polars
  exports — verified by the parity tests).
- **`week` uses ISO-8601 week numbering** in both pandas and Polars. Weeks
  start on Monday, and week 1 is the first week with a Thursday in the calendar
  year, so dates near New Year can belong to the previous or next ISO week-year.
- The Polars export subtracts one from its native weekday numbering to match
  pandas. For string input, Polars needs to infer a datetime format; if every
  non-null value is invalid, parse the column upstream with an explicit format.
- If the source is text, [Parse dates](./parse-dates.md) or
  [Change types](./cast-types.md) → `datetime` first when you need a chosen
  format or error policy.

## See also

- [Parse dates](./parse-dates.md) · [Change types](./cast-types.md)
