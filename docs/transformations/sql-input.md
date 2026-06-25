---
title: SQL input
search: sql input database table query connection live read postgres mysql mongo
description: Read rows live from a database at run time via a reusable connection
---

# SQL input — `sqlInput`

Read rows **live** from a database at run time, via a reusable
[Connection](/guide/connections). Because the read happens on every run,
scheduled flows always process **fresh data**.

<FlowPipeline
  :nodes='[
    {"type":"input","label":"SQL Input","detail":"orders table — live DB"},
    {"type":"clean","label":"Filter Rows","detail":"status = shipped"},
    {"type":"transform","label":"Group By","detail":"revenue by region"},
    {"type":"output","label":"CSV Output","detail":"daily report"}
  ]'
/>

## Use cases

- Run a flow against the current contents of a production table on a schedule.
- Pull a query result (a join or filter computed in the database) into a flow.
- Read from MongoDB by selecting a collection.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | The connection to read from |
| `mode` | string | No | `table` (default) or `query` |
| `table` | string | Conditional | Table name (required in `table` mode) |
| `schema` | string | No | Schema the table lives in |
| `query` | string | Conditional | Custom SQL (required in `query` mode) |

## Generated Python code

```python
import os
from sqlalchemy import create_engine

_engine_1 = create_engine(f"postgresql+psycopg://reader:{os.environ['PG_PASSWORD']}@host:5432/shop")
df_1 = pd.read_sql_table("orders", _engine_1)
```

Each run also snapshots the input to parquet for reproducibility. MongoDB sources
use collection selection (no custom query).

## Tips & common mistakes

- **Passwords come from the environment.** Exported code reads the secret from
  `os.environ` — FlowFrame never stores or embeds it.
- **Test the connection first.** Use the connection's *Test* action to confirm
  credentials and reachability before wiring it into a flow.

## See also

- [Database Connections](/guide/connections) — create and manage connections
- [SQL output](./sql-output.md)
- [Connections API](/api/connections)
