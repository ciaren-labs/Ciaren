---
title: Time Series Analysis
description: "Ciaren example: turn time-stamped events into a monthly summary with Change Types, Extract Date Parts and Group By Aggregate, then add a moving average with Rolling Aggregate."
search: example time series date parts monthly aggregate rolling moving average window temporal
---

# Time Series Analysis

You have one row per event and you want one row per month: the total value, the
number of events, and a two-month moving average to smooth the trend. Ciaren
builds the monthly rows by extracting the year and month from the timestamp and
grouping on them, then adds the moving average with **Rolling Aggregate**.

**You'll use:** File Input → Change Types → Extract Date Parts →
Group By Aggregate → Rename Columns → Sort Rows → Rolling Aggregate →
File Output.

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"events.csv"},
  {"type":"clean","label":"Change Types","detail":"occurred_at → datetime · value → float"},
  {"type":"transform","label":"Extract Date Parts","detail":"adds occurred_at_year, occurred_at_month"},
  {"type":"transform","label":"Group By Aggregate","detail":"year + month · sum(value) · count(event_id)"},
  {"type":"clean","label":"Rename Columns","detail":"value → total_value · event_id → num_events"},
  {"type":"clean","label":"Sort Rows","detail":"year, month ascending"},
  {"type":"transform","label":"Rolling Aggregate","detail":"mean of total_value over 2 rows"},
  {"type":"output","label":"File Output","detail":"monthly_summary.csv"}
]' :vertical="true" />

## Sample data

Save this as `events.csv`, or [download events.csv](/samples/time-series/events.csv),
and upload it on the **Datasets** page:

```csv
event_id,occurred_at,value
1,2024-01-05,10
2,2024-01-20,14
3,2024-02-02,9
4,2024-02-18,21
5,2024-03-01,17
6,2024-03-29,13
```

Six events, two in each of January, February and March 2024.

## Build the flow

1. **File Input**: **File type** CSV, dataset `events.csv`.
2. **Change Types**: under **Casts**, set `occurred_at` → `datetime` and
   `value` → `float`. Extract Date Parts can parse date strings itself, but a
   real datetime column fails loudly on a malformed date here instead of
   producing an empty month later.
3. **Extract Date Parts**: **Date column** `occurred_at`, **Parts to extract**
   `year` and `month`. This adds `occurred_at_year` and `occurred_at_month`.
4. **Group By Aggregate**: **Group by columns** `occurred_at_year`,
   `occurred_at_month`. Under **Aggregations**, set `value` → `sum` and
   `event_id` → `count`. Group on both parts: grouping on month alone would
   merge January 2024 with January 2025.
5. **Rename Columns**: `value` → `total_value`, `event_id` → `num_events`.
6. **Sort Rows**: **Sort by columns** `occurred_at_year`, `occurred_at_month`,
   **Order** *Ascending*.
7. **Rolling Aggregate**: **Target column** `total_value`, **Function**
   *Mean (moving average)*, **Window (rows)** `2`, **Order by**
   `occurred_at_year`, `occurred_at_month`, **New column** `avg_2_months`. Leave
   **Min periods** and **Partition by** empty.
8. **File Output**: **File type** CSV, **Dataset name** `monthly_summary`.

## How the rolling window moves

Rolling Aggregate orders the rows by **Order by**, then, for each row, takes the
mean of that row and the row before it. The window is counted in rows, not in
calendar time, so here two rows means two months only because there is exactly
one row per month.

![A two-row window slides down the monthly table: January has no earlier row and gets null, February averages 24 and 30 to 27, March averages 30 and 30 to 30](/illustrations/examples/timeseries-rolling-window.svg)

January gets null because its window is not full: there is no December row. Set
**Min periods** to `1` if you want January to show 24.0, the mean of the one row
it has.

## Result

<DataTransform
  transform="Full flow"
  :before='{
    "columns":["event_id","occurred_at","value"],
    "rows":[
      [1,"2024-01-05",10],[2,"2024-01-20",14],
      [3,"2024-02-02",9],[4,"2024-02-18",21],
      [5,"2024-03-01",17],[6,"2024-03-29",13]
    ]
  }'
  :after='{
    "columns":["occurred_at_year","occurred_at_month","total_value","num_events","avg_2_months"],
    "rows":[
      [2024,1,24.0,2,null],[2024,2,30.0,2,27.0],[2024,3,30.0,2,30.0]
    ]
  }'
  :highlight='["total_value","num_events","avg_2_months"]'
/>

### Check the result

- Three rows, one per month, in calendar order.
- `num_events` is 2 in every month and adds up to 6, the number of events.
- `total_value` adds up to 84, the sum of the six values.
- `avg_2_months` is empty for January, 27.0 for February and 30.0 for March.

## Exported Python

Click **Export** in the editor toolbar and open the **pandas** tab:

```python
import pandas as pd

df_events = pd.read_csv('events.csv')
df_events = df_events.assign(occurred_at=lambda _d: pd.to_datetime(_d['occurred_at']), value=lambda _d: _d['value'].astype('float64'))
_dt = pd.to_datetime(df_events['occurred_at'], errors='coerce')
df_events = df_events.assign(occurred_at_year=_dt.dt.year, occurred_at_month=_dt.dt.month)

df_events = (
    df_events.groupby(['occurred_at_year', 'occurred_at_month'])
    .agg({'value': 'sum', 'event_id': 'count'})
    .reset_index()
    .rename(columns={'value': 'total_value', 'event_id': 'num_events'})
    .sort_values(['occurred_at_year', 'occurred_at_month'])
    .assign(avg_2_months=lambda _d: _d.sort_values(['occurred_at_year', 'occurred_at_month'], kind='stable')['total_value'].rolling(2).mean())
)

df_events.to_csv('monthly_summary.csv', index=False)
```

Run it next to `events.csv` and `monthly_summary.csv` matches the result table,
with an empty cell for January's average. The rolling step sorts by its own
**Order by** columns, so it gives the same averages even without the Sort Rows
node; Sort Rows is there for the order of the output file.

## Pitfalls

- **A month with no events has no row.** Group By Aggregate only creates rows
  for months that appear in the data. If April had no events, the window for May
  would average May with March.
- **Windows are rows, not days.** On event-level data, a window of 7 is seven
  events, not seven days. Group to one row per day or month first.
- **Set Order by.** Without it, the window follows the incoming row order, which
  may not be chronological.

## Variations

- **Day-of-week pattern:** pick `weekday` in Extract Date Parts and group by
  `occurred_at_weekday` instead.
- **Change from the previous month:** use **Row Difference** on `total_value`,
  ordered by year and month.
- **Separate series per group:** set **Partition by** in Rolling Aggregate (for
  example a `region` column) so each group gets its own moving average.

## Next steps

- [Data Quality Checks](/examples/data-quality)
- [Rolling Aggregate reference](/transformations/rolling-aggregate)
- [Extract Date Parts reference](/transformations/extract-date-parts)
