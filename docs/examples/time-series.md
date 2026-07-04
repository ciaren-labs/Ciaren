---
title: Time Series Analysis
description: Aggregate time-stamped data into monthly summaries
search: example time series date parts monthly aggregate temporal
---

# Time Series Analysis

Turn a stream of time-stamped events into a tidy monthly summary. Ciaren does
this by **extracting date parts** and grouping by them.

**You'll use:** CSV Input → Change Types → Extract Date Parts → Group by + Aggregate
→ Rename → Sort → File Output.

<FlowPipeline :nodes='[
  {"type":"input","label":"CSV Input","detail":"events.csv"},
  {"type":"clean","label":"Change Types","detail":"occurred_at→datetime · value→float"},
  {"type":"transform","label":"Extract Date Parts","detail":"adds occurred_at_year, occurred_at_month"},
  {"type":"transform","label":"Group By + Aggregate","detail":"by year+month · sum(value) · count(events)"},
  {"type":"clean","label":"Rename Columns","detail":"value→total_value · event_id→num_events"},
  {"type":"clean","label":"Sort Rows","detail":"year asc, month asc"},
  {"type":"output","label":"File Output","detail":"monthly_summary.csv"}
]' />

::: info Scope
Ciaren aggregates time data by calendar period (year, month, day, weekday,
hour). It does not do rolling windows or `resample`-style smoothing — for those,
export the Python and add a `.rolling(...)` step. See *Next steps* below.
:::

## Sample data

`events.csv`:

```csv
event_id,occurred_at,value
1,2024-01-05,10
2,2024-01-20,14
3,2024-02-02,9
4,2024-02-18,21
5,2024-03-01,17
6,2024-03-29,13
```

Upload it on the **Datasets** page
(📥 [download events.csv](/samples/time-series/events.csv)).

## Build the flow

1. **CSV Input** — select `events.csv`.
2. **Change Types** — `casts: { "occurred_at": "datetime", "value": "float" }`.
3. **Extract Date Parts** — `column: "occurred_at"`, `parts: ["year", "month"]`.
   This adds `occurred_at_year` and `occurred_at_month` columns.
4. **Group by + Aggregate** —
   `group_by: ["occurred_at_year", "occurred_at_month"]`,
   `aggregations: { "value": "sum", "event_id": "count" }`.
5. **Rename Columns** —
   `mapping: { "value": "total_value", "event_id": "num_events" }`.
6. **Sort Rows** — `columns: ["occurred_at_year", "occurred_at_month"]`,
   `ascending: true`.
7. **File Output** — `format: csv` (name `monthly_summary`).

## Exported Python

```python
import pandas as pd

df_1 = pd.read_csv("events.csv")
df_1 = df_1.assign(**{'occurred_at': pd.to_datetime(df_1['occurred_at'])})
df_1 = df_1.assign(**{'value': df_1['value'].astype('float64')})
_dt = pd.to_datetime(df_1['occurred_at'])
df_1 = (
    df_1.assign(**{'occurred_at_year': _dt.dt.year, 'occurred_at_month': _dt.dt.month})
    .groupby(['occurred_at_year', 'occurred_at_month'])
    .agg({'value': 'sum', 'event_id': 'count'})
    .reset_index()
    .rename(columns={'value': 'total_value', 'event_id': 'num_events'})
    .sort_values(by=['occurred_at_year', 'occurred_at_month'], ascending=[True, True])
)
df_1.to_csv("monthly_summary.csv", index=False)
```

## Result

The raw event-level rows are collapsed into monthly summaries. The date column is
split into `year` and `month` so each period becomes its own group key.

<DataTransform
  transform="Full pipeline"
  :before='{
    "columns":["event_id","occurred_at","value"],
    "rows":[
      [1,"2024-01-05",10],[2,"2024-01-20",14],
      [3,"2024-02-02",9],[4,"2024-02-18",21],
      [5,"2024-03-01",17],[6,"2024-03-29",13]
    ]
  }'
  :after='{
    "columns":["occurred_at_year","occurred_at_month","total_value","num_events"],
    "rows":[
      [2024,1,24.0,2],[2024,2,30.0,2],[2024,3,30.0,2]
    ]
  }'
  :highlight='["occurred_at_year","occurred_at_month","total_value","num_events"]'
/>

## Next steps

- **Smoothing / moving averages.** Export the flow and add a rolling window to the
  result, e.g. `df_1['rolling_avg'] = df_1['total_value'].rolling(3).mean()`.
- **Day-of-week patterns.** Add `weekday` to the Extract Date Parts node and group
  by it instead.
- [Data Quality Checks](/examples/data-quality)
