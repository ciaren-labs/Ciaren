---
title: Database Connections
description: Connect FlowFrame to PostgreSQL, MySQL, SQLite, SQL Server, and MongoDB
search: connections database sql postgres mysql mongodb sqlite security
layout: doc
---

# Database Connections

Connections let FlowFrame read from and write to databases through the **SQL
Input** and **SQL Output** nodes. You define a connection to a database **once**
on the Connections page, then reuse it across as many flows and nodes as you like
— each node just picks a table (or writes a query).

<FlowPipeline :nodes='[
  {"type":"input","label":"Database","detail":"PostgreSQL · MySQL · SQLite · SQL Server · MongoDB"},
  {"type":"input","label":"Connection","detail":"host · port · user · password_env (never stored)"},
  {"type":"input","label":"SQL Input node","detail":"picks a table or runs a custom query"},
  {"type":"transform","label":"Transformation nodes","detail":"clean, reshape, combine"},
  {"type":"output","label":"SQL Output node","detail":"replace · append · fail if exists"},
  {"type":"output","label":"Database","detail":"result written back"}
]' />

## Security model

> **FlowFrame never stores your database password.**

A connection stores only the **name** of an environment variable
(`password_env`) — for example `PG_PASSWORD`. The actual secret is read from the
process environment when a connection is used, and is:

- never written to the database,
- never returned by the API,
- never embedded in exported Python (generated code reads `os.environ[...]`).

Set the variable before starting FlowFrame, e.g. in your shell or `.env`:

```bash
export PG_PASSWORD="super-secret"
flowframe serve
```

Other safeguards: the SQLAlchemy URL is built from structured fields (no raw DSN
to inject into), table/schema identifiers are validated, and any secret is
scrubbed from driver error messages.

## Supported databases

| Provider | Driver (optional) | Install |
| ---------- | ------------------- | --------- |
| PostgreSQL | `psycopg` | `pip install flowframe[postgres]` |
| MySQL / MariaDB | `pymysql` | `pip install flowframe[mysql]` |
| SQLite | built-in | — |
| SQL Server | `pyodbc` | `pip install flowframe[mssql]` |
| MongoDB | `pymongo` | `pip install flowframe[mongo]` |

To pull in **every** database driver at once:

```bash
pip install flowframe[all]
```

Drivers are **optional**. If one isn't installed, that provider appears disabled
on the Connections page with an "install …" hint, so the core stays lightweight.
SQLite needs no driver and is great for trying things out.

## Creating a connection

![Connections page — list of saved database connections with test/edit actions](/screenshots/connections.png)

1. Go to **Connections → Add connection**.
2. Pick a **provider**. SQLite asks only for a file path; the others ask for
   host, port, database, username, and the **password env-var name**.
3. Save, then click **Test** to verify connectivity.

## Using SQL nodes in a flow

- **SQL Input** — choose the connection, then either pick a **table** (the list
  is read from the database) or switch to **Custom SQL** and write a query. The
  data is read live each run; scheduled flows therefore always get fresh data.
- **SQL Output** — choose the connection and a **target table**, and whether to
  `replace`, `append`, or `fail` if it already exists.

## Reproducibility

Each run snapshots its SQL inputs to parquet, so a run records exactly the data
it processed even though the source is live.

## Limitations

- MongoDB inputs use **collection selection** only (no custom SQL).
- `rank` and similar are per the [transformations reference](/transformations/overview).

## Next steps

- [Transformations reference](/transformations/overview) — the SQL Input/Output nodes
- [Scheduling](/guide/scheduling) — automate flows that pull fresh data
