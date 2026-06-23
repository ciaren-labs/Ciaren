---
title: Connections API
description: Manage reusable database connections for SQL input/output nodes
search: api connections database sql providers test tables postgres mysql mongo
---

# Connections API

Reusable database connections that power the [SQL input](/transformations/sql-input)
and [SQL output](/transformations/sql-output) nodes. A connection stores the
non-secret parts of a database target; **passwords are read from environment
variables, never stored** (see [Connections](/guide/connections) for the security
model).

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/connections` | List connections |
| `POST` | `/api/connections` | Create a connection |
| `GET` | `/api/connections/providers` | List supported database providers |
| `POST` | `/api/connections/test-config` | Test an unsaved connection config |
| `GET` | `/api/connections/{connection_id}` | Get one connection |
| `PATCH` | `/api/connections/{connection_id}` | Update a connection |
| `DELETE` | `/api/connections/{connection_id}` | Delete a connection |
| `POST` | `/api/connections/{connection_id}/test` | Test a saved connection (connectivity + auth) |
| `GET` | `/api/connections/{connection_id}/tables` | List tables/collections available to the connection |

`POST /api/connections/test-config` validates a config **before** saving it;
`POST /api/connections/{id}/test` checks an already-saved one. `GET .../tables`
backs the table picker in the SQL node config form.

## See also

- [Database Connections](/guide/connections) — create and manage connections
- [SQL input](/transformations/sql-input) · [SQL output](/transformations/sql-output)
