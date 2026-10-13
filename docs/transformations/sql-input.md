---
title: Read SQL Tables and Queries with Both Engines
search: sql input database table query connection live read postgres mysql mongo
description: Read live SQL tables and queries in Ciaren. Compare exact pandas and Polars exports, runnable SQLite examples and PostgreSQL secret references.
---

# SQL input — `sqlInput`

Read rows **live** from a database at run time, via a reusable
[Connection](/guide/connections). Because the read happens on every run,
scheduled flows always process **fresh data**.

During a Ciaren run, SQL sources are materialized to Parquet before the engine
executes the flow. The portable examples below read the database directly.

<FlowPipeline
  :nodes='[
    {"type":"input","label":"SQL Input","detail":"orders table — live DB"},
    {"type":"clean","label":"Filter Rows","detail":"status = shipped"},
    {"type":"transform","label":"Group By","detail":"revenue by region"},
    {"type":"output","label":"File Output","detail":"daily report"}
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

These separate SQL Input → File Output flows read live rows and write local
`result.parquet`. The PostgreSQL example preserves `table: orders`, with a `postgresql`
connection using user `reader`, host `host`, port `5432`, database `shop` and secret
reference `PG_PASSWORD`. It needs a reachable configured database, the original table,
the secret in your environment and the PostgreSQL driver (`ciaren[postgres]`). SQLite
examples instead use your local `warehouse.db`: table mode reads all `orders`, while
query mode selects positive amounts ordered by `id`. Use Ciaren and its file-format
dependencies; Polars exports are eager. These scripts do not create Ciaren run records
or managed input snapshots.

### pandas

#### PostgreSQL

```python
import os
import pandas as pd
from sqlalchemy import URL, create_engine

_engine_1 = create_engine(URL.create('postgresql+psycopg', username='reader', host='host', port=5432, database='shop', password=os.environ['PG_PASSWORD']))
df_orders = pd.read_sql_table('orders', _engine_1)
df_orders.to_parquet('result.parquet', index=False)
```

#### Table

```python
import os
import pandas as pd
from sqlalchemy import URL, create_engine

_engine_1 = create_engine(URL.create('sqlite', database='warehouse.db'))
df_orders = pd.read_sql_table('orders', _engine_1)
df_orders.to_parquet('result.parquet', index=False)
```

#### Query

```python
import os
import pandas as pd
from sqlalchemy import URL, create_engine

_engine_1 = create_engine(URL.create('sqlite', database='warehouse.db'))
df_1 = pd.read_sql_query('SELECT id, name, amount FROM orders WHERE amount > 0 ORDER BY id', _engine_1)
df_1.to_parquet('result.parquet', index=False)
```

### Polars

#### PostgreSQL

```python
import os
import polars as pl
from sqlalchemy import URL, create_engine

_engine_1 = create_engine(URL.create('postgresql+psycopg', username='reader', host='host', port=5432, database='shop', password=os.environ['PG_PASSWORD']))
df_orders = pl.read_database('SELECT * FROM orders', _engine_1.connect())
df_orders.write_parquet('result.parquet')
```

#### Table

```python
import os
import polars as pl
from sqlalchemy import URL, create_engine

_engine_1 = create_engine(URL.create('sqlite', database='warehouse.db'))
df_orders = pl.read_database('SELECT * FROM orders', _engine_1.connect())
df_orders.write_parquet('result.parquet')
```

#### Query

```python
import os
import polars as pl
from sqlalchemy import URL, create_engine

_engine_1 = create_engine(URL.create('sqlite', database='warehouse.db'))
df_1 = pl.read_database('SELECT id, name, amount FROM orders WHERE amount > 0 ORDER BY id', _engine_1.connect())
df_1.write_parquet('result.parquet')
```

## Tips & common mistakes

- **Passwords are never embedded.** Exported code resolves the secret at
  runtime from its reference scheme — `os.environ[...]` for a bare name or
  `env:NAME`, `keyring.get_password(...)` for `keyring:NAME` (recommended on
  desktop), or a `file:/path` read for a mounted secret file. See
  [Connections](/guide/connections) for the full scheme list.
- **Test the connection first.** Use the connection's *Test* action to confirm
  credentials and reachability before wiring it into a flow.
- **Review exported connection settings.** The current generators do not
  automatically carry node `schema` or driver-specific connection `options`.
  Add required schema, TLS or other provider settings to the exported calls.
- **Exports run as normal Python.** Ciaren's connector path restrictions, read
  limits and error scrubbing are not included in the script. Review its target
  and SQL before running it under your own account.
- **MongoDB differs from SQL.** Collection reads work through the runtime
  connector; these SQLAlchemy exports do not implement MongoDB collection reads.

## See also

- [Database Connections](/guide/connections) — create and manage connections
- [SQL output](./sql-output.md)
- [Connections API](/api/connections)
