---
title: Write SQL Tables with pandas and Polars
search: sql output database table write connection if_exists append replace
description: Write Ciaren results to SQL tables with replace, append or fail policies. Compare pandas and Polars exports, SQLite examples and secret handling.
---

# SQL output — `sqlOutput`

Write the result to a database table via a reusable
[Connection](/guide/connections).

<FlowPipeline
  :nodes='[
    {"type":"input","label":"SQL Input","detail":"raw orders"},
    {"type":"clean","label":"Drop Nulls"},
    {"type":"transform","label":"Calculated Column","detail":"total = price × qty"},
    {"type":"output","label":"SQL Output","detail":"cleaned_orders — append"}
  ]'
/>

## Use cases

- Land a cleaned dataset into an analytics table on a schedule.
- Append daily results to a growing table, or replace a table each run.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | The connection to write to |
| `table` | string | Yes | Target table |
| `schema` | string | No | Schema to write into |
| `if_exists` | string | No | `replace` (default), `append`, or `fail` |

## Generated Python code

These independent File Input → SQL Output flows read original local `source.csv` and
write `cleaned_orders`. The illustration above instead shows a SQL source, upstream
transforms and an append sink. The PostgreSQL example preserves `if_exists: replace` and
uses the same reader/host/shop connection and `PG_PASSWORD` reference as SQL Input; use
an account with write permission, a reachable database and the PostgreSQL driver
(`ciaren[postgres]`). SQLite examples use local `warehouse.db` and show each overwrite
policy. `replace` replaces the target; `append` adds rows without deduplication; `fail`
raises when the table already exists. Run one example at a time after reviewing the
destination and policy. Polars uses `write_database`, whose SQLAlchemy path also
requires pandas and PyArrow. These complete exports do not create Ciaren run records.

### pandas

#### PostgreSQL

```python
import os
import pandas as pd
from sqlalchemy import URL, create_engine

df_source = pd.read_csv('source.csv')
_engine_1 = create_engine(URL.create('postgresql+psycopg', username='reader', host='host', port=5432, database='shop', password=os.environ['PG_PASSWORD']))
df_source.to_sql('cleaned_orders', _engine_1, if_exists='replace', index=False)
```

#### Replace

```python
import os
import pandas as pd
from sqlalchemy import URL, create_engine

df_source = pd.read_csv('source.csv')
_engine_1 = create_engine(URL.create('sqlite', database='warehouse.db'))
df_source.to_sql('cleaned_orders', _engine_1, if_exists='replace', index=False)
```

#### Append

```python
import os
import pandas as pd
from sqlalchemy import URL, create_engine

df_source = pd.read_csv('source.csv')
_engine_1 = create_engine(URL.create('sqlite', database='warehouse.db'))
df_source.to_sql('cleaned_orders', _engine_1, if_exists='append', index=False)
```

#### Fail

```python
import os
import pandas as pd
from sqlalchemy import URL, create_engine

df_source = pd.read_csv('source.csv')
_engine_1 = create_engine(URL.create('sqlite', database='warehouse.db'))
df_source.to_sql('cleaned_orders', _engine_1, if_exists='fail', index=False)
```

### Polars

#### PostgreSQL

```python
import os
import polars as pl
from sqlalchemy import URL, create_engine

df_source = pl.read_csv('source.csv')
_engine_1 = create_engine(URL.create('postgresql+psycopg', username='reader', host='host', port=5432, database='shop', password=os.environ['PG_PASSWORD']))
df_source.write_database('cleaned_orders', connection=_engine_1, if_table_exists='replace')
```

#### Replace

```python
import os
import polars as pl
from sqlalchemy import URL, create_engine

df_source = pl.read_csv('source.csv')
_engine_1 = create_engine(URL.create('sqlite', database='warehouse.db'))
df_source.write_database('cleaned_orders', connection=_engine_1, if_table_exists='replace')
```

#### Append

```python
import os
import polars as pl
from sqlalchemy import URL, create_engine

df_source = pl.read_csv('source.csv')
_engine_1 = create_engine(URL.create('sqlite', database='warehouse.db'))
df_source.write_database('cleaned_orders', connection=_engine_1, if_table_exists='append')
```

#### Fail

```python
import os
import polars as pl
from sqlalchemy import URL, create_engine

df_source = pl.read_csv('source.csv')
_engine_1 = create_engine(URL.create('sqlite', database='warehouse.db'))
df_source.write_database('cleaned_orders', connection=_engine_1, if_table_exists='fail')
```

::: tip Security
Exported code never embeds the password — it resolves the connection's secret
reference at runtime (`os.environ[...]` for `env:`/bare names,
`keyring.get_password(...)` for `keyring:NAME`, or a `file:/path` read for a
mounted secret file). See [Connections](/guide/connections).
:::

## Tips & common mistakes

- **`replace` drops and recreates the target table.** Existing column
  definitions, constraints and indexes may be lost. Use `append` to keep an
  existing table and add rows; `fail` to abort if it exists.
- **Match the table's columns.** With `append`, the frame's columns should line
  up with the target table.
- **Review exported connection settings.** The current generators do not
  automatically carry node `schema` or driver-specific connection `options`.
  Supply required schema, TLS or other provider settings in the exported calls.
- **Exports use your local permissions.** Ciaren's connector confinement and
  error scrubbing are not included. Check the target before executing a script
  that replaces or appends rows.

## See also

- [SQL input](./sql-input.md)
- [Database Connections](/guide/connections)
- [Connections API](/api/connections)
