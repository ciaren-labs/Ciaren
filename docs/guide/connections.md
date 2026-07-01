---
title: Database Connections
description: Connect Ciaren to PostgreSQL, MySQL, SQLite, SQL Server, and MongoDB
search: connections database sql postgres mysql mongodb sqlite security
layout: doc
---

# Database Connections

Connections let Ciaren read from and write to databases through the **SQL
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

> **Ciaren never stores your database password.**

A connection stores only the **name** of an environment variable
(`password_env`) — for example `PG_PASSWORD`. The actual secret is read from the
process environment when a connection is used, and is:

- never written to the database,
- never returned by the API,
- never embedded in exported Python (generated code reads `os.environ[...]`).

Set the variable before starting Ciaren, e.g. in your shell or `.env`:

```bash
export PG_PASSWORD="super-secret"
ciaren serve
```

Other safeguards: the SQLAlchemy URL is built from structured fields (no raw DSN
to inject into), table/schema identifiers are validated, and any secret is
scrubbed from driver error messages.

## Supported databases

| Provider | Driver (optional) | Install |
| ---------- | ------------------- | --------- |
| PostgreSQL | `psycopg` | `pip install ciaren[postgres]` |
| MySQL / MariaDB | `pymysql` | `pip install ciaren[mysql]` |
| SQLite | built-in | — |
| SQL Server | `pyodbc` | `pip install ciaren[mssql]` |
| MongoDB | `pymongo` | `pip install ciaren[mongo]` |

To pull in **every** database driver at once:

```bash
pip install ciaren[all]
```

Drivers are **optional**. If one isn't installed, that provider appears disabled
on the Connections page with an "install …" hint, so the core stays lightweight.
SQLite needs no driver and is great for trying things out.

## Creating a connection

![Connections page — list of saved database connections with test/edit actions](/screenshots/connections.png)

1. Go to **Connections → Add connection**. A provider picker appears:

   ![Add connection dialog — grid of database and storage providers: PostgreSQL, MySQL/MariaDB, SQLite, DuckDB, SQL Server, Snowflake, MongoDB, Local Folder, AWS S3, Azure Blob Storage, Google Cloud Storage](/screenshots/connection-add-dialog.png)

1. Pick a **provider**. After selecting one (e.g. PostgreSQL) the connection form appears:

   ![Configure connection form — name, host, port, database, username, and Password env var fields with "PG_PASSWORD" hint](/screenshots/connection-form-postgres.png)

   SQLite asks only for a file path; the others ask for host, port, database,
   username, and the **password env-var name** (the actual secret is never stored).
1. Save, then click **Test** to verify connectivity.

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

- [SQL input](../transformations/sql-input.md) / [SQL output](../transformations/sql-output.md) — database I/O nodes
- [Storage input](../transformations/storage-input.md) / [Storage output](../transformations/storage-output.md) — S3/GCS/Azure Blob I/O nodes
- [Scheduling](/guide/scheduling) — automate flows that pull fresh data
