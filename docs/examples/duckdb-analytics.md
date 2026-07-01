---
title: DuckDB Analytics
description: Read from and write to a DuckDB database in a visual flow — push a query down to DuckDB, transform the result, and land it back in a table.
search: example duckdb sql analytics connection query local database olap parquet
---

# DuckDB Analytics

DuckDB is a fast, in-process analytical (OLAP) database — perfect for local
analytics on files and tables. In Ciaren, DuckDB is available as a **SQL
connection**, so you can read from it with a **SQL Input** node, transform the
result on the canvas, and write back with a **SQL Output** node.

:::tip DuckDB is a connector, not the run engine
Your flow still executes on Ciaren's dataframe engine (**polars** by default, or
pandas). DuckDB is the *source/sink* — a great place to keep analytical tables and
to push heavy filtering/joins down to before the data reaches the canvas.
:::

**You'll use:** SQL Input (DuckDB) → Filter Rows → Group by + Aggregate →
SQL Output (DuckDB).

<FlowPipeline :nodes='[
  {"type":"input","label":"SQL Input","detail":"DuckDB · query mode"},
  {"type":"clean","label":"Filter Rows","detail":"amount > 0"},
  {"type":"transform","label":"Group By + Aggregate","detail":"region · sum(amount)"},
  {"type":"output","label":"SQL Output","detail":"DuckDB · revenue_by_region"}
]' :vertical="true" />

## 1. Create a DuckDB connection

Install the driver and add a connection:

```bash
pip install duckdb
```

On the **Connections** page, choose **DuckDB**, and point it at a database file
(for example `analytics.duckdb`). Use the connection's **Test** action to confirm
it works. See [Database Connections](/guide/connections) for the full walkthrough.

## 2. Build the flow

1. **SQL Input** — select your DuckDB connection. Use **query mode** to push work
   down to DuckDB:

   ```sql
   SELECT region, amount, ordered_at
   FROM orders
   WHERE ordered_at >= '2024-01-01'
   ```

   Or use **table mode** with `table: "orders"` to read the whole table.
2. **Filter Rows** — `column: "amount"`, `operator: ">"`, `value: 0`.
3. **Group by + Aggregate** — `group_by: ["region"]`,
   `aggregations: { "amount": "sum" }`.
4. **SQL Output** — select the same DuckDB connection, `table: "revenue_by_region"`,
   `if_exists: "replace"` (or `append` to grow the table each run).

Preview at each step, then **Run**. Re-running with `if_exists: replace` refreshes
the summary table; pair it with a [schedule](/guide/scheduling) for a daily refresh.

## Why push down to DuckDB?

- **Read less.** A `WHERE`/`JOIN` in query mode means DuckDB does the heavy lifting
  and only the rows you need cross into the flow.
- **Keep results queryable.** Writing back to a DuckDB table makes the output
  instantly available to BI tools, notebooks, or another flow.
- **Stay local.** DuckDB runs in-process — no server to manage, no data leaving
  your machine.

## Exported Python

Click **Export → Python**. The SQL nodes generate standard SQLAlchemy / pandas
reads and writes against your DuckDB database, and the transforms export as polars
or pandas — a standalone script you can run on a schedule or in CI.

## Next steps

- [Database Connections](/guide/connections) — all supported databases and storage
- [SQL Input](/transformations/sql-input) · [SQL Output](/transformations/sql-output)
- [Engines (polars / pandas)](/guide/engines)
