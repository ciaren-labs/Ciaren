---
title: Connections API
description: Manage reusable database connections for SQL input/output nodes
search: api connections database sql providers test tables postgres mysql mongo
---

# Connections API

Reusable database connections that power the [SQL input](/transformations/sql-input)
and [SQL output](/transformations/sql-output) nodes. A connection stores the
non-secret parts of a database target; **passwords are fetched at runtime from
a secret reference — an env var, the OS keychain (`keyring:NAME`), or a secret
file (`file:/path`) — and never stored** (see
[Connections](/guide/connections) for the security model).

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/connections` | List connections |
| `POST` | `/api/connections` | Create a connection |
| `GET` | `/api/connections/providers` | List supported database providers |
| `POST` | `/api/connections/test-config` | Test an unsaved connection config |
| `GET` | `/api/connections/{connection_id}` | Get one connection |
| `PATCH` | `/api/connections/{connection_id}` | Update a connection |
| `DELETE` | `/api/connections/{connection_id}` | Delete a connection (`409` while flows reference it; `?force=true` overrides) |
| `POST` | `/api/connections/{connection_id}/test` | Test a saved connection (connectivity + auth) |
| `GET` | `/api/connections/{connection_id}/tables` | List tables/collections available to the connection |
| `GET` | `/api/connections/{connection_id}/objects` | List files/objects available to a storage connection (optional `?prefix=`) |
| `GET` | `/api/connections/keyring` | Whether this host has a usable OS keychain |
| `POST` | `/api/connections/keyring` | Store a secret in the OS keychain; returns its `keyring:NAME` reference |
| `GET` | `/api/connections/keyring/{name}` | Whether a keychain secret exists (never its value) |
| `DELETE` | `/api/connections/keyring/{name}` | Remove a keychain secret |

`POST /api/connections/test-config` validates a config **before** saving it;
`POST /api/connections/{id}/test` checks an already-saved one. `GET .../tables`
backs the table picker in the SQL node config form, and `GET .../objects` backs
the equivalent picker for storage connections (S3, Azure Blob, GCS, local folder).

The `password_env` field takes a secret reference: a bare env var name,
`env:NAME`, `keyring:NAME`, or `file:/path`. Save-time validation refuses a
reference naming one of Ciaren's own configuration variables (or, when
`CIAREN_SECRET_ENV_ALLOWLIST` is set, any env var outside that allowlist),
refuses `file:` paths outside the allowed secrets folders
(`CIAREN_SECRET_FILE_DIRS`), and refuses credential-bearing custom headers
on REST API connections. `DELETE` returns `409 Conflict` while flows still
reference the connection — the message lists them; pass `?force=true` to delete
anyway (those flows then fail at run time until repointed).

The `/keyring` endpoints back the connection form's "save to keychain" action.
`POST /api/connections/keyring` takes `{ "name", "value", "overwrite"? }`,
writes the value to the OS keychain under the `ciaren` service, and returns
`{ "name", "exists", "reference": "keyring:NAME" }` — never the value. It
returns `409` if the name is already used (unless `overwrite` is true). The
submitted value is never persisted by Ciaren, returned, or logged; validation
errors are redacted so a rejected value never appears in a `422` body. On a
network-exposed deployment, prefer the `ciaren secret` CLI (which keeps the
value on the machine) or terminate TLS in front of the API.

## See also

- [Database Connections](/guide/connections) — create and manage connections
- [SQL input](/transformations/sql-input) · [SQL output](/transformations/sql-output)
