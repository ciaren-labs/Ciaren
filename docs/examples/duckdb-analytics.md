---
title: DuckDB Analytics
description: "Ciaren example: read from and write to a local DuckDB file in a visual flow. Push a filter down with SQL Input, finish the summary on the canvas and write it back with SQL Output."
search: example duckdb sql analytics connection query local database olap pushdown
---

# DuckDB Analytics

DuckDB is an analytical database that runs inside your process and keeps its
data in a single local file. In Ciaren it is a **SQL connection**: a
**SQL Input** node reads from it, the canvas transforms the rows, and a
**SQL Output** node writes the result back as a table. This walkthrough
summarizes revenue by region from an `orders` table and stores the summary next
to it in the same file.

:::tip DuckDB is the source and the destination, not the run engine
The flow runs on Ciaren's dataframe engine, pandas or polars, whichever the
run uses.
DuckDB runs the SQL you put in the SQL Input node, before any rows reach the
canvas.
:::

**You'll use:** SQL Input → String Transform → Fill Nulls →
Group By Aggregate → SQL Output.

<FlowPipeline :nodes='[
  {"type":"input","label":"SQL Input","detail":"DuckDB · custom SQL, amount > 0"},
  {"type":"clean","label":"String Transform","detail":"region: title case"},
  {"type":"clean","label":"Fill Nulls","detail":"region → Unknown"},
  {"type":"transform","label":"Group By Aggregate","detail":"region · sum(amount)"},
  {"type":"output","label":"SQL Output","detail":"DuckDB · revenue_by_region, replace"}
]' :vertical="true" />

## 1. Install the driver

DuckDB connections need the `duckdb` package and its SQLAlchemy dialect,
`duckdb-engine`, in the environment Ciaren runs in. The `duckdb` extra
installs both:

```bash
pip install "ciaren[duckdb]"
```

## 2. Create the database file

The example uses the same six orders as [Sales Data Analysis](/examples/sales-analysis).
Save them as `sales.csv`, or [download sales.csv](/samples/sales-analysis/sales.csv):

```csv
order_id,region,amount,ordered_at,internal_note
1001,North,120.50,2024-01-03,batch-a
1002,south,89.00,2024-01-03,batch-a
1003,North,,2024-01-04,batch-b
1004,South,-5.00,2024-01-04,refund
1005,,42.25,2024-01-05,batch-b
1006,north,210.00,2024-01-06,batch-c
```

Load them into a table called `orders` in a new file, `analytics.duckdb`. Run
this Python in the folder that holds `sales.csv`:

```python
import duckdb

con = duckdb.connect("analytics.duckdb")
con.execute("CREATE OR REPLACE TABLE orders AS SELECT * FROM read_csv('sales.csv')")
con.close()
```

DuckDB infers the types: `amount` becomes `DOUBLE` and `ordered_at` becomes
`DATE`. Close the connection before Ciaren opens the file; DuckDB allows only
one process to write to a file at a time.

## 3. Add the connection

On the **Connections** page, click **Add connection**, choose **DuckDB**, and
set **Database file path** to the full path of `analytics.duckdb`. Use the
connection's test action to confirm Ciaren can open it. If the operator has set
`CIAREN_STORAGE_ALLOWED_ROOTS`, the file must be inside one of those
directories. See [Database Connections](/guide/connections) for details.

## 4. Build the flow

1. **SQL Input**: **Connection** = your DuckDB connection, **Source**
   *Custom SQL*:

   ```sql
   SELECT region, amount FROM orders WHERE amount > 0
   ```

   DuckDB applies the filter, so only 4 of the 6 rows reach the canvas: the
   refund fails `amount > 0`, and so does the order with no amount, because a
   comparison with null is not true. To read the whole table instead, pick
   **Source** *Table* and choose `orders`.
2. **String Transform**: **Column** `region`, **Operation**
   *Title Case*. `north` and `south` become `North` and `South`; the
   null region stays null.
3. **Fill Nulls**: **Strategy** *Constant value*, **Fill value** `Unknown`,
   **Columns** `region`.
4. **Group By Aggregate**: **Group by columns** `region`; under
   **Aggregations**, `amount` → `sum`.
5. **SQL Output**: **Connection** = the same DuckDB connection,
   **Target table** `revenue_by_region`, **If table exists** *Replace*.

Preview each node, then click **Run**. Each run rebuilds `revenue_by_region`
from the current `orders`; pair the flow with a [schedule](/guide/scheduling)
for a daily refresh. *Append* adds rows on every run instead, so a rerun would
duplicate the summary.

## Where the work happens

![The WHERE clause runs inside DuckDB, so 4 of the 6 order rows reach the Ciaren canvas, which cleans and groups them into 3 rows written back to the revenue_by_region table](/illustrations/examples/duckdb-pushdown.svg)

Filtering in the query reads fewer rows into the flow. On six rows that does not
matter; on a table with millions of orders it is the difference between moving
the whole table into memory and moving only what you need. Joins and filters
that DuckDB can do belong in the query; steps you want to see and adjust on the
canvas belong in nodes.

## Result

`revenue_by_region` in `analytics.duckdb`:

| region | amount |
| --- | --- |
| North | 330.5 |
| South | 89.0 |
| Unknown | 42.25 |

### Check the result

Ciaren does not keep the file open between runs, so once the run finishes you
can query the new table from Python:

```python
import duckdb

con = duckdb.connect("analytics.duckdb", read_only=True)
print(con.sql("SELECT * FROM revenue_by_region ORDER BY amount DESC").fetchall())
```

It prints `[('North', 330.5), ('South', 89.0), ('Unknown', 42.25)]`, the same
totals as the [Sales Data Analysis](/examples/sales-analysis) example.

## Exported Python

Click **Export** in the editor toolbar and open the **pandas** tab:

```python
import os
import pandas as pd
from sqlalchemy import URL, create_engine

_engine_1 = create_engine(URL.create('duckdb', database='analytics.duckdb'))
df_1 = pd.read_sql_query('SELECT region, amount FROM orders WHERE amount > 0', _engine_1)
df_1 = df_1.assign(region=lambda _d: _d['region'].astype('string').str.title())
df_1 = df_1.copy()
for _col in ['region']:
    try:
        _fill = pd.array(['Unknown'], dtype=df_1[_col].dtype)[0]
    except (ValueError, TypeError):
        continue  # the value does not fit this column's type
    df_1[_col] = df_1[_col].fillna(_fill)
df_1 = df_1.groupby('region').agg({'amount': 'sum'}).reset_index()
df_1.to_sql('revenue_by_region', _engine_1, if_exists='replace', index=False)
```

The `database` value is the path saved in your connection; it appears here as
`analytics.duckdb`. The script needs pandas, SQLAlchemy, `duckdb` and
`duckdb-engine`. Run against the file from step 2, it writes the same three
rows. The **polars** tab reads with `pl.read_database` and writes with
`write_database` to the same table.

## Pitfalls

- **One writer at a time.** If a notebook or the DuckDB CLI holds
  `analytics.duckdb` open for writing, the run cannot open it. Close the other
  connection first.
- **Null comparisons drop rows.** `WHERE amount > 0` removes rows where `amount`
  is null as well. Write `WHERE amount > 0 OR amount IS NULL` if you want to
  keep them for a later step.

## Next steps

- [Database Connections](/guide/connections): every supported database and
  storage provider
- [SQL Input](/transformations/sql-input) · [SQL Output](/transformations/sql-output)
- [Engines (polars / pandas)](/guide/engines)
